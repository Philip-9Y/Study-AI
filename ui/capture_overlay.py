"""全屏框选层：显示半透明截图，拖拽选区。"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ui.utils import pil_to_pixmap


class CaptureOverlay(QWidget):
    """selected 发送的是截图物理像素坐标；cancelled 表示用户取消。"""

    selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, image: Image.Image) -> None:
        super().__init__(
            None,
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self._pixmap: QPixmap = pil_to_pixmap(image)
        self._origin = QPoint()
        self._rect = QRect()
        self._dragging = False
        self._sx = 1.0
        self._sy = 1.0
        self._closed = False
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("框选提问区域")

    # ------------------------------------------------------------------
    def show_overlay(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setScreen(screen)
            self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.grabKeyboard()
        self._recalc_ratios()

    def _recalc_ratios(self) -> None:
        self._sx = self._pixmap.width() / max(1, self.width())
        self._sy = self._pixmap.height() / max(1, self.height())

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(self.rect(), self._pixmap)
        painter.fillRect(self.rect(), QColor(8, 10, 14, 168))

        if not self._rect.isNull() and self._rect.width() > 0:
            source = QRectF(
                self._rect.x() * self._sx,
                self._rect.y() * self._sy,
                self._rect.width() * self._sx,
                self._rect.height() * self._sy,
            )
            painter.drawPixmap(QRectF(self._rect), self._pixmap, source)
            painter.setPen(QPen(QColor("#4c8dff"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self._rect.adjusted(0, 0, -1, -1))

            font = QFont("Microsoft YaHei UI", 10)
            painter.setFont(font)
            painter.setPen(QColor("#dfe8ff"))
            label = f"{int(self._rect.width() * self._sx)} × {int(self._rect.height() * self._sy)}"
            painter.drawText(self._rect.topLeft() + QPoint(6, -8), label)

        font = QFont("Microsoft YaHei UI", 14, QFont.Bold)
        painter.setFont(font)
        text = "拖拽框选要提问的画面      Esc 取消"
        metrics = QFontMetrics(font)
        box_w = metrics.horizontalAdvance(text) + 44
        box_h = metrics.height() + 22
        box = QRectF((self.width() - box_w) / 2, 40, box_w, box_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(18, 20, 26, 215))
        painter.drawRoundedRect(box, 10, 10)
        painter.setPen(QColor("#e8eaf0"))
        painter.drawText(box, Qt.AlignCenter, text)

    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.RightButton:
            self._cancel()
            return
        if event.button() == Qt.LeftButton:
            self._origin = event.position().toPoint()
            self._rect = QRect(self._origin, self._origin)
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            self._rect = QRect(self._origin, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or not self._dragging:
            return
        self._dragging = False
        self._rect = self._rect.normalized()
        if self._rect.width() < 8 or self._rect.height() < 8:
            self._cancel()
            return
        physical = QRect(
            int(self._rect.x() * self._sx),
            int(self._rect.y() * self._sy),
            int(self._rect.width() * self._sx),
            int(self._rect.height() * self._sy),
        )
        self._cleanup()
        self.selected.emit(physical)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.releaseKeyboard()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    def _cancel(self) -> None:
        if self._closed:
            return
        self._cleanup()
        self.cancelled.emit()

    def _cleanup(self) -> None:
        self._closed = True
        self.releaseKeyboard()
        self.hide()
        self.close()
