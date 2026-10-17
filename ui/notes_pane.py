"""笔记页：左侧列表 + 右侧编辑器，支持新建、修改、删除、导出。"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.store import Store
from ui.utils import elide, format_time


class NotesPane(QWidget):
    changed = Signal()
    back_requested = Signal()

    def __init__(self, store: Store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._current_id: str | None = None
        self._dirty = False
        self._auto_save = QTimer(self)
        self._auto_save.setSingleShot(True)
        self._auto_save.setInterval(1200)
        self._auto_save.timeout.connect(self.save_note)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_list())
        splitter.addWidget(self._build_editor())
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

    # ------------------------------------------------------------------
    def _build_list(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("NotesListPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        back = QPushButton("← 对话")
        back.setObjectName("Ghost")
        back.clicked.connect(self.back_requested.emit)
        title = QLabel("笔记")
        title.setObjectName("SectionTitle")
        new_btn = QPushButton("新建")
        new_btn.setObjectName("Primary")
        new_btn.setFixedHeight(28)
        new_btn.clicked.connect(self.new_note)
        header.addWidget(back)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(new_btn)
        layout.addLayout(header)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("搜索笔记…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.refresh())
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setObjectName("NotesList")
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setSpacing(3)
        self.list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list, 1)
        return panel

    def _build_editor(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("NotesEditorPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(8)

        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("NoteTitle")
        self.title_edit.setPlaceholderText("笔记标题")
        self.title_edit.textChanged.connect(self._mark_dirty)
        layout.addWidget(self.title_edit)

        self.tags_edit = QLineEdit()
        self.tags_edit.setObjectName("Search")
        self.tags_edit.setPlaceholderText("标签（逗号分隔，可选）")
        self.tags_edit.textChanged.connect(self._mark_dirty)
        layout.addWidget(self.tags_edit)

        self.content_edit = QTextEdit()
        self.content_edit.setObjectName("NoteContent")
        self.content_edit.setPlaceholderText(
            "在这里写笔记，或者让 Agent 在对话里说“记到笔记里”自动生成。"
        )
        self.content_edit.textChanged.connect(self._mark_dirty)
        layout.addWidget(self.content_edit, 1)

        footer = QHBoxLayout()
        self.status = QLabel("选择左侧笔记，或新建一条")
        self.status.setObjectName("Muted")
        self.export_btn = QPushButton("导出 .md")
        self.export_btn.setObjectName("Ghost")
        self.export_btn.clicked.connect(self.export_note)
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("DangerGhost")
        self.delete_btn.clicked.connect(self.delete_note)
        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self.save_note)
        footer.addWidget(self.status, 1)
        footer.addWidget(self.export_btn)
        footer.addWidget(self.delete_btn)
        footer.addWidget(self.save_btn)
        layout.addLayout(footer)
        return panel

    # ------------------------------------------------------------------
    def refresh(self, select: str | None = None) -> None:
        notes = self.store.list_notes(self.search.text().strip())
        self.list.blockSignals(True)
        self.list.clear()
        target = select or self._current_id
        if target is None and notes:
            target = notes[0]["id"]
        selected_item = None
        for note in notes:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, note["id"])
            item.setText(f"{note['title']}\n{format_time(note['updated_at'])}")
            item.setSizeHint(QSize(0, 52))
            self.list.addItem(item)
            if note["id"] == target:
                selected_item = item
        if selected_item is not None:
            selected_item.setSelected(True)
            self.list.setCurrentItem(selected_item)
        self.list.blockSignals(False)
        if target and target != self._current_id:
            note = self.store.get_note(target)
            if note:
                self._load(note)
        if not notes:
            self._clear_editor()
            self.status.setText("还没有笔记，点「新建」开始")

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        note_id = item.data(Qt.UserRole)
        note = self.store.get_note(note_id)
        if note:
            self._load(note)

    def _load(self, note: dict) -> None:
        self._current_id = note["id"]
        self.title_edit.blockSignals(True)
        self.tags_edit.blockSignals(True)
        self.content_edit.blockSignals(True)
        self.title_edit.setText(note["title"])
        self.tags_edit.setText(note["tags"])
        self.content_edit.setPlainText(note["content"])
        self.title_edit.blockSignals(False)
        self.tags_edit.blockSignals(False)
        self.content_edit.blockSignals(False)
        self._dirty = False
        self.status.setText(f"最后更新：{format_time(note['updated_at'])}")

    def _clear_editor(self) -> None:
        self._current_id = None
        self._dirty = False
        for widget in (self.title_edit, self.tags_edit):
            widget.blockSignals(True)
            widget.clear()
            widget.blockSignals(False)
        self.content_edit.blockSignals(True)
        self.content_edit.clear()
        self.content_edit.blockSignals(False)

    def new_note(self) -> None:
        self._clear_editor()
        self.list.clearSelection()
        self.title_edit.setFocus()
        self.status.setText("新笔记（保存后创建）")

    def save_note(self) -> None:
        title = self.title_edit.text().strip() or "未命名笔记"
        content = self.content_edit.toPlainText()
        tags = self.tags_edit.text().strip()
        if not content.strip() and not title:
            return
        if self._current_id:
            self.store.update_note(self._current_id, title=title, content=content, tags=tags)
        else:
            self._current_id = self.store.add_note(title, content, tags)
        self._dirty = False
        self.status.setText(f"已保存 · {time.strftime('%H:%M:%S')}")
        self.refresh(self._current_id)
        self.changed.emit()

    def delete_note(self) -> None:
        if not self._current_id:
            return
        answer = QMessageBox.question(
            self,
            "删除笔记",
            "确定删除这条笔记吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.store.delete_note(self._current_id)
            self._current_id = None
            self._clear_editor()
            self.refresh()
            self.changed.emit()

    def export_note(self) -> None:
        if self._current_id:
            self.save_note()
        title = self.title_edit.text().strip() or "note"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出笔记", f"{title}.md", "Markdown (*.md)"
        )
        if not path:
            return
        body = f"# {title}\n\n{self.content_edit.toPlainText()}\n"
        Path(path).write_text(body, encoding="utf-8")
        self.status.setText(f"已导出：{path}")

    def _mark_dirty(self) -> None:
        self._dirty = True
        self.status.setText("未保存…")
        if self._current_id:
            self._auto_save.start()
