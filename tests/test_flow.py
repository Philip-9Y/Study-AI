"""对话式 Agent 端到端测试：截图提问、文字任务、连续会话、工具卡片。"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import core.controller as controller_module  # noqa: E402
from core.config import Config  # noqa: E402
from core.context import ScreenContext  # noqa: E402
from core.controller import Controller  # noqa: E402
from core.conversation import ConversationAgent  # noqa: E402
from core.memory import MemoryManager  # noqa: E402
from core.store import Store  # noqa: E402
from core.tools import ToolRegistry, build_default_registry  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


class ScriptedLLM:
    def __init__(self, answers: list) -> None:
        self.answers = list(answers)
        self.calls: list[list[dict]] = []

    def chat_with_tools(self, messages, tools, tool_choice="auto"):
        self.calls.append(list(messages))
        if not self.answers:
            return {"role": "assistant", "content": "（没有脚本答案）"}
        response = self.answers.pop(0)
        if isinstance(response, str):
            return {"role": "assistant", "content": response}
        return response


class _Watcher:
    def best(self) -> ScreenContext:
        return ScreenContext(
            window_title="递归树_哔哩哔哩_bilibili - Google Chrome",
            process_name="chrome.exe",
            video_title="递归树",
            is_bilibili=True,
        )


class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.store = Store(self.tmp_path / "data")
        self.config = Config(path=self.tmp_path / "config.json")
        self.config.data.update(
            {"api_key": "sk-test", "save_captures": True, "thinking": False}
        )
        self.main = MainWindow(self.store, self.config)
        self.questions: list[str] = []
        self.registry: ToolRegistry = build_default_registry()
        self.llm = ScriptedLLM(["这是回答一。", "这是回答二。", "这是回答三。", "这是回答四。"])
        self.memory = MemoryManager(self.store, self.config)
        self.agent = ConversationAgent(
            self.store,
            self.config,
            self.registry,
            memory=self.memory,
            llm_factory=lambda: self.llm,
        )
        self.controller = Controller(
            self.store,
            self.config,
            self.main,
            self.agent,
            context_watcher=_Watcher(),  # type: ignore[arg-type]
            question_provider=lambda _crop: self.questions.pop(0) if self.questions else None,
        )
        self._orig_grab = controller_module.grab_primary_screen
        controller_module.grab_primary_screen = lambda: Image.new("RGB", (1000, 700), "white")

    def tearDown(self) -> None:
        self.controller.shutdown()
        self.main.hide()
        self.main.deleteLater()
        self.store.close()
        controller_module.grab_primary_screen = self._orig_grab
        self.tmp.cleanup()

    # ------------------------------------------------------------------
    def _pump(self, sid: str, timeout: float = 5.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.processEvents()
            if not self.agent.is_running(sid):
                break
            time.sleep(0.005)
        for _ in range(20):
            self.app.processEvents()
            time.sleep(0.002)

    def _capture(self) -> str:
        self.controller.start_capture()
        deadline = time.time() + 2
        while self.controller._overlay is None and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        overlay = self.controller._overlay
        self.assertIsNotNone(overlay, "框选层没有创建")
        overlay.selected.emit(QRect(10, 10, 300, 200))
        sessions = self.store.list_sessions()
        self.assertTrue(sessions, "截图后没有创建会话")
        sid = sessions[0]["id"]
        self._pump(sid)
        return sid

    # ------------------------------------------------------------------
    def test_two_consecutive_screenshots(self) -> None:
        self.questions[:] = ["第一个问题", "第二个问题"]
        self._capture()
        self.assertEqual(self.store.session_count(), 1)
        self._capture()
        self.assertEqual(self.store.session_count(), 2)
        for session in self.store.list_sessions():
            messages = self.store.get_messages(session["id"])
            self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
            self.assertIn("这是回答", messages[1]["content"])
            self.assertIsNotNone(session["image_path"])
        self.assertEqual(len(list((self.tmp_path / "data" / "captures").rglob("*.png"))), 2)

    def test_text_agent_conversation_and_followup(self) -> None:
        self.controller.send_text("", "帮我查一下现在几点")
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 1)
        sid = sessions[0]["id"]
        self._pump(sid)
        messages = self.store.get_messages(sid)
        self.assertEqual([m["role"] for m in messages], ["user", "assistant"])

        self.controller.send_text(sid, "再解释一下")
        self._pump(sid)
        messages = self.store.get_messages(sid)
        self.assertEqual(
            [m["role"] for m in messages], ["user", "assistant", "user", "assistant"]
        )
        self.assertIsNotNone(self.store.get_session(sid)["context"])

    def test_cancel_does_not_block_next_capture(self) -> None:
        self.questions[:] = []
        self.controller.start_capture()
        overlay = self.controller._overlay
        self.assertIsNotNone(overlay)
        overlay.selected.emit(QRect(10, 10, 300, 200))
        self.app.processEvents()
        self.assertEqual(self.store.session_count(), 0)
        self.assertFalse(self.controller._capturing)

        self.questions[:] = ["取消之后的提问"]
        self._capture()
        self.assertEqual(self.store.session_count(), 1)

    def test_overlay_cancel_resets_state(self) -> None:
        self.controller.start_capture()
        overlay = self.controller._overlay
        self.assertIsNotNone(overlay)
        overlay.cancelled.emit()
        self.assertFalse(self.controller._capturing)
        self.assertIsNone(self.controller._overlay)

    def test_memory_injected_into_prompt(self) -> None:
        sid = self.store.create_session("递归树问题")
        self.store.add_message(sid, "user", "递归树复杂度怎么算")
        self.store.add_memory("递归树时间复杂度用主定理分析", "算法")
        self.store.add_memory("用户喜欢黑底代码截图", "偏好")
        messages = self.agent._build_messages(sid)
        system_prompt = messages[0]["content"]
        self.assertIn("主定理", system_prompt)
        self.assertNotIn("黑底", system_prompt)

    def test_context_stored_in_session(self) -> None:
        self.questions[:] = ["这是哪个视频"]
        sid = self._capture()
        context = self.store.get_session(sid)["context"]
        self.assertIn("递归树", context)

    def test_tool_calls_persisted_in_meta(self) -> None:
        self.llm.answers = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "get_current_time", "arguments": "{}"},
                    }
                ],
            },
            {"role": "assistant", "content": "已经查到当前时间。"},
        ]
        self.controller.send_text("", "现在几点？用工具查一下")
        sid = self.store.list_sessions()[0]["id"]
        self._pump(sid)
        messages = self.store.get_messages(sid)
        self.assertEqual(messages[-1]["role"], "assistant")
        meta = messages[-1]["meta"]
        self.assertIsNotNone(meta)
        self.assertIn("get_current_time", meta)
        self.assertIn("tool_call", meta)

    def test_length_limit_auto_continuation(self) -> None:
        self.llm.answers = [
            {"role": "assistant", "content": "前半段内容。", "_finish_reason": "length"},
            {"role": "assistant", "content": "后半段内容。", "_finish_reason": "stop"},
        ]
        self.controller.send_text("", "请写一个很长的回答")
        sid = self.store.list_sessions()[0]["id"]
        self._pump(sid)
        message = self.store.get_messages(sid)[-1]
        self.assertEqual(message["role"], "assistant")
        self.assertEqual(message["content"], "前半段内容。后半段内容。")
        self.assertNotIn("长度上限", message["content"])

    def test_navigation_back_and_new_chat(self) -> None:
        sid = self.store.create_session("导航测试")
        self.store.add_message(sid, "user", "你好")
        self.main.show_notes()
        self.assertEqual(self.main.stack.currentIndex(), 1)
        self.main.open_session(sid)
        self.assertEqual(self.main.stack.currentIndex(), 0)

        self.main.show_memory()
        self.assertEqual(self.main.stack.currentIndex(), 2)
        self.main.notes_pane.back_requested.emit()
        self.assertEqual(self.main.stack.currentIndex(), 0)

        self.main.show_notes()
        self.main.new_chat()
        self.assertEqual(self.main.stack.currentIndex(), 0)

    def test_word_tools_registered(self) -> None:
        names = build_default_registry().names()
        for name in (
            "get_word_status",
            "insert_image_to_word",
            "insert_screenshot_to_word",
            "insert_clipboard_image_to_word",
            "insert_text_to_word",
        ):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
