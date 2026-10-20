# 项目文件清单（公开透明版）

> 统计时间：2026-10-17
> 说明：本文件列出项目里**每一个目录和文件的作用**，以及哪些内容会进入 Git/GitHub、哪些只保存在本机。
> 密钥、聊天内容、截图内容不会写进本文件。

---

## 0. 一句话结论

- **源码、文档、测试、插件、图标、示例截图**：都在 GitHub 仓库里。
- **`config.json`（含 API Key）和 `data/`（聊天记录、记忆、截图、日志、数据库）**：只在本机，**不会上传**。
- `.git/`：版本库内部数据，不是项目源码。
- `__pycache__/`：Python 自动生成的字节码缓存，可随时删除。

---

## 1. 顶层结构

```
Study-AI/
├── .git/                  # Git 版本库（本地）
├── .gitignore             # 忽略 config.json / data/ / __pycache__ / backup/
├── app.py                 # 程序入口
├── config.json            # 本机配置（含 API Key，私有）
├── config.example.json    # 配置模板（公开）
├── requirements.txt       # Python 依赖
├── start.bat              # Windows 启动脚本
├── README.md              # 使用说明
├── assets/                # 图标、文档截图
├── core/                  # 业务核心（不依赖 Qt 界面）
├── ui/                    # PySide6 界面
├── tests/                 # 测试与开发脚本
├── docs/                  # 架构/阅读/学习文档
├── plugins/               # 内置插件
├── legacy/                # 旧 Tk 版本（仅参考）
├── backup/                # 本机源码备份（gitignore，不上传）
├── data/                  # 运行时私有数据（不上传）
└── __pycache__/           # Python 缓存（可删）
```

> 同级目录 `..\DSH-debug-20261017\` 是 DSH 调试/配置归档，不属于 Study-AI 项目。

---

## 2. 根目录文件

| 文件 | 作用 | 是否上 GitHub |
| --- | --- | --- |
| `app.py` | 入口：单实例、QApplication、组装组件、热键、托盘、退出 | 是 |
| `config.example.json` | 配置示例（不含真实 Key） | 是 |
| `config.json` | 本机配置：API Key、模型、tokens、桌宠位置等 | **否（私有）** |
| `requirements.txt` | 依赖：PySide6、Pillow、requests、matplotlib、markdown、pygments、pywin32 | 是 |
| `start.bat` | `pythonw app.py` 启动脚本 | 是 |
| `README.md` | 功能、使用、热键、测试、开发者文档入口 | 是 |
| `.gitignore` | 排除 `config.json`、`data/`、`__pycache__/`、`*.pyc` | 是 |
| `.git/` | 提交历史、分支、remote 配置 | 版本库内部 |
| `__pycache__/` | 根目录 Python 缓存 | 否（忽略） |

---

## 3. core/：业务核心

| 文件 | 作用 |
| --- | --- |
| `__init__.py` | 空包标记 |
| `agent.py` | **旧版**独立 AgentRunner（当前主流程已改用 `conversation.py`，保留供旧测试参考） |
| `bilibili.py` | B 站视频信息查询：API + 页面标题兜底 |
| `capture.py` | 抓主屏、裁剪图片 |
| `config.py` | `config.json` 读写与默认值 |
| `context.py` | 前台窗口/进程/视频标题上下文、`ContextWatcher` |
| `controller.py` | 业务编排：截图流程、文字消息、Agent 回调、确认、记忆/笔记入口 |
| `conversation.py` | **对话式 Agent 核心**：构建 messages、工具循环、持久化、发信号 |
| `hotkey.py` | Win32 全局热键线程（RegisterHotKey + 消息循环） |
| `llm.py` | DeepSeek/OpenAI 兼容客户端：chat、stream、tool calling、图片编码 |
| `memory.py` | 长期记忆：检索、注入 prompt、LLM 整理合并 |
| `plugins.py` | 插件发现/安装/启用/卸载 |
| `store.py` | SQLite 数据层：会话、消息、笔记、记忆、截图路径、迁移 |
| `tools.py` | 工具注册表 + 15 个内置工具 |
| `word.py` | Word COM 自动化：插入图片/截图/剪贴板图片/文字 |

> `core/` 里除 `agent.py` 外，其余都在当前主流程中。

---

## 4. ui/：PySide6 界面

| 文件 | 作用 |
| --- | --- |
| `__init__.py` | 空包标记 |
| `main_window.py` | **主窗口**：无边框浅色标题栏、会话列表、对话流、输入框、页面切换 |
| `notes_pane.py` | 笔记页：列表 + 编辑器 + 自动保存 + 导出 |
| `memory_pane.py` | 记忆页：卡片、启停、编辑、删除、整理入口 |
| `answer_render.py` | Markdown/代码高亮/LaTeX 公式 → 富文本 HTML |
| `theme.py` | 浅色 QSS 全局样式 |
| `pet_window.py` | 桌宠窗口：透明、拖动、右键菜单、全屏隐藏 |
| `pet_art.py` | 程序化绘制路飞、生成应用图标 |
| `capture_overlay.py` | 全屏框选遮罩 |
| `question_dialog.py` | 截图后输入问题的弹窗 |
| `settings_dialog.py` | API Key、模型、tokens、桌宠、深度思考等设置 |
| `plugins_dialog.py` | 插件管理：安装文件夹/zip、启停、卸载、打开目录 |
| `utils.py` | 时间格式化、文本截断、PIL→QPixmap |
| `agent_pane.py` | **旧版** Agent 任务页（新 UI 不再使用） |
| `answer_panel.py` | **旧版** 浮动回答面板（新 UI 不再使用） |

---

## 5. tests/：测试与开发脚本

| 文件 | 作用 |
| --- | --- |
| `__init__.py` | 测试包标记 |
| `test_core.py` | 配置、Store、会话上下文、笔记 CRUD、消息 meta |
| `test_flow.py` | 连续截图、取消、文字任务/追问、工具步骤、导航、Word 工具注册 |
| `test_memory.py` | 记忆检索、整理、合并 |
| `test_context.py` | 前台上下文、B 站标题解析、BV 号 |
| `test_plugins.py` | 插件加载、安装、卸载 |
| `test_render.py` | Markdown/公式/代码/表格/异常公式 |
| `test_pet.py` | 桌宠状态、双击 |
| `test_agent.py` | 旧版 AgentRunner 的测试 |
| `live_api_check.py` | 手动真实 API 连通性检查（会产生少量 token 费用） |
| `render_screenshots.py` | 不弹窗生成 `assets/screenshot_*.png` |

运行：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest discover -s tests -t .
```

