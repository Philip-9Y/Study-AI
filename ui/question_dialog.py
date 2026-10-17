"""截图后的提问输入框。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

DEFAULT_QUESTION = "请讲解一下当前画面里的内容。"


class QuestionDialog(QDialog):
    def __init__(self, preview: QPixmap, anchor: QPoint, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("提问")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self._question = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        thumb = preview.scaled(320, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        preview_label = QLabel()
        preview_label.setPixmap(thumb)
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setStyleSheet("background:#f3f5f9; border-radius:8px; padding:6px;")
        layout.addWidget(preview_label)

        hint = QLabel("输入你的问题（留空则让它讲解画面），回车发送")
        hint.setObjectName("Muted")
        layout.addWidget(hint)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("例如：这段代码在做什么？/ 这个公式怎么推导？")
        self.edit.returnPressed.connect(self._accept)
        layout.addWidget(self.edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        send = QPushButton("发送")
        send.setObjectName("Primary")
        send.setDefault(True)
        send.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(send)
        layout.addLayout(buttons)

        self.resize(430, self.sizeHint().height())
        self._place_near(anchor)

    def _place_near(self, anchor: QPoint) -> None:
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = min(max(area.left() + 8, anchor.x() + 14), area.right() - self.width() - 8)
        y = anchor.y() + 18
        if y + self.height() > area.bottom() - 8:
            y = max(area.top() + 8, anchor.y() - self.height() - 18)
        self.move(int(x), int(y))

    def _accept(self) -> None:
        self._question = self.edit.text().strip() or DEFAULT_QUESTION
        self.accept()

    def question(self) -> str:
        return self._question

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()
