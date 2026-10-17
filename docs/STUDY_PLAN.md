# Study-AI 系统学习执行计划

> 目标：8 周后能**独立维护 Study-AI**，并能从零搭一个自己的桌面 Agent Demo。
> 节奏：每天 1.5–2 小时，每周 5 天学习 + 1 天整合 + 1 天休息。
> 原则：**以项目为主线，缺什么补什么；每周必须有可运行的代码产出。**

---

## 0. 先定目标：你要学到什么程度

### 最低目标（能维护自己的 App）

- 能改界面颜色/布局、加一个设置项；
- 能加一个工具并让 Agent 调用；
- 能看懂报错、看日志、定位问题；
- 能备份/恢复数据，不弄丢聊天记录。

### 主目标（推荐）

- 理解 Agent 工具循环、上下文、记忆、线程与确认机制；
- 能独立新增一个功能（工具/页面/插件/Word 自动化）；
- 能写测试、写文档、用 Git 管理版本；
- 能解释这个 App 每一层为什么存在。

### 进阶目标（做完 8 周后）

- 流式输出、向量记忆、MCP、浏览器扩展；
- 打包安装包、自动更新；
- 能设计一个新的 Agent 产品，而不是只会改这个项目。

---

## 1. 能力地图（先看全局）

```
L1 Python 工程
   ↓
L2 Qt 桌面 / 事件循环 / 线程边界
   ↓
L3 HTTP / JSON / LLM API / 流式 / token
   ↓
L4 Agent / Function Calling / 工具循环
   ↓
L5 数据 / 记忆 / RAG / Prompt
   ↓
L6 Windows 集成（Win32/ctypes/COM/剪贴板/DPI）
   ↓
L7 软件工程（测试/日志/Git/打包/安全）
```

每周对应一层；L1–L4 是主线，L5–L7 是让你从“能用”到“能交付”。

---

## 2. 8 周总表

| 周 | 主题 | 读哪些文件 | 本周产出 | 验收 |
| --- | --- | --- | --- | --- |
| 1 | Python + 数据层 | `core/config.py`、`core/store.py`、`tests/test_core.py` | 一个查库小脚本 + 笔记 | 能解释四张表 |
| 2 | Qt 桌面基础 | `app.py`、`ui/main_window.py`、`ui/theme.py` | 一个最小 Qt 窗口 | 能解释信号槽/线程边界 |
| 3 | HTTP + LLM API | `core/llm.py` | 命令行 chat demo | 能解释 messages/token/SSE |
| 4 | Agent + 工具 | `core/conversation.py`、`core/tools.py` | 自己的 2 工具 Agent | 能画工具循环 |
| 5 | 记忆 + Prompt | `core/memory.py`、`conversation._build_messages` | 检索评测表 | 能解释关键词 vs 向量 |
| 6 | SQLite/插件/测试 | `core/store.py`、`core/plugins.py`、`tests/` | 一个插件 + 测试 | 能加迁移/写插件 |
| 7 | Windows 集成 | `context.py`、`hotkey.py`、`word.py` | Word 插图脚本 | 能解释 COM/热键/DPI |
| 8 | 架构/重构/发布 | 全项目 + `docs/` | 一个完整新功能 + 测试 + 文档 | 能端到端交付 |

> 如果时间紧，最低限度完成 **1、2、3、4、6** 周，就能独立维护这个项目。

---

## 3. 每周详细任务

### 第 1 周：Python 工程 + 数据层

**学：**

- 类型标注：`str | None`、`list[dict]`、`dataclass`
- 模块/包/`__init__.py`
- 异常与 `logging`
- `pathlib`、`with` 上下文管理器
- `sqlite3`：表、主键、索引、事务、WAL
- `threading.RLock` 为什么存在

**读：**

- `core/config.py`
- `core/store.py` 的 `SCHEMA`、`_ensure_columns`、`add_message`、`notes` CRUD
- `tests/test_core.py`

**做：**

1. 用 SQL 查出每个会话有多少条消息；
2. 写一个 `scripts/list_sessions.py`，打印最近 10 个会话；
3. 给 `sessions` 加一个 `title` 字段的迁移练习（先在自己的分支做）。

**验收：**

- 能画出 `sessions / messages / notes / memories` 关系；
- 能解释为什么写库要加锁。

---

### 第 2 周：Qt 桌面基础

**学：**

- 事件循环 `QApplication.exec()`
- QWidget / 布局 / 对象树
- Signal/Slot、跨线程 `QueuedConnection`
- QTimer
- QSS 与 objectName
- 线程规则：控件只在主线程改

**读：**

- `app.py` 的启动顺序
- `ui/main_window.py`：`_build_ui`、`open_session`、`agent_step`
- `ui/theme.py`

**做：**

