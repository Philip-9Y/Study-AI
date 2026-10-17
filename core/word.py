"""Word 自动化工具：把截图/图片插入当前打开的 Word 文档。"""

from __future__ import annotations

from pathlib import Path

from core.config import DATA_DIR


def _latest_capture() -> Path | None:
    folder = DATA_DIR / "captures"
    if not folder.exists():
        return None
    files = sorted(folder.rglob("*.png"), key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _get_word_app():
    """返回 (Word COM 对象, 是否由我们启动)。优先 Word，其次 WPS。"""
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    for prog_id in ("Word.Application", "KWps.Application"):
        try:
            app = win32com.client.GetActiveObject(prog_id)
            return app, False
        except Exception:
            continue
    for prog_id in ("Word.Application", "KWps.Application"):
        try:
            app = win32com.client.Dispatch(prog_id)
            return app, True
        except Exception:
            continue
    return None, False


def _active_document():
    app, started = _get_word_app()
    if app is None:
        raise RuntimeError("没有找到 Word/WPS，请先安装并打开文档")
    if app.Documents.Count == 0:
        if started:
            try:
                app.Quit()
            except Exception:
                pass
        raise RuntimeError("请先打开一个 Word 文档，并把光标放到要插入的位置")
    return app, app.ActiveDocument, started


def get_word_status() -> str:
    """查看当前打开的 Word 文档。"""
    try:
        app, doc, started = _active_document()
    except Exception as exc:  # noqa: BLE001
        return f"Word 状态：{exc}"
    try:
        count = doc.InlineShapes.Count
        return f"当前 Word 文档：{doc.Name}（已有 {count} 个内嵌图片）"
    finally:
        if started:
            try:
                app.Quit()
            except Exception:
                pass


def insert_image_to_word(image_path: str = "", caption: str = "", center: bool = True) -> str:
    """把图片插入当前 Word 文档光标处；不传路径则使用最近一次截图。"""
    path = Path(image_path).expanduser() if image_path else _latest_capture()
    if path is None or not Path(path).exists():
        raise RuntimeError("找不到图片，请先截图或提供图片路径")
    path = Path(path).resolve()

    app, doc, started = _active_document()
    try:
        selection = app.Selection
        if center:
            selection.ParagraphFormat.Alignment = 1
        shape = selection.InlineShapes.AddPicture(str(path), False, True)
        selection.TypeParagraph()
        if caption:
            selection.ParagraphFormat.Alignment = 1
            selection.TypeText(caption)
            selection.TypeParagraph()
        return (
            f"已插入图片到《{doc.Name}》当前光标位置：{path.name}"
            + (f"，图注：{caption}" if caption else "")
        )
    finally:
        if started:
            try:
                app.Quit()
            except Exception:
                pass


def insert_text_to_word(text: str) -> str:
    """把一段文字插入当前 Word 文档光标处。"""
    if not (text or "").strip():
        raise RuntimeError("插入文本为空")
    app, doc, started = _active_document()
    try:
        app.Selection.TypeText(text)
        return f"已插入文本到《{doc.Name}》"
    finally:
        if started:
            try:
                app.Quit()
            except Exception:
                pass


def insert_screenshot_to_word(caption: str = "") -> str:
    """截取当前屏幕并插入 Word 当前光标处。"""
    from datetime import datetime

    from PIL import ImageGrab

    when = datetime.now()
    folder = DATA_DIR / "captures" / when.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (when.strftime("%H%M%S_%f")[:-3] + "_word.png")
    ImageGrab.grab(all_screens=False).save(path, format="PNG")
    return insert_image_to_word(str(path), caption)


def insert_clipboard_image_to_word(caption: str = "") -> str:
    """把剪贴板里的图片（或复制的图片文件）插入 Word 当前光标处。"""
    from datetime import datetime

    from PIL import Image, ImageGrab

    content = ImageGrab.grabclipboard()
    if content is None:
        raise RuntimeError("剪贴板里没有图片，请先复制一张图片")
    if isinstance(content, list):
        images = [
            Path(item)
            for item in content
            if str(item).lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))
        ]
        if not images:
            raise RuntimeError("剪贴板里没有可用的图片文件")
        path = images[0]
    else:
        when = datetime.now()
        folder = DATA_DIR / "captures" / when.strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (when.strftime("%H%M%S_%f")[:-3] + "_clipboard.png")
        content.save(path, format="PNG")
    return insert_image_to_word(str(path), caption)
