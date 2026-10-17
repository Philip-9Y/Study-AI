"""主窗口（DSH 风格）：左侧会话列表，右侧对话 / 笔记 / 记忆。

对话即 Agent：文字消息和截图提问都进入同一个对话，工具调用以卡片形式内联展示。
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.store import Store
from ui.answer_render import render_answer, render_stream_text
from ui.memory_pane import MemoryPane
from ui.notes_pane import NotesPane
from ui.pet_art import render_pet
from ui.theme import make_icon
from ui.utils import elide, format_time


class _TitleBar(QFrame):
    """无边框窗口的自定义浅色标题栏。"""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(6)

        icon = QLabel()
        icon.setPixmap(make_icon().pixmap(18, 18))
        icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title = QLabel("B站学习助手 · 路飞")
        title.setObjectName("TitleBarTitle")
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addStretch(1)

        self.min_btn = QPushButton("—")
        self.max_btn = QPushButton("□")
        self.close_btn = QPushButton("×")
        for button in (self.min_btn, self.max_btn, self.close_btn):
            button.setObjectName("TitleButton")
            button.setFixedSize(34, 26)
            button.setFocusPolicy(Qt.NoFocus)
            layout.addWidget(button)
        self.close_btn.setObjectName("TitleCloseButton")
        self.min_btn.clicked.connect(window.showMinimized)
        self.max_btn.clicked.connect(self._toggle_max)
        self.close_btn.clicked.connect(window.close)

    def _toggle_max(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            self.max_btn.setText("□")
        else:
            self._window.showMaximized()
            self.max_btn.setText("❐")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._toggle_max()
            return
        super().mouseDoubleClickEvent(event)


class _Composer(QTextEdit):
    submitted = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and (
            event.modifiers() & Qt.ControlModifier
        ):
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class MainWindow(QWidget):
    capture_requested = Signal()
    settings_requested = Signal()
    plugins_requested = Signal()
    message_sent = Signal(str, str)
    delete_requested = Signal(str)
    stop_requested = Signal(str)
    note_requested = Signal(str, str)
    consolidate_requested = Signal()
    memory_toggle_requested = Signal(str, bool)
    memory_delete_requested = Signal(str)
    memory_update_requested = Signal(str, str, str)
    hidden_to_tray = Signal()

    def __init__(self, store: Store, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.config = config
        self._active_sid = ""
        self._running_sid = ""
        self._live_bubble: dict | None = None

        self.setWindowTitle("B站学习助手 · 路飞")
        self.setWindowIcon(make_icon())
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.resize(1240, 820)
        self.setMinimumSize(1040, 700)

        self._build_ui()
        self._size_grip = QSizeGrip(self)
        self._size_grip.setFixedSize(16, 16)
        self._size_grip.raise_()
        self.refresh_history()
        self.refresh_memories()
        self.notes_pane.refresh()
        self.show_empty()
        self._back_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._back_shortcut.activated.connect(self._back_to_chat)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.setObjectName("Root")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_TitleBar(self))
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_main(), 1)
        outer.addWidget(body, 1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_size_grip"):
            self._size_grip.move(self.width() - 18, self.height() - 18)
            self._size_grip.raise_()

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(300)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(9)

        header = QHBoxLayout()
        avatar = QLabel()
        avatar.setPixmap(render_pet(40))
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("B站学习助手")
        title.setObjectName("AppTitle")
        subtitle = QLabel("对话 · 学习 · 干活")
        subtitle.setObjectName("AppSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(avatar)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        new_chat = QPushButton("＋ 新对话")
        new_chat.setObjectName("Primary")
        new_chat.setMinimumHeight(36)
        new_chat.clicked.connect(self.new_chat)
        layout.addWidget(new_chat)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("搜索对话…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.refresh_history())
        layout.addWidget(self.search)

        self.history = QListWidget()
        self.history.setObjectName("HistoryList")
        self.history.setSelectionMode(QListWidget.SingleSelection)
        self.history.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.history.setSpacing(2)
        self.history.itemClicked.connect(self._on_history_clicked)
        layout.addWidget(self.history, 1)

        self.history_empty = QLabel("还没有对话\n直接输入，或截图提问")
        self.history_empty.setObjectName("Muted")
        self.history_empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.history_empty)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        for text, handler in (
            ("笔记", self.show_notes),
            ("记忆", self.show_memory),
            ("插件", self.plugins_requested.emit),
            ("设置", self.settings_requested.emit),
        ):
            button = QPushButton(text)
            button.setObjectName("NavButton")
            button.clicked.connect(handler)
            nav.addWidget(button)
        layout.addLayout(nav)
        return side

    def _build_main(self) -> QWidget:
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_chat_page())
        self.notes_pane = NotesPane(self.store)
        self.notes_pane.back_requested.connect(self._back_to_chat)
        notes_page = QWidget()
        notes_layout = QVBoxLayout(notes_page)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.addWidget(self.notes_pane)
        self.stack.addWidget(notes_page)
        self.memory_pane = MemoryPane()
        memory_page = QWidget()
        memory_layout = QVBoxLayout(memory_page)
        memory_layout.setContentsMargins(26, 16, 26, 20)
        memory_header = QHBoxLayout()
        memory_back = QPushButton("← 对话")
        memory_back.setObjectName("Ghost")
        memory_back.clicked.connect(self._back_to_chat)
        memory_header.addWidget(memory_back)
        memory_header.addStretch(1)
        memory_layout.addLayout(memory_header)
        memory_layout.addWidget(self.memory_pane)
        self.stack.addWidget(memory_page)
        self.memory_pane.consolidate_requested.connect(self.consolidate_requested.emit)
        self.memory_pane.toggle_requested.connect(self.memory_toggle_requested.emit)
        self.memory_pane.delete_requested.connect(self.memory_delete_requested.emit)
        self.memory_pane.update_requested.connect(self.memory_update_requested.emit)
        return self.stack

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 16, 28, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_label = QLabel("新对话")
        self.title_label.setObjectName("SessionTitle")
        self.context_label = QLabel("")
        self.context_label.setObjectName("ContextChip")
        self.context_label.setVisible(False)
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.context_label)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Status")
        self.model_label = QLabel(self.config.model)
        self.model_label.setObjectName("ModelChip")
        self.note_btn = QPushButton("存为笔记")
        self.note_btn.setObjectName("Ghost")
        self.note_btn.clicked.connect(self.note_from_last)
        self.note_btn.hide()
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("DangerGhost")
        self.delete_btn.clicked.connect(self._delete_current)
        self.delete_btn.hide()
        header.addLayout(title_box, 1)
        header.addWidget(self.status_label)
        header.addWidget(self.model_label)
        header.addWidget(self.note_btn)
        header.addWidget(self.delete_btn)
        layout.addLayout(header)

        self.chat_stack = QStackedWidget()
        self.chat_stack.addWidget(self._build_welcome())
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("ChatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._reset_chat_container()
        self.chat_stack.addWidget(self.chat_scroll)
        layout.addWidget(self.chat_stack, 1)

        composer = QFrame()
        composer.setObjectName("Composer")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(12, 8, 12, 8)
        composer_layout.setSpacing(6)
        self.composer = _Composer()
        self.composer.setObjectName("ComposerEdit")
        self.composer.setPlaceholderText(
            "问点什么，或直接让 Agent 帮你做事：查视频、读文件、记笔记…（Ctrl+Enter 发送）"
        )
        self.composer.setFixedHeight(74)
        self.composer.submitted.connect(self._send)
        composer_layout.addWidget(self.composer)
        row = QHBoxLayout()
        self.screenshot_btn = QPushButton("截图提问")
        self.screenshot_btn.setObjectName("Ghost")
        self.screenshot_btn.clicked.connect(self.capture_requested.emit)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("DangerGhost")
        self.stop_btn.hide()
        self.stop_btn.clicked.connect(self._stop)
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("Primary")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.screenshot_btn)
        row.addStretch(1)
        row.addWidget(self.stop_btn)
        row.addWidget(self.send_btn)
        composer_layout.addLayout(row)
        layout.addWidget(composer)
        return page

    def _build_welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        pet = QLabel()
        pet.setPixmap(render_pet(140))
        pet.setAlignment(Qt.AlignCenter)
        title = QLabel("和你的桌面 Agent 开始")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignCenter)
        text = QLabel(
            "直接输入任务或问题；也可以截图问视频里的内容。\n"
            "Agent 会自己调用工具：查视频、读文件、写笔记……"
        )
        text.setObjectName("EmptyText")
        text.setAlignment(Qt.AlignCenter)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        capture = QPushButton("截图提问")
        capture.setObjectName("Primary")
        capture.clicked.connect(self.capture_requested.emit)
        buttons.addWidget(capture)
        buttons.addStretch(1)
        layout.addWidget(pet)
        layout.addWidget(title)
        layout.addWidget(text)
        layout.addSpacing(8)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return page

    def _reset_chat_container(self) -> None:
        old = self.chat_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        container = QWidget()
        container.setObjectName("ChatContainer")
        self.chat_layout = QVBoxLayout(container)
        self.chat_layout.setContentsMargins(2, 4, 8, 4)
        self.chat_layout.setSpacing(14)
        self.chat_layout.addStretch(1)
        self.chat_scroll.setWidget(container)

    # ------------------------------------------------------------------ 会话
    def refresh_history(self) -> None:
        sessions = self.store.list_sessions(self.search.text().strip())
        self.history.blockSignals(True)
        self.history.clear()
        selected = None
        for session in sessions:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, session["id"])
            widget = QLabel()
            widget.setTextFormat(Qt.RichText)
            widget.setText(
                f'<div style="font-size:12px;color:#1f2329;">{elide(session["question"], 26)}</div>'
                f'<div style="font-size:10px;color:#6b7280;margin-top:3px;">'
                f'{format_time(session["created_at"])} · {max(0, session["msg_count"])} 条</div>'
            )
            widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            widget.setContentsMargins(10, 7, 10, 7)
            widget.setFixedSize(256, 58)
            item.setSizeHint(widget.size())
            self.history.addItem(item)
            self.history.setItemWidget(item, widget)
            if session["id"] == self._active_sid:
                selected = item
        if selected is not None:
            selected.setSelected(True)
        self.history.blockSignals(False)
        self.history_empty.setVisible(len(sessions) == 0)

    def _on_history_clicked(self, item: QListWidgetItem) -> None:
        sid = item.data(Qt.UserRole)
        if sid:
            self.open_session(sid)

    def open_session(self, sid: str) -> None:
        session = self.store.get_session(sid)
        if not session:
            return
        self.stack.setCurrentIndex(0)
        self._active_sid = sid
        self._live_bubble = None
        self._reset_chat_container()
        for index, message in enumerate(self.store.get_messages(sid)):
            steps = _parse_steps(message.get("meta"))
            if message["role"] == "user":
                self._add_user_bubble(
                    message["content"], session.get("image_path") if index == 0 else None
                )
            elif message["role"] == "assistant":
                self._add_assistant_bubble(message["content"], steps)
        self.title_label.setText(elide(session["question"], 54))
        self.set_video_context(session.get("context") or "")
        self.delete_btn.show()
        self.note_btn.show()
        self.status_label.setText(format_time(session["created_at"]))
        self.chat_stack.setCurrentWidget(self.chat_scroll)
        self._set_running(False)
        self._enable_composer(True)
        self._scroll_bottom()

    def new_chat(self) -> None:
        self.stack.setCurrentIndex(0)
        self.show_empty()
        self.composer.setFocus()

    def show_empty(self) -> None:
        self._active_sid = ""
        self._live_bubble = None
        self._reset_chat_container()
        self.title_label.setText("新对话")
        self.context_label.hide()
        self.status_label.setText("")
        self.delete_btn.hide()
        self.note_btn.hide()
        self.chat_stack.setCurrentIndex(0)
        self._enable_composer(True)
        self.history.clearSelection()

    def _send(self) -> None:
        if self._running_sid:
            return
        text = self.composer.toPlainText().strip()
        if not text:
            return
        self.composer.clear()
        self._enable_composer(False)
        self.message_sent.emit(self._active_sid, text)

    def _stop(self) -> None:
        if self._running_sid:
            self.stop_requested.emit(self._running_sid)

    def _enable_composer(self, enabled: bool) -> None:
        self.composer.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        self.screenshot_btn.setEnabled(enabled)

    def _set_running(self, running: bool, sid: str = "") -> None:
        self._running_sid = sid if running else ""
        self.stop_btn.setVisible(running)
        if running:
            self.status_label.setText("生成中…")
            return
        session = self.store.get_session(self._active_sid) if self._active_sid else None
        self.status_label.setText(format_time(session["created_at"]) if session else "")

    # ------------------------------------------------------------------ Agent
    def agent_started(self, sid: str) -> None:
        if sid != self._active_sid:
            return
        self._set_running(True, sid)
        self._enable_composer(False)
        self._begin_live_bubble()

    def agent_step(self, sid: str, step: dict) -> None:
        if sid != self._active_sid or self._live_bubble is None:
            return
        self._add_step_card(self._live_bubble["steps"], step)
        self._scroll_bottom()

    def agent_finished(self, sid: str, text: str) -> None:
        if sid == self._active_sid:
            if self._live_bubble is not None:
                body = self._live_bubble["body"]
                try:
                    body.setTextFormat(Qt.RichText)
                    body.setText(render_answer(text))
                except RuntimeError:
                    pass
                self._live_bubble = None
                self._enable_composer(True)
                self._set_running(False)
                self._scroll_bottom()
            else:
                self.open_session(sid)
        self.refresh_history()

    def agent_failed(self, sid: str, message: str) -> None:
        if sid == self._active_sid:
            if self._live_bubble is not None:
                body = self._live_bubble["body"]
                try:
                    body.setTextFormat(Qt.RichText)
                    body.setText(f'<span style="color:#b91c1c;">⚠️ {_escape(message)}</span>')
                except RuntimeError:
                    pass
                self._live_bubble = None
                self._enable_composer(True)
                self._set_running(False)
            else:
                self.open_session(sid)
        self.refresh_history()

    def _begin_live_bubble(self) -> None:
        frame, steps, body = self._add_assistant_shell("正在思考…")
        self._live_bubble = {"frame": frame, "steps": steps, "body": body}
        self._scroll_bottom()

    # ------------------------------------------------------------------ 气泡
    def _add_user_bubble(self, text: str, image_path: str | None = None) -> None:
        frame = QFrame()
        frame.setObjectName("UserBubble")
        frame.setMaximumWidth(760)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)
        role = QLabel("你")
        role.setObjectName("BubbleRole")
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(role)
        lay.addWidget(body)
        if image_path:
            abs_path = self.store.image_abspath(image_path)
            if abs_path:
                pixmap = QPixmap(str(abs_path))
                if not pixmap.isNull():
                    thumb = pixmap.scaledToWidth(320, Qt.SmoothTransformation)
                    image_label = QLabel()
                    image_label.setPixmap(thumb)
                    image_label.setStyleSheet("border-radius:8px;")
                    lay.addWidget(image_label)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        row.addWidget(frame)
        row.addWidget(self._avatar("你", "AvatarUser"), 0, Qt.AlignTop)
        self.chat_layout.insertLayout(self.chat_layout.count() - 1, row)

    def _add_assistant_shell(self, initial_text: str):
        frame = QFrame()
        frame.setObjectName("AssistantBubble")
        frame.setMaximumWidth(920)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        steps = QVBoxLayout()
        steps.setSpacing(6)
        role = QLabel("助手")
        role.setObjectName("BubbleRole")
        body = QLabel(initial_text)
        body.setWordWrap(True)
        body.setTextFormat(Qt.MarkdownText)
        body.setTextInteractionFlags(Qt.TextBrowserInteraction)
        body.setOpenExternalLinks(True)
        lay.addWidget(role)
        lay.addLayout(steps)
        lay.addWidget(body)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._avatar("B", "AvatarBot"), 0, Qt.AlignTop)
        row.addWidget(frame, 1)
        row.addStretch(0)
        self.chat_layout.insertLayout(self.chat_layout.count() - 1, row)
        return frame, steps, body

    def _add_assistant_bubble(self, text: str, steps: list[dict] | None = None) -> None:
        frame, steps_layout, body = self._add_assistant_shell("")
        for step in steps or []:
            self._add_step_card(steps_layout, step)
        body.setTextFormat(Qt.RichText)
        body.setText(render_answer(text))

    def _add_step_card(self, layout: QVBoxLayout, step: dict) -> None:
        kind = step.get("type")
        if kind == "tool_call":
            name = _escape(step.get("name") or "")
            args = json.dumps(step.get("args") or {}, ensure_ascii=False)
            if len(args) > 240:
                args = args[:240] + "…"
            card = QFrame()
            card.setObjectName("ToolCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 7, 10, 7)
            card_layout.setSpacing(2)
            title = QLabel(f"🔧 调用工具 <b>{name}</b>")
            title.setObjectName("ToolTitle")
            title.setTextFormat(Qt.RichText)
            detail = QLabel(args)
            detail.setObjectName("ToolDetail")
            detail.setTextFormat(Qt.PlainText)
            detail.setWordWrap(True)
            detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
            card_layout.addWidget(title)
            card_layout.addWidget(detail)
            layout.addWidget(card)
        elif kind == "tool_result":
            ok = step.get("ok")
            summary = str(step.get("summary") or "")
            card = QFrame()
            card.setObjectName("ToolResult")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 6, 10, 6)
            title = QLabel(("✓ " if ok else "✗ ") + _escape(step.get("name") or ""))
            title.setObjectName("ToolTitle")
            title.setStyleSheet("color:#15803d;" if ok else "color:#b91c1c;")
            detail = QLabel(summary)
            detail.setObjectName("ToolDetail")
            detail.setTextFormat(Qt.PlainText)
            detail.setWordWrap(True)
            detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
            card_layout.addWidget(title)
            card_layout.addWidget(detail)
            layout.addWidget(card)
        elif kind == "assistant":
            text = _escape(str(step.get("text") or "")).replace("\n", "<br>")
            if text:
                label = QLabel(f'<span style="color:#6b7280;">Agent：</span>{text}')
                label.setObjectName("ToolDetail")
                label.setWordWrap(True)
                layout.addWidget(label)

    def _avatar(self, text: str, role: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(role)
        label.setAlignment(Qt.AlignCenter)
        label.setFixedSize(28, 28)
        return label

    # ------------------------------------------------------------------ 笔记/记忆
    def refresh_notes(self, select: str | None = None) -> None:
        self.notes_pane.refresh(select)

    def show_notes(self, select: str | None = None) -> None:
        self.stack.setCurrentIndex(1)
        self.notes_pane.refresh(select)

    def show_memory(self) -> None:
        self.stack.setCurrentIndex(2)
        self.refresh_memories()

    def show_chat(self) -> None:
        self.stack.setCurrentIndex(0)
        self.composer.setFocus()

    def _back_to_chat(self) -> None:
        self.stack.setCurrentIndex(0)
        self.composer.setFocus()

    def refresh_memories(self) -> None:
        self.memory_pane.refresh(self.store)

    def set_memory_status(self, text: str) -> None:
        self.memory_pane.set_status(text)

    def set_memory_busy(self, busy: bool, text: str = "") -> None:
        self.memory_pane.set_busy(busy, text)

    def note_from_last(self) -> None:
        if not self._active_sid:
            return
        messages = self.store.get_messages(self._active_sid)
        assistant = next((m for m in reversed(messages) if m["role"] == "assistant"), None)
        session = self.store.get_session(self._active_sid) or {}
        if assistant and assistant["content"].strip():
            title = session.get("question") or "学习笔记"
            self.note_requested.emit(elide(title, 40), assistant["content"])
        else:
            self.status_label.setText("还没有可保存的回答")

    # ------------------------------------------------------------------ 其他
    def set_video_context(self, context_text: str) -> None:
        text = " ".join((context_text or "").split())
        if not text:
            self.context_label.setText("")
            self.context_label.setVisible(False)
            self.context_label.setToolTip("")
            return
        self.context_label.setText(elide(text, 64))
        self.context_label.setToolTip(text)
        self.context_label.setVisible(True)

    def _delete_current(self) -> None:
        if not self._active_sid:
            return
        answer = QMessageBox.question(
            self,
            "删除对话",
            "确定删除这条对话吗？截图文件也会一并删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.delete_requested.emit(self._active_sid)

    def on_session_deleted(self, sid: str) -> None:
        if sid == self._active_sid:
            self.show_empty()
        self.refresh_history()

    def show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _scroll_bottom(self) -> None:
        QTimer.singleShot(0, self._do_scroll_bottom)

    def _do_scroll_bottom(self) -> None:
        bar = self.chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide()
        self.hidden_to_tray.emit()


def _parse_steps(meta: str | None) -> list[dict]:
    if not meta:
        return []
    try:
        data = json.loads(meta)
        steps = data.get("steps") or []
        return [step for step in steps if isinstance(step, dict)]
    except (json.JSONDecodeError, TypeError):
        return []


def _escape(text: str) -> str:
    import html

    return html.escape(text or "")
