"""Agent 循环：LLM 规划 → 调用工具 → 观察结果 → 继续，直到给出最终答复。"""

from __future__ import annotations

import json
import logging
import threading
import uuid

from PySide6.QtCore import QObject, Signal

from core.config import Config
from core.llm import DeepSeekClient, LLMError
from core.tools import ToolRegistry

LOGGER = logging.getLogger("biliask.agent")

SYSTEM_PROMPT = """你是一个可以操作本机工具的桌面 Agent。你的任务是帮用户真正把事情做完，而不只是给建议。

规则：
1. 能用工具获取真实信息时就调用工具，不要编造工具结果。
2. 复杂任务先调用必要的工具（例如读取屏幕上下文、查询视频信息、读取文件），再给结论或执行操作。
3. 工具失败时说明失败原因，并尝试替代方案；不要假装成功。
4. 危险操作（写文件、打开程序等）会由用户确认；用户拒绝就换方案。
5. 最终用简体中文回答，Markdown 排版，先给结果，再列出做了哪些操作。
6. 不要输出 HTML，不要寒暄。"""


class AgentRunner(QObject):
    step = Signal(dict)
    finished = Signal(str)
    failed = Signal(str)
    confirmation_requested = Signal(str, str, str)  # request_id, tool, args_json

    def __init__(
        self,
        config: Config,
        registry: ToolRegistry,
        llm_factory=None,
        max_steps: int = 8,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.registry = registry
        self._llm_factory = llm_factory
        self.max_steps = max_steps
        self._running = False
        self._stop_event = threading.Event()
        self._confirm_waiters: dict[str, threading.Event] = {}
        self._confirm_results: dict[str, bool] = {}

    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        return self._running

    def start(self, task: str, context_text: str = "") -> None:
        if self._running:
            self.failed.emit("上一个任务还在执行")
            return
        task = (task or "").strip()
        if not task:
            self.failed.emit("任务不能为空")
            return
        self._running = True
        self._stop_event.clear()
        threading.Thread(
            target=self._run, args=(task, context_text), daemon=True, name="agent-runner"
        ).start()

    def stop(self) -> None:
        self._stop_event.set()

    def resolve_confirmation(self, request_id: str, allowed: bool) -> None:
        self._confirm_results[request_id] = allowed
        waiter = self._confirm_waiters.pop(request_id, None)
        if waiter is not None:
            waiter.set()

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

    def _run(self, task: str, context_text: str) -> None:
        try:
            client = self._make_client()
        except Exception as exc:  # noqa: BLE001
            self._running = False
            self.failed.emit(str(exc))
            return

        system = SYSTEM_PROMPT
        if context_text:
            system += f"\n\n【当前屏幕上下文】\n{context_text}"
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        tools = self.registry.specs()

        try:
            for step_index in range(self.max_steps):
                if self._stop_event.is_set():
                    self.failed.emit("已停止")
                    return
                message = client.chat_with_tools(messages, tools)
                content = (message.get("content") or "").strip()
                tool_calls = message.get("tool_calls") or []

                if not tool_calls:
                    self.finished.emit(content or "任务完成，但模型没有返回文字结果。")
                    return

                if content:
                    self.step.emit({"type": "assistant", "text": content})

                messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    }
                )
                for call in tool_calls:
                    if self._stop_event.is_set():
                        self.failed.emit("已停止")
                        return
                    function = call.get("function") or {}
                    name = function.get("name") or ""
                    raw_arguments = function.get("arguments") or "{}"
                    try:
                        arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
                    except json.JSONDecodeError:
                        arguments = {}
                    self.step.emit(
                        {"type": "tool_call", "name": name, "args": arguments, "step": step_index + 1}
                    )
                    if self._needs_confirmation(name) and not self._ask_confirmation(name, arguments):
                        result_text = "用户拒绝了这次操作，请换一种方式或询问用户。"
                        self.step.emit(
                            {"type": "tool_result", "name": name, "ok": False, "summary": result_text}
                        )
                    else:
                        result = self.registry.execute(name, arguments)
                        result_text = result.content
                        self.step.emit(
                            {
                                "type": "tool_result",
                                "name": name,
                                "ok": result.ok,
                                "summary": result.display or result.content[:200],
                            }
                        )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                            "content": result_text[:6000],
                        }
                    )
            self.failed.emit(f"超过最大步数（{self.max_steps}），任务未完成")
        except LLMError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Agent 执行失败")
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self._running = False

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
