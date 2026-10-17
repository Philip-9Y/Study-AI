"""插件管理对话框：安装、启用/停用、卸载。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.plugins import PluginInfo, PluginManager


class _PluginCard(QWidget):
    def __init__(self, info: PluginInfo, manager: PluginManager, parent=None) -> None:
        super().__init__(parent)
        self.info = info
        self.manager = manager
        self.setObjectName("PluginCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(4)

        top = QHBoxLayout()
        enabled = QCheckBox()
        enabled.setChecked(info.enabled)
        enabled.setToolTip("启用/停用插件")
        enabled.toggled.connect(lambda checked: self._toggle(checked))
        name = QLabel(info.name)
        name.setObjectName("PluginName")
        meta = QLabel(
            f"{info.version or '0.0'} · {'内置' if info.builtin else '已安装'}"
            + (f" · {info.author}" if info.author else "")
        )
        meta.setObjectName("MemoryMeta")
        top.addWidget(enabled)
        top.addWidget(name)
        top.addWidget(meta)
        top.addStretch(1)
        if not info.builtin:
            uninstall = QPushButton("卸载")
            uninstall.setObjectName("DangerGhost")
            uninstall.clicked.connect(self._uninstall)
            top.addWidget(uninstall)
        layout.addLayout(top)

        desc = QLabel(info.description or "（没有描述）")
        desc.setObjectName("MemoryContent")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        status_parts = []
        if info.tools:
            status_parts.append("工具：" + "、".join(info.tools))
        if info.error:
            status_parts.append("错误：" + info.error)
        if status_parts:
            status = QLabel(" · ".join(status_parts))
            status.setObjectName("MemoryMeta")
            status.setWordWrap(True)
            layout.addWidget(status)

    def _toggle(self, enabled: bool) -> None:
        try:
            self.manager.set_enabled(self.info.name, enabled)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "插件", str(exc))

    def _uninstall(self) -> None:
        answer = QMessageBox.question(
            self,
            "卸载插件",
            f"确定卸载插件「{self.info.name}」吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            try:
                self.manager.uninstall(self.info.name)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "插件", str(exc))


class PluginsDialog(QDialog):
    def __init__(self, manager: PluginManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("插件")
        self.setModal(True)
        self.resize(620, 520)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel("工具插件")
        title.setObjectName("AppTitle")
        layout.addWidget(title)
        hint = QLabel(
            "插件是可执行的本地 Python 代码，仅安装你信任的插件；"
            "启用后其中的工具会出现在 Agent 的工具列表里。"
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.list = QListWidget()
        self.list.setObjectName("PluginList")
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setSpacing(4)
        layout.addWidget(self.list, 1)

        self.empty = QLabel("还没有安装插件。内置插件 study-notes 已加载。")
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty)

        buttons = QHBoxLayout()
        install_dir = QPushButton("安装文件夹…")
        install_dir.setObjectName("Ghost")
        install_dir.clicked.connect(self._install_folder)
        install_zip = QPushButton("安装 zip…")
        install_zip.setObjectName("Ghost")
        install_zip.clicked.connect(self._install_zip)
        open_dir = QPushButton("打开插件目录")
        open_dir.setObjectName("Ghost")
        open_dir.clicked.connect(self.manager.open_user_dir)
        reload_btn = QPushButton("重新加载")
        reload_btn.setObjectName("Ghost")
        reload_btn.clicked.connect(self.refresh)
        close = QPushButton("关闭")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        buttons.addWidget(install_dir)
        buttons.addWidget(install_zip)
        buttons.addWidget(open_dir)
        buttons.addWidget(reload_btn)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        self.manager.load_all()
        self.list.clear()
        plugins = self.manager.list_plugins()
        for info in plugins:
            item = QListWidgetItem()
            card = _PluginCard(info, self.manager)
            item.setSizeHint(card.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, card)
        self.empty.setVisible(not plugins)

    def _install_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择插件文件夹（包含 plugin.json）")
        if not folder:
            return
        try:
            info = self.manager.install_from_folder(Path(folder))
            QMessageBox.information(self, "插件", f"已安装：{info.name}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "安装失败", str(exc))
        self.refresh()

    def _install_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择插件 zip", filter="Zip (*.zip)")
        if not path:
            return
        try:
            info = self.manager.install_from_zip(Path(path))
            QMessageBox.information(self, "插件", f"已安装：{info.name}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "安装失败", str(exc))
        self.refresh()
