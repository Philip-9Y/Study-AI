# Study-AI 学习总纲

> 这份文档把三件事合成一张地图：
> 1. **每个文件是干什么的**
> 2. **代码整体怎么跑**
> 3. **从 Python 底层到 Qt、网络、LLM、Agent、Windows、工程化的系统学习路线**
>
> 用法：
> - 第 1–2 章：建立全局地图（1–2 天）
> - 第 3 章：按周系统学习（12 周，可压缩到 8 周）
> - 第 4–6 章：查漏、练习、验收
>
> 旧的 `ARCHITECTURE.md`、`READING_GUIDE.md`、`LEARNING_PATH.md`、`STUDY_PLAN.md`、`CODE_FRAMEWORK.md` 保留作深入阅读；本文件是总入口。

---

# 第 1 章 文件地图

## 1.1 总览

```
Study-AI/
├── app.py                 程序入口
├── start.bat              Windows 启动脚本
├── config.json            本机配置（含 API Key，私有）
├── config.example.json    配置模板
├── requirements.txt       Python 依赖
├── README.md              使用说明
│
├── core/                  业务核心（15 个 py）
├── ui/                    界面（15 个 py）
├── tests/                 测试与开发脚本（11 个）
├── docs/                  文档（本文件 + 5 份深入文档）
├── assets/                图标 + 界面截图
├── plugins/               内置插件
├── legacy/                旧 Tk 版本（仅参考）
├── data/                  私有运行数据（不上传）
└── backup/                本机源码备份（gitignore）
```

## 1.2 根目录文件

| 文件 | 内容 | 作用 | 学习优先级 |
| --- | --- | --- | --- |
| `app.py` | `main()`、组件装配、单实例、托盘、热键循环、退出清理 | 入口 | ★★★ 必读 |
| `start.bat` | `pythonw app.py` | 双击启动 | ★ |
| `config.json` | API Key、模型、tokens、桌宠位置 | 本机配置 | 知道即可，别公开 |
| `config.example.json` | 空 Key 模板 | 配置示例 | ★ |
| `requirements.txt` | PySide6、Pillow、requests、matplotlib、markdown、pygments、pywin32 | 依赖 | ★★ |
| `README.md` | 功能、热键、测试、文档入口 | 使用说明 | ★★ |
| `.gitignore` | 排除 config/data/backup/缓存 | Git 边界 | ★★ |

## 1.3 core/ 每个文件

| 文件 | 内容 | 作用 | 优先级 |
| --- | --- | --- | --- |
| `__init__.py` | 空 | 包标记 | — |
| `agent.py` | 旧版 `AgentRunner` | 当前主流程不用 | 忽略 |
| `bilibili.py` | `fetch_video_info`：API + 页面标题兜底 | 查 B 站视频信息 | ★ |
| `capture.py` | `grab_primary_screen`、`crop_image` | 抓屏/裁剪 | ★★ |
| `config.py` | `Config` 类：JSON 读写、环境变量 | 配置 | ★★★ |
| `context.py` | `ScreenContext`、`get_foreground_context`、`_fill_video`、`ContextWatcher` | 前台窗口/视频上下文 | ★★ |
| `controller.py` | 截图流程、`send_text`、Agent 回调、确认、记忆/笔记入口 | 流程编排 | ★★★ |
| `conversation.py` | `ConversationAgent`、`CHAT_SYSTEM_PROMPT`、`_build_messages`、`_run` | Agent 核心 | ★★★ |
| `hotkey.py` | `HotkeyManager` 线程、Win32 热键 | 全局热键 | ★★ |
| `llm.py` | `DeepSeekClient`、`chat_with_tools`、`stream_chat`、图片编码 | LLM 客户端 | ★★★ |
| `memory.py` | `MemoryManager`：检索、注入、整理、合并 | 长期记忆 | ★★ |
| `plugins.py` | `PluginInfo`、`PluginManager`：扫描/安装/启停 | 插件系统 | ★★ |
| `store.py` | `SCHEMA`、`Store`：会话/消息/笔记/记忆 CRUD、迁移 | 数据层 | ★★★ |
| `tools.py` | `ToolSpec`、`ToolResult`、`ToolRegistry`、15 个内置工具 | 工具层 | ★★★ |
| `word.py` | Word COM：插图/截图/剪贴板/文字 | Windows 自动化 | ★★ |

