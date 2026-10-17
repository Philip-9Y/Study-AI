"""随手回答面板：热键提问后在屏幕右下角流式显示回答，可继续追问。"""

from __future__ import annotations

import html
import time

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui.answer_render import render_answer, render_stream_text
from ui.pet_art import render_pet
from ui.utils import elide


class _DragBar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._offset: QPoint | None = None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._offset = None


class AnswerPanel(QWidget):
    followup_requested = Signal(str, str)
    open_main_requested = Signal(str)
    closed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("学习助手")
        self._sid = ""
        self._buffer = ""
        self._streaming = False
        self._started = 0.0
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(90)
        self._flush_timer.timeout.connect(self._flush)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("PanelCard")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)

        header = _DragBar()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        pet_avatar = QLabel()
        pet_avatar.setPixmap(render_pet(28))
        pet_avatar.setFixedSize(28, 28)
        self.title = QLabel("学习助手")
        self.title.setObjectName("SessionTitle")
        self.open_btn = QPushButton("主窗口")
        self.open_btn.setObjectName("Ghost")
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("Ghost")
        self.close_btn.setFixedWidth(30)
        header_layout.addWidget(pet_avatar)
        header_layout.addWidget(self.title, 1)
        header_layout.addWidget(self.open_btn)
        header_layout.addWidget(self.close_btn)
        layout.addWidget(header)

        self.body = QTextBrowser()
        self.body.setObjectName("AnswerBody")
        self.body.setOpenExternalLinks(True)
        self.body.setMinimumHeight(240)
        layout.addWidget(self.body, 1)

        self.status = QLabel("思考中…")
        self.status.setObjectName("Muted")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("继续追问…")
        self.send_btn = QPushButton("追问")
        self.send_btn.setObjectName("Primary")
        self.input.returnPressed.connect(self._send_followup)
        self.send_btn.clicked.connect(self._send_followup)
        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        layout.addLayout(row)

        self.open_btn.clicked.connect(self._open_main)
        self.close_btn.clicked.connect(self._close_panel)
        self.resize(600, 500)
        self._position()

    # ------------------------------------------------------------------
    def _position(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.right() - self.width() - 24
        y = area.top() + 72
        self.move(max(area.left(), x), max(area.top(), y))

    def _tick_elapsed(self) -> None:
        if self._streaming:
            self.status.setText(f"正在生成… {time.time() - self._started:.1f}s")

    def show_session(self, sid: str, question: str) -> None:
        self._sid = sid
        self._buffer = ""
        self._streaming = True
        self._started = time.time()
        self.title.setText(elide(question, 30))
        self.body.clear()
        self.status.setText("正在生成… 0.0s")
        self.input.clear()
        self.input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self._elapsed_timer.start()
        self.show()
        self.raise_()
        self.activateWindow()

    def begin_followup(self, text: str) -> None:
        self._buffer += f"\n\n---\n\n**追问：** {text}\n\n"
        self._streaming = True
        self._started = time.time()
        self.input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.status.setText("正在生成… 0.0s")
        self._elapsed_timer.start()
        self._flush()

    def append(self, chunk: str) -> None:
        self._buffer += chunk
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush(self) -> None:
        if not self._buffer:
            return
        self.body.setMarkdown(render_stream_text(self._buffer))
        bar = self.body.verticalScrollBar()
        bar.setValue(bar.maximum())

    def finish(self, elapsed: float) -> None:
        self._streaming = False
        self._elapsed_timer.stop()
        try:
            self.body.setHtml(render_answer(self._buffer))
        except Exception:
            self.body.setMarkdown(self._buffer)
        bar = self.body.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.status.setText(f"已完成 · {elapsed:.1f}s")
        self.input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input.setFocus()

    def show_error(self, message: str) -> None:
        self._streaming = False
        self._elapsed_timer.stop()
        try:
            self.body.setHtml(
                render_answer(self._buffer)
                + f'<div style="color:#ff8a8a;">⚠️ 请求失败：{html.escape(message)}</div>'
            )
        except Exception:
            self.body.append(f"\n\n⚠️ 请求失败：{message}")
        self.status.setText("请求失败，可继续追问重试")
        self.input.setEnabled(True)
        self.send_btn.setEnabled(True)

    # ------------------------------------------------------------------
    def _send_followup(self) -> None:
        if not self._sid or self._streaming:
            return
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.followup_requested.emit(self._sid, text)

    def _open_main(self) -> None:
        if self._sid:
            self.open_main_requested.emit(self._sid)

    def _close_panel(self) -> None:
        self.hide()
        self.closed.emit(self._sid)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.hide()
        event.ignore()
        if self._sid:
            self.closed.emit(self._sid)

    def current_sid(self) -> str:
        return self._sid
