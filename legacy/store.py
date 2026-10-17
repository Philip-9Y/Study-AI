"""问答记录的持久化：截图 + JSONL + 人类可读的 Markdown 笔记。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PIL import Image


class Store:
    def __init__(self, base_dir: Path) -> None:
        self.base = base_dir
        self.captures = base_dir / "captures"
        self.notes = base_dir / "notes"
        self.captures.mkdir(parents=True, exist_ok=True)
        self.notes.mkdir(parents=True, exist_ok=True)

    def save_capture(self, img: Image.Image, when: datetime | None = None) -> str:
        """保存截图，返回相对 data 目录的路径（统一用 / 分隔）。"""
        when = when or datetime.now()
        day_dir = self.captures / when.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        name = when.strftime("%H%M%S_%f")[:-3] + ".png"
        path = day_dir / name
        img.save(path, format="PNG")
        return path.relative_to(self.base).as_posix()

    def append(self, record: dict, when: datetime | None = None) -> None:
        when = when or datetime.now()
        line = json.dumps(record, ensure_ascii=False)
        with (self.base / "notes.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

        md_path = self.notes / f"{when:%Y-%m-%d}.md"
        first = not md_path.exists()
        with md_path.open("a", encoding="utf-8") as fh:
            if first:
                fh.write(f"# {when:%Y-%m-%d} 学习问答\n\n")
            fh.write(f"## {when:%H:%M:%S}\n\n**问：** {record.get('question', '')}\n\n")
            image = record.get("image")
            if image:
                fh.write(f"![截图](../{image})\n\n")
            fh.write(f"**答：**\n\n{record.get('answer', '')}\n\n---\n\n")