## 1.4 ui/ 每个文件

| 文件 | 内容 | 作用 | 优先级 |
| --- | --- | --- | --- |
| `__init__.py` | 空 | 包标记 | — |
| `main_window.py` | `_TitleBar`、`_Composer`、`MainWindow`、页面栈、信号 | 主界面 | ★★★ |
| `notes_pane.py` | 笔记列表 + 编辑器 + 自动保存/导出 | 笔记页 | ★★ |
| `memory_pane.py` | 记忆卡片、启停/编辑/删除/整理 | 记忆页 | ★★ |
| `answer_render.py` | Markdown → HTML、pygments 代码、matplotlib 公式、缓存 | 答案渲染 | ★★ |
| `theme.py` | 浅色 QSS 全局样式 | 主题 | ★★ |
| `pet_window.py` | 透明桌宠、拖动、右键菜单、全屏隐藏 | 桌宠 | ★ |
| `pet_art.py` | 程序化绘制路飞、应用图标 | 美术 | ★ |
| `capture_overlay.py` | 全屏框选遮罩 | 截图 | ★★ |
| `question_dialog.py` | 截图后输入问题的弹窗 | 截图 | ★ |
| `settings_dialog.py` | API Key/模型/tokens/桌宠/思考开关 | 设置 | ★ |
| `plugins_dialog.py` | 插件安装/启停/卸载 | 插件管理 | ★ |
| `utils.py` | 时间格式、截断、PIL→QPixmap | 小工具 | ★ |
| `agent_pane.py` | 旧版 Agent 任务页 | 不用 | 忽略 |
| `answer_panel.py` | 旧版浮动回答面板 | 不用 | 忽略 |

## 1.5 tests/ 每个文件

| 文件 | 测什么 |
| --- | --- |
| `test_core.py` | 配置、Store、会话上下文、笔记 CRUD、消息 meta |
| `test_flow.py` | 连续截图、取消、文字对话/追问、工具持久化、导航、Word 工具注册 |
| `test_memory.py` | 记忆检索、整理、合并 |
| `test_context.py` | 前台上下文、B 站标题解析、BV 号 |
| `test_plugins.py` | 插件加载、安装、卸载 |
| `test_render.py` | Markdown/公式/代码/表格/异常公式 |
| `test_pet.py` | 桌宠状态、双击 |
| `test_agent.py` | 旧版 AgentRunner |
| `live_api_check.py` | 手动真实 API 连通性（会产生少量费用） |
| `render_screenshots.py` | 不弹窗生成 `assets/screenshot_*.png` |
| `__init__.py` | 包标记 |

## 1.6 docs/

| 文件 | 用途 |
| --- | --- |
| `MASTER_GUIDE.md` | 本文件：总纲（文件地图 + 框架 + 学习路线） |
| `CODE_FRAMEWORK.md` | 整体代码框架（更偏结构图） |
| `ARCHITECTURE.md` | 深入架构、线程、数据流、扩展点、技术债 |
| `READING_GUIDE.md` | 源码阅读顺序、断点、调用链、练习 |
| `LEARNING_PATH.md` | 知识地图、8 周路线、资源 |
| `STUDY_PLAN.md` | 8 周执行表（每日节奏、前 7 天） |
| `PROJECT_INVENTORY.md` | 文件清单、公开/私有边界、备份 |

## 1.7 其他目录

