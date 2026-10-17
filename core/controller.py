"""业务编排：截图/文字 → 对话 Agent（工具调用）→ 入库。"""

from __future__ import annotations

import logging
from datetime import datetime

from PIL import Image
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QDialog, QMessageBox

from core.capture import crop_image, grab_primary_screen
from core.config import Config
from core.context import ContextWatcher, get_foreground_context
from core.conversation import ConversationAgent
from core.memory import MemoryManager
from core.store import Store
from ui.capture_overlay import CaptureOverlay
from ui.main_window import MainWindow
from ui.question_dialog import QuestionDialog
from ui.settings_dialog import SettingsDialog
from ui.utils import pil_to_pixmap

LOGGER = logging.getLogger("biliask")


class Controller(QObject):
    toast = Signal(str)
    history_changed = Signal(str)
    capture_started = Signal()
    capture_finished = Signal()
    answer_started = Signal(str)
    answer_finished = Signal(str)
    answer_failed = Signal(str, str)
    memory_changed = Signal()
    memory_status = Signal(str)
    settings_changed = Signal()

    def __init__(
        self,
        store: Store,
        config: Config,
        main_window: MainWindow,
        agent: ConversationAgent,
        context_watcher: ContextWatcher | None = None,
        question_provider=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.config = config
        self.main = main_window
        self.agent = agent
        self.context_watcher = context_watcher
        self.memory = agent.memory or MemoryManager(store, config)
        self._question_provider = question_provider or self._ask_question

        self._capturing = False
        self._pending_image: Image.Image | None = None
        self._overlay: CaptureOverlay | None = None
        self._pending_context = None
        self._restore_main = False
        self._consolidating = False

        self.main.capture_requested.connect(self.start_capture)
        self.main.settings_requested.connect(self.open_settings)
        self.main.message_sent.connect(self.send_text)
        self.main.delete_requested.connect(self.delete_session)
        self.main.consolidate_requested.connect(self.consolidate_memories)
        self.main.memory_toggle_requested.connect(self.toggle_memory)
        self.main.memory_delete_requested.connect(self.delete_memory)
        self.main.memory_update_requested.connect(self.update_memory)
        self.main.note_requested.connect(self.create_note_from_message)

        self.agent.started.connect(self._on_agent_started)
        self.agent.step.connect(self._on_agent_step)
        self.agent.finished.connect(self._on_agent_finished)
        self.agent.failed.connect(self._on_agent_failed)
        self.agent.confirmation_requested.connect(self._on_confirmation)
        self._consolidation_done.connect(self._on_consolidation_done)

    # ------------------------------------------------------------------ 截图
    def start_capture(self) -> None:
        if self._capturing:
            self.toast.emit("正在框选中，请稍候")
            return
        self._capturing = True
        if self.context_watcher is not None:
            self._pending_context = self.context_watcher.best()
        else:
            self._pending_context = get_foreground_context()
        self.capture_started.emit()
        if self.main.isVisible():
            self._restore_main = True
            self.main.hide()
            QTimer.singleShot(180, self._capture_now)
        else:
            self._restore_main = False
            self._capture_now()

    def _capture_now(self) -> None:
        if not self._capturing:
            return
        try:
            image = grab_primary_screen()
        except Exception as exc:  # noqa: BLE001
            self._capturing = False
            LOGGER.exception("截屏失败")
            self.toast.emit(f"截屏失败：{exc}")
            self._restore_main_window()
            self.capture_finished.emit()
            return
        self._pending_image = image
        overlay = CaptureOverlay(image)
        overlay.selected.connect(self._on_region_selected)
        overlay.cancelled.connect(self._on_capture_cancelled)
        self._overlay = overlay
        overlay.show_overlay()

    def _release_overlay(self) -> None:
        overlay, self._overlay = self._overlay, None
        if overlay is not None:
            try:
                overlay.hide()
                overlay.deleteLater()
            except RuntimeError:
                pass

    def _restore_main_window(self) -> None:
        if self._restore_main:
            self._restore_main = False
            self.main.show_and_raise()

    def _on_capture_cancelled(self) -> None:
        self._capturing = False
        self._pending_image = None
        self._release_overlay()
        self.capture_finished.emit()
        self._restore_main_window()

    def _on_region_selected(self, rect) -> None:  # QRect（物理像素）
        image = self._pending_image
        self._pending_image = None
        self._release_overlay()
        if image is None:
            self._capturing = False
            self.capture_finished.emit()
            self._restore_main_window()
            return
        crop = crop_image(image, rect.x(), rect.y(), rect.width(), rect.height())
        try:
            question = self._question_provider(crop)
        except Exception:  # noqa: BLE001
            LOGGER.exception("提问失败")
            question = None
        finally:
            self._capturing = False
        if question:
            self._restore_main = False
            self._submit_screenshot(question, crop)
            self.capture_finished.emit()
        else:
            self.capture_finished.emit()
            self._restore_main_window()

    def _ask_question(self, crop: Image.Image) -> str | None:
        dialog = QuestionDialog(
            pil_to_pixmap(crop), QCursor.pos(), parent=self.main if self.main.isVisible() else None
        )
        if dialog.exec() == QDialog.Accepted and dialog.question():
            return dialog.question()
        return None

    # ------------------------------------------------------------------ 提交
    def _submit_screenshot(self, question: str, crop: Image.Image) -> None:
        if not self.config.api_key:
            self.open_settings()
            if not self.config.api_key:
                self.toast.emit("未配置 API Key，本次提问已取消")
                return
        when = datetime.now()
        image_rel = None
        if self.config.data.get("save_captures", True):
            image_rel = self.store.save_capture(crop, when)
        context_text = self._pending_context.prompt_text() if self._pending_context else ""
        sid = self.store.create_session(
            question, image_rel, self.config.model, when, context=context_text or None
        )
        self.store.add_message(sid, "user", question, image_path=image_rel, when=when)
        self.main.open_session(sid)
        self.main.show_and_raise()
        self.history_changed.emit(sid)
        self.agent.run(sid)

    def send_text(self, sid: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        if sid and self.agent.is_running(sid):
            self.toast.emit("这个会话还在生成，请稍候")
            return
        if not sid:
            context_text = ""
            if self.context_watcher is not None:
                context_text = self.context_watcher.best().prompt_text()
            sid = self.store.create_session(
                text,
                None,
                self.config.model,
                datetime.now(),
                context=context_text or None,
            )
        self.store.add_message(sid, "user", text)
        self.main.open_session(sid)
        self.history_changed.emit(sid)
        self.agent.run(sid)

    # ------------------------------------------------------------------ Agent
    def _on_agent_started(self, sid: str) -> None:
        self.main.agent_started(sid)
        self.answer_started.emit(sid)

    def _on_agent_step(self, sid: str, step: dict) -> None:
        self.main.agent_step(sid, step)

    def _on_agent_finished(self, sid: str, text: str) -> None:
        self.main.agent_finished(sid, text)
        self.main.refresh_history()
        self.main.refresh_notes()
        self.answer_finished.emit(sid)

    def _on_agent_failed(self, sid: str, message: str) -> None:
        self.main.agent_failed(sid, message)
        self.main.refresh_history()
        self.answer_failed.emit(sid, message)

    def _on_confirmation(self, request_id: str, tool: str, args_json: str) -> None:
        preview = args_json if len(args_json) <= 500 else args_json[:500] + "…"
        answer = QMessageBox.question(
            self.main,
            "工具需要确认",
            f"Agent 想执行危险操作：\n\n工具：{tool}\n参数：\n{preview}\n\n允许执行吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        self.agent.resolve_confirmation(request_id, answer == QMessageBox.Yes)

    # ------------------------------------------------------------------ 笔记
    def create_note_from_message(self, title: str, content: str) -> None:
        if not content.strip():
            return
        note_id = self.store.add_note(title or "学习笔记", content, tags="")
        self.main.show_notes(select=note_id)
        self.toast.emit("已保存到笔记")

    # ------------------------------------------------------------------ 记忆
    def consolidate_memories(self) -> None:
        if self._consolidating:
            self.toast.emit("正在整理记忆，请稍候")
            return
        if not self.config.api_key:
            self.open_settings()
            if not self.config.api_key:
                return
        session_ids = self.store.get_session_ids(20)
        if not session_ids:
            self.toast.emit("还没有问答记录，先聊几句再整理")
            return
        self._consolidating = True
        self.memory_status.emit("正在整理最近的对话…")

        def work() -> None:
            result = self.memory.consolidate(session_ids)
            self._consolidation_done.emit(result)

        import threading

        threading.Thread(target=work, daemon=True, name="memory-consolidate").start()

    _consolidation_done = Signal(object)

    def _on_consolidation_done(self, result) -> None:
        self._consolidating = False
        error = result.get("error")
        if error:
            self.memory_status.emit(f"整理失败：{error}")
            self.toast.emit(f"记忆整理失败：{error}")
            return
        added = result.get("added", 0)
        merged = result.get("merged", 0)
        self.memory_status.emit(f"已整理：新增 {added} 条，合并 {merged} 条")
        self.memory_changed.emit()
        self.toast.emit(f"记忆已更新：新增 {added} 条，合并 {merged} 条")

    def toggle_memory(self, memory_id: str, enabled: bool) -> None:
        self.store.update_memory(memory_id, enabled=enabled)
        self.memory_changed.emit()

    def delete_memory(self, memory_id: str) -> None:
        self.store.delete_memory(memory_id)
        self.memory_changed.emit()

    def update_memory(self, memory_id: str, content: str, tags: str) -> None:
        if content.strip():
            self.store.update_memory(memory_id, content=content.strip(), tags=tags.strip())
            self.memory_changed.emit()

    # ------------------------------------------------------------------ 其他
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, parent=self.main)
        if dialog.exec():
            self.toast.emit("设置已保存")
            self.settings_changed.emit()

    def open_in_main(self, sid: str) -> None:
        self.main.show_and_raise()
        self.main.open_session(sid)

    def delete_session(self, sid: str) -> None:
        self.agent.stop(sid)
        image_rel = self.store.delete_session(sid)
        if image_rel:
            path = self.store.data_dir / image_rel
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                LOGGER.warning("删除截图失败: %s", path)
        self.main.on_session_deleted(sid)

    def shutdown(self) -> None:
        self.agent.stop()
        self._capturing = False
        self._release_overlay()
