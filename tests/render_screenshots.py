"""生成文档/演示用的界面截图（不弹窗、不抢焦点）。

    python tests/render_screenshots.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from core.config import Config  # noqa: E402
from core.store import Store  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.pet_art import render_pet  # noqa: E402
from ui.theme import apply_theme  # noqa: E402

ASSETS = ROOT / "assets"

ANSWER_SAMPLE = r"""## 结论
递归式 $T(n)=4T(n/2)+n$ 的时间复杂度是 $\Theta(n^2)$。

用代入法证明：

$$T(n) = 4T(n/2) + n \leq c n^2$$

推导步骤：
1. 假设对所有 $k<n$ 有 $T(k)\leq c k^2$
2. 代入得 $T(n) \leq 4c(n/2)^2 + n = c n^2 + n$
3. 取足够大的 $c$，即可吸收低阶项

```python
def cost(n):
    if n <= 1:
        return 1
    return 4 * cost(n // 2) + n
```

> 易错点：不要把 $n/2$ 的平方写成 $n/2$。
"""

STEPS = [
    {"type": "tool_call", "name": "get_screen_context", "args": {}},
    {
        "type": "tool_result",
        "name": "get_screen_context",
        "ok": True,
        "summary": "前台窗口：递归树_哔哩哔哩_bilibili - Google Chrome；视频：递归树",
    },
    {"type": "tool_call", "name": "create_note", "args": {"title": "递归树复杂度", "content": "..."}},
    {
        "type": "tool_result",
        "name": "create_note",
        "ok": True,
        "summary": "笔记已保存（id=7f3a…）：递归树复杂度",
    },
]


def _new_window(store: Store, config: Config) -> MainWindow:
    window = MainWindow(store, config)
    window.setAttribute(Qt.WA_DontShowOnScreen, True)
    window.resize(1240, 820)
    window.show()
    QApplication.instance().processEvents()
    return window


def render_welcome(store: Store, config: Config, path: Path) -> None:
    window = _new_window(store, config)
    window.grab().save(str(path))
    window.hide()
    window.deleteLater()
    print("saved", path)


def render_chat(store: Store, config: Config, path: Path) -> None:
    sid = store.create_session(
        "递归树复杂度怎么证明？",
        None,
        config.model,
        context="前台窗口：递归树_哔哩哔哩_bilibili - Google Chrome；视频：递归树",
    )
    store.add_message(sid, "user", "递归树复杂度怎么证明？")
    store.add_message(
        sid,
        "assistant",
        ANSWER_SAMPLE,
        elapsed_s=6.4,
        meta=json.dumps({"steps": STEPS}, ensure_ascii=False),
    )
    window = _new_window(store, config)
    window.open_session(sid)
    QApplication.instance().processEvents()
    window.grab().save(str(path))
    window.hide()
    window.deleteLater()
    print("saved", path)


def render_notes(store: Store, config: Config, path: Path) -> None:
    first = store.add_note(
        "递归树复杂度",
        "主定理：T(n)=aT(n/b)+f(n)，比较 f(n) 与 n^(log_b a) 的阶。\n\n"
        "递归树每层代价求和，猜界后用代入法验证。",
        "算法,递归树",
    )
    store.add_note(
        "实验报告写作清单",
        "1. 截图统一编号\n2. 图注写在图下方\n3. 代码块用等宽字体",
        "实验报告",
    )
    window = _new_window(store, config)
    window.show_notes(first)
    QApplication.instance().processEvents()
    window.grab().save(str(path))
    window.hide()
    window.deleteLater()
    print("saved", path)


def render_memory(store: Store, config: Config, path: Path) -> None:
    store.add_memory("用户遇到算法写法时会追问“为什么要这样”，需要解释原理", "偏好,讲解方式")
    store.add_memory("递归树按层展开、逐层求和后猜界，再用代入法验证", "知识点,算法")
    window = _new_window(store, config)
    window.show_memory()
    QApplication.instance().processEvents()
    window.grab().save(str(path))
    window.hide()
    window.deleteLater()
    print("saved", path)


def render_pet_asset(path: Path) -> None:
    width, height = 240, 280
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor("#ffffff"))
    gradient.setColorAt(1.0, QColor("#eef4ff"))
    painter.setBrush(gradient)
    painter.setPen(QColor("#e3e7ef"))
    painter.drawRoundedRect(0, 0, width - 1, height - 1, 24, 24)
    painter.drawPixmap(35, 55, render_pet(170))
    painter.end()
    pixmap.save(str(path))
    print("saved", path)


def main() -> int:
    app = QApplication([])
    apply_theme(app)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        store = Store(root / "data")
        config = Config(path=root / "config.json")
        config.data["api_key"] = "sk-demo"
        config.data["model"] = "deepseek-flash"
        render_welcome(store, config, ASSETS / "screenshot_main.png")
        render_chat(store, config, ASSETS / "screenshot_chat.png")
        render_notes(store, config, ASSETS / "screenshot_notes.png")
        render_memory(store, config, ASSETS / "screenshot_memory.png")
        store.close()

    render_pet_asset(ASSETS / "screenshot_pet.png")
    for leftover in ("screenshot_answer.png", "screenshot_agent.png"):
        old = ASSETS / leftover
        if old.exists():
            old.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