---

## 6. docs/：开发者文档

| 文件 | 作用 |
| --- | --- |
| `MASTER_GUIDE.md` | 总纲：全文件地图 + 代码框架 + 12 周系统学习路线 |
| `ARCHITECTURE.md` | 架构、线程模型、数据流、数据库、扩展点、技术债 |
| `CODE_FRAMEWORK.md` | 整体代码框架：分层图、启动流程、核心类、数据流、改功能对照表 |
| `READING_GUIDE.md` | 源码阅读顺序、断点、三条调用链、练习任务 |
| `LEARNING_PATH.md` | 8 周系统学习路线、底层知识地图、官方资源 |
| `STUDY_PLAN.md` | 可执行的 8 周学习计划、每日模板、前 7 天安排、验收清单 |

---

## 7. plugins/：内置插件

```
plugins/study_notes/
├── plugin.json     # 插件元数据：名称、版本、入口
└── tool.py         # register(registry)，注册 add_study_note/list_study_notes
```

插件运行在本机进程内，**没有沙箱**；只安装信任的插件。用户安装的插件会放到 `data/plugins/`（当前为空）。

---

## 8. assets/：图标与文档截图

| 文件 | 作用 |
| --- | --- |
| `app.png` | 应用图标源图 |
| `app.ico` | 通用 Windows 图标 |
| `luffy.ico` | 旧版图标 |
| `luffy_v2.ico` | 浅色图标 v2 |
| `luffy_v3.ico` | **当前使用**的浅色图标（桌面快捷方式） |
| `screenshot_main.png` | 欢迎页截图 |
| `screenshot_chat.png` | 对话 + 工具卡片截图 |
| `screenshot_notes.png` | 笔记页截图 |
| `screenshot_memory.png` | 记忆页截图 |
| `screenshot_pet.png` | 桌宠截图 |

---

## 9. legacy/：旧 Tk 版本

| 文件 | 作用 |
| --- | --- |
| `app.py` | 旧 Tkinter 界面 |
| `config.py` | 旧配置 |
| `hotkey.py` | 旧热键 |
| `llm.py` | 旧 LLM 客户端 |
| `store.py` | 旧存储 |
| `selftest.py` | 旧自检 |

仅作历史参考，当前不运行。

---

## 10. data/：本机私有数据（不上传）

