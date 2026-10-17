"""示例插件：学习笔记。"""

from __future__ import annotations

import time
from pathlib import Path

from core.tools import ToolSpec

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
NOTES_PATH = DATA_DIR / "notes" / "study-notes.md"


def add_study_note(title: str, content: str) -> str:
    """追加一条学习笔记。"""
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTES_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {time.strftime('%Y-%m-%d %H:%M')} {title}\n\n{content}\n")
    return f"已保存学习笔记：{NOTES_PATH}"


def list_study_notes() -> str:
    """查看最近的学习笔记。"""
    if not NOTES_PATH.exists():
        return "还没有学习笔记。"
    text = NOTES_PATH.read_text(encoding="utf-8")
    return text[-4000:]


def register(registry) -> None:
    registry.register(
        ToolSpec(
            name="add_study_note",
            description="把 Agent 整理好的学习笔记追加到本地 study-notes.md。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "笔记标题"},
                    "content": {"type": "string", "description": "Markdown 正文"},
                },
                "required": ["title", "content"],
            },
            func=add_study_note,
        )
    )
    registry.register(
        ToolSpec(
            name="list_study_notes",
            description="查看最近保存的学习笔记。",
            parameters={"type": "object", "properties": {}},
            func=list_study_notes,
        )
    )
