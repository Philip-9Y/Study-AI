"""B站学习助手 —— 框选屏幕上的内容，直接向 AI 提问。

用法：
    python app.py

热键：
    Ctrl+Alt+Q  截图提问
    Ctrl+Alt+S  设置 API Key
    Ctrl+Alt+X  退出

首次运行会弹出设置窗口，粘贴 DeepSeek API Key 即可。
"""

from __future__ import annotations

import ctypes
import logging
import queue
import sys
import threading
import time
import uuid
from datetime import datetime

import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageEnhance, ImageGrab, ImageTk

from config import APP_DIR, DATA_DIR, Config
from hotkey import MOD_ALT, MOD_CONTROL, VK_Q, VK_S, VK_X, HotkeyManager
from llm import DeepSeekClient, encode_image, messages_with_image
from store import Store

LOGGER = logging.getLogger("biliask")

HOTKEY_CAPTURE = 1
HOTKEY_QUIT = 2
HOTKEY_SETTINGS = 3

APP_TITLE = "B站学习助手"


def enable_dpi_awareness() -> None:
    """必须在创建 Tk / 截图之前调用，保证坐标与物理像素一致。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = logging.FileHandler(DATA_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])


class LearningAssistant:
    def __init__(self, root: tk.Tk, check_mode: bool = False) -> None:
        self.root = root
        self.check_mode = check_mode
        self.cfg = Config()
        self.store = Store(DATA_DIR)

        self.events: queue.Queue = queue.Queue()
        self.stop = False
        self.busy = False

        self.screenshot: Image.Image | None = None
        self.selector: tk.Toplevel | None = None
        self.settings_win: tk.Toplevel | None = None
        self.toast_win: tk.Toplevel | None = None
        self.sessions: dict[str, dict] = {}

        self.hotkeys = HotkeyManager(
            {
                HOTKEY_CAPTURE: (MOD_CONTROL | MOD_ALT, VK_Q, "Ctrl+Alt+Q"),
                HOTKEY_SETTINGS: (MOD_CONTROL | MOD_ALT, VK_S, "Ctrl+Alt+S"),
                HOTKEY_QUIT: (MOD_CONTROL | MOD_ALT, VK_X, "Ctrl+Alt+X"),
            },
            self.events.put,
        )
        self.hotkeys.start()

    # ------------------------------------------------------------------ 主循环
    def run(self) -> None:
        self.root.after(60, self._poll)
        if not self.check_mode:
            self.root.after(350, self._startup_toast)
            self.root.after(900, self._ensure_key)
        self.root.mainloop()

    def _poll(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            try:
                self._handle_event(event)
            except Exception:
                LOGGER.exception("处理事件失败: %r", event)
        if not self.stop:
            self.root.after(60, self._poll)

    def _handle_event(self, event) -> None:
        kind = event[0]
        if kind == "hotkeys_ready":
            LOGGER.info("全局热键注册成功")
            if self.check_mode:
                print("HOTKEY_OK", flush=True)
        elif kind == "hotkey_error":
            name = event[1] if len(event) > 1 else "热键"
            LOGGER.error("热键注册失败: %s (err=%s)", name, event[2] if len(event) > 2 else "?")
            if self.check_mode:
                print("HOTKEY_FAIL", flush=True)
                return
            messagebox.showerror(
                "热键冲突",
                f"{name} 已被其他程序占用，无法启动。\n请关闭占用该热键的程序后重试。",
                parent=self.root,
            )
            self.shutdown()
        elif kind == "hotkey":
            action = int(event[1])
            if action == HOTKEY_CAPTURE:
                self.begin_capture()
            elif action == HOTKEY_SETTINGS:
                self.open_settings()
            elif action == HOTKEY_QUIT:
                self.shutdown()
        elif kind == "delta":
            self._on_delta(event[1], event[2])
        elif kind == "done":
            self._on_done(event[1])
        elif kind == "error":
            self._on_error(event[1], event[2])

    def shutdown(self) -> None:
        if self.stop:
            return
        self.stop = True
        LOGGER.info("正在退出…")
        if self.hotkeys.is_alive():
            self.hotkeys.stop()
        for session in self.sessions.values():
            session["stop"].set()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def _startup_toast(self) -> None:
        self.toast("已启动 · Ctrl+Alt+Q 截图提问 · Ctrl+Alt+S 设置 · Ctrl+Alt+X 退出", 4200)

    def _ensure_key(self) -> None:
        if not self.cfg.api_key:
            self.open_settings()

    # ------------------------------------------------------------------ 截图与框选
    def begin_capture(self) -> None:
        if self.stop or self.busy or self.selector is not None:
            return
        self.busy = True
        self.root.after(10, self._capture)

    def _capture(self) -> None:
        try:
            img = ImageGrab.grab(all_screens=False)
        except Exception as exc:
            self.busy = False
            LOGGER.exception("截屏失败")
            messagebox.showerror("截屏失败", str(exc), parent=self.root)
            return
        self.screenshot = img
        self._show_selector(img)

    def _show_selector(self, img: Image.Image) -> None:
        sw, sh = img.size
        overlay = tk.Toplevel(self.root)
        overlay.withdraw()
        overlay.overrideredirect(True)
        overlay.geometry(f"{sw}x{sh}+0+0")
        overlay.attributes("-topmost", True)
        try:
            overlay.attributes("-alpha", 0.96)
        except tk.TclError:
            pass

        canvas = tk.Canvas(overlay, width=sw, height=sh, bd=0, highlightthickness=0, cursor="crosshair")
        canvas.pack(fill="both", expand=True)

        dimmed = ImageEnhance.Brightness(img).enhance(0.55)
        photo = ImageTk.PhotoImage(dimmed)
        canvas.image = photo  # 防止被回收
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas.create_text(
            sw // 2,
            42,
            text="拖拽框选要提问的画面      Esc 取消",
            fill="#ffffff",
            font=("Microsoft YaHei UI", 15, "bold"),
        )

        state = {"x0": 0, "y0": 0, "rect": None, "size": None}

        def on_press(event) -> None:
            state["x0"], state["y0"] = event.x, event.y
            if state["rect"]:
                canvas.delete(state["rect"])
            state["rect"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y, outline="#ff4d4f", width=2
            )
            if state["size"]:
                canvas.delete(state["size"])
                state["size"] = None

        def on_drag(event) -> None:
            if not state["rect"]:
                return
            x0, y0 = state["x0"], state["y0"]
            canvas.coords(state["rect"], x0, y0, event.x, event.y)
            if state["size"]:
                canvas.delete(state["size"])
            state["size"] = canvas.create_text(
                min(x0, event.x) + 6,
                min(y0, event.y) - 6,
                anchor="sw",
                text=f"{abs(event.x - x0)} × {abs(event.y - y0)}",
                fill="#ffd666",
                font=("Microsoft YaHei UI", 10),
            )

        def on_release(event) -> None:
            if not state["rect"]:
                return
            x0, y0 = state["x0"], state["y0"]
            left, top = min(x0, event.x), min(y0, event.y)
            right, bottom = max(x0, event.x), max(y0, event.y)
            self._close_selector()
            if right - left < 12 or bottom - top < 12:
                self.busy = False
                self.toast("框选区域太小，请重试")
                return
            self._open_question_dialog((left, top, right, bottom))

        def cancel(_event=None) -> None:
            self._close_selector()
            self.busy = False

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", cancel)
        overlay.bind("<ButtonPress-3>", cancel)

        self.selector = overlay
        overlay.deiconify()
        overlay.focus_force()
        canvas.focus_set()

    def _close_selector(self) -> None:
        if self.selector is not None:
            try:
                self.selector.destroy()
            except Exception:
                pass
            self.selector = None

    # ------------------------------------------------------------------ 提问
    def _open_question_dialog(self, bbox: tuple[int, int, int, int]) -> None:
        assert self.screenshot is not None
        crop = self.screenshot.crop(bbox)
        dialog = tk.Toplevel(self.root)
        dialog.title("提问")
        dialog.attributes("-topmost", True)
        dialog.configure(bg="#202020")
        dialog.resizable(False, False)

        thumb = crop.copy()
        thumb.thumbnail((280, 170))
        tphoto = ImageTk.PhotoImage(thumb)
        preview = tk.Label(dialog, image=tphoto, bg="#202020")
        preview.image = tphoto
        preview.pack(padx=12, pady=(12, 6))

        tk.Label(
            dialog,
            text="输入问题（留空则让它讲解画面）",
            bg="#202020",
            fg="#bdbdbd",
            font=("Microsoft YaHei UI", 9),
        ).pack()

        var = tk.StringVar()
        entry = tk.Entry(
            dialog,
            textvariable=var,
            width=44,
            font=("Microsoft YaHei UI", 11),
            bg="#2d2d2d",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
        )
        entry.pack(padx=12, pady=8, ipady=5)

        row = tk.Frame(dialog, bg="#202020")
        row.pack(padx=12, pady=(0, 12), fill="x")

        def submit(_event=None) -> None:
            question = var.get().strip() or "请讲解一下当前画面里的内容。"
            dialog.destroy()
            self._submit_question(question, crop)

        def cancel(_event=None) -> None:
            dialog.destroy()
            self.busy = False

        tk.Button(
            row,
            text="发送 (Enter)",
            command=submit,
            bg="#3b82f6",
            fg="white",
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=5,
        ).pack(side="right")
        tk.Button(
            row,
            text="取消",
            command=cancel,
            bg="#3a3a3a",
            fg="#dddddd",
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=5,
        ).pack(side="right", padx=(0, 8))

        entry.bind("<Return>", submit)
        dialog.bind("<Escape>", cancel)

        dialog.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        x = max(0, min(bbox[0], sw - w))
        y = bbox[3] + 10
        if y + h > sh:
            y = max(0, bbox[1] - h - 10)
        dialog.geometry(f"+{x}+{y}")
        entry.focus_set()

    def _submit_question(self, question: str, crop: Image.Image) -> None:
        self.busy = False
        if not self.cfg.api_key:
            self.open_settings()
            self.toast("请先填写 API Key，然后重新截图")
            return
        when = datetime.now()
        image_rel = (
            self.store.save_capture(crop, when) if self.cfg.data.get("save_captures", True) else None
        )
        try:
            img_b64 = encode_image(crop)
        except Exception as exc:
            LOGGER.exception("图片编码失败")
            messagebox.showerror("图片编码失败", str(exc), parent=self.root)
            return

        sid = uuid.uuid4().hex[:8]
        session = {
            "id": sid,
            "turn": 1,
            "question": question,
            "answer": "",
            "messages": messages_with_image(question, img_b64),
            "image": image_rel,
            "started": time.time(),
            "closed": False,
            "finished": False,
            "streaming": True,
            "stop": threading.Event(),
            "win": None,
            "text": None,
            "footer": None,
            "entry": None,
            "send_btn": None,
        }
        self.sessions[sid] = session
        self._open_answer_window(sid)
        self._start_worker(sid)

    # ------------------------------------------------------------------ 回答窗口
    def _open_answer_window(self, sid: str) -> None:
        session = self.sessions[sid]
        win = tk.Toplevel(self.root)
        win.title(APP_TITLE)
        win.attributes("-topmost", True)
        win.configure(bg="#1e1e1e")
        win.minsize(480, 340)

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = 680, 560
        x = max(0, sw - width - 24)
        y = max(0, min(70, sh - height - 40))
        win.geometry(f"{width}x{height}+{x}+{y}")

        header = tk.Frame(win, bg="#1e1e1e")
        header.pack(fill="x", padx=14, pady=(12, 0))
        head_text = session["question"]
        if len(head_text) > 60:
            head_text = head_text[:60] + "…"
        tk.Label(
            header,
            text="问：" + head_text,
            bg="#1e1e1e",
            fg="#ffffff",
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
            justify="left",
            wraplength=560,
        ).pack(side="left", fill="x", expand=True)

        def copy_answer() -> None:
            content = session["text"].get("1.0", "end-1c") if session.get("text") else ""
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.toast("已复制回答")

        tk.Button(
            header,
            text="复制",
            command=copy_answer,
            bg="#333333",
            fg="#dddddd",
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=2,
        ).pack(side="right", padx=(6, 0))

        body = tk.Frame(win, bg="#1e1e1e")
        body.pack(fill="both", expand=True, padx=14, pady=8)

        text = tk.Text(
            body,
            wrap="word",
            bg="#1e1e1e",
            fg="#e9e9e9",
            insertbackground="#e9e9e9",
            relief="flat",
            padx=4,
            pady=2,
            font=("Microsoft YaHei UI", 11),
            spacing1=2,
            spacing3=4,
        )
        text.tag_configure("err", foreground="#ff6b6b")
        text.tag_configure("q", foreground="#7fb3ff", font=("Microsoft YaHei UI", 11, "bold"))
        scroll = tk.Scrollbar(body, command=text.yview, width=12)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.configure(state="disabled")

        footer = tk.Label(
            win,
            text="思考中…",
            bg="#1e1e1e",
            fg="#8f8f8f",
            anchor="w",
            font=("Microsoft YaHei UI", 9),
        )
        footer.pack(fill="x", padx=14)

        row = tk.Frame(win, bg="#1e1e1e")
        row.pack(fill="x", padx=14, pady=(4, 12))
        var = tk.StringVar()
        entry = tk.Entry(
            row,
            textvariable=var,
            bg="#2a2a2a",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Microsoft YaHei UI", 11),
        )
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        send_btn = tk.Button(
            row,
            text="追问",
            bg="#3b82f6",
            fg="white",
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=4,
        )
        send_btn.pack(side="left", padx=(8, 0))

        def close(_event=None) -> None:
            session["closed"] = True
            session["stop"].set()
            try:
                win.destroy()
            except Exception:
                pass

        def follow(_event=None) -> None:
            question = var.get().strip()
            if not question or session.get("streaming"):
                return
            var.set("")
            self._ask_followup(sid, question)

        send_btn.configure(command=follow)
        entry.bind("<Return>", follow)
        win.bind("<Escape>", close)
        win.protocol("WM_DELETE_WINDOW", close)

        session.update(
            {"win": win, "text": text, "footer": footer, "entry": entry, "send_btn": send_btn}
        )

    def _append_text(self, session: dict, chunk: str, tag: str | None = None) -> None:
        text = session.get("text")
        if not text:
            return
        try:
            if not text.winfo_exists():
                return
            text.configure(state="normal")
            text.insert("end", chunk, tag)
            text.see("end")
            text.configure(state="disabled")
        except tk.TclError:
            pass

    def _ask_followup(self, sid: str, question: str) -> None:
        session = self.sessions[sid]
        session["turn"] += 1
        session["question"] = question
        session["answer"] = ""
        session["started"] = time.time()
        session["streaming"] = True
        session["messages"].append({"role": "user", "content": question})
        self._append_text(session, f"\n\n追问：{question}\n\n", tag="q")
        try:
            session["footer"].configure(text="思考中…")
            session["entry"].configure(state="disabled")
            session["send_btn"].configure(state="disabled")
        except tk.TclError:
            pass
        self._start_worker(sid)

    # ------------------------------------------------------------------ 模型调用
    def _start_worker(self, sid: str) -> None:
        session = self.sessions[sid]
        client = DeepSeekClient(
            api_key=self.cfg.api_key,
            base_url=self.cfg.base_url,
            model=self.cfg.model,
            max_tokens=int(self.cfg.data.get("max_tokens", 1500)),
            temperature=float(self.cfg.data.get("temperature", 0.6)),
        )

        def run() -> None:
            try:
                client.stream_chat(
                    session["messages"],
                    lambda chunk: self.events.put(("delta", sid, chunk)),
                    session["stop"],
                )
                self.events.put(("done", sid))
            except Exception as exc:
                LOGGER.exception("模型请求失败")
                self.events.put(("error", sid, str(exc)))

        threading.Thread(target=run, daemon=True, name=f"llm-{sid}").start()

    def _on_delta(self, sid: str, chunk: str) -> None:
        session = self.sessions.get(sid)
        if not session or session["closed"]:
            return
        session["answer"] += chunk
        self._append_text(session, chunk)

    def _on_done(self, sid: str) -> None:
        session = self.sessions.get(sid)
        if not session:
            return
        session["streaming"] = False
        session["finished"] = True
        elapsed = time.time() - session["started"]

        if not session["closed"]:
            try:
                session["footer"].configure(text=f"用时 {elapsed:.1f}s · 已自动保存到笔记")
                session["entry"].configure(state="normal")
                session["send_btn"].configure(state="normal")
                session["entry"].focus_set()
            except tk.TclError:
                pass

        answer = session["answer"].strip()
        if not answer:
            return
        session["messages"].append({"role": "assistant", "content": answer})
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "session": sid,
            "turn": session["turn"],
            "image": session["image"] if session["turn"] == 1 else None,
            "question": session["question"],
            "answer": answer,
            "model": self.cfg.model,
            "elapsed_s": round(elapsed, 2),
            "interrupted": session["closed"],
        }
        try:
            self.store.append(record, datetime.now())
        except Exception:
            LOGGER.exception("保存笔记失败")

    def _on_error(self, sid: str, message: str) -> None:
        session = self.sessions.get(sid)
        if not session:
            return
        session["streaming"] = False
        LOGGER.error("API 错误: %s", message)
        if session["closed"]:
            return
        self._append_text(session, f"\n\n⚠️ 请求失败：{message}", tag="err")
        try:
            session["footer"].configure(text="请求失败，可重试")
            session["entry"].configure(state="normal")
            session["send_btn"].configure(state="normal")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ 设置
    def open_settings(self) -> None:
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.lift()
            self.settings_win.focus_force()
            return
        win = tk.Toplevel(self.root)
        win.title("设置 DeepSeek API Key")
        win.attributes("-topmost", True)
        win.configure(bg="#202020")
        win.resizable(False, False)

        tk.Label(
            win,
            text="需要 DeepSeek API Key 才能让 AI 看截图答题。",
            bg="#202020",
            fg="#ffffff",
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(
            win,
            text="① 打开 platform.deepseek.com → API Keys 创建\n"
            "② 粘贴到下面（也可设置环境变量 DEEPSEEK_API_KEY）",
            bg="#202020",
            fg="#bdbdbd",
            justify="left",
            anchor="w",
            font=("Microsoft YaHei UI", 9),
        ).pack(fill="x", padx=16)

        var = tk.StringVar(value=str(self.cfg.data.get("api_key", "")))
        entry = tk.Entry(
            win,
            textvariable=var,
            width=54,
            show="*",
            bg="#2d2d2d",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Consolas", 10),
        )
        entry.pack(padx=16, pady=10, ipady=5)

        row = tk.Frame(win, bg="#202020")
        row.pack(fill="x", padx=16, pady=(0, 14))

        def save() -> None:
            key = var.get().strip()
            if not key:
                messagebox.showwarning("提示", "API Key 不能为空", parent=win)
                return
            self.cfg.data["api_key"] = key
            self.cfg.save()
            win.destroy()
            self.toast("API Key 已保存，按 Ctrl+Alt+Q 开始")

        tk.Button(
            row,
            text="保存",
            command=save,
            bg="#3b82f6",
            fg="white",
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=5,
        ).pack(side="right")
        tk.Button(
            row,
            text="稍后",
            command=win.destroy,
            bg="#3a3a3a",
            fg="#dddddd",
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=5,
        ).pack(side="right", padx=(0, 8))

        win.bind("<Escape>", lambda _event: win.destroy())
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")
        entry.focus_set()
        self.settings_win = win

    # ------------------------------------------------------------------ 提示条
    def toast(self, text: str, milliseconds: int = 2800) -> None:
        try:
            if self.toast_win is not None and self.toast_win.winfo_exists():
                self.toast_win.destroy()
            tip = tk.Toplevel(self.root)
            tip.overrideredirect(True)
            tip.attributes("-topmost", True)
            tip.configure(bg="#111111")
            tk.Label(
                tip,
                text=text,
                bg="#111111",
                fg="#f0f0f0",
                padx=16,
                pady=8,
                font=("Microsoft YaHei UI", 10),
            ).pack()
            tip.update_idletasks()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            w, h = tip.winfo_reqwidth(), tip.winfo_reqheight()
            tip.geometry(f"+{sw - w - 24}+{sh - h - 64}")
            self.toast_win = tip
            tip.after(milliseconds, tip.destroy)
        except tk.TclError:
            pass


def main() -> None:
    check_mode = "--check" in sys.argv
    enable_dpi_awareness()
    setup_logging()

    root = tk.Tk()
    root.withdraw()
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        pass

    app = LearningAssistant(root, check_mode=check_mode)
    if check_mode:
        root.after(2000, app.shutdown)

    LOGGER.info("启动完成，等待热键…")
    app.run()
    LOGGER.info("程序已退出")


if __name__ == "__main__":
    main()
