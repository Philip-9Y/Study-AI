"""真实 API 连通性检查（会产生极少量 token 费用）。

    python tests/live_api_check.py

读取本机 config.json / DEEPSEEK_API_KEY，发送一张合成测试图，
验证 Key、模型名和视觉输入是否可用。不会发送你的屏幕内容。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from core.config import Config  # noqa: E402
from core.llm import DeepSeekClient, encode_image, image_block  # noqa: E402


def make_image() -> Image.Image:
    img = Image.new("RGB", (640, 220), "white")
    draw = ImageDraw.Draw(img)
    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    font = ImageFont.truetype(str(font_path), 30) if font_path.exists() else ImageFont.load_default()
    draw.text((30, 40), "梯度下降：沿负梯度方向更新参数", fill="black", font=font)
    draw.text((30, 110), "θ = θ - α * ∇J(θ)", fill="black", font=font)
    return img


def main() -> int:
    config = Config()
    if not config.api_key:
        print("FAIL: 没有配置 API Key")
        return 1
    print(f"使用模型: {config.model}，Key: {config.api_key[:6]}…{config.api_key[-4:]}")
    client = DeepSeekClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        max_tokens=300,
        temperature=0.2,
    )
    messages = [
        {"role": "system", "content": "简洁回答。"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "图片里写了什么？请逐行原样复述。"},
                image_block(encode_image(make_image())),
            ],
        },
    ]
    try:
        answer = client.chat(messages)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1
    print("OK，模型回答：")
    print(answer.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
