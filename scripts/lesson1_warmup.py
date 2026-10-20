"""第一周热身脚本：让 Python 找到项目、读懂配置、用 pathlib 找文件。

老师的演示文件，不是作业答案。请在读懂后自己写一份 hello.py。

两种目录都可以跑，对比输出差异：

    cd Study-AI
    python scripts/lesson1_warmup.py

    cd ..
    python Study-AI/scripts/lesson1_warmup.py

它只读不写，也不会打印 API Key。
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1) 让 Python 找到 core 包
#    直接 `python scripts/xxx.py` 时，sys.path[0] 是 scripts/，不是项目根目录，
#    所以 `import core` 会失败。这里把项目根目录手动插到搜索路径最前面。
# ---------------------------------------------------------------------------
print("== 1. 解释器与搜索路径 ==")
print("Python:", sys.version.split()[0])
print("sys.path[0]:", sys.path[0])

APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))

from core.config import APP_DIR, DATA_DIR, DEFAULTS, Config  # noqa: E402

print("本文件 __file__:", Path(__file__).resolve())
print("推导出的项目根:", APP_ROOT)
print("config.APP_DIR:", APP_DIR, "| 两者一致:", APP_ROOT == APP_DIR)

# ---------------------------------------------------------------------------
# 2) 配置：DEFAULTS 打底，config.json 覆盖，环境变量再覆盖
# ---------------------------------------------------------------------------
print("\n== 2. 配置 ==")
config = Config()
print("模型:", config.model)
print("base_url:", config.base_url)
print("Key 是否已配置:", bool(config.api_key), "（只判断有没有，不打印内容）")
print("DEFAULTS 字段数:", len(DEFAULTS))
print("运行时字段数:", len(config.data))
print("只在 config.json 里的字段:", sorted(set(config.data) - set(DEFAULTS)))
print("只在 DEFAULTS 里的字段:", sorted(set(DEFAULTS) - set(config.data)))

# ---------------------------------------------------------------------------
# 3) pathlib：找截图。数据库里存的是相对路径，这里演示相对路径怎么来
# ---------------------------------------------------------------------------
print("\n== 3. 用 pathlib 找截图 ==")
captures = sorted((DATA_DIR / "captures").rglob("*.png"))
print("截图数量:", len(captures))
for path in captures[-3:]:
    relative = path.relative_to(DATA_DIR).as_posix()
    print(f"  {relative}  ({path.stat().st_size} bytes)")

# ---------------------------------------------------------------------------
# 4) 相对路径 vs 当前工作目录：这就是“换台电脑就找不到文件”的根源
# ---------------------------------------------------------------------------
print("\n== 4. 相对路径会被解释成什么 ==")
print("当前工作目录 cwd:", Path.cwd())
print('Path("data") 解析为:', Path("data").resolve())
print("它等于项目里的 data 吗:", Path("data").resolve() == DATA_DIR.resolve())

print("\n结论：绝对路径从 __file__ 推导；相对路径取决于你在哪里敲命令。")
