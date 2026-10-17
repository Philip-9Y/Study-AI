"""Agent 任务页：输入任务、展示工具调用过程与最终结果。"""

from __future__ import annotations

import html
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.answer_render import render_answer


class AgentPane(QWidget):
    run_requested = Signal(str, bool)
    stop_requested = Signal()
    plugins_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("任务 Agent")
        title.setObjectName("SessionTitle")
        self.status = QLabel("可以调用工具帮你做事")
        self.status.setObjectName("Muted")
        plugins_btn = QPushButton("插件")
        plugins_btn.setObjectName("Ghost")
        plugins_btn.clicked.connect(self.plugins_requested.emit)
        header.addWidget(title)
        header.addWidget(self.status)
        header.addStretch(1)
        header.addWidget(plugins_btn)
        layout.addLayout(header)

        self.log = QTextBrowser()
        self.log.setObjectName("AgentLog")
        self.log.setOpenExternalLinks(True)
        layout.addWidget(self.log, 1)

        self.task = QTextEdit()
        self.task.setObjectName("AgentTask")
        self.task.setPlaceholderText(
            "例如：看看我现在看的这个视频讲了什么，整理成笔记；\n"
            "或者：把桌面上的实验数据文件读出来，总结关键结论"
        )
        self.task.setFixedHeight(86)
        layout.addWidget(self.task)

        bottom = QHBoxLayout()
        self.use_context = QCheckBox("附带屏幕上下文（前台窗口 / 视频标题）")
        self.use_context.setChecked(True)
        self.run_btn = QPushButton("执行任务")
        self.run_btn.setObjectName("Primary")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("Ghost")
        self.stop_btn.hide()
        self.run_btn.clicked.connect(self._run)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        bottom.addWidget(self.use_context)
        bottom.addStretch(1)
        bottom.addWidget(self.stop_btn)
        bottom.addWidget(self.run_btn)
        layout.addLayout(bottom)

        hint = QLabel("危险操作会弹窗确认；Agent 可调用内置工具和插件工具。")
        hint.setObjectName("Muted")
        layout.addWidget(hint)

    # ------------------------------------------------------------------
    def _run(self) -> None:
        task = self.task.toPlainText().strip()
        if not task:
            return
        self.run_requested.emit(task, self.use_context.isChecked())

    def set_running(self, running: bool) -> None:
        self.task.setEnabled(not running)
        self.run_btn.setEnabled(not running)
        self.use_context.setEnabled(not running)
        self.stop_btn.setVisible(running)
        self.status.setText("执行中…" if running else "可以调用工具帮你做事")

    def begin(self, task: str) -> None:
        self.log.clear()
        self._append(
            '<div style="background:#1b2232;border:1px solid #2a3244;border-radius:8px;'
            'padding:10px 12px;color:#dfe4ef;"><b>任务</b><br>'
            + html.escape(task).replace("\n", "<br>")
            + "</div>"
        )
        self.set_running(True)

    def step(self, step: dict) -> None:
        kind = step.get("type")
        if kind == "assistant":
            text = html.escape(step.get("text") or "").replace("\n", "<br>")
            self._append(
                '<div style="color:#aeb8cc;padding:6px 2px;">'
                '<span style="color:#8a92a6;">Agent：</span>' + text + "</div>"
            )
        elif kind == "tool_call":
            name = html.escape(step.get("name") or "")
            arguments = json.dumps(step.get("args") or {}, ensure_ascii=False)
            if len(arguments) > 300:
                arguments = arguments[:300] + "…"
            self._append(
                '<div style="background:#141821;border-left:3px solid #6d5efc;'
                'border-radius:6px;padding:8px 12px;margin:2px 0;">'
                f'<span style="color:#8ea7ff;">🔧 调用工具</span> <b>{name}</b><br>'
                f'<span style="color:#8a92a6;font-family:Consolas,monospace;">'
                f"{html.escape(arguments)}</span></div>"
            )
        elif kind == "tool_result":
            ok = step.get("ok")
            summary = html.escape(step.get("summary") or "")
            color = "#7fd18b" if ok else "#ff8a8a"
            icon = "✓" if ok else "✗"
            self._append(
                f'<div style="color:{color};padding:4px 12px 8px 12px;">'
                f"{icon} {html.escape(step.get('name') or '')}：{summary}</div>"
            )

    def finish(self, markdown: str) -> None:
        self._append(
            '<div style="border-top:1px solid #2a3244;margin:8px 0 6px 0;"></div>'
            '<div style="color:#8a92a6;font-size:12px;margin-bottom:4px;">最终结果</div>'
        )
        self._append(render_answer(markdown))
        self.set_running(False)
        self.status.setText("完成 · 可以继续下一个任务")

    def fail(self, message: str) -> None:
        self._append(
            '<div style="color:#ff8a8a;background:#2a1a1f;border:1px solid #4a2a33;'
            'border-radius:8px;padding:8px 12px;">⚠️ '
            + html.escape(message)
            + "</div>"
        )
        self.set_running(False)
        self.status.setText("任务失败")

    def _append(self, html_text: str) -> None:
        self.log.append(html_text)
        self.log.moveCursor(QTextCursor.End)
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())
