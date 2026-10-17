"""DeepSeek 视觉模型客户端（OpenAI 兼容 Chat Completions）。

文档：https://api-docs.deepseek.com/zh-cn/guides/vision
"""

from __future__ import annotations

import base64
import io
import json
from typing import Callable, Iterable

import requests
from PIL import Image

# 图片最长边超过该值时先缩放，控制请求体大小和延迟
MAX_IMAGE_SIDE = 2000

SYSTEM_PROMPT = """你是一个桌面学习助手，用户正在看 B 站视频（或在线课程），会把此刻的屏幕画面截图并发给你提问。

请遵守：
1. 优先依据截图里的信息回答（字幕、PPT、代码、公式、弹幕等）。截图里没有的内容，先明确说“画面里看不到……”，再做一般性解释，不要臆造。
2. 用中文回答，结构清晰、重点突出；公式用普通文本或 LaTeX 表示。
3. 如果用户问的是代码，说明这段代码在做什么、输入输出是什么、有没有坑。
4. 如果截图内容和问题无关，直接指出可能框错了区域。
5. 回答简洁，不要复述题目。"""


class LLMError(RuntimeError):
    pass


def encode_image(img: Image.Image, max_side: int = MAX_IMAGE_SIDE) -> str:
    """把 PIL 图片压缩成 JPEG 并返回 base64（不含 data: 前缀）。"""
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def image_content_block(img_b64: str) -> dict:
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "original"},
    }


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-flash",
        max_tokens: int = 1500,
        temperature: float = 0.6,
        timeout: tuple[float, float] = (10.0, 180.0),
    ) -> None:
        if not api_key:
            raise LLMError("未配置 API Key")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    @property
    def url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, messages: list[dict], stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    def chat(self, messages: list[dict]) -> str:
        """非流式调用，返回完整回答；用于自检。"""
        try:
            resp = requests.post(
                self.url,
                headers=self._headers(),
                json=self._payload(messages, stream=False),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LLMError(f"网络请求失败：{exc}") from exc
        if resp.status_code != 200:
            raise LLMError(f"HTTP {resp.status_code}：{resp.text[:400]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"响应格式异常：{data}") from exc

    def stream_chat(
        self,
        messages: list[dict],
        on_delta: Callable[[str], None],
        stop_event=None,
    ) -> None:
        """流式调用，逐段回调 on_delta；stop_event 置位时可提前中断。"""
        try:
            resp = requests.post(
                self.url,
                headers=self._headers(),
                json=self._payload(messages, stream=True),
                timeout=self.timeout,
                stream=True,
            )
        except requests.RequestException as exc:
            raise LLMError(f"网络请求失败：{exc}") from exc

        with resp:
            if resp.status_code != 200:
                raise LLMError(f"HTTP {resp.status_code}：{resp.text[:400]}")
            for line in resp.iter_lines(decode_unicode=True):
                if stop_event is not None and stop_event.is_set():
                    return
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    on_delta(text)


def messages_with_image(question: str, img_b64: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                image_content_block(img_b64),
            ],
        },
    ]
