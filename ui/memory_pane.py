"""侧边栏的「记忆库」：整理、筛选、启用/停用、编辑、删除。"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.store import Store
from ui.utils import elide, format_time


class _MemoryItem(QWidget):
    toggled = Signal(str, bool)
    edit_clicked = Signal(dict)
    delete_clicked = Signal(str)

    def __init__(self, memory: dict, parent=None) -> None:
        super().__init__(parent)
        self.memory = memory
        self.setObjectName("MemoryCard")
        self.setFixedWidth(286)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.check = QCheckBox()
        self.check.setObjectName("MemCheck")
        self.check.setChecked(bool(memory["enabled"]))
        self.check.setToolTip("启用/停用这条记忆")
        self.check.toggled.connect(lambda checked: self.toggled.emit(memory["id"], checked))
        content = QLabel(elide(memory["content"], 60))
        content.setObjectName("MemoryContent")
        content.setWordWrap(True)
        content.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        top.addWidget(self.check, 0, Qt.AlignTop)
        top.addWidget(content, 1)
        layout.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        meta = QLabel(
            (memory["tags"].replace(",", " · ") + " · " if memory["tags"] else "")
            + format_time(memory["updated_at"])
        )
        meta.setObjectName("MemoryMeta")
        meta.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        edit_btn = QPushButton("改")
        edit_btn.setObjectName("Ghost")
        edit_btn.setFixedWidth(28)
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.memory))
        delete_btn = QPushButton("删")
        delete_btn.setObjectName("DangerGhost")
        delete_btn.setFixedWidth(28)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.memory["id"]))
        bottom.addWidget(meta, 1)
        bottom.addWidget(edit_btn)
        bottom.addWidget(delete_btn)
        layout.addLayout(bottom)


class _EditMemoryDialog(QDialog):
    def __init__(self, content: str, tags: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑记忆")
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)
        layout.addWidget(QLabel("记忆内容"))
        self.content = QTextEdit()
        self.content.setPlainText(content)
        self.content.setFixedHeight(100)
        layout.addWidget(self.content)
        layout.addWidget(QLabel("标签（用逗号分隔）"))
        self.tags = QLineEdit(tags)
        layout.addWidget(self.tags)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setObjectName("Primary")
        save.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(save)
        layout.addLayout(row)

    def values(self) -> tuple[str, str]:
        return self.content.toPlainText().strip(), self.tags.text().strip()


class MemoryPane(QWidget):
    consolidate_requested = Signal()
    toggle_requested = Signal(str, bool)
    delete_requested = Signal(str)
    update_requested = Signal(str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("长期记忆")
        title.setObjectName("SectionTitle")
        self.count_label = QLabel("0 条")
        self.count_label.setObjectName("Muted")
        self.consolidate_btn = QPushButton("整理")
        self.consolidate_btn.setObjectName("Primary")
        self.consolidate_btn.setFixedHeight(28)
        self.consolidate_btn.setToolTip("把最近的问答压缩成长期记忆，并自动合并相似条目")
        self.consolidate_btn.clicked.connect(self.consolidate_requested.emit)
        header.addWidget(title)
        header.addWidget(self.count_label)
        header.addStretch(1)
        header.addWidget(self.consolidate_btn)
        layout.addLayout(header)

        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("搜索记忆…")
        self.search.setClearButtonEnabled(True)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self._reload)
        self.search.textChanged.connect(lambda _: self._search_timer.start())
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setObjectName("MemoryList")
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setSpacing(4)
        layout.addWidget(self.list, 1)

        self.empty = QLabel("还没有记忆\n点「整理」把最近的问答压缩成长期记忆")
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty)

        self._store: Store | None = None
        self._busy = False

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.consolidate_btn.setEnabled(not busy)
        self.consolidate_btn.setText("整理中…" if busy else "整理")
        if message:
            self.set_status(message)

    def set_status(self, text: str) -> None:
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def refresh(self, store: Store) -> None:
        self._store = store
        self._reload()

    def _reload(self) -> None:
        if self._store is None:
            return
        memories = self._store.list_memories(self.search.text().strip())
        self.list.clear()
        for memory in memories:
            item = QListWidgetItem()
            widget = _MemoryItem(memory)
            widget.toggled.connect(self.toggle_requested.emit)
            widget.delete_clicked.connect(self._confirm_delete)
            widget.edit_clicked.connect(self._edit)
            item.setSizeHint(widget.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
        self.empty.setVisible(not memories)
        self.count_label.setText(f"{len(memories)} 条")

    def _confirm_delete(self, memory_id: str) -> None:
        answer = QMessageBox.question(
            self,
            "删除记忆",
            "确定删除这条记忆吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.delete_requested.emit(memory_id)

    def _edit(self, memory: dict) -> None:
        dialog = _EditMemoryDialog(memory["content"], memory["tags"], parent=self)
        if dialog.exec():
            content, tags = dialog.values()
            if content:
                self.update_requested.emit(memory["id"], content, tags)
