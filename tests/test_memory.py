"""记忆库测试：存储、检索、整理合并。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import Config  # noqa: E402
from core.memory import MemoryManager  # noqa: E402
from core.store import Store  # noqa: E402


class _FakeLLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def chat(self, messages) -> str:
        return self.answer


class MemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.store = Store(self.tmp_path / "data")
        self.config = Config(path=self.tmp_path / "config.json")
        self.config.data["api_key"] = "sk-test"

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_store_crud(self) -> None:
        mid = self.store.add_memory("用户喜欢黑底代码截图", "偏好,代码")
        memories = self.store.list_memories()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["content"], "用户喜欢黑底代码截图")
        self.assertEqual(memories[0]["enabled"], 1)

        self.store.update_memory(mid, content="用户偏好黑底代码截图", tags="偏好")
        self.assertEqual(self.store.get_memory(mid)["content"], "用户偏好黑底代码截图")

        self.store.update_memory(mid, enabled=False)
        self.assertEqual(len(self.store.list_memories("", include_disabled=False)), 0)
        self.assertEqual(len(self.store.list_memories()), 1)

        self.assertEqual(len(self.store.list_memories("黑底")), 1)
        self.store.delete_memory(mid)
        self.assertEqual(self.store.memory_count(), 0)

    def test_retrieve_filters_by_keywords(self) -> None:
        recursive = self.store.add_memory("递归树的时间复杂度分析", "算法")
        self.store.add_memory("用户偏好黑底代码截图", "偏好")
        manager = MemoryManager(self.store, self.config)

        results = manager.retrieve("递归树怎么算时间复杂度")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], recursive)
        self.assertIn("递归树", manager.build_context("递归树怎么算时间复杂度"))

        self.assertEqual(manager.retrieve("完全无关的问题"), [])

    def test_consolidate_merges_similar(self) -> None:
        sid = self.store.create_session("递归树复杂度")
        self.store.add_message(sid, "user", "递归树复杂度怎么算")
        self.store.add_message(sid, "assistant", "用主定理分析")
        self.store.add_memory("递归树时间复杂度用主定理分析", "算法")

        answer = (
            '[{"content": "递归树时间复杂度用主定理分析，T(n)=aT(n/b)+f(n)", "tags": ["算法"]},'
            ' {"content": "用户喜欢黑底代码截图", "tags": ["偏好"]}]'
        )
        manager = MemoryManager(self.store, self.config, llm_factory=lambda: _FakeLLM(answer))
        result = manager.consolidate([sid])
        self.assertIsNone(result["error"])
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["merged"], 1)
        self.assertEqual(self.store.memory_count(), 2)

        # 再整理一次不应无限新增
        result2 = manager.consolidate([sid])
        self.assertEqual(result2["added"], 0)
        self.assertEqual(result2["merged"], 2)
        self.assertEqual(self.store.memory_count(), 2)

    def test_consolidate_without_sessions(self) -> None:
        manager = MemoryManager(self.store, self.config, llm_factory=lambda: _FakeLLM("[]"))
        result = manager.consolidate([])
        self.assertEqual(result["error"], "没有可整理的问答记录")


if __name__ == "__main__":
    unittest.main()
