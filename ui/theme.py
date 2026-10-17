"""浅色主题：白色界面、蓝色强调，接近 DSH 的简洁风格。"""

from __future__ import annotations

from PySide6.QtGui import QIcon

from ui.pet_art import render_app_icon

COLORS = {
    "bg": "#f6f7fb",
    "panel": "#ffffff",
    "card": "#ffffff",
    "border": "#e3e7ef",
    "text": "#1f2329",
    "muted": "#6b7280",
    "accent": "#2563eb",
}

QSS = """
* {
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #1f2329;
}
QWidget#Root { background: #f6f7fb; }
QFrame#Sidebar {
    background: #ffffff;
    border-right: 1px solid #e8ebf1;
}
QFrame#Content { background: transparent; }

QLabel#AppTitle { font-size: 18px; font-weight: 700; color: #111827; }
QLabel#AppSubtitle { color: #8a94a6; font-size: 11px; }
QLabel#SectionTitle { font-size: 13px; font-weight: 600; color: #111827; }
QLabel#SessionTitle { font-size: 16px; font-weight: 600; color: #111827; }
QLabel#Status { color: #8a94a6; font-size: 11px; }
QLabel#Muted { color: #8a94a6; font-size: 11px; }
QLabel#BubbleRole { color: #8a94a6; font-size: 11px; }
QLabel#EmptyTitle { font-size: 22px; font-weight: 700; color: #111827; }
QLabel#EmptyText { color: #6b7280; font-size: 13px; }
QLabel#HintKey {
    color: #4b5563;
    background: #f1f4f9;
    border: 1px solid #e3e7ef;
    border-radius: 6px;
    padding: 2px 7px;
    font-size: 11px;
}

QFrame#UserBubble {
    background: #eaf1ff;
    border: 1px solid #d5e2ff;
    border-radius: 12px;
}
QFrame#AssistantBubble {
    background: #ffffff;
    border: 1px solid #e6eaf2;
    border-radius: 12px;
}
QFrame#ErrorBubble {
    background: #fff1f2;
    border: 1px solid #ffd6d9;
    border-radius: 12px;
}
QFrame#PanelCard {
    background: #ffffff;
    border: 1px solid #e3e7ef;
    border-radius: 14px;
}
QFrame#InputCard {
    background: #ffffff;
    border: 1px solid #e3e7ef;
    border-radius: 14px;
}
QLineEdit#InputEdit {
    background: transparent;
    border: none;
    padding: 6px 4px;
    font-size: 13px;
}
QLineEdit#InputEdit:focus { border: none; }

QLabel#AvatarUser, QLabel#AvatarBot {
    min-width: 28px; max-width: 28px;
    min-height: 28px; max-height: 28px;
    border-radius: 14px;
    font-weight: 700;
    font-size: 11px;
}
QLabel#AvatarUser { background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
QLabel#AvatarBot {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8cff, stop:1 #2563eb);
    color: #ffffff;
}

QLineEdit {
    background: #ffffff;
    border: 1px solid #dfe4ec;
    border-radius: 9px;
    padding: 8px 12px;
    selection-background-color: #bfdbfe;
}
QLineEdit:focus { border: 1px solid #2563eb; }
QLineEdit#Search { padding: 7px 10px; font-size: 12px; }

QPushButton {
    background: #f3f5f9;
    border: 1px solid #e3e7ef;
    border-radius: 9px;
    padding: 7px 14px;
    color: #374151;
}
QPushButton:hover { background: #e9eef7; border-color: #d5dce8; }
QPushButton:pressed { background: #dde5f2; }
QPushButton:disabled { color: #a3aab8; background: #f2f4f8; border-color: #e8ebf1; }
QPushButton#Primary {
    background: #2563eb;
    border: none;
    color: #ffffff;
    font-weight: 600;
    padding: 8px 16px;
}
QPushButton#Primary:hover { background: #1d4ed8; }
QPushButton#Primary:disabled { background: #c7d7f8; color: #f5f8ff; }
QPushButton#Ghost { background: transparent; border: none; color: #4b5563; padding: 5px 8px; }
QPushButton#Ghost:hover { background: #eef2f9; color: #111827; }
QPushButton#DangerGhost { background: transparent; border: none; color: #b91c1c; padding: 5px 8px; }
QPushButton#DangerGhost:hover { background: #fef2f2; color: #991b1b; }
QPushButton#Segment {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    color: #6b7280;
}
QPushButton#Segment:hover { color: #111827; }
QPushButton#Segment:checked { background: #eaf1ff; color: #1d4ed8; font-weight: 600; }

QListWidget#HistoryList, QListWidget#MemoryList {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget#HistoryList::item { border-radius: 9px; margin: 2px 2px; }
QListWidget#HistoryList::item:selected {
    background: #eaf1ff;
    border-left: 2px solid #2563eb;
}
QListWidget#HistoryList::item:hover { background: #f4f6fa; }

QWidget#MemoryCard {
    background: #ffffff;
    border: 1px solid #e6eaf2;
    border-radius: 10px;
}
QWidget#MemoryCard:hover { border-color: #cdd8ea; }
QLabel#MemoryContent { color: #1f2329; font-size: 12px; }
QLabel#MemoryMeta { color: #8a94a6; font-size: 10px; }
QCheckBox#MemCheck::indicator {
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #cbd5e1; background: #ffffff;
}
QCheckBox#MemCheck::indicator:checked {
    background: #2563eb;
    border: 1px solid #2563eb;
}

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QTextBrowser#AnswerBody {
    background: transparent;
    border: none;
    selection-background-color: #bfdbfe;
    font-size: 13px;
}
QTextBrowser#AnswerBody a { color: #2563eb; }

QLabel#PetBubble {
    background: #ffffff;
    border: 1px solid #e3e7ef;
    border-radius: 12px;
    color: #1f2329;
    font-size: 11px;
    padding: 6px 8px;
}
QLabel#ContextChip {
    color: #1d4ed8;
    background: #eaf1ff;
    border: 1px solid #d5e2ff;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 10px;
}
QLabel#ModelChip {
    color: #1d4ed8;
    background: #eaf1ff;
    border: 1px solid #d5e2ff;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 10px;
}
QTextBrowser#AgentLog {
    background: #ffffff;
    border: 1px solid #e6eaf2;
    border-radius: 12px;
    padding: 10px;
}
QTextEdit#AgentTask {
    background: #ffffff;
    border: 1px solid #dfe4ec;
    border-radius: 10px;
    padding: 8px;
    selection-background-color: #bfdbfe;
}
QTextEdit#AgentTask:focus { border: 1px solid #2563eb; }

QFrame#Composer {
    background: #ffffff;
    border: 1px solid #dfe4ec;
    border-radius: 14px;
}
QTextEdit#ComposerEdit {
    background: transparent;
    border: none;
    padding: 2px;
    font-size: 13px;
    selection-background-color: #bfdbfe;
}
QFrame#ToolCard {
    background: #f8faff;
    border: 1px solid #dbe6ff;
    border-left: 3px solid #2563eb;
    border-radius: 8px;
}
QFrame#ToolResult {
    background: #f8f9fb;
    border: 1px solid #e8ebf1;
    border-radius: 8px;
}
QLabel#ToolTitle { color: #374151; font-size: 11px; }
QLabel#ToolDetail {
    color: #6b7280;
    font-size: 11px;
    font-family: Consolas, "Cascadia Mono", monospace;
}

QFrame#NotesListPanel {
    background: #ffffff;
    border-right: 1px solid #e8ebf1;
}
QFrame#NotesEditorPanel { background: #ffffff; }
QLineEdit#NoteTitle {
    font-size: 17px;
    font-weight: 600;
    padding: 8px 10px;
}
QTextEdit#NoteContent {
    background: #fbfcfe;
    border: 1px solid #e6eaf2;
    border-radius: 10px;
    padding: 10px;
    font-size: 13px;
    selection-background-color: #bfdbfe;
}
QListWidget#NotesList { background: transparent; border: none; outline: none; }
QListWidget#NotesList::item {
    border-radius: 8px;
    padding: 8px 10px;
    color: #374151;
}
QListWidget#NotesList::item:selected { background: #eaf1ff; color: #1d4ed8; }
QListWidget#NotesList::item:hover { background: #f4f6fa; }

QListWidget#PluginList { background: transparent; border: none; outline: none; }
QWidget#PluginCard {
    background: #ffffff;
    border: 1px solid #e6eaf2;
    border-radius: 10px;
}
QLabel#PluginName { font-weight: 600; color: #111827; font-size: 13px; }

QMenu { background: #ffffff; border: 1px solid #e3e7ef; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 22px; border-radius: 7px; }
QMenu::item:selected { background: #eef2f9; }
QMenu::separator { height: 1px; background: #eef1f6; margin: 4px 8px; }

QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff; border: 1px solid #dfe4ec; border-radius: 9px; padding: 6px 8px;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #2563eb; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #e3e7ef; selection-background-color: #eef2f9; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #cbd5e1; background: #ffffff; }
QCheckBox::indicator:checked { background: #2563eb; border: 1px solid #2563eb; }

QDialog { background: #ffffff; }
QToolTip { background: #ffffff; color: #1f2329; border: 1px solid #e3e7ef; padding: 4px 8px; }

QPushButton#NavButton {
    background: transparent;
    border: none;
    color: #6b7280;
    padding: 7px 4px;
    border-radius: 7px;
    font-size: 12px;
}
QPushButton#NavButton:hover { background: #eef2f9; color: #111827; }

QFrame#TitleBar {
    background: #ffffff;
    border-bottom: 1px solid #e8ebf1;
}
QLabel#TitleBarTitle { color: #111827; font-size: 12px; font-weight: 600; }
QPushButton#TitleButton {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: #4b5563;
    padding: 0;
    font-size: 13px;
}
QPushButton#TitleButton:hover { background: #eef2f9; color: #111827; }
QPushButton#TitleCloseButton {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: #4b5563;
    padding: 0;
    font-size: 15px;
}
QPushButton#TitleCloseButton:hover { background: #dc2626; color: #ffffff; }

QTextEdit {
    background: #ffffff;
    border: 1px solid #dfe4ec;
    border-radius: 9px;
    selection-background-color: #bfdbfe;
}
"""


def apply_theme(app) -> None:
    app.setStyleSheet(QSS)


def make_icon(size: int = 64) -> QIcon:
    return QIcon(render_app_icon(size))
