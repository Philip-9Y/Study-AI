"""B站学习助手 —— 桌面版入口（对话即 Agent）。

    python app.py           启动
    python app.py --check   自检（热键注册 + 启动退出）

热键：Ctrl+Alt+Q 截图提问 / Ctrl+Alt+A 对话 / Ctrl+Alt+H 主界面 /
      Ctrl+Alt+S 设置 / Ctrl+Alt+X 退出
"""

from __future__ import annotations

import ctypes
import logging
import os
import queue
import sys

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.config import APP_DIR, DATA_DIR, Config
from core.context import ContextWatcher
from core.controller import Controller
from core.conversation import ConversationAgent
from core.hotkey import MOD_ALT, MOD_CONTROL, VK_A, VK_H, VK_Q, VK_S, VK_X, HotkeyManager
from core.memory import MemoryManager
from core.plugins import PluginManager
from core.store import Store
from core.tools import build_default_registry
from ui.main_window import MainWindow
from ui.pet_window import PetWindow
from ui.plugins_dialog import PluginsDialog
from ui.theme import apply_theme, make_icon

LOGGER = logging.getLogger("biliask")
SERVER_NAME = "bili-ask-single-v4"


def setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = logging.FileHandler(DATA_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])


def apply_dark_title_bar(widget) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(0)
        for attribute in (20, 19):
            if (
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
                )
                == 0
            ):
                return
    except Exception:
        pass


def default_pet_position(pet: PetWindow) -> QPoint:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return QPoint(100, 100)
    area = screen.availableGeometry()
    return QPoint(area.right() - pet.width() - 24, area.bottom() - pet.height() - 16)


