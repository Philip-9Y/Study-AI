"""上下文识别与工具注册表测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.context import ScreenContext, _fill_video, parse_bvid  # noqa: E402
from core.tools import ToolRegistry, build_default_registry  # noqa: E402


class _FakeWatcher:
    def best(self) -> ScreenContext:
        return ScreenContext(
            window_title="【算法】递归树展开_哔哩哔哩_bilibili - Google Chrome",
            process_name="chrome.exe",
            video_title="【算法】递归树展开",
            is_bilibili=True,
        )


class ContextTest(unittest.TestCase):
    def test_prompt_text(self) -> None:
        context = ScreenContext(
            window_title="课程视频 - Google Chrome",
            process_name="chrome.exe",
            video_title="课程视频",
            is_bilibili=True,
        )
        text = context.prompt_text()
        self.assertIn("前台窗口", text)
        self.assertIn("课程视频", text)

    def test_parse_bvid(self) -> None:
        self.assertEqual(parse_bvid("https://www.bilibili.com/video/BV1GJ411x7h7/"), "BV1GJ411x7h7")
        self.assertEqual(parse_bvid("没有 BV"), "")

    def test_video_title_from_window_title(self) -> None:
        context = ScreenContext(
            window_title="【算法】递归树展开_哔哩哔哩_bilibili - Google Chrome",
            process_name="chrome.exe",
        )
        _fill_video(context)
        self.assertTrue(context.is_bilibili)
        self.assertEqual(context.video_title, "【算法】递归树展开")


class ToolRegistryTest(unittest.TestCase):
    def test_time_tool(self) -> None:
        registry = build_default_registry()
        result = registry.execute("get_current_time", {})
        self.assertTrue(result.ok)
        self.assertIn("-", result.content)

    def test_screen_context_tool(self) -> None:
        registry = build_default_registry(_FakeWatcher())  # type: ignore[arg-type]
        result = registry.execute("get_screen_context", {})
        self.assertTrue(result.ok)
        self.assertIn("递归树", result.content)

    def test_dangerous_flags(self) -> None:
        registry = build_default_registry()
        self.assertTrue(registry.get("write_text_file").dangerous)
        self.assertFalse(registry.get("get_current_time").dangerous)

    def test_file_tools(self) -> None:
        registry = build_default_registry()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "a.txt"
            write = registry.execute("write_text_file", {"path": str(path), "content": "hello"})
            self.assertTrue(write.ok)
            read = registry.execute("read_text_file", {"path": str(path)})
            self.assertTrue(read.ok)
            self.assertEqual(read.content, "hello")
            listing = registry.execute("list_directory", {"path": temp})
            self.assertTrue(listing.ok)
            self.assertIn("a.txt", listing.content)

    def test_unknown_tool(self) -> None:
        registry = ToolRegistry()
        result = registry.execute("nope", {})
        self.assertFalse(result.ok)
        self.assertIn("未知工具", result.content)


if __name__ == "__main__":
    unittest.main()