| 路径 | 内容 | 作用 | 是否上传 |
| --- | --- | --- | --- |
| `assets/` | `app.png`、`app.ico`、`luffy*.ico`、5 张 screenshot | 图标/截图 | 是 |
| `plugins/study_notes/` | `plugin.json`、`tool.py` | 示例插件 | 是 |
| `legacy/` | 旧 Tk 版：app/config/hotkey/llm/store/selftest | 历史参考 | 是 |
| `backup/` | source.zip、git bundle、README | 本机源码备份 | 否（gitignore） |
| `data/` | DB、截图、日志、公式缓存 | 运行数据 | 否（私有） |
| `.git/` | 提交历史 | 版本库 | 版本库内部 |

## 1.8 data/ 里有什么

```
data/
├── bili_ask.db          SQLite：会话/消息/笔记/记忆
├── bili_ask.db-shm      WAL 共享内存
├── bili_ask.db-wal      WAL 日志
├── app.log              运行日志
├── captures/            截图（按日期）
├── math_cache/          公式 PNG 缓存
├── notes/               旧版笔记目录（通常空）
└── plugins/             用户插件（通常空）
```

> 这些是**你的私有数据**：不上传、不分享、改前先备份。

---

# 第 2 章 代码框架

## 2.1 四层结构

```
┌──────────────────────────────────────────────┐
│ 表现层 ui/                                    │
│ MainWindow / NotesPane / MemoryPane / Pet    │
└──────────────────▲───────────────────────────┘
                   │ Qt Signal / 方法调用
┌──────────────────┴───────────────────────────┐
│ 流程层 core/controller.py                     │
│ 截图、文字、确认、笔记/记忆入口                │
└──────────────────▲───────────────────────────┘
                   │
┌──────────────────┴───────────────────────────┐
│ 智能层 core/conversation.py                   │
│ messages / 工具循环 / 持久化 / 信号            │
└───────▲────────────────────────▲─────────────┘
        │                        │
┌───────┴────────┐    ┌──────────┴─────────────┐
│ llm.py         │    │ tools.py / word.py     │
│ 模型调用        │    │ 工具执行               │
└────────────────┘    └──────────┬─────────────┘
                                 │
┌────────────────────────────────┴─────────────┐
│ 数据/系统层：store / memory / context / hotkey│
└──────────────────────────────────────────────┘
```

**边界规则：**

- UI 不直接调 LLM；
- Controller 不实现 Agent 循环；
- ConversationAgent 不碰 QWidget；
- Store 不依赖 UI；
- 工具统一由 `ToolRegistry` 管理。

## 2.2 启动链路

```
QApplication
→ Config
→ Store
→ ContextWatcher
→ ToolRegistry
→ PluginManager.load_all()
→ MemoryManager
→ ConversationAgent
→ MainWindow
→ Controller
→ PetWindow
→ Tray + HotkeyManager
→ show_and_raise()
→ app.exec()
```

## 2.3 文字任务

```
MainWindow._send
→ Controller.send_text
→ Store.create_session / add_message(user)
→ MainWindow.open_session
→ ConversationAgent.run（worker）
   → _build_messages（system + 上下文 + 记忆 + 历史）
   → chat_with_tools
   → 有工具：ToolRegistry.execute → 结果回填
   → 无工具：Store.add_message(assistant, meta.steps)
→ finished → MainWindow.agent_finished → render_answer
```

## 2.4 截图任务

```
热键/桌宠
→ Controller.start_capture
→ 记录上下文 → 隐藏主窗口 → 抓屏
→ CaptureOverlay 框选
→ QuestionDialog
→ Store.save_capture / create_session
→ ConversationAgent.run
```

## 2.5 线程与信号

| 工作 | 线程 |
| --- | --- |
| UI/控件 | Qt 主线程 |
| LLM + 工具 | Agent worker |
| 全局热键 | HotkeyManager 线程 |
| 记忆整理 | 单独线程 |
| SQLite | 主线程/worker + RLock |

