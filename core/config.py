"""应用配置。

优先级：环境变量 DEEPSEEK_API_KEY > config.json > 默认值。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.json"
DATA_DIR = APP_DIR / "data"

DEFAULTS = {
    "api_key": "",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-flash",
    "max_tokens": 1500,
    "temperature": 0.6,
    "save_captures": True,
    "thinking": False,
    "hotkey_capture": "Ctrl+Alt+Q",
}


class Config:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else CONFIG_PATH
        self.data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except Exception as exc:  # 配置坏了不影响启动
                print(f"[config] 读取失败，使用默认配置: {exc}")
        env_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if env_key:
            self.data["api_key"] = env_key

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def api_key(self) -> str:
        return str(self.data.get("api_key") or "").strip()

    @property
    def base_url(self) -> str:
        return str(self.data.get("base_url") or DEFAULTS["base_url"]).rstrip("/")

    @property
    def model(self) -> str:
        return str(self.data.get("model") or DEFAULTS["model"])
