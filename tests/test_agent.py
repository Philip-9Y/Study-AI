"""Agent 工具调用循环测试（脚本化 LLM，不联网）。"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.agent import AgentRunner  # noqa: E402
from core.config import Config  # noqa: E402
from core.tools import ToolSpec, ToolRegistry  # noqa: E402


class ScriptedLLM:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def chat_with_tools(self, messages, tools, tool_choice="auto"):
        self.calls.append(list(messages))
        return self.responses.pop(0)


def _tool_call(name: str, arguments: str, call_id: str = "call_1") -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


class AgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Config(path=Path(self.tmp.name) / "config.json")
        self.config.data["api_key"] = "sk-test"
        self.registry = ToolRegistry()
        self.registry.register(
            ToolSpec(
                name="echo",
                description="回显文本",
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                func=lambda text: f"echo:{text}",
            )
        )
        self.registry.register(
            ToolSpec(
                name="dangerous_write",
                description="危险写入",
                parameters={"type": "object", "properties": {}},
                func=lambda: "written",
                dangerous=True,
            )
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _wait(self, timeout: float = 4.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
            if self.registry is None:
                break

    def test_tool_call_then_final_answer(self) -> None:
        llm = ScriptedLLM(
            [
                _tool_call("echo", '{"text": "hi"}'),
                {"role": "assistant", "content": "最终结果：hi"},
            ]
        )
        runner = AgentRunner(self.config, self.registry, llm_factory=lambda: llm)
        events: list[dict] = []
        finals: list[str] = []
        failures: list[str] = []
        runner.step.connect(events.append)
        runner.finished.connect(finals.append)
        runner.failed.connect(failures.append)
        runner.start("测试一下")
        deadline = time.time() + 5
        while time.time() < deadline and not finals and not failures:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertEqual(failures, [])
        self.assertEqual(finals, ["最终结果：hi"])
        kinds = [event["type"] for event in events]
        self.assertIn("tool_call", kinds)
        self.assertIn("tool_result", kinds)
        tool_result = next(event for event in events if event["type"] == "tool_result")
        self.assertTrue(tool_result["ok"])
        self.assertEqual(tool_result["name"], "echo")
        self.assertFalse(runner.is_running())

    def test_dangerous_tool_confirmation_allowed(self) -> None:
        llm = ScriptedLLM(
            [
                _tool_call("dangerous_write", "{}"),
                {"role": "assistant", "content": "写好了"},
            ]
        )
        runner = AgentRunner(self.config, self.registry, llm_factory=lambda: llm)
        requests: list[tuple[str, str, str]] = []
        finals: list[str] = []

        def confirm(request_id: str, tool: str, args: str) -> None:
            requests.append((request_id, tool, args))
            runner.resolve_confirmation(request_id, True)

        runner.confirmation_requested.connect(confirm)
        runner.finished.connect(finals.append)
        runner.start("写点东西")
        deadline = time.time() + 5
        while time.time() < deadline and not finals:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][1], "dangerous_write")
        self.assertEqual(finals, ["写好了"])
        self.assertFalse(runner.is_running())

    def test_dangerous_tool_confirmation_denied(self) -> None:
        llm = ScriptedLLM(
            [
                _tool_call("dangerous_write", "{}"),
                {"role": "assistant", "content": "那我换个方式"},
            ]
        )
        runner = AgentRunner(self.config, self.registry, llm_factory=lambda: llm)
        finals: list[str] = []

        def confirm(request_id: str, tool: str, args: str) -> None:
            runner.resolve_confirmation(request_id, False)

        runner.confirmation_requested.connect(confirm)
        runner.finished.connect(finals.append)
        runner.start("写点东西")
        deadline = time.time() + 5
        while time.time() < deadline and not finals:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertEqual(finals, ["那我换个方式"])
        # 第二轮消息里 tool result 应该是拒绝文本
        second_call = llm.calls[1]
        tool_message = [m for m in second_call if m.get("role") == "tool"][0]
        self.assertIn("拒绝", tool_message["content"])


if __name__ == "__main__":
    unittest.main()
