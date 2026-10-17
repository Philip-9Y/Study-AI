"""工具注册表与内置工具。

Agent 通过 OpenAI 兼容的 tools 调用这里注册的工具。
插件也可以把自己的 ToolSpec 注册进来。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.config import DATA_DIR
from core.context import ContextWatcher, parse_bvid


class ToolError(RuntimeError):
    pass


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    func: Callable[..., str]
    dangerous: bool = False
    source: str = "builtin"


@dataclass
class ToolResult:
    ok: bool
    content: str
    display: str = ""

    def to_payload(self) -> str:
        return self.content


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec, source: str | None = None) -> None:
        if source:
            spec.source = source
        if spec.name in self._tools:
            raise ToolError(f"工具名重复：{spec.name}")
        self._tools[spec.name] = spec

    def unregister_source(self, source: str) -> None:
        for name in [n for n, s in self._tools.items() if s.source == source]:
            self._tools.pop(name, None)

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict | str | None) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(False, f"错误：未知工具 {name}")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as exc:
                return ToolResult(False, f"错误：工具参数不是合法 JSON（{exc}）")
        if not isinstance(arguments, dict):
            arguments = {}
        try:
            output = spec.func(**arguments)
        except TypeError as exc:
            return ToolResult(False, f"错误：参数不匹配（{exc}）")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(False, f"错误：{type(exc).__name__}: {exc}")
        if not isinstance(output, str):
            output = json.dumps(output, ensure_ascii=False)
        display = output if len(output) <= 160 else output[:160] + "…"
        return ToolResult(True, output, display)


# ---------------------------------------------------------------------- 内置工具
def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_default_registry(watcher: ContextWatcher | None = None, store=None) -> ToolRegistry:
    registry = ToolRegistry()

    def get_time() -> str:
        """获取当前日期和时间。"""
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def get_screen_context() -> str:
        """获取当前前台窗口、进程和识别到的 B 站视频标题。"""
        if watcher is not None:
            context = watcher.best()
        else:
            from core.context import get_foreground_context

            context = get_foreground_context()
        return _json(context.to_dict())

    def get_bilibili_video(url_or_bvid: str) -> str:
        """根据 B 站链接或 BV 号查询视频标题、UP 主、时长和分 P 信息。"""
        from core.bilibili import fetch_video_info

        return _json(fetch_video_info(url_or_bvid))

    def list_directory(path: str = "") -> str:
        """列出目录下的文件和子目录（最多 100 项）。"""
        target = Path(path).expanduser() if path else Path.home()
        target = target.resolve()
        if not target.exists():
            raise ToolError(f"目录不存在：{target}")
        if not target.is_dir():
            raise ToolError(f"不是目录：{target}")
        items = []
        for index, entry in enumerate(sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))):
            if index >= 100:
                items.append("... 其余省略")
                break
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            items.append(f"{'DIR ' if entry.is_dir() else 'FILE'} {entry.name}  {size} bytes")
        return f"目录：{target}\n" + "\n".join(items)

    def read_text_file(path: str, max_chars: int = 8000) -> str:
        """读取本地文本文件（最多 8000 字符）。"""
        target = Path(path).expanduser().resolve()
        if not target.exists() or not target.is_file():
            raise ToolError(f"文件不存在：{target}")
        if target.stat().st_size > 2_000_000:
            raise ToolError("文件太大（>2MB），请换用其他方式")
        text = target.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars]

    def write_text_file(path: str, content: str, append: bool = False) -> str:
        """写入或追加本地文本文件（危险操作，会请求确认）。"""
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8") as handle:
            handle.write(content)
        return f"已{'追加' if append else '写入'}：{target}"

    def create_note(title: str, content: str, tags: str = "") -> str:
        """把一段学习笔记保存到笔记库（用户可以在笔记页随时修改）。"""
        if store is not None:
            note_id = store.add_note(title or "学习笔记", content, tags or "agent")
            return f"笔记已保存（id={note_id}）：{title or '学习笔记'}"
        notes_dir = DATA_DIR / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        path = notes_dir / "agent-notes.md"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## {time.strftime('%Y-%m-%d %H:%M')} {title}\n\n{content}\n")
        return f"笔记已保存到 {path}"

    def list_notes() -> str:
        """列出最近的笔记（标题 + 更新时间）。"""
        if store is not None:
            notes = store.list_notes()[:20]
            if not notes:
                return "还没有笔记。"
            return "\n".join(
                f"- {note['title']}（{note['updated_at'][:16]}）" for note in notes
            )
        return "笔记库未初始化。"

    def insert_image_to_word(image_path: str = "", caption: str = "", center: bool = True) -> str:
        """把图片插入当前 Word 文档光标处；不传路径则用最近一次截图。"""
        from core.word import insert_image_to_word as _insert

        return _insert(image_path, caption, center)

    def insert_screenshot_to_word(caption: str = "") -> str:
        """截取当前屏幕并插入 Word 光标处。"""
        from core.word import insert_screenshot_to_word as _insert

        return _insert(caption)

    def insert_clipboard_image_to_word(caption: str = "") -> str:
        """把剪贴板里的图片插入 Word 光标处。"""
        from core.word import insert_clipboard_image_to_word as _insert

        return _insert(caption)

    def insert_text_to_word(text: str) -> str:
        """把一段文字插入当前 Word 文档光标处。"""
        from core.word import insert_text_to_word as _insert

        return _insert(text)

    def get_word_status() -> str:
        """查看当前打开的 Word 文档。"""
        from core.word import get_word_status as _status

        return _status()

    def open_path(path: str) -> str:
        """用系统默认程序打开文件、文件夹或网址（危险操作，会请求确认）。"""
        if path.startswith(("http://", "https://")):
            os.startfile(path)  # type: ignore[attr-defined]
            return f"已在浏览器打开：{path}"
        target = Path(path).expanduser().resolve()
        if not target.exists():
            raise ToolError(f"路径不存在：{target}")
        os.startfile(str(target))  # type: ignore[attr-defined]
        return f"已打开：{target}"

    def extract_bvid(url_or_text: str) -> str:
        """从文本中提取 B 站视频 BV 号。"""
        bvid = parse_bvid(url_or_text)
        return bvid or "未找到 BV 号"

    specs = [
        ToolSpec(
            name="get_screen_context",
            description="获取当前前台窗口标题、进程名，以及识别到的 B 站视频标题。",
            parameters={"type": "object", "properties": {}},
            func=get_screen_context,
        ),
        ToolSpec(
            name="get_bilibili_video",
            description="根据 B 站视频链接或 BV 号查询视频信息（标题、UP 主、时长、分 P）。",
            parameters={
                "type": "object",
                "properties": {
                    "url_or_bvid": {"type": "string", "description": "B站链接或 BV 号"},
                },
                "required": ["url_or_bvid"],
            },
            func=get_bilibili_video,
        ),
        ToolSpec(
            name="get_current_time",
            description="获取当前日期和时间。",
            parameters={"type": "object", "properties": {}},
            func=get_time,
        ),
        ToolSpec(
            name="list_directory",
            description="列出目录下的文件和子目录。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认用户主目录"},
                },
            },
            func=list_directory,
        ),
        ToolSpec(
            name="read_text_file",
            description="读取本地文本文件内容（最多 8000 字符）。读取文件会请求用户确认。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "max_chars": {"type": "integer", "description": "最多读取字符数"},
                },
                "required": ["path"],
            },
            func=read_text_file,
            dangerous=True,
        ),
        ToolSpec(
            name="write_text_file",
            description="写入或追加本地文本文件。危险操作，会请求用户确认。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "写入内容"},
                    "append": {"type": "boolean", "description": "是否追加"},
                },
                "required": ["path", "content"],
            },
            func=write_text_file,
            dangerous=True,
        ),
        ToolSpec(
            name="create_note",
            description="把学习笔记保存到笔记库，用户可以在笔记页随时编辑。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "笔记标题"},
                    "content": {"type": "string", "description": "Markdown 正文"},
                    "tags": {"type": "string", "description": "标签，逗号分隔，可选"},
                },
                "required": ["title", "content"],
            },
            func=create_note,
        ),
        ToolSpec(
            name="list_notes",
            description="列出最近保存的笔记标题和时间。",
            parameters={"type": "object", "properties": {}},
            func=list_notes,
        ),
        ToolSpec(
            name="get_word_status",
            description="查看当前打开的 Word/WPS 文档名称和内嵌图片数量。",
            parameters={"type": "object", "properties": {}},
            func=get_word_status,
        ),
        ToolSpec(
            name="insert_image_to_word",
            description="把图片插入当前打开的 Word 文档光标处；不传 image_path 时使用最近一次截图。危险操作，会请求确认。",
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "图片绝对路径，留空则用最近截图"},
                    "caption": {"type": "string", "description": "图注，可选"},
                    "center": {"type": "boolean", "description": "是否居中，默认 true"},
                },
            },
            func=insert_image_to_word,
            dangerous=True,
        ),
        ToolSpec(
            name="insert_screenshot_to_word",
            description="截取当前屏幕并插入当前 Word 文档光标处。危险操作，会请求确认。",
            parameters={
                "type": "object",
                "properties": {"caption": {"type": "string", "description": "图注，可选"}},
            },
            func=insert_screenshot_to_word,
            dangerous=True,
        ),
        ToolSpec(
            name="insert_clipboard_image_to_word",
            description="把剪贴板里的图片（或复制的图片文件）粘贴到当前 Word 文档光标处。危险操作，会请求确认。",
            parameters={
                "type": "object",
                "properties": {"caption": {"type": "string", "description": "图注，可选"}},
            },
            func=insert_clipboard_image_to_word,
            dangerous=True,
        ),
        ToolSpec(
            name="insert_text_to_word",
            description="把一段文字插入当前 Word 文档光标处。危险操作，会请求确认。",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "要插入的文字"}},
                "required": ["text"],
            },
            func=insert_text_to_word,
            dangerous=True,
        ),
        ToolSpec(
            name="open_path",
            description="用系统默认程序打开文件、文件夹或网址。危险操作，会请求确认。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "路径或网址"}},
                "required": ["path"],
            },
            func=open_path,
            dangerous=True,
        ),
        ToolSpec(
            name="extract_bvid",
            description="从链接或文本中提取 B 站视频 BV 号。",
            parameters={
                "type": "object",
                "properties": {"url_or_text": {"type": "string", "description": "包含 BV 号的文本"}},
                "required": ["url_or_text"],
            },
            func=extract_bvid,
        ),
    ]
    for spec in specs:
        registry.register(spec)
    return registry
