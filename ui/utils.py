"""UI 小工具：PIL→QPixmap、时间格式化、文本省略。"""

from __future__ import annotations

import io
from datetime import datetime

from PIL import Image
from PySide6.QtGui import QPixmap


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    try:
        from PIL import ImageQt

        return QPixmap.fromImage(ImageQt.ImageQt(img))
    except Exception:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue(), "PNG")
        return pixmap


def format_time(iso: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    try:
        dt = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return str(iso)
    if dt.date() == now.date():
        return dt.strftime("今天 %H:%M")
    if dt.year == now.year:
        return dt.strftime("%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d %H:%M")


def elide(text: str, limit: int = 46) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
