"""把模型回答渲染成富文本：Markdown + LaTeX 公式图片 + 代码高亮。

Qt 原生富文本不支持 MathML/KaTeX，这里用 matplotlib 把公式渲染成透明 PNG，
以内联 data URI 嵌入，离线可用、效果稳定。
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import re
from functools import lru_cache
from pathlib import Path

import markdown
from PIL import Image

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MATH_CACHE = DATA_DIR / "math_cache"
MATH_CACHE.mkdir(parents=True, exist_ok=True)

TEXT_COLOR = "#1f2329"
MUTED = "#6b7280"
CODE_BG = "#f6f8fa"
CODE_FG = "#1f2937"
INLINE_BG = "#eef1f5"
LINK = "#2563eb"

_TAG_STYLE = (
    "font-family:'Microsoft YaHei UI','Segoe UI',sans-serif;"
    f"color:{TEXT_COLOR};font-size:14px;line-height:1.75;"
)

_INLINE_MATH = re.compile(r"(?<!\$)\$([^$\n]+?)\$(?!\$)")
_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]", re.S)
_PAREN_MATH = re.compile(r"\\\((.+?)\\\)", re.S)


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


_UNICODE_MAP = {
    r"\le": "≤",
    r"\leq": "≤",
    r"\ge": "≥",
    r"\geq": "≥",
    r"\ne": "≠",
    r"\neq": "≠",
    r"\times": "×",
    r"\cdot": "·",
    r"\pm": "±",
    r"\infty": "∞",
    r"\sum": "Σ",
    r"\prod": "∏",
    r"\int": "∫",
    r"\partial": "∂",
    r"\nabla": "∇",
    r"\to": "→",
    r"\rightarrow": "→",
    r"\Rightarrow": "⇒",
    r"\Leftarrow": "⇐",
    r"\approx": "≈",
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\epsilon": "ε",
    r"\theta": "θ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\pi": "π",
    r"\sigma": "σ",
    r"\phi": "φ",
    r"\omega": "ω",
    r"\Omega": "Ω",
    r"\Theta": "Θ",
}


def _repair_incomplete(text: str) -> tuple[str, bool]:
    """清理被截断回答末尾未闭合的 Markdown/LaTeX 标记。

    模型被 max_tokens 截断时，常见尾巴是 ``**``、``$``、``$\\`` 或未闭合代码块。
    直接显示会留下大量原始标记，这里做最小修复；返回 (文本, 是否修复过)。
    """
    repaired = False
    text = text.rstrip()

    # 未闭合代码块：从最后一个 ``` 截断
    if text.count("```") % 2:
        text = text[: text.rfind("```")].rstrip()
        repaired = True

    # 未闭合的粗体 **
    if text.count("**") % 2:
        index = text.rfind("**")
        text = (text[:index] + text[index + 2 :]).rstrip()
        repaired = True

    # 未闭合的行内/块级公式：找最后一个未转义的 $
    dollar_positions: list[int] = []
    escaped = False
    for index, char in enumerate(text):
        if char == "\\" and not escaped:
            escaped = True
            continue
        if char == "$" and not escaped:
            dollar_positions.append(index)
        escaped = False
    if len(dollar_positions) % 2:
        text = text[: dollar_positions[-1]].rstrip()
        repaired = True

    # 截断处可能留下孤立反斜杠
    if text.endswith("\\"):
        text = text[:-1].rstrip()
        repaired = True

    return text, repaired


def _render_incomplete_warning() -> str:
    return (
        '<div style="margin-top:8px;padding:6px 10px;border-radius:8px;'
        'background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;font-size:12px;">'
        "⚠️ 这条回答在长度限制处中断，已自动清理不完整格式；建议让它继续写或重新提问。"
        "</div>"
    )


def _unicode_math(latex: str) -> str:
    """matplotlib 渲染失败时的兜底：转成常见 Unicode 符号。"""
    text = latex
    for command, symbol in _UNICODE_MAP.items():
        text = text.replace(command, symbol)
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", text)
    text = re.sub(r"\\text\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", text)
    text = text.replace("\\left", "").replace("\\right", "")
    text = text.replace("\\,", " ").replace("\\;", " ").replace("\\ ", " ")
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = text.replace("{", "").replace("}", "")
    return text.strip()


def _normalize_latex(latex: str) -> str:
    """把常见但 mathtext 不认识的写法规范成可渲染形式。"""
    text = latex
    text = re.sub(r"\\le(?![a-zA-Z])", r"\\leq", text)
    text = re.sub(r"\\ge(?![a-zA-Z])", r"\\geq", text)
    text = re.sub(r"\\ne(?![a-zA-Z])", r"\\neq", text)
    text = text.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    text = text.replace(r"\text{", r"\mathrm{")
    text = text.replace(r"\operatorname{", r"\mathrm{")
    text = re.sub(r"\\boxed\{([^{}]*)\}", r"\1", text)
    text = text.replace(r"\displaystyle", "")
    text = text.replace(r"\lt", "<").replace(r"\gt", ">")
    text = text.replace(r"\,", r"\ ").replace(r"\;", r"\ ")
    return text.strip()


_ENV_RE = re.compile(
    r"\\begin\{(aligned|align\*?|cases|array|matrix|pmatrix|bmatrix)\}(.*?)\\end\{\1\}",
    re.S,
)


def _render_environment(latex: str, display: bool) -> str | None:
    match = _ENV_RE.search(latex)
    if not match:
        return None
    content = match.group(2)
    rows = re.split(r"\\\\", content)
    rendered_rows: list[str] = []
    for row in rows:
        row = row.replace("&", r"\quad ").strip()
        if not row:
            continue
        image = _math_image(row, display=True, _env_guard=True)
        if image:
            rendered_rows.append(image)
    if not rendered_rows:
        return None
    joined = "<br>".join(rendered_rows)
    if display:
        return f'<div align="center">{joined}</div>'
    return joined


def _math_image(latex: str, display: bool, _env_guard: bool = False) -> str | None:
    latex = latex.strip()
    if not latex:
        return None
    if _cjk(latex):
        # mathtext 不支持中文，直接文本展示
        return _escape(_unicode_math(latex))

    if not _env_guard:
        environment = _render_environment(latex, display)
        if environment is not None:
            return environment

    latex = _normalize_latex(latex)
    key = hashlib.sha1(
        f"light-v2-300:{TEXT_COLOR}:{display}:{latex}".encode("utf-8")
    ).hexdigest()
    path = MATH_CACHE / f"{key}.png"
    if not path.exists():
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.figure import Figure

            figure = Figure(dpi=300)
            figure.patch.set_alpha(0)
            figure.text(
                0,
                0,
                f"${latex}$",
                fontsize=20 if display else 17,
                color=TEXT_COLOR,
            )
            canvas = FigureCanvasAgg(figure)
            canvas.draw()
            figure.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0.04)
        except Exception:
            return _escape(_unicode_math(latex))

    try:
        with Image.open(path) as image:
            width, height = image.size
    except Exception:
        return _escape(_unicode_math(latex))
    if height <= 0:
        return None

    target_height = 36 if display else 25
    target_width = max(1, round(width * target_height / height))
    if target_width > 820:
        target_height = max(14, round(target_height * 820 / target_width))
        target_width = 820

    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f'<img src="data:image/png;base64,{data}" '
        f'width="{target_width}" height="{target_height}" '
        'style="vertical-align:middle;" />'
    )


def _render_code_block(code: str, language: str) -> str:
    language = (language or "").strip().lower()
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import TextLexer, get_lexer_by_name

        lexer = get_lexer_by_name(language) if language else TextLexer()
        formatter = HtmlFormatter(noclasses=True, nowrap=True, style="friendly")
        highlighted = highlight(code, lexer, formatter)
    except Exception:
        highlighted = _escape(code)
    return (
        '<pre style="background:%s;border:1px solid #e3e7ef;border-radius:8px;'
        "padding:10px;font-family:Consolas,'Cascadia Mono',monospace;font-size:12px;"
        'color:%s;white-space:pre-wrap;">%s</pre>' % (CODE_BG, CODE_FG, highlighted)
    )


def _render_inline_code(code: str) -> str:
    return (
        '<code style="background:%s;color:#1f2937;padding:1px 4px;'
        "border-radius:4px;font-family:Consolas,monospace;font-size:12px;"
        '">%s</code>' % (INLINE_BG, _escape(code))
    )


def render_stream_text(text: str) -> str:
    """流式阶段的轻量显示：把 LaTeX 转成 Unicode，避免满屏反斜杠。"""
    if not text:
        return ""
    source = text.replace("\r\n", "\n")
    source = _DISPLAY_MATH.sub(
        lambda match: "\n" + _unicode_math(match.group(1) or match.group(2) or "") + "\n", source
    )
    source = _PAREN_MATH.sub(lambda match: _unicode_math(match.group(1)), source)
    source = _INLINE_MATH.sub(lambda match: _unicode_math(match.group(1)), source)
    return source


@lru_cache(maxsize=64)
def render_answer(text: str) -> str:
    """把回答正文渲染成 QLabel/QTextBrowser 可用的 HTML。"""
    if not text:
        return ""
    source = text.replace("\r\n", "\n")

    code_blocks: list[str] = []
    inline_codes: list[str] = []
    display_maths: list[str] = []
    inline_maths: list[str] = []

    def stash_code_block(match: re.Match) -> str:
        language = match.group(1) or ""
        code = match.group(2)
        code_blocks.append(_render_code_block(code, language))
        return f"\n\nCODEBLOCK{len(code_blocks) - 1}TOKEN\n\n"

    source = re.sub(r"```([\w+-]*)\n(.*?)```", stash_code_block, source, flags=re.S)

    def stash_inline_code(match: re.Match) -> str:
        inline_codes.append(_render_inline_code(match.group(1)))
        return f"CODESPAN{len(inline_codes) - 1}TOKEN"

    source = re.sub(r"`([^`\n]+)`", stash_inline_code, source)
    source, repaired_incomplete = _repair_incomplete(source)

    def stash_display(match: re.Match) -> str:
        latex = match.group(1) or match.group(2) or ""
        display_maths.append(_math_image(latex, display=True) or _escape(latex))
        return f"\n\nMATHBLOCK{len(display_maths) - 1}TOKEN\n\n"

    source = _DISPLAY_MATH.sub(stash_display, source)

    def stash_inline_math(match: re.Match) -> str:
        latex = match.group(1)
        inline_maths.append(_math_image(latex, display=False) or _escape(latex))
        return f"MATHINLINE{len(inline_maths) - 1}TOKEN"

    source = _PAREN_MATH.sub(stash_inline_math, source)
    source = _INLINE_MATH.sub(stash_inline_math, source)

    body = markdown.markdown(
        source,
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
        output_format="html5",
    )

    for index, block in enumerate(display_maths):
        body = body.replace(f"<p>MATHBLOCK{index}TOKEN</p>", f'<div align="center">{block}</div>')
        body = body.replace(f"MATHBLOCK{index}TOKEN", f'<div align="center">{block}</div>')
    for index, image in enumerate(inline_maths):
        body = body.replace(f"MATHINLINE{index}TOKEN", image)
    for index, block in enumerate(code_blocks):
        body = body.replace(f"<p>CODEBLOCK{index}TOKEN</p>", block)
        body = body.replace(f"CODEBLOCK{index}TOKEN", block)
    for index, code in enumerate(inline_codes):
        body = body.replace(f"CODESPAN{index}TOKEN", code)

    body = re.sub(r"<table>", '<table border="1" cellspacing="0" cellpadding="5" '
                  'style="border-collapse:collapse;font-size:12px;color:%s;">' % TEXT_COLOR, body)
    body = re.sub(r"<th>", '<th style="background:#eef2f7;padding:5px;">', body)
    body = re.sub(r"<td>", '<td style="padding:5px;">', body)
    body = re.sub(r"<h1>", '<h1 style="font-size:18px;color:#111827;">', body)
    body = re.sub(r"<h2>", '<h2 style="font-size:16px;color:#111827;">', body)
    body = re.sub(r"<h3>", '<h3 style="font-size:14px;color:#111827;">', body)
    body = re.sub(r"<blockquote>", '<blockquote style="border-left:3px solid #2563eb;'
                  'background:#f7f9fc;padding:6px 10px;color:%s;">' % MUTED, body)
    body = re.sub(r"<a href=", f'<a style="color:{LINK};" href=', body)
    body = re.sub(r"<hr\s*/?>", '<hr style="border:1px solid #e3e7ef;" />', body)
    if repaired_incomplete:
        body += _render_incomplete_warning()

    return f'<div style="{_TAG_STYLE}">{body}</div>'
