"""设置对话框：API Key、模型参数、测试连接。"""

from __future__ import annotations

import os
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from core.config import DATA_DIR, Config
from core.llm import DeepSeekClient


class _TestSignals(QObject):
    finished = Signal(bool, str)


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(560)
        self._test_signals = _TestSignals(self)
        self._test_signals.finished.connect(self._on_test_done)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        title = QLabel("连接到 DeepSeek")
        title.setObjectName("AppTitle")
        layout.addWidget(title)
        hint = QLabel(
            "API Key 只保存在本机 config.json；也可以设置环境变量 DEEPSEEK_API_KEY。\n"
            "获取地址：platform.deepseek.com → API Keys"
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.key_edit = QLineEdit(str(config.data.get("api_key", "")))
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-…")
        self.show_key_btn = QPushButton("显示")
        self.show_key_btn.setObjectName("Ghost")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(self.show_key_btn)
        form.addRow("API Key", key_row)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(["deepseek-flash", "deepseek-pro"])
        self.model_combo.setCurrentText(config.model)
        form.addRow("模型", self.model_combo)

        self.tokens = QSpinBox()
        self.tokens.setRange(256, 8192)
        self.tokens.setSingleStep(100)
        self.tokens.setValue(int(config.data.get("max_tokens", 4096)))
        form.addRow("最大回复 tokens", self.tokens)

        self.temp = QDoubleSpinBox()
        self.temp.setRange(0.0, 2.0)
        self.temp.setSingleStep(0.1)
        self.temp.setValue(float(config.data.get("temperature", 0.6)))
        form.addRow("温度", self.temp)

        self.save_caps = QCheckBox("保存截图原图到本地（推荐）")
        self.save_caps.setChecked(bool(config.data.get("save_captures", True)))
        form.addRow("", self.save_caps)

        self.pet_enabled = QCheckBox("显示桌面宠物（双击它可截图提问）")
        self.pet_enabled.setChecked(bool(config.data.get("pet_enabled", True)))
        form.addRow("", self.pet_enabled)

        self.thinking = QCheckBox("深度思考（复杂题更准，但明显更慢；预算不够会自动回退）")
        self.thinking.setChecked(bool(config.data.get("thinking", False)))
        self.thinking.setToolTip(
            "开启后模型会先输出思维链。截图快问快答建议关闭，否则可能长时间无正文。"
        )
        form.addRow("", self.thinking)

        self.note_template = QTextEdit()
        self.note_template.setPlainText(config.note_template)
        self.note_template.setFixedHeight(130)
        self.note_template.setToolTip(
            "点「笔记 → 新建」会用这个模板；Agent 记笔记时也会按这个结构组织。"
        )
        form.addRow("笔记模板", self.note_template)

        data_row = QHBoxLayout()
        data_label = QLabel(str(DATA_DIR))
        data_label.setObjectName("Muted")
        open_btn = QPushButton("打开文件夹")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(self._open_data_dir)
        data_row.addWidget(data_label, 1)
        data_row.addWidget(open_btn)
        form.addRow("数据目录", data_row)

        layout.addLayout(form)

        test_row = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setObjectName("Ghost")
        self.test_btn.clicked.connect(self._test_connection)
        self.test_status = QLabel("")
        self.test_status.setObjectName("Muted")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status, 1)
        layout.addLayout(test_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setObjectName("Primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    def _toggle_key_visibility(self, visible: bool) -> None:
        self.key_edit.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)

    def _open_data_dir(self) -> None:
        try:
            os.startfile(str(DATA_DIR))
        except Exception:
            pass

    def _test_connection(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            self.test_status.setText("请先填写 API Key")
            return
        self.test_btn.setEnabled(False)
        self.test_status.setText("测试中…")
        model = self.model_combo.currentText().strip() or "deepseek-flash"
        base_url = self.config.base_url

        def run() -> None:
            try:
                client = DeepSeekClient(
                    api_key=key, base_url=base_url, model=model, max_tokens=32, temperature=0.0
                )
                answer = client.chat(
                    [{"role": "user", "content": "请只回复：连接成功"}]
                )
                self._test_signals.finished.emit(True, answer.strip()[:80])
            except Exception as exc:  # noqa: BLE001
                self._test_signals.finished.emit(False, str(exc))

        threading.Thread(target=run, daemon=True).start()

    def _on_test_done(self, ok: bool, message: str) -> None:
        try:
            self.test_btn.setEnabled(True)
            self.test_status.setText(("✓ " if ok else "✗ ") + message)
        except RuntimeError:
            pass

    def _save(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "提示", "API Key 不能为空")
            return
        self.config.data["api_key"] = key
        self.config.data["model"] = self.model_combo.currentText().strip() or "deepseek-flash"
        self.config.data["max_tokens"] = int(self.tokens.value())
        self.config.data["temperature"] = float(self.temp.value())
        self.config.data["save_captures"] = bool(self.save_caps.isChecked())
        self.config.data["pet_enabled"] = bool(self.pet_enabled.isChecked())
        self.config.data["thinking"] = bool(self.thinking.isChecked())
        self.config.data["note_template"] = self.note_template.toPlainText().strip()
        self.config.save()
        self.accept()