规则：**worker 只发信号；主线程改 UI；危险工具用 Event 等待主线程确认。**

## 2.6 数据模型

```
sessions 1 ─── n messages
   ├─ context（首轮屏幕上下文）
   └─ image_path（首张截图）

notes      独立表
memories   独立表
```

## 2.7 工具协议

```python
ToolSpec(
    name, description, parameters,  # JSON Schema
    func,
    dangerous=True/False,
)
```

`ToolRegistry.execute()` 负责 JSON 参数、执行、异常转失败结果；危险工具先确认。

## 2.8 关键文件只读 6 个

```
app.py
→ core/controller.py
→ core/conversation.py
→ core/tools.py
→ core/store.py
→ ui/main_window.py
```

---

# 第 3 章 系统学习路线（12 周）

## 3.0 原则

1. **以项目为主线**：每周在 Study-AI 里做一个能跑的改动。
2. **从底层往上**：Python → 数据 → Qt → 网络 → LLM → Agent → Windows。
3. **每学一个概念，写一个最小实验**（20–50 行）。
4. **每周有验收**：能讲清楚 + 能跑通 + 能提交。

每天 1.5–2 小时：

| 时间 | 内容 |
| --- | --- |
| 30 min | 官方文档/教程 |
| 40 min | 读对应源码 |
| 30 min | 最小实验 |
| 15 min | 笔记/画图 |
| 5 min | Git 提交（可选） |

---

## 阶段一：Python 与数据（第 1–3 周）

### 第 1 周：Python 基础与工程环境

**学：**

- 变量、类型、字符串、列表/字典/集合
- 条件/循环/函数/参数
- 模块、包、导入
- 虚拟环境、pip、requirements.txt
- 命令行、路径、文件读写
- Git 基础：`status/add/commit/log/diff`

**读：**

- `app.py`（只看 `main()` 的创建顺序）
- `config.py`
- `README.md` 的快速开始

**做：**

1. 新建 `scripts/hello.py`，读取 `config.json` 并打印模型名（不打印 Key）；
2. 用 `pathlib` 列出 `data/captures` 下的图片；
3. `git status`、`git diff` 各执行一次。

**验收：**

- 能解释 `python app.py` 发生了什么；
- 能说清 `config.json` 和 `config.example.json` 的区别。

---

### 第 2 周：Python 进阶

**学：**

- 类/对象/继承/组合
- 异常处理、`try/except/finally`
- 类型标注：`list[dict]`、`str | None`、`Optional`
- `dataclass`
- 迭代器/生成器/推导式
- 上下文管理器 `with`
- 装饰器（理解即可）
- JSON 序列化/反序列化
- 日志 `logging`

**读：**

- `core/config.py`
- `core/store.py` 的 `Store.__init__` 和 CRUD
- `core/context.py` 的 `ScreenContext`

**做：**

1. 写一个 `Note` dataclass，支持 `to_dict/from_dict`；
2. 用 `logging` 记录脚本运行；
3. 写一个 `with` 计时器。

**验收：**

- 能解释 `ScreenContext` 每个字段；
- 能解释 `with self._lock, self._conn` 的作用。

---

### 第 3 周：并发与 SQLite

**学：**

- 进程 vs 线程 vs 协程
- GIL 是什么
- `threading.Thread`、`Lock/RLock`、`Event`、`Queue`
- 线程安全与竞态
- SQLite：表、主键、索引、事务、WAL
- 参数化查询防注入
- 简单迁移（加列）

**读：**

- `core/store.py` 的 `SCHEMA`、`_ensure_columns`
- `core/conversation.py` 的线程/停止事件
- `tests/test_core.py`

**做：**

1. 写一个线程安全的计数器；
2. 用 SQL 查“每个会话的消息数”；
3. 给 `notes` 加一个练习字段并做迁移。

**验收：**

