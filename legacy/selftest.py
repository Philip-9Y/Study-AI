"""自检脚本。

用法：
    python selftest.py capture   # 验证截图
    python selftest.py ui        # 验证 Tk 窗口能正常创建
    python selftest.py api       # 验证 API Key 与视觉接口（会发一张合成测试图）
    python selftest.py all       # 依次执行
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402


def enable_dpi_awareness() -> None:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def test_capture() -> bool:
    from PIL import ImageGrab

    enable_dpi_awareness()
    img = ImageGrab.grab(all_screens=False)
    gray = img.convert("L")
    extrema = gray.getextrema()
    print(f"[capture] OK size={img.size} mode={img.mode} 亮度范围={extrema}")
    if extrema[1] - extrema[0] < 8:
        print("[capture] 警告：截图几乎纯色，可能是受保护画面/黑屏")
    return True


def test_ui() -> bool:
    import tkinter as tk

    root = tk.Tk()
    root.title("selftest")
    tk.Label(root, text="UI OK", font=("Microsoft YaHei UI", 16)).pack(padx=40, pady=30)
    root.after(700, root.destroy)
    root.mainloop()
    print("[ui] OK")
    return True


def make_test_image() -> Image.Image:
    img = Image.new("RGB", (720, 260), "white")
    draw = ImageDraw.Draw(img)
    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    font = ImageFont.truetype(str(font_path), 26) if font_path.exists() else ImageFont.load_default()
    draw.text((30, 30), "测试画面：质能方程 E = m c²", fill="black", font=font)
    draw.text((30, 90), "光速 c ≈ 3 × 10⁸ m/s", fill="black", font=font)
    draw.text((30, 150), "勾股定理 a² + b² = c²", fill="black", font=font)
    draw.rectangle((30, 200, 690, 230), outline="red", width=3)
    return img


def test_api() -> int:
    import requests

    from config import Config
    from llm import DeepSeekClient, encode_image, image_content_block

    try:
        resp = requests.get("https://api.deepseek.com", timeout=15)
        print(f"[net] api.deepseek.com 可达 (HTTP {resp.status_code})")
    except requests.RequestException as exc:
        print(f"[net] FAIL 无法访问 api.deepseek.com: {exc}")
        return 1

    cfg = Config()
    if not cfg.api_key:
        print("[api] SKIP：未配置 DEEPSEEK_API_KEY 或 config.json 里的 api_key")
        return 2

    img = make_test_image()
    out_dir = APP_DIR / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "selftest.png"
    img.save(out_path)
    print(f"[api] 测试图已保存: {out_path}")

    client = DeepSeekClient(api_key=cfg.api_key, base_url=cfg.base_url, model=cfg.model)
    messages = [
        {"role": "system", "content": "简洁回答，不要展开。"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "图片里有哪些文字？请逐行复述。"},
                image_content_block(encode_image(img)),
            ],
        },
    ]
    try:
        answer = client.chat(messages)
    except Exception as exc:
        print(f"[api] FAIL: {exc}")
        return 1
    print("[api] OK，模型回答：")
    print(answer)
    return 0


def test_gui() -> bool:
    """模拟一次完整交互：唤起框选 → 拖拽 → 弹出提问窗（不发请求）。"""
    import tkinter as tk

    from app import LearningAssistant, enable_dpi_awareness

    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    app = LearningAssistant(root, check_mode=True)
    result = {"selector": False, "dialog": False}

    def verify_selector() -> None:
        overlay = app.selector
        result["selector"] = bool(overlay is not None and overlay.winfo_exists())
        if not result["selector"]:
            root.after(100, finish)
            return
        canvas = overlay.winfo_children()[0]
        canvas.event_generate("<ButtonPress-1>", x=80, y=80)
        canvas.event_generate("<B1-Motion>", x=520, y=400)
        canvas.event_generate("<ButtonRelease-1>", x=520, y=400)
        root.after(400, verify_dialog)

    def verify_dialog() -> None:
        for child in root.winfo_children():
            if isinstance(child, tk.Toplevel) and child.title() == "提问":
                result["dialog"] = True
                child.destroy()
                break
        app.busy = False
        root.after(100, finish)

    def finish() -> None:
        app.shutdown()

    root.after(300, app.begin_capture)
    root.after(1500, verify_selector)
    app.run()
    print(f"[gui] 框选层={result['selector']} 提问窗={result['dialog']}")
    return result["selector"] and result["dialog"]


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    ok = True
    if what in ("all", "capture"):
        ok = test_capture() and ok
    if what in ("all", "ui"):
        ok = test_ui() and ok
    if what in ("all", "gui"):
        ok = test_gui() and ok
    if what in ("all", "api"):
        rc = test_api()
        if rc == 1:
            ok = False
    print("SELFTEST_RESULT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
