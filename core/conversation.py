"""对话式 Agent：在同一个会话里回答问题或调用工具完成任务。

与旧 AgentRunner 的区别：
- 直接读写会话历史（截图/追问都在同一上下文里）
- 工具调用结果持久化到 assistant 消息的 meta 字段，历史可回放
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime

from PIL import Image
from PySide6.QtCore import QObject, Signal

from core.config import Config
from core.llm import SYSTEM_PROMPT, DeepSeekClient, encode_image, image_block
from core.memory import MemoryManager
from core.store import Store
from core.tools import ToolRegistry

LOGGER = logging.getLogger("biliask.chat")

CHAT_SYSTEM_PROMPT = """你是一个桌面学习助手 + 可以调用工具的 Agent。用户可能：
1. 截屏后问学习问题（算法、数学、代码、视频讲解）；
2. 直接用一句话让你帮他做事（查视频、读文件、记笔记、写文件等）。

规则：
- 需要真实信息时调用工具，不要编造工具结果；工具失败就说明并换方法。
- 危险操作会由用户确认；被拒绝就换方案。
- 最终用简体中文回答，Markdown 排版：先给结论，再分点/步骤；公式用 $...$ 或 $$...$$，代码用 ```语言 代码块。
- 用户让你“记笔记/记录下来”时，调用 create_note 工具把内容写进笔记库。
- 用户让你把截图/图片粘贴到 Word 时，按情况调用 insert_clipboard_image_to_word（剪贴板图片）、insert_image_to_word（最近截图/指定文件）或 insert_screenshot_to_word（截当前屏幕）；先确认用户已经打开 Word 文档并把光标放在目标位置。
- 不要输出 HTML，不要寒暄。"""


class ConversationAgent(QObject):
    started = Signal(str)
    step = Signal(str, dict)
    finished = Signal(str, str)
    failed = Signal(str, str)
    confirmation_requested = Signal(str, str, str)

    def __init__(
        self,
        store: Store,
        config: Config,
        registry: ToolRegistry,
        memory: MemoryManager | None = None,
        llm_factory=None,
        max_steps: int = 8,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.config = config
        self.registry = registry
        self.memory = memory
        self._llm_factory = llm_factory
        self.max_steps = max_steps
        self._runs: dict[str, threading.Event] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._confirm_waiters: dict[str, threading.Event] = {}
        self._confirm_results: dict[str, bool] = {}

    # ------------------------------------------------------------------
    def is_running(self, sid: str) -> bool:
        return sid in self._runs

    def stop(self, sid: str | None = None) -> None:
        if sid is None:
            for event in self._stop_events.values():
                event.set()
        else:
            event = self._stop_events.get(sid)
            if event is not None:
                event.set()

    def resolve_confirmation(self, request_id: str, allowed: bool) -> None:
        self._confirm_results[request_id] = allowed
        waiter = self._confirm_waiters.pop(request_id, None)
        if waiter is not None:
            waiter.set()

    def run(self, sid: str, task: str = "") -> None:
        if sid in self._runs:
            self.failed.emit(sid, "这个会话正在生成中")
            return
        stop_event = threading.Event()
        self._runs[sid] = stop_event
        self._stop_events[sid] = stop_event
        self.started.emit(sid)
        threading.Thread(
            target=self._run, args=(sid, task, stop_event), daemon=True, name=f"chat-{sid}"
        ).start()

    # ------------------------------------------------------------------
    def _make_client(self):
        if self._llm_factory is not None:
            return self._llm_factory()
        return DeepSeekClient(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=self.config.model,
            max_tokens=int(self.config.data.get("max_tokens", 1500)),
            temperature=float(self.config.data.get("temperature", 0.6)),
        )

    def _build_messages(self, sid: str) -> list[dict]:
        session = self.store.get_session(sid) or {}
        rows = self.store.get_messages(sid)
        question = ""
        for row in reversed(rows):
            if row["role"] == "user":
                question = row["content"]
                break

        system = CHAT_SYSTEM_PROMPT
        context_text = (session.get("context") or "").strip()
        if context_text:
            system += "\n\n【当前屏幕上下文】\n" + context_text
        if self.memory is not None and question:
            memory_text = self.memory.build_context(question)
            if memory_text:
                system += (
                    "\n\n【用户的长期记忆（可能相关，参考即可；无关就忽略）】\n" + memory_text
                )

        messages: list[dict] = [{"role": "system", "content": system}]
        image_b64: str | None = None
        image_path = self.store.image_abspath(session.get("image_path"))
        if image_path is not None:
            try:
                image_b64 = encode_image(Image.open(image_path))
            except Exception:  # noqa: BLE001
                LOGGER.exception("读取截图失败")
        image_attached = False
        for row in rows:
            if row["role"] == "user":
                if image_b64 and not image_attached:
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": row["content"]},
                                image_block(image_b64),
                            ],
                        }
                    )
                    image_attached = True
                else:
                    messages.append({"role": "user", "content": row["content"]})
            elif row["role"] == "assistant":
                messages.append({"role": "assistant", "content": row["content"]})
        return messages

    def _run(self, sid: str, task: str, stop_event: threading.Event) -> None:
        started = time.time()
        steps: list[dict] = []
        try:
            client = self._make_client()
            messages = self._build_messages(sid)
            if task:
                messages.append({"role": "user", "content": task})
            tools = self.registry.specs()

            for _ in range(self.max_steps):
                if stop_event.is_set():
                    self.failed.emit(sid, "已停止")
                    return
                message = client.chat_with_tools(messages, tools)
                content = (message.get("content") or "").strip()
                tool_calls = message.get("tool_calls") or []

                if not tool_calls:
                    elapsed = round(time.time() - started, 2)
                    self.store.add_message(
                        sid,
                        "assistant",
                        content or "（模型没有返回内容）",
                        elapsed_s=elapsed,
                        meta=json.dumps({"steps": steps}, ensure_ascii=False) if steps else None,
                    )
                    self.finished.emit(sid, content or "（模型没有返回内容）")
                    return

                if content:
                    steps.append({"type": "assistant", "text": content})
                    self.step.emit(sid, {"type": "assistant", "text": content})

                messages.append(
                    {"role": "assistant", "content": content, "tool_calls": tool_calls}
                )
                for call in tool_calls:
                    if stop_event.is_set():
                        self.failed.emit(sid, "已停止")
                        return
                    function = call.get("function") or {}
                    name = function.get("name") or ""
                    raw_arguments = function.get("arguments") or "{}"
                    try:
                        arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
                    except json.JSONDecodeError:
                        arguments = {}
                    self.step.emit(
                        sid, {"type": "tool_call", "name": name, "args": arguments}
                    )
                    steps.append(
                        {"type": "tool_call", "name": name, "args": arguments}
                    )

                    if self._needs_confirmation(name) and not self._ask_confirmation(name, arguments):
                        result_text = "用户拒绝了这次操作，请换一种方式或询问用户。"
                        ok = False
                    else:
                        result = self.registry.execute(name, arguments)
                        result_text = result.content
                        ok = result.ok
                    self.step.emit(
                        sid,
                        {
                            "type": "tool_result",
                            "name": name,
                            "ok": ok,
                            "summary": result_text[:300],
                        },
                    )
                    steps.append(
                        {
                            "type": "tool_result",
                            "name": name,
                            "ok": ok,
                            "summary": result_text[:300],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                            "content": result_text[:6000],
                        }
                    )
            self.failed.emit(sid, f"超过最大步数（{self.max_steps}），任务未完成")
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("对话 Agent 执行失败")
            self.failed.emit(sid, str(exc))
        finally:
            self._runs.pop(sid, None)
            self._stop_events.pop(sid, None)

    def _needs_confirmation(self, tool_name: str) -> bool:
        spec = self.registry.get(tool_name)
        return bool(spec and spec.dangerous)

    def _ask_confirmation(self, tool_name: str, arguments: dict) -> bool:
        request_id = uuid.uuid4().hex[:8]
        waiter = threading.Event()
        self._confirm_waiters[request_id] = waiter
        self.confirmation_requested.emit(
            request_id, tool_name, json.dumps(arguments, ensure_ascii=False)
        )
        if not waiter.wait(timeout=90):
            self._confirm_waiters.pop(request_id, None)
            return False
        return self._confirm_results.pop(request_id, False)
