"""桌面宠物：双击截图提问，可拖动、右键菜单、全屏时自动隐藏。"""

from __future__ import annotations

import ctypes
import math
import os
import random
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter
from PySide6.QtWidgets import QLabel, QMenu, QWidget

from ui.pet_art import render_pet


class _Bubble(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PetWindow(QWidget):
    capture_requested = Signal()
    open_main_requested = Signal()
    settings_requested = Signal()
    hidden_requested = Signal()
    quit_requested = Signal()
    moved = Signal(QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(200, 240)
        self.setWindowTitle("桌宠")
        self.setToolTip("双击我：截图提问\n拖动我：换个位置\n右键：更多")

        self._enabled = True
        self._state = "idle"
        self._phase = 0.0
        self._blink = False
        self._auto_hidden = False
        self._pix_cache: dict[tuple[str, bool], object] = {}
        self._drag_offset: QPoint | None = None
        self._drag_start: QPoint | None = None
        self._moved_while_drag = False
        self._pet_rect = QRect(20, 58, 160, 160)

        self.bubble = _Bubble(self)
        self.bubble.setObjectName("PetBubble")
        self.bubble.setGeometry(4, 0, 192, 52)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignCenter)
        self.bubble.hide()
        self.bubble.clicked.connect(self.open_main_requested.emit)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(60)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start()

        self._blink_timer = QTimer(self)
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._do_blink)
        self._blink_timer.start(random.randint(2500, 5000))

        self._fullscreen_timer = QTimer(self)
        self._fullscreen_timer.setInterval(2000)
        self._fullscreen_timer.timeout.connect(self._check_fullscreen)
        self._fullscreen_timer.start()

        self._reset_done_timer = QTimer(self)
        self._reset_done_timer.setSingleShot(True)
        self._reset_done_timer.timeout.connect(lambda: self.set_state("idle"))

    # ------------------------------------------------------------------ 状态
    def set_state(self, state: str, text: str = "") -> None:
        self._state = state
        self._reset_done_timer.stop()
        if state == "idle":
            self.bubble.hide()
        elif state == "thinking":
            self.bubble.hide()
        else:
            self.bubble.setText(text or ("回答好啦 · 点我看" if state == "done" else "出错了…"))
            self.bubble.show()
            self.bubble.raise_()
            self._reset_done_timer.start(6000)
        self.update()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            self._auto_hidden = False
            self.show_pet()
        else:
            self.hide()

    def show_pet(self) -> None:
        if not self._enabled or self._auto_hidden:
            return
        self.show()
        self.raise_()

    def hide_pet(self) -> None:
        self.hide()

    def _tick(self) -> None:
        if not self.isVisible():
            return
        self._phase += 0.08
        self.update()

    def _do_blink(self) -> None:
        self._blink = True
        self.update()
        QTimer.singleShot(120, self._finish_blink)

    def _finish_blink(self) -> None:
        self._blink = False
        self.update()
        self._blink_timer.start(random.randint(2500, 6000))

    # ------------------------------------------------------------------ 绘制
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        key = (self._state, self._blink)
        pixmap = self._pix_cache.get(key)
        if pixmap is None:
            pixmap = render_pet(160, mood=self._state, blink=self._blink, phase=0.0)
            self._pix_cache[key] = pixmap
        offset = int(math.sin(self._phase) * 2)
        painter.drawPixmap(QPoint(20, 58 + offset), pixmap)
        if self._state == "thinking":
            for index in range(3):
                alpha = 110 + int(120 * (0.5 + 0.5 * math.sin(self._phase * 2 + index)))
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(190, 210, 255, alpha))
                painter.drawEllipse(QPoint(76 + index * 16, 62 + offset), 4, 4)
        painter.end()

    # ------------------------------------------------------------------ 交互
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._pet_rect.contains(event.position().toPoint()):
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_start = event.globalPosition().toPoint()
            self._moved_while_drag = False
        else:
            event.ignore()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is None or not (event.buttons() & Qt.LeftButton):
            return
        point = event.globalPosition().toPoint()
        if self._drag_start is not None and (point - self._drag_start).manhattanLength() > 4:
            self._moved_while_drag = True
        self.move(point - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and self._moved_while_drag:
            self.moved.emit(self.pos())
        self._drag_offset = None
        self._drag_start = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._pet_rect.contains(event.position().toPoint()):
            self.capture_requested.emit()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if not self._pet_rect.contains(event.pos()):
            return
        menu = QMenu(self)
        menu.addAction("截图提问（双击）", self.capture_requested.emit)
        menu.addAction("打开主界面", self.open_main_requested.emit)
        menu.addSeparator()
        menu.addAction("设置…", self.settings_requested.emit)
        menu.addAction("隐藏桌宠", self.hidden_requested.emit)
        menu.addSeparator()
        menu.addAction("退出", self.quit_requested.emit)
        menu.exec(event.globalPos())

    # ------------------------------------------------------------------ 全屏检测
    def _check_fullscreen(self) -> None:
        if not self._enabled:
            return
        if _foreground_is_foreign_fullscreen():
            if self.isVisible():
                self._auto_hidden = True
                self.hide()
        elif self._auto_hidden:
            self._auto_hidden = False
            self.show_pet()


_user32 = ctypes.WinDLL("user32", use_last_error=True)


def _foreground_is_foreign_fullscreen() -> bool:
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return False
        buffer = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buffer, 256)
        if buffer.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Windows.UI.Core.CoreWindow"):
            return False
        rect = wintypes.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        monitor = _user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not monitor or not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False
        width = info.rcMonitor.right - info.rcMonitor.left
        height = info.rcMonitor.bottom - info.rcMonitor.top
        return (
            rect.left <= info.rcMonitor.left
            and rect.top <= info.rcMonitor.top
            and rect.right >= info.rcMonitor.right
            and rect.bottom >= info.rcMonitor.bottom
            and (rect.right - rect.left) >= width
            and (rect.bottom - rect.top) >= height
        )
    except Exception:
        return False


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetClassNameW.restype = ctypes.c_int
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.MonitorFromWindow.restype = wintypes.HANDLE
_user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MONITORINFO)]
_user32.GetMonitorInfoW.restype = wintypes.BOOL
