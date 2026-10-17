"""屏幕截图（Pillow ImageGrab）。"""

from __future__ import annotations

from PIL import Image, ImageGrab


def grab_primary_screen() -> Image.Image:
    """截取主显示器（物理像素）。"""
    return ImageGrab.grab(all_screens=False)


def crop_image(img: Image.Image, x: int, y: int, width: int, height: int) -> Image.Image:
    x = max(0, min(x, img.width - 1))
    y = max(0, min(y, img.height - 1))
    width = max(1, min(width, img.width - x))
    height = max(1, min(height, img.height - y))
    return img.crop((x, y, x + width, y + height))