- 能解释为什么写库要 `RLock`；
- 能解释 WAL 是什么、何时用。

---

## 阶段二：Qt 桌面（第 4–5 周）

### 第 4 周：Qt 基础

**学：**

- 事件循环 `QApplication.exec()`
- QWidget、父子对象、布局
- Signal/Slot
- QTimer
- 常用控件：按钮、输入框、标签、列表、滚动区、对话框

**读：**

- `app.py` 的 `QApplication/QTimer`
- `ui/main_window.py` 的 `_build_ui`、`_build_chat_page`
- `ui/theme.py`

**做：**

1. 写一个最小窗口：输入框 + 按钮 + 标签；
2. 点击按钮后标签显示输入内容；
3. 把窗口改成浅色 QSS。

**验收：**

- 能解释信号和槽怎么连；
- 能解释 `QApplication` 为什么必须有。

---

### 第 5 周：Qt 进阶

**学：**

- 线程边界：QWidget 只能在主线程
- QueuedConnection
- QThread/worker 模式（本项目用 Python 线程 + Signal）
- QSS 选择器、objectName
- QPainter 绘制
- 无边框窗口、拖动、QSizeGrip
- 高 DPI

**读：**

- `ui/main_window.py` 的 `_TitleBar`、`agent_step`、`agent_finished`
- `ui/pet_window.py`
- `ui/answer_render.py`

**做：**

1. 写一个“线程 sleep 2 秒后更新 label”的窗口；
2. 故意在工作线程改 label，观察问题；
3. 改主题色并截图。

**验收：**

- 能解释为什么 Agent 线程不能直接改 UI；
- 能画出一次 UI 更新的信号路径。

---

## 阶段三：网络、LLM 与 Prompt（第 6–7 周）

### 第 6 周：HTTP 与 LLM API

**学：**

- HTTP 请求/响应、headers、状态码
- JSON
- API Key / Bearer Token
- 超时、重试、错误分类
- Chat Completions 消息格式
- 图片输入（base64）
- token 与上下文窗口

**读：**

- `core/llm.py` 的 `_payload`、`chat_with_tools`、`image_block`

**做：**

1. 用 `requests` 手写最小 chat 请求；
2. 打印 `usage`，估算 token；
3. 发一张图片给模型。

**验收：**

- 能解释 system/user/assistant/tool 四种角色；
- 能解释为什么“思考模式”可能导致空回答。

---

### 第 7 周：流式、Prompt 与结构化输出

**学：**

- SSE 流式解析
- temperature、top_p、max_tokens
- system prompt 的作用
- few-shot
- JSON Schema / 结构化输出
- 幻觉与事实性

**读：**

- `core/llm.py` 的 `stream_chat`
- `core/conversation.py` 的 `CHAT_SYSTEM_PROMPT`

**做：**

1. 写一个 SSE 逐行解析脚本；
2. 改 system prompt，让回答固定格式；
3. 让模型输出 JSON 并解析。

**验收：**

- 能解释流式和非流式的区别；
- 能写出一个稳定的 system prompt。

---

## 阶段四：Agent 与工具（第 8–9 周）

### 第 8 周：Function Calling 与工具循环

**学：**

- Function Calling 是什么
- tools 的 JSON Schema
- `assistant.tool_calls`
- `role="tool"` 的 `tool_call_id`
- 工具循环、最大步数
- 工具失败如何回填
- 并行工具调用（了解）

**读：**

- `core/conversation.py` 的 `_build_messages`、`_run`
- `core/tools.py` 的 `ToolSpec`、`ToolRegistry`

**做：**

1. 给 `tools.py` 加 `add_numbers(a, b)`；
2. 重启 App，让 Agent 调用；
3. 写一个会抛异常的工具，观察恢复。

**验收：**

- 能画出“模型 → 工具 → 结果 → 模型”的循环；
- 能独立加一个工具。

---