```
data/
├── bili_ask.db          # SQLite：会话/消息/笔记/记忆
├── bili_ask.db-shm      # SQLite WAL 共享内存
├── bili_ask.db-wal      # SQLite WAL 日志（当前空）
├── app.log              # 运行日志
├── captures/            # 截图
│   └── 2026-10-17/      # 按日期分目录（当前 4 张）
├── math_cache/          # 公式渲染缓存 PNG（当前 182 张）
├── notes/               # 旧版笔记文件目录（当前空）
└── plugins/             # 用户安装的插件（当前空）
```

数据库当前行数（会随使用变化）：

| 表 | 行数 |
| --- | --- |
| `sessions` | 5 |
| `messages` | 15 |
| `notes` | 0 |
| `memories` | 8 |

**为什么不上传 `data/`：**

- 里面有你的真实提问、回答、截图、长期记忆；
- 可能包含个人信息/学习内容；
- 体积会持续增长；
- GitHub 不是私人网盘，公开仓库会把内容公开。

需要备份时，单独复制 `data/` 和 `config.json`，或者用项目外的加密压缩包。

---

## 11. config.json：本机配置（不上传）

包含：

- `api_key`：**已设置，但不在本文件/仓库中显示**
- `base_url`：`https://api.deepseek.com`
- `model`：`deepseek-flash`
- `max_tokens`（默认 4096，长回答会自动续写）、`temperature`
- `save_captures`、`thinking`、`note_template`
- `hotkey_capture`、`pet_pos`、`pet_enabled`

`config.example.json` 只保留空 Key 模板，可安全公开。

**如果 `config.json` 曾经被发到公开渠道：请立刻去 DeepSeek 平台轮换 Key。**

---

## 12. Git 与 GitHub 上到底有什么

当前仓库：https://github.com/Philip-9Y/Study-AI

- 分支：`main`
- 提交：以 `git log --oneline -1` 为准
- 跟踪文件：69 个
- 内容：`app.py`、`core/`、`ui/`、`tests/`、`docs/`、`plugins/`、`assets/`、`legacy/`、`README.md`、`requirements.txt`、`start.bat`、`config.example.json`、`.gitignore`

**不在 GitHub：**

- `config.json`（Key）
- `data/`（数据库、截图、日志、记忆）
- `__pycache__/`、`*.pyc`
- `backup/`（源码 zip、git bundle；已在 gitignore）

`.git/` 里保存提交历史；`git status` 干净表示本地与远程同步。

---

## 13. 本机备份（backup/，已 gitignore）

在 `Study-AI/backup/`：

| 文件/目录 | 说明 |
| --- | --- |
| `bili-ask-20261017-1917-source.zip` | 源码快照（不含 config/data） |
| `bili-ask-20261017-1917.bundle` | Git 完整历史 bundle，可 clone 恢复 |

`backup/README.md` 记录了每项的用途和恢复方式。整个 `backup/` 不会进入 Git。

与 Study-AI 无关的 DSH 调试/配置归档已移到项目外：

```
..\DSH-debug-20261017\
├── profile-backup-20261017/
├── tools/
├── err.txt
└── out.txt
```

---

## 14. 缓存与可删除内容

- `__pycache__/`、`*.pyc`：Python 字节码，删除后会自动重建；
- `data/math_cache/`：公式图片缓存，删除后会重新生成（变慢一次）；
- `data/bili_ask.db-shm` / `-wal`：SQLite 运行时文件，**退出 App 后再删**，不要手动编辑；
- `data/captures/`：截图，删除后历史里的图片会缺失；
- `data/app.log`：可删，下一次启动会新建。

---

## 15. 如何自己核对

```powershell
cd "D:\deepseek harness workplace\usually\Study-AI"

# 看所有文件（含隐藏）
Get-ChildItem -Force -Recurse | Select-Object FullName, Length

# 看每个目录大小
Get-ChildItem -Directory | ForEach-Object {
  $s = (Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum
  "{0} {1:N0} KB" -f $_.Name, ($s/1KB)
}

# 看 Git 跟踪了什么
git ls-files

# 看哪些被忽略
git status --ignored --short

# 看数据库行数
python -c "import sqlite3; c=sqlite3.connect('data/bili_ask.db'); print({t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in ('sessions','messages','notes','memories')})"
```

---

## 16. 一句话总结

**GitHub 上是“可公开的源代码 + 文档 + 资源”；本地 `config.json` 和 `data/` 是“你的私人 Key + 学习数据”。这两类内容刻意分开，是安全设计，不是隐藏。**