1. 写一个最小窗口：按钮点击后启动线程，线程 sleep 2 秒，发信号更新标签；
2. 故意在工作线程里改 QLabel，观察警告/崩溃；
3. 改主题主色，截图对比。

**验收：**

- 能解释为什么 Agent 线程不能直接 `setText`；
- 能画出 `MainWindow → Controller → Agent → MainWindow` 的信号回路。

---

### 第 3 周：HTTP + LLM API

**学：**

- HTTP 方法/headers/状态码/超时
- JSON 序列化
- Bearer Token 认证
- Chat Completions 消息角色：system/user/assistant/tool
- 图片 base64 + 视觉消息
- SSE 流式解析
- token、上下文窗口、`max_tokens`
- 为什么思考模式可能导致空回答

**读：**

- `core/llm.py` 的 `_payload`、`chat_with_tools`、`stream_chat`、`image_block`

**做：**

1. 用 `requests` 手写一个最小 chat 请求；
2. 打印 `usage`，估算一次问答成本；
3. 发一张图片；
4. 写一个 SSE 逐行解析脚本。

**验收：**

- 能解释 `assistant.tool_calls` 和 `role="tool"` 的配对；
- 能解释 `finish_reason=length` 且 content 为空的常见原因。

---

### 第 4 周：Agent + 工具调用（核心）

**学：**

- Function Calling / JSON Schema
- 工具描述为什么是 prompt 的一部分
- 工具循环、最大步数、停止条件
- 工具失败如何回填
- 危险工具确认（Event + 信号）
- Agent 设计模式：ReAct / Plan-Execute / Reflection

**读：**

- `core/conversation.py` 的 `_build_messages`、`_run`、`_ask_confirmation`
- `core/tools.py` 的 `ToolSpec`、`ToolRegistry.execute`

**做：**

1. 给 `tools.py` 加 `add_numbers(a, b)`；
2. 给一个工具加 `dangerous=True`，实现确认；
3. 写一个会抛异常的工具，观察模型如何恢复；
4. 把 max_steps 改成 1，观察失败。

**验收：**

- 能画出“模型 → 工具 → 结果 → 模型”的循环；
- 能独立加一个工具并让 Agent 调用成功。

---

### 第 5 周：记忆 / RAG / Prompt

**学：**

- 短期上下文 vs 长期记忆
- 关键词检索 vs embedding
- 检索、重排、上下文预算
- 记忆整理/去重/冲突
- Prompt 注入与指令层级

**读：**

- `core/memory.py`
- `core/conversation.py` 的 `_build_messages`
- `ui/memory_pane.py`

**做：**

1. 构造 10 个问题，评估当前关键词检索的命中率；
2. 用 `sentence-transformers` 做一个最小语义检索 demo；
3. 给记忆加“来源会话”展示。

**验收：**

- 能解释为什么关键词检索会漏掉同义表达；
- 能说出什么时候该上向量库。

---

### 第 6 周：SQLite / 插件 / 测试 / 安全

**学：**

- schema 设计、索引、事务
- WAL、迁移
- 插件发现/加载/安装
- 单元测试 vs 集成测试、fake LLM
- 插件信任模型、确认机制、密钥管理

**读：**

- `core/store.py`
- `core/plugins.py`
- `tests/test_flow.py` 的 `ScriptedLLM`
- `plugins/study_notes/`

**做：**

1. 写一个自己的插件（例如“查单词”）；
2. 给 `add_numbers` 写测试；
3. 做一次数据库迁移：给 notes 加字段并回填。

**验收：**

- 能解释插件如何注册到 ToolRegistry；
- 能解释危险操作为什么需要确认。

---

### 第 7 周：Windows 集成

**学：**

- HWND、前台窗口、进程名
- `RegisterHotKey` + 消息循环
- 屏幕抓取、DPI、物理/逻辑像素
- ctypes 调用 Win32
- COM：ProgID、ActiveDocument、Selection
- 剪贴板图片/文件

**读：**

- `core/context.py`
- `core/hotkey.py`
- `core/word.py`
- `core/capture.py`

**做：**

1. 打印当前前台窗口标题和进程；
2. 注册一个热键并弹窗；
3. 用 COM 往临时 Word 文档插图片；
4. 读取剪贴板图片并保存。

**验收：**

- 能解释线程里为什么要 `CoInitialize`；
- 能解释 DPI 对截图坐标的影响。

---

### 第 8 周：架构 / 重构 / 发布

**学：**

- 分层与依赖方向（UI 不直接调 LLM）
- 重构手法：拆组件、删死代码
- 日志与可观测性
- 打包（PyInstaller / Inno Setup）
- Git 分支、发布、回滚

**读：**

- 全项目
- `docs/ARCHITECTURE.md`
- `docs/READING_GUIDE.md`

**做（选一个）：**

