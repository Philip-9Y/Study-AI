"""核心逻辑单测：存储、配置、图片编码。"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from core.config import Config  # noqa: E402
from core.llm import DeepSeekClient, build_user_message, encode_image  # noqa: E402
from core.store import Store  # noqa: E402


class StoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "data")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_session_and_messages(self) -> None:
        sid = self.store.create_session("第一个问题", "captures/a.png", "deepseek-flash")
        self.store.add_message(sid, "user", "第一个问题")
        self.store.add_message(sid, "assistant", "第一个回答", elapsed_s=1.2)

        session = self.store.get_session(sid)
        self.assertIsNotNone(session)
        self.assertEqual(session["question"], "第一个问题")
        messages = self.store.get_messages(sid)
        self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
        self.assertAlmostEqual(messages[1]["elapsed_s"], 1.2)

        listed = self.store.list_sessions()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["msg_count"], 2)
        self.assertEqual(self.store.get_session(sid)["context"], None)

    def test_session_context(self) -> None:
        sid = self.store.create_session("问题", context="前台窗口：B站视频")
        self.assertEqual(self.store.get_session(sid)["context"], "前台窗口：B站视频")

    def test_notes_crud(self) -> None:
        note_id = self.store.add_note("递归树", "主定理内容", "算法")
        notes = self.store.list_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["title"], "递归树")
        self.assertEqual(len(self.store.list_notes("主定理")), 1)

        self.store.update_note(note_id, title="递归树（改）", content="新内容")
        note = self.store.get_note(note_id)
        self.assertEqual(note["title"], "递归树（改）")
        self.assertEqual(note["content"], "新内容")

        self.store.delete_note(note_id)
        self.assertEqual(self.store.list_notes(), [])

    def test_message_meta(self) -> None:
        sid = self.store.create_session("带工具的消息")
        self.store.add_message(sid, "assistant", "回答", meta='{"steps": [{"type": "tool_call"}]}')
        message = self.store.get_messages(sid)[0]
        self.assertIn("tool_call", message["meta"])

    def test_search_and_delete(self) -> None:
        sid1 = self.store.create_session("梯度下降怎么理解")
        self.store.add_message(sid1, "user", "梯度下降怎么理解")
        self.store.add_message(sid1, "assistant", "可以想象成下山。")
        sid2 = self.store.create_session("矩阵乘法")
        self.store.add_message(sid2, "user", "矩阵乘法")

        self.assertEqual(len(self.store.list_sessions("下山")), 1)
        self.assertEqual(len(self.store.list_sessions("梯度")), 1)
        self.assertEqual(len(self.store.list_sessions()), 2)

        image = self.store.delete_session(sid1)
        self.assertIsNone(image)
        self.assertEqual(self.store.session_count(), 1)
        self.assertEqual(self.store.get_messages(sid1), [])

    def test_save_capture(self) -> None:
        img = Image.new("RGB", (120, 80), "red")
        rel = self.store.save_capture(img)
        self.assertTrue(rel.endswith(".png"))
        path = self.store.image_abspath(rel)
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        self.assertIsNone(self.store.image_abspath("../outside.png"))

    def test_import_legacy_jsonl(self) -> None:
        legacy = Path(self.tmp.name) / "notes.jsonl"
        records = [
            {
                "ts": "2026-10-17T16:00:00",
                "session": "old1",
                "turn": 1,
                "image": "captures/2026-10-17/a.png",
                "question": "旧问题一",
                "answer": "旧回答一",
                "model": "deepseek-flash",
            },
            {
                "ts": "2026-10-17T16:00:10",
                "session": "old1",
                "turn": 2,
                "image": None,
                "question": "旧追问",
                "answer": "旧回答二",
                "model": "deepseek-flash",
            },
        ]
        legacy.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), "utf-8")
        imported = self.store.import_legacy_jsonl(legacy)
        self.assertEqual(imported, 1)
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["question"], "旧问题一")
        messages = self.store.get_messages(sessions[0]["id"])
        self.assertEqual(len(messages), 4)
        # 再次导入不会重复
        self.assertEqual(self.store.import_legacy_jsonl(legacy), 0)


class ConfigTest(unittest.TestCase):
    def test_save_and_reload(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "config.json"
        config = Config(path=path)
        config.data["api_key"] = "sk-test"
        config.data["model"] = "deepseek-flash"
        config.save()

        reloaded = Config(path=path)
        self.assertEqual(reloaded.api_key, "sk-test")
        self.assertEqual(reloaded.model, "deepseek-flash")
        tmp.cleanup()

    def test_env_override(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "config.json"
        path.write_text('{"api_key": "sk-file"}', "utf-8")
        old = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "sk-env"
        try:
            config = Config(path=path)
            self.assertEqual(config.api_key, "sk-env")
        finally:
            if old is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old
            tmp.cleanup()


class ImageTest(unittest.TestCase):
    def test_encode_and_message(self) -> None:
        img = Image.new("RGB", (4000, 100), "white")
        b64 = encode_image(img)
        raw = base64.b64decode(b64)
        decoded = Image.open(__import__("io").BytesIO(raw))
        self.assertLessEqual(max(decoded.size), 2000)
        message = build_user_message("这是什么？", b64)
        self.assertEqual(message["role"], "user")
        self.assertEqual(message["content"][0]["type"], "text")
        self.assertEqual(message["content"][1]["type"], "image_url")
        self.assertTrue(message["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))


class LLMPayloadTest(unittest.TestCase):
    def test_thinking_disabled_by_default(self) -> None:
        client = DeepSeekClient(api_key="sk-test")
        payload = client._payload([], stream=False)
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertIn("temperature", payload)
        self.assertNotIn("reasoning_effort", payload)

    def test_thinking_enabled_payload(self) -> None:
        client = DeepSeekClient(api_key="sk-test", thinking=True)
        payload = client._payload([], stream=True)
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertIn("reasoning_effort", payload)
        self.assertNotIn("temperature", payload)


if __name__ == "__main__":
    unittest.main()