def main() -> int:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BiliAsk.Luffy.v5")
        except Exception:
            pass
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("B站学习助手")
    app.setQuitOnLastWindowClosed(False)
    setup_logging()
    apply_theme(app)
    icon_file = APP_DIR / "assets" / "luffy_v3.ico"
    if not icon_file.exists():
        icon_file = APP_DIR / "assets" / "luffy_v2.ico"
    if not icon_file.exists():
        icon_file = APP_DIR / "assets" / "luffy.ico"
    icon = QIcon(str(icon_file)) if icon_file.exists() else make_icon()
    app.setWindowIcon(icon)

    check_mode = "--check" in sys.argv

    # ---------------------------------------------------------- 单实例
    probe = QLocalSocket()
    probe.connectToServer(SERVER_NAME)
    if probe.waitForConnected(400):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(400)
        probe.disconnectFromServer()
        return 0
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)

    # ---------------------------------------------------------- 数据与核心
    config = Config()
    store = Store(DATA_DIR)
    store.import_legacy_jsonl(DATA_DIR / "notes.jsonl")

    watcher = ContextWatcher()
    registry = build_default_registry(watcher, store)
    plugin_manager = PluginManager(config, registry)
    plugin_manager.load_all()

    memory = MemoryManager(store, config)
    agent = ConversationAgent(store, config, registry, memory=memory)
    main_window = MainWindow(store, config)
    controller = Controller(
        store, config, main_window, agent, context_watcher=watcher
    )
    pet = PetWindow()

    pet_position = config.data.get("pet_pos")
    if isinstance(pet_position, list) and len(pet_position) == 2:
        try:
            pet.move(int(pet_position[0]), int(pet_position[1]))
        except (TypeError, ValueError):
            pet.move(default_pet_position(pet))
    else:
        pet.move(default_pet_position(pet))

    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("B站学习助手 · 路飞")
    menu = QMenu()
    act_show = menu.addAction("打开主界面")
    act_capture = menu.addAction("截图提问")
    act_pet = menu.addAction("显示桌宠")
    act_pet.setCheckable(True)
    menu.addSeparator()
    act_plugins = menu.addAction("插件管理…")
    act_settings = menu.addAction("设置…")
    menu.addSeparator()
    act_quit = menu.addAction("退出")

    events: queue.Queue = queue.Queue()
    hotkeys = HotkeyManager(
        {
            1: (MOD_CONTROL | MOD_ALT, VK_Q, "Ctrl+Alt+Q"),
            2: (MOD_CONTROL | MOD_ALT, VK_H, "Ctrl+Alt+H"),
            3: (MOD_CONTROL | MOD_ALT, VK_S, "Ctrl+Alt+S"),
            4: (MOD_CONTROL | MOD_ALT, VK_X, "Ctrl+Alt+X"),
            5: (MOD_CONTROL | MOD_ALT, VK_A, "Ctrl+Alt+A"),
        },
        events.put,
    )

    def show_main() -> None:
        main_window.show_and_raise()

    def show_chat() -> None:
        main_window.show_and_raise()
        main_window.show_chat()
        main_window.composer.setFocus()

    def sync_pet_action(enabled: bool) -> None:
        act_pet.blockSignals(True)
        act_pet.setChecked(enabled)
        act_pet.blockSignals(False)

    def set_pet_enabled(enabled: bool, save: bool = True) -> None:
        pet.set_enabled(enabled)
        sync_pet_action(enabled)
        if save:
            config.data["pet_enabled"] = enabled
            config.save()

    def open_plugins() -> None:
        dialog = PluginsDialog(plugin_manager, main_window)
        dialog.exec()

    def quit_app() -> None:
        if getattr(quit_app, "_done", False):
            return
        quit_app._done = True  # type: ignore[attr-defined]
        try:
            config.data["pet_pos"] = [pet.x(), pet.y()]
            config.save()
        except Exception:
            pass
        controller.shutdown()
        watcher.stop()
        hotkeys.stop()
        server.close()
        pet.hide()
        tray.hide()
        store.close()
        app.quit()
        QTimer.singleShot(800, lambda: os._exit(0))

    act_show.triggered.connect(show_main)
    act_capture.triggered.connect(controller.start_capture)
    act_pet.toggled.connect(lambda checked: set_pet_enabled(checked))
    act_plugins.triggered.connect(open_plugins)
    act_settings.triggered.connect(controller.open_settings)
    act_quit.triggered.connect(quit_app)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: show_main() if reason == QSystemTrayIcon.DoubleClick else None
    )
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()

    # ---------------------------------------------------------- 主窗口连接
    main_window.plugins_requested.connect(open_plugins)
    controller.memory_changed.connect(main_window.refresh_memories)

    def on_memory_status(text: str) -> None:
        main_window.set_memory_status(text)
        main_window.set_memory_busy(text.startswith("正在整理"), text)

    controller.memory_status.connect(on_memory_status)

    # ---------------------------------------------------------- 桌宠
    pet.capture_requested.connect(controller.start_capture)
    pet.open_main_requested.connect(show_main)
    pet.settings_requested.connect(controller.open_settings)
    pet.quit_requested.connect(quit_app)

    def on_pet_hidden() -> None:
        set_pet_enabled(False)
        if tray.isVisible():
            tray.showMessage(
                "桌宠已隐藏",
                "可在托盘菜单勾选「显示桌宠」重新打开",
                QSystemTrayIcon.Information,
                2500,
            )

    pet.hidden_requested.connect(on_pet_hidden)

    pet_position_timer = QTimer()
    pet_position_timer.setSingleShot(True)
    pet_position_timer.setInterval(500)
    pending_position = {"value": None}

    def save_pet_position() -> None:
        position = pending_position["value"] or pet.pos()
        config.data["pet_pos"] = [position.x(), position.y()]
        config.save()

    pet_position_timer.timeout.connect(save_pet_position)

    def on_pet_moved(position: QPoint) -> None:
        pending_position["value"] = position
        pet_position_timer.start()

    pet.moved.connect(on_pet_moved)
    controller.capture_started.connect(pet.hide_pet)

    def on_capture_finished() -> None:
        if config.data.get("pet_enabled", True):
            pet.show_pet()

    controller.capture_finished.connect(on_capture_finished)
    controller.answer_started.connect(lambda _sid: pet.set_state("thinking"))
    controller.answer_finished.connect(lambda _sid: pet.set_state("done", "回答好啦 · 点我看"))
    controller.answer_failed.connect(
        lambda _sid, _message: pet.set_state("error", "出错了 · 点我看")
    )

    def on_settings_changed() -> None:
        enabled = bool(config.data.get("pet_enabled", True))
        pet.set_enabled(enabled)
        sync_pet_action(enabled)

    controller.settings_changed.connect(on_settings_changed)

    pet_enabled = bool(config.data.get("pet_enabled", True))
    if check_mode:
        pet.set_enabled(False)
    else:
        set_pet_enabled(pet_enabled, save=False)

    # 把主窗口放到主屏中央，避免系统恢复到一个已经离开屏幕的位置
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        main_window.move(
            area.left() + (area.width() - main_window.width()) // 2,
            area.top() + (area.height() - main_window.height()) // 2,
        )

    def toast(message: str) -> None:
        LOGGER.info("提示: %s", message)
        if tray.isVisible():
            tray.showMessage("B站学习助手", message, QSystemTrayIcon.Information, 2600)

    controller.toast.connect(toast)

    balloon_shown = {"value": False}

    def on_hidden_to_tray() -> None:
        if not balloon_shown["value"]:
            balloon_shown["value"] = True
            tray.showMessage(
                "仍在后台运行",
                "双击桌宠截图提问 · Ctrl+Alt+H 打开主界面 · Ctrl+Alt+A 对话",
                QSystemTrayIcon.Information,
                3000,
            )

    main_window.hidden_to_tray.connect(on_hidden_to_tray)

    # ---------------------------------------------------------- 单实例唤醒
    def on_new_connection() -> None:
        connection = server.nextPendingConnection()
        if connection is None:
            return

        def handle() -> None:
            try:
                data = bytes(connection.readAll())
            except Exception:
                data = b""
            if b"show" in data:
                show_main()

        connection.readyRead.connect(handle)

    server.newConnection.connect(on_new_connection)

    # ---------------------------------------------------------- 热键
    def poll_hotkeys() -> None:
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "hotkey":
                action = event[1]
                if action == 1:
                    controller.start_capture()
                elif action == 2:
                    show_main()
                elif action == 3:
                    controller.open_settings()
                elif action == 4:
                    quit_app()
                elif action == 5:
                    show_chat()
            elif kind == "hotkeys_ready":
                LOGGER.info("全局热键注册成功")
                if check_mode:
                    print("HOTKEY_OK", flush=True)
            elif kind == "hotkey_error":
                name = event[1] if len(event) > 1 else "热键"
                LOGGER.error("热键注册失败: %s", name)
                if check_mode:
                    print("HOTKEY_FAIL", flush=True)
                elif tray.isVisible():
                    tray.showMessage(
                        "热键被占用",
                        f"{name} 被其他程序占用，可用托盘菜单或主界面按钮。",
                        QSystemTrayIcon.Warning,
                        5000,
                    )

    poll_timer = QTimer()
    poll_timer.timeout.connect(poll_hotkeys)
    poll_timer.start(80)
    hotkeys.start()

    if check_mode:
        QTimer.singleShot(1600, quit_app)
        LOGGER.info("自检模式启动")
    else:
        main_window.show_and_raise()
        QTimer.singleShot(120, lambda: apply_dark_title_bar(main_window))
        LOGGER.info("启动完成")
        if not config.api_key:
            QTimer.singleShot(600, controller.open_settings)

    code = app.exec()
    try:
        poll_timer.stop()
    except Exception:
        pass
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