### 第 9 周：Agent 设计、确认与评测

**学：**

- ReAct / Plan-Execute / Reflection
- 危险操作确认
- 超时与取消
- 工具权限
- Prompt 注入
- Agent 评测：成功率、步数、延迟、成本

**读：**

- `core/conversation.py` 的 `_ask_confirmation`
- `core/controller.py` 的 `_on_confirmation`
- `core/word.py`

**做：**

1. 给一个工具加 `dangerous=True` 并确认；
2. 记录 10 次 Agent 任务的成功率/步数；
3. 构造一个“工具返回恶意指令”的例子，理解注入风险。

**验收：**

- 能解释确认机制的线程同步；
- 能说出 Agent 失败时的 3 种恢复策略。

---

## 阶段五：记忆、RAG 与 Prompt 工程（第 10 周）

**学：**

- 短期上下文 vs 长期记忆
- 关键词检索 vs embedding
- 向量、余弦相似度
- chunking、rerank
- 上下文预算
- 记忆整理/去重/冲突

**读：**

- `core/memory.py`
- `core/conversation.py` 的 `_build_messages`

**做：**

1. 评估当前关键词检索的命中率；
2. 用 `sentence-transformers` 做最小语义检索；
3. 给记忆加“来源会话”。

**验收：**

- 能解释 keyword 与 vector 的差别；
- 能设计一个简单的检索评测集。

---

## 阶段六：Windows 与工程化（第 11–12 周）

### 第 11 周：Win32、COM、剪贴板

**学：**

- HWND、前台窗口、进程名
- `RegisterHotKey` + 消息循环
- 屏幕抓取、DPI
- ctypes 调用 Win32
- COM：ProgID、ActiveDocument、Selection
- 剪贴板图片/文件

**读：**

- `core/context.py`
- `core/hotkey.py`
- `core/word.py`
- `core/capture.py`

**做：**

1. 打印当前前台窗口标题/进程；
2. 注册热键；
3. 用 COM 往临时 Word 文档插图片；
4. 读取剪贴板图片。

**验收：**

- 能解释 `CoInitialize`；
- 能解释 DPI 对截图坐标的影响。

---

### 第 12 周：架构、测试、打包、发布

**学：**

- 分层与依赖方向
- 测试金字塔、fake、offline Qt
- 日志与可观测性
- Git 分支/发布/回滚
- PyInstaller / Inno Setup
- 安全：密钥、插件信任、权限

**读：**

- 全项目
- `docs/ARCHITECTURE.md`
- `tests/`

**做（选一个）：**

1. 最终回答流式输出；
2. 拆 `main_window.py`；
3. 新增 Excel 工具 + 测试 + 文档；
4. 打一个最小安装包。

**验收：**

- 能端到端交付：需求 → 代码 → 测试 → 文档 → Git。

---

## 3.9 如果只有 8 周

把以下合并：

- 第 1+2 周 → Python 基础 + 进阶（压缩）
- 第 4+5 周 → Qt（压缩）
- 第 6+7 周 → 网络/LLM（压缩）
- 第 11+12 周 → Windows/工程（压缩）

保留第 8–9 周 Agent 和第 10 周记忆作为重点。

---

# 第 4 章 知识点 → 文件 → 练习

| 知识点 | 对应文件 | 练习 |
| --- | --- | --- |
| Python 类/异常/类型 | 全部 `core/` | 写 dataclass + 异常处理 |
| SQLite | `store.py` | 查会话消息数/加迁移 |
| 线程/锁 | `store.py`、`conversation.py` | 线程安全计数器 |
| Qt 事件/信号 | `main_window.py` | 最小窗口 + 线程更新 |
| QSS | `theme.py` | 改主题色 |
| 绘制 | `pet_art.py` | 画一个简单图形 |
| HTTP/JSON | `llm.py` | 手写 chat 请求 |
| 流式 | `llm.py` | 解析 SSE |
| Prompt | `conversation.py` | 改 system prompt |
| Function Calling | `conversation.py`、`tools.py` | 加 `add_numbers` |
| 工具确认 | `conversation.py`、`controller.py` | 加危险工具 |
| 记忆/RAG | `memory.py` | 检索评测 |
| Win32/热键 | `hotkey.py`、`context.py` | 打印前台窗口 |
| COM/Word | `word.py` | 临时文档插图 |
| 测试 | `tests/` | 给新工具写测试 |
| 打包 | — | PyInstaller 最小 demo |

