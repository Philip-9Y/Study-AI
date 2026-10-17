"""桌宠形象：路飞风格的小海贼（草帽 + 红背心 + 眼下疤痕）。

说明：这是程序绘制的致敬形象，不使用官方素材；个人使用为主，
对外分发请自行确认版权。
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

SKIN = QColor("#f0c29a")
SKIN_SHADOW = QColor("#d9a273")
HAIR = QColor("#1d1d24")
HAT = QColor("#e9b949")
HAT_SHADOW = QColor("#c99a32")
HAT_BAND = QColor("#b83b2e")
VEST = QColor("#c0392b")
VEST_SHADOW = QColor("#96271f")
SHORTS = QColor("#2b4f9e")
OUTLINE = QColor("#2a1d0f")


def _rounded(painter: QPainter, rect: QRectF, radius: float, color: QColor) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawRoundedRect(rect, radius, radius)


def _draw_head(painter: QPainter, mood: str, blink: bool) -> None:
    # 后脑头发
    _rounded(painter, QRectF(34, 50, 20, 34), 9, HAIR)
    _rounded(painter, QRectF(106, 50, 20, 34), 9, HAIR)

    # 耳朵
    _rounded(painter, QRectF(30, 70, 12, 18), 6, SKIN)
    _rounded(painter, QRectF(118, 70, 12, 18), 6, SKIN)
    painter.setPen(QPen(SKIN_SHADOW, 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawArc(QRectF(31, 74, 8, 10), 90 * 16, 180 * 16)
    painter.drawArc(QRectF(121, 74, 8, 10), 90 * 16, 180 * 16)

    # 脸
    _rounded(painter, QRectF(38, 44, 84, 66), 30, SKIN)

    # 刘海
    hair_path = QPainterPath()
    hair_path.moveTo(38, 62)
    hair_path.cubicTo(40, 42, 60, 36, 80, 36)
    hair_path.cubicTo(100, 36, 118, 44, 122, 62)
    hair_path.lineTo(112, 58)
    hair_path.lineTo(104, 64)
    hair_path.lineTo(96, 56)
    hair_path.lineTo(86, 64)
    hair_path.lineTo(76, 56)
    hair_path.lineTo(66, 64)
    hair_path.lineTo(56, 56)
    hair_path.lineTo(46, 64)
    hair_path.closeSubpath()
    painter.setPen(Qt.NoPen)
    painter.setBrush(HAIR)
    painter.drawPath(hair_path)

    # 眉毛
    painter.setPen(QPen(HAIR, 2.4, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(55, 75), QPointF(68, 73))
    painter.drawLine(QPointF(92, 73), QPointF(105, 75))

    eye_y = 84
    if mood == "done":
        # 开心眯眼
        painter.setPen(QPen(OUTLINE, 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(55, eye_y - 4, 16, 12), 200 * 16, 140 * 16)
        painter.drawArc(QRectF(89, eye_y - 4, 16, 12), 200 * 16, 140 * 16)
    elif mood == "error":
        painter.setPen(QPen(OUTLINE, 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(58, eye_y - 5), QPointF(68, eye_y + 5))
        painter.drawLine(QPointF(68, eye_y - 5), QPointF(58, eye_y + 5))
        painter.drawLine(QPointF(92, eye_y - 5), QPointF(102, eye_y + 5))
        painter.drawLine(QPointF(102, eye_y - 5), QPointF(92, eye_y + 5))
    elif blink:
        painter.setPen(QPen(OUTLINE, 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(57, eye_y), QPointF(69, eye_y))
        painter.drawLine(QPointF(91, eye_y), QPointF(103, eye_y))
    else:
        look_y = -2.0 if mood == "thinking" else 0.5
        painter.setPen(Qt.NoPen)
        painter.setBrush(OUTLINE)
        painter.drawEllipse(QRectF(57, eye_y - 5 + look_y, 11, 12))
        painter.drawEllipse(QRectF(92, eye_y - 5 + look_y, 11, 12))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(60, eye_y - 3 + look_y, 3.5, 3.5))
        painter.drawEllipse(QRectF(95, eye_y - 3 + look_y, 3.5, 3.5))

    # 眼下疤痕（路飞左眼，画面右侧）
    painter.setPen(QPen(QColor("#a5533f"), 1.8, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(100, 91), QPointF(107, 94))
    painter.drawLine(QPointF(100, 95), QPointF(107, 98))

    # 鼻子
    painter.setPen(QPen(SKIN_SHADOW, 1.6, Qt.SolidLine, Qt.RoundCap))
    painter.drawArc(QRectF(76, 88, 8, 6), 200 * 16, 140 * 16)

    # 嘴 / 表情
    if mood == "thinking":
        painter.setPen(QPen(OUTLINE, 2.4))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(76, 98, 8, 7))
    elif mood == "error":
        painter.setPen(QPen(OUTLINE, 2.4, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(72, 103, 16, 9), 20 * 16, 140 * 16)
    elif mood == "done":
        painter.setPen(QPen(OUTLINE, 2.2))
        painter.setBrush(QColor("#7a2a24"))
        painter.drawRoundedRect(QRectF(68, 98, 24, 13), 6, 6)
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawLine(QPointF(68, 102), QPointF(92, 102))
    else:
        painter.setPen(QPen(OUTLINE, 2.6, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRectF(68, 96, 24, 14), 200 * 16, 140 * 16)

    # 草帽
    hat_brim = QPainterPath()
    hat_brim.addEllipse(QRectF(16, 36, 128, 20))
    painter.setPen(QPen(QColor("#8a6420"), 1.8))
    painter.setBrush(HAT)
    painter.drawPath(hat_brim)

    crown = QPainterPath()
    crown.moveTo(50, 40)
    crown.cubicTo(52, 14, 108, 14, 110, 40)
    crown.closeSubpath()
    gradient = QLinearGradient(50, 16, 110, 40)
    gradient.setColorAt(0.0, QColor("#f2c75c"))
    gradient.setColorAt(1.0, HAT)
    painter.setPen(QPen(QColor("#8a6420"), 1.8))
    painter.setBrush(gradient)
    painter.drawPath(crown)

    # 帽带
    band = QPainterPath()
    band.moveTo(52, 34)
    band.cubicTo(64, 30, 96, 30, 108, 34)
    band.lineTo(108, 41)
    band.cubicTo(96, 37, 64, 37, 52, 41)
    band.closeSubpath()
    painter.setPen(Qt.NoPen)
    painter.setBrush(HAT_BAND)
    painter.drawPath(band)


def _draw_body(painter: QPainter) -> None:
    # 手臂
    _rounded(painter, QRectF(20, 108, 18, 32), 9, SKIN)
    _rounded(painter, QRectF(122, 108, 18, 32), 9, SKIN)
    painter.setPen(QPen(SKIN_SHADOW, 1.2))
    painter.setBrush(Qt.NoBrush)
    painter.drawArc(QRectF(24, 132, 10, 8), 0, 180 * 16)
    painter.drawArc(QRectF(126, 132, 10, 8), 0, 180 * 16)

    # 红背心
    vest = QPainterPath()
    vest.moveTo(40, 106)
    vest.cubicTo(52, 102, 62, 104, 66, 112)
    vest.lineTo(80, 136)
    vest.lineTo(94, 112)
    vest.cubicTo(98, 104, 108, 102, 120, 106)
    vest.lineTo(122, 142)
    vest.cubicTo(100, 150, 60, 150, 38, 142)
    vest.closeSubpath()
    gradient = QLinearGradient(40, 106, 120, 146)
    gradient.setColorAt(0.0, QColor("#d0453a"))
    gradient.setColorAt(1.0, VEST_SHADOW)
    painter.setPen(QPen(QColor("#6f1c15"), 1.6))
    painter.setBrush(gradient)
    painter.drawPath(vest)

    # 胸口
    chest = QPainterPath()
    chest.moveTo(66, 112)
    chest.lineTo(80, 136)
    chest.lineTo(94, 112)
    chest.cubicTo(86, 108, 74, 108, 66, 112)
    painter.setPen(Qt.NoPen)
    painter.setBrush(SKIN)
    painter.drawPath(chest)

    # 胸口 X 疤
    painter.setPen(QPen(QColor("#a5533f"), 1.6, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(76, 116), QPointF(84, 126))
    painter.drawLine(QPointF(84, 116), QPointF(76, 126))

    # 短裤
    _rounded(painter, QRectF(44, 142, 72, 12), 5, SHORTS)
    painter.setPen(QPen(QColor("#1d3a78"), 1.4))
    painter.drawLine(QPointF(80, 143), QPointF(80, 153))

    # 背后的草帽绳
    painter.setPen(QPen(QColor("#c9a15a"), 1.6))
    painter.drawArc(QRectF(34, 104, 16, 18), 90 * 16, 120 * 16)
    painter.drawArc(QRectF(110, 104, 16, 18), 270 * 16, 120 * 16)


def render_pet(size: int = 160, mood: str = "idle", blink: bool = False, phase: float = 0.0) -> QPixmap:
    dpr = 2
    pixmap = QPixmap(size * dpr, size * dpr)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scale = size / 160.0
    painter.scale(dpr * scale, dpr * scale)

    bob = math.sin(phase) * 2.0
    painter.translate(0, bob)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0, 55))
    painter.drawEllipse(QRectF(38, 148, 84, 10))

    _draw_body(painter)
    _draw_head(painter, mood, blink)

    # 思考点（放在帽子上方）
    if mood == "thinking":
        for index in range(3):
            alpha = 110 + int(120 * (0.5 + 0.5 * math.sin(phase * 2 + index)))
            painter.setBrush(QColor(190, 210, 255, alpha))
            painter.drawEllipse(QRectF(56 + index * 16, 2, 7, 7))

    if mood == "error":
        # 汗滴
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(120, 190, 255, 220))
        drop = QPainterPath()
        drop.moveTo(126, 58)
        drop.cubicTo(120, 68, 120, 76, 126, 76)
        drop.cubicTo(132, 76, 132, 68, 126, 58)
        painter.drawPath(drop)

    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def render_pet_emoji(size: int = 40) -> QPixmap:
    return render_pet(size, mood="idle")


def render_app_icon(size: int = 256) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#ffffff"))
    gradient.setColorAt(1.0, QColor("#eaf1ff"))
    painter.setBrush(gradient)
    painter.setPen(QPen(QColor("#d5e2ff"), max(2.0, size * 0.012)))
    painter.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), size * 0.24, size * 0.24)

    # 把 160 坐标系的路飞画进图标
    scale = size / 160.0 * 1.18
    painter.translate(size * 0.5 - 80 * scale, size * 0.52 - 84 * scale)
    painter.scale(scale, scale)
    painter.setBrush(Qt.NoBrush)
    _draw_body(painter)
    _draw_head(painter, "idle", False)
    painter.end()
    return pixmap
