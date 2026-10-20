"""回答渲染测试：公式、代码、表格、兜底。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.answer_render import render_answer, render_stream_text  # noqa: E402


class AnswerRenderTest(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(render_answer(""), "")

    def test_inline_math(self) -> None:
        html = render_answer("递归式 $T(n)=4T(n/2)+n$ 的复杂度。")
        self.assertIn("<img", html)
        self.assertNotIn("$T(n)", html)

    def test_display_math_aliases(self) -> None:
        html = render_answer(r"$$\frac{a}{b} + \sqrt{x} \le \sum_{i=1}^{n} i$$")
        self.assertIn("<img", html)
        self.assertNotIn(r"\frac", html)
        self.assertNotIn(r"\le", html)

    def test_aligned_environment(self) -> None:
        html = render_answer(r"推导：\n\n$$\begin{aligned} x &= 1 \\ y &= 2 \end{aligned}$$")
        self.assertIn("<img", html)
        self.assertNotIn(r"\begin{aligned}", html)

    def test_parenthesis_math(self) -> None:
        html = render_answer(r"结果是 \(\Theta(n^2)\)，注意这个上界。")
        self.assertIn("<img", html)
        self.assertNotIn(r"\(", html)

    def test_code_block_and_table(self) -> None:
        html = render_answer(
            "示例：\n\n```python\nprint(1)\n```\n\n| 层级 | 代价 |\n| --- | --- |\n| 0 | n |"
        )
        self.assertIn("<pre", html)
        self.assertIn("<table", html)
        self.assertIn("print", html)

    def test_cjk_math_falls_back_to_text(self) -> None:
        html = render_answer("$中文公式$")
        self.assertIn("中文", html)
        self.assertNotIn("$", html)

    def test_invalid_math_does_not_crash(self) -> None:
        html = render_answer(r"$$\begin{unknown} x \end{unknown}$$")
        self.assertTrue(html)
        self.assertIn("<div", html)

    def test_incomplete_markdown_is_cleaned(self) -> None:
        html = render_answer("1. **$f(n)$ 的指数要与 $\\")
        self.assertNotIn("**", html)
        self.assertNotIn("$\\", html)
        self.assertIn("长度限制", html)

    def test_stream_text_removes_latex(self) -> None:
        text = render_stream_text(r"公式 $\frac{a}{b}$ 和 \(x^2\)，还有 $$n^2$$")
        self.assertNotIn(r"\frac", text)
        self.assertNotIn("$", text)


if __name__ == "__main__":
    unittest.main()