---

# 第 5 章 前 14 天任务

| 天 | 任务 |
| --- | --- |
| 1 | 跑 App/测试；读 `app.py`；画组件图 |
| 2 | 读 `config.py`；写脚本读配置 |
| 3 | 读 `store.py` 建表；SQL 查库 |
| 4 | 写 dataclass + 日志 |
| 5 | 线程安全计数器 |
| 6 | SQLite 迁移练习 |
| 7 | 复盘 + 笔记 + Git 提交 |
| 8 | 读 `main_window`；写最小 Qt 窗口 |
| 9 | 信号槽/按钮/输入框 |
| 10 | QTimer + 线程更新 label |
| 11 | 改 QSS 主题 |
| 12 | 读 `llm.py`；手写请求 |
| 13 | 图片请求 + token 统计 |
| 14 | 读 `conversation.py` 的 `_build_messages`，画出消息结构 |

---

# 第 6 章 验收题库

能答出 15 题以上，说明框架和基础都过关：

1. `sessions` 和 `messages` 是什么关系？
2. `messages.meta` 存什么？
3. 为什么写 SQLite 要加锁？
4. WAL 是什么？
5. Signal/Slot 解决什么问题？
6. 为什么 Agent 线程不能直接改 UI？
7. `QApplication.exec()` 在做什么？
8. Chat Completions 四种角色分别是什么？
9. 图片怎么发给模型？
10. `tool_calls` 和 `role="tool"` 怎么配对？
11. Agent 循环什么时候停止？
12. 危险工具确认怎么实现？
13. 关键词检索和向量检索的区别？
14. 什么是 prompt 注入？
15. Win32 热键怎么注册？
16. COM 里 `CoInitialize` 为什么需要？
17. 什么是 DPI 缩放，截图坐标为什么要小心？
18. 插件怎么注册成工具？
19. 为什么 `config.json` 不能上传？
20. 如果回答为空，可能有哪些原因？

---

# 第 7 章 资源

- Python：https://docs.python.org/3/
- Qt for Python：https://doc.qt.io/qtforpython-6/
- Qt 事件：https://doc.qt.io/qt-6/eventsandfilters.html
- SQLite：https://www.sqlite.org/docs.html
- DeepSeek API：https://api-docs.deepseek.com/
- OpenAI Function Calling：https://platform.openai.com/docs/guides/function-calling
- Win32：https://learn.microsoft.com/en-us/windows/win32/api/
- pywin32：https://pywin32.readthedocs.io/
- MCP：https://modelcontextprotocol.io/

---

# 第 8 章 进度表

- [ ] 第 1 周：Python 基础
- [ ] 第 2 周：Python 进阶
- [ ] 第 3 周：并发 + SQLite
- [ ] 第 4 周：Qt 基础
- [ ] 第 5 周：Qt 进阶
- [ ] 第 6 周：HTTP + LLM
- [ ] 第 7 周：流式 + Prompt
- [ ] 第 8 周：Function Calling
- [ ] 第 9 周：Agent 设计/确认/评测
- [ ] 第 10 周：记忆/RAG
- [ ] 第 11 周：Win32/COM
- [ ] 第 12 周：架构/测试/打包

---

# 最后：一句话

**先看文件地图知道“有什么”，再看四层框架知道“怎么跑”，最后按 12 周把“为什么”补上。**
