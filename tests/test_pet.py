"""桌宠与绘制测试（离屏）。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.pet_art import render_pet  # noqa: E402
from ui.pet_window import PetWindow  # noqa: E402


class PetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_render_pet_moods(self) -> None:
        for mood in ("idle", "thinking", "done", "error"):
            pixmap = render_pet(120, mood=mood, blink=mood == "idle", phase=1.0)
            self.assertFalse(pixmap.isNull(), mood)
            self.assertEqual(pixmap.devicePixelRatio(), 2.0)

    def test_double_click_requests_capture(self) -> None:
        pet = PetWindow()
        pet.show()
        triggered: list[int] = []
        pet.capture_requested.connect(lambda: triggered.append(1))
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(40, 80),
            QPointF(40, 80),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        pet.mouseDoubleClickEvent(event)
        self.assertEqual(triggered, [1])
        pet.hide()
        pet.deleteLater()

    def test_states_and_enable(self) -> None:
        pet = PetWindow()
        pet.set_state("thinking")
        pet.set_state("done", "回答好啦")
        self.assertTrue(pet.bubble.isVisibleTo(pet))
        pet.set_state("idle")
        pet.set_enabled(False)
        self.assertFalse(pet.isVisible())
        pet.deleteLater()


if __name__ == "__main__":
    unittest.main()
