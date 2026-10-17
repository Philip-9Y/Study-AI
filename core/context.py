"""前台窗口 / 视频上下文识别。

不依赖浏览器插件：读取前台窗口标题与进程名，识别 B 站视频标题；
B 站链接或 BV 号可以通过工具进一步查询（网络可用时）。
"""

from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)

_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextLengthW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetClassNameW.restype = ctypes.c_int
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

_BROWSER_SUFFIXES = [
    " - Google Chrome",
    " — Google Chrome",
    " - Microsoft Edge",
    " — Microsoft Edge",
    " - Mozilla Firefox",
    " — Mozilla Firefox",
    " - Brave",
    " - Opera",
    " - Vivaldi",
    " - 360安全浏览器",
    " - 360极速浏览器",
]

_BILI_MARKERS = [
    "_哔哩哔哩_bilibili",
    "-哔哩哔哩_bilibili",
    "哔哩哔哩_bilibili",
    "_bilibili",
    "-bilibili",
    " - 哔哩哔哩",
]

_BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")


@dataclass
class ScreenContext:
    window_title: str = ""
    process_name: str = ""
    class_name: str = ""
    video_title: str = ""
    is_bilibili: bool = False
    pid: int = 0
    extra: dict = field(default_factory=dict)

    def prompt_text(self) -> str:
        if not self.window_title and not self.video_title:
            return ""
        lines = []
        if self.window_title:
            lines.append(f"前台窗口：{self.window_title}")
        if self.process_name:
            lines.append(f"进程：{self.process_name}")
        if self.video_title:
            lines.append(f"识别到的视频：{self.video_title}（哔哩哔哩）")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "window_title": self.window_title,
            "process_name": self.process_name,
            "class_name": self.class_name,
            "video_title": self.video_title,
            "is_bilibili": self.is_bilibili,
            "pid": self.pid,
        }


def _process_name(pid: int) -> str:
    if not pid:
        return ""
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(len(buffer))
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return os.path.basename(buffer.value)
    finally:
        _kernel32.CloseHandle(handle)
    return ""


def get_foreground_context() -> ScreenContext:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return ScreenContext()
    length = _user32.GetWindowTextLengthW(hwnd)
    title_buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, title_buffer, length + 1)
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    class_buffer = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, class_buffer, 256)
    context = ScreenContext(
        window_title=title_buffer.value.strip(),
        process_name=_process_name(pid.value),
        class_name=class_buffer.value,
        pid=pid.value,
    )
    _fill_video(context)
    return context


def _fill_video(context: ScreenContext) -> None:
    title = context.window_title
    lower = title.lower()
    context.is_bilibili = "bilibili" in lower or "哔哩哔哩" in title
    if not context.is_bilibili:
        return
    cleaned = title
    for suffix in _BROWSER_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    for marker in _BILI_MARKERS:
        cleaned = cleaned.replace(marker, "")
    cleaned = cleaned.strip(" -_|·")
    context.video_title = cleaned


def parse_bvid(text: str) -> str:
    match = _BVID_RE.search(text or "")
    return match.group(0) if match else ""


class ContextWatcher(QObject):
    """记录“最后一个不属于本程序的前台窗口”，避免桌宠/主窗口抢焦点后丢失视频上下文。"""

    def __init__(self, interval_ms: int = 1200, parent=None) -> None:
        super().__init__(parent)
        self._last_foreign: ScreenContext | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        context = get_foreground_context()
        if context.pid and context.pid != os.getpid() and context.window_title:
            self._last_foreign = context

    def best(self) -> ScreenContext:
        current = get_foreground_context()
        if current.window_title and current.pid not in (0, os.getpid()):
            return current
        if self._last_foreign is not None:
            return self._last_foreign
        # 当前前台是本程序且没有历史外部窗口：不要把自己的窗口当成视频上下文
        return ScreenContext()

    def stop(self) -> None:
        self._timer.stop()