1. 最终回答流式输出；
2. 把 `main_window.py` 拆成 `title_bar.py`、`chat_view.py`、`composer.py`；
3. 新增一个完整功能（例如 Excel 工具）+ 测试 + 文档；
4. 用 PyInstaller 打一个最小 exe。

**验收：**

- 能端到端交付一个功能：需求 → 代码 → 测试 → 文档 → Git 提交。

---

## 4. 每天怎么学（2 小时模板）

| 时间 | 内容 |
| --- | --- |
| 30 min | 读官方文档/教程，只读今天用得到的部分 |
| 40 min | 读项目对应代码，打断点/加 print |
| 30 min | 写最小实验（20–50 行） |
| 15 min | 写学习笔记：今天的数据流/坑/结论 |
| 5 min | 提交 Git（可选） |

**每周固定产出：**

1. 一个可运行的小实验；
2. 一篇 300–500 字笔记；
3. 一张手画数据流图；
4. 一次 `git commit`。

---

## 5. 前 7 天具体安排（可以直接照做）

### Day 1：跑起来 + 看入口

- 运行 `python app.py`
- 跑测试：
  ```powershell
  $env:QT_QPA_PLATFORM='offscreen'
  python -m unittest discover -s tests -t .
  ```
- 读 `app.py`，画组件创建顺序图。
- 笔记：App 启动时创建了哪些对象？

### Day 2：数据层

- 读 `core/store.py` 的建表 SQL；
- 用 SQLite 工具查 `sessions/messages`；
- 写一个脚本列出最近会话。
- 笔记：`meta` 字段是干什么的？

### Day 3：Qt 信号槽

- 读 `ui/main_window.py` 的 `agent_step`、`agent_finished`；
- 改一个按钮文字/颜色；
- 笔记：为什么 Agent 线程不能直接改 UI？

### Day 4：LLM 消息格式

- 读 `core/llm.py`；
- 手写一个最小请求；
- 打印 usage。
- 笔记：system/user/assistant/tool 各是什么？

### Day 5：Agent 循环

- 读 `core/conversation.py` 的 `_run`；
- 用 `ScriptedLLM` 跑一个不联网的对话；
- 笔记：工具调用循环的停止条件有哪些？

### Day 6：加一个工具

- 在 `core/tools.py` 加 `add_numbers`；
- 重启 App，对 Agent 说“算 123+456”；
- 笔记：工具描述怎么写模型才会用？

### Day 7：复盘

- 画一张完整数据流图；
- 把本周笔记整理成 `notes/week1.md`；
- 提交 Git；
- 列出 3 个还没懂的问题。

---

## 6. 三条学习路线（按你的时间选）

### A. 最低维护线（约 4 周）

第 1、2、3、4、6 周。目标：能改 UI、加工具、看懂报错、备份数据。

### B. 推荐主线（8 周）

全部 8 周。目标：能独立加功能、写测试、做 Windows 自动化。

### C. 进阶 Agent 工程师（8 周 + 4 周）

在 B 之上加：

- 流式 Agent / 工具并行；
- 向量记忆 + 评测集；
- MCP；
- 插件沙箱；
- 打包与自动更新；
- 本地模型（Ollama/vLLM）。

---

## 7. 必读资源（少而精）

- Python：https://docs.python.org/3/
- Qt for Python：https://doc.qt.io/qtforpython-6/
- Qt 事件系统：https://doc.qt.io/qt-6/eventsandfilters.html
- SQLite：https://www.sqlite.org/docs.html
- DeepSeek API：https://api-docs.deepseek.com/
- OpenAI Function Calling：https://platform.openai.com/docs/guides/function-calling
- Win32 API：https://learn.microsoft.com/en-us/windows/win32/api/
- pywin32：https://pywin32.readthedocs.io/
- MCP：https://modelcontextprotocol.io/

---

## 8. 学习记录模板

每次学习后，在 `docs/notes/` 下新建 `weekX-dayY.md`：

```markdown
# Week 1 Day 2

## 今天读了
- core/store.py 的 SCHEMA

## 我理解的数据流
输入 → ... → 输出

## 3 个新概念
1.
2.
3.

## 还没懂的问题
1.

## 明天要做
1.
```

> 不要只收藏教程；**能用自己的话讲清楚 + 能跑出结果**才算学会。

---

## 9. 进度自检

- [ ] 第 1 周：能解释四张表
- [ ] 第 2 周：能解释信号槽和线程边界
- [ ] 第 3 周：能手写 LLM 请求
- [ ] 第 4 周：能独立加一个工具
- [ ] 第 5 周：能解释关键词 vs 向量检索
- [ ] 第 6 周：能写插件和测试
- [ ] 第 7 周：能用 COM 操作 Word
- [ ] 第 8 周：能端到端交付一个功能

完成 6 项以上，你就能独立维护 Study-AI 了。
