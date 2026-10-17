# 系统学习路线：从“会用 Python”到“能独立做桌面 Agent”

> 这个项目表面是“B 站学习助手”，本质是 7 层技术的组合：
> **Python 工程 → Qt 桌面 → HTTP/LLM → Agent/工具调用 → 数据/记忆 → Windows 系统集成 → 软件工程。**
>
> 下面是一条可以照着走 8 周的路线。每天 1.5–2 小时，周末做整合练习。

---

## 0. 先建立正确的心智模型

不要按“语法书目录”学，按 **数据流** 学。这个项目的数据流是：

```
用户操作
  → Qt 事件
  → Controller 编排
  → Agent 组织 messages
  → HTTP 请求 LLM
  → 模型返回 tool_calls
  → 本地执行工具
  → 结果回填模型
  → 最终文本 → Markdown/公式渲染 → 数据库
```

每学一个知识点，都问自己：

1. 它在这条链的哪一段？
2. 没有它，会出什么问题？
3. 我能写一个 20 行的小实验验证它吗？

---

## 1. 能力地图

| 层级 | 需要掌握 | 本项目对应 |
| --- | --- | --- |
| L1 Python 工程 | 类型标注、模块、异常、OOP、虚拟环境、包管理 | 所有 `core/` |
| L2 GUI/事件循环 | Qt 对象树、Signal/Slot、QTimer、线程边界、QSS | `ui/` |
| L3 网络/LLM | HTTP、JSON、SSE、Chat Completions、视觉输入、token | `core/llm.py` |
| L4 Agent | Function Calling、工具注册、循环、确认、错误恢复 | `core/conversation.py`、`core/tools.py` |
| L5 数据/记忆 | SQLite、schema、事务、检索、整理、prompt | `core/store.py`、`core/memory.py` |
| L6 Windows | Win32 窗口、全局热键、抓屏、DPI、COM、剪贴板 | `core/hotkey.py`、`context.py`、`word.py` |
| L7 软件工程 | 测试、日志、配置、安全、打包、版本管理 | `tests/`、`app.py`、`git` |

---

## 2. 前置：Python 工程能力（3–5 天）

### 必须会

- 模块/包/`__init__.py`、相对导入；
- 类型标注：`str | None`、`list[dict]`、`Signal(str, dict)`；
- 类、继承、`@property`、dataclass；
- 异常处理与日志（`logging`）；
- 上下文管理器（`with`）；
- 线程：`threading.Thread`、`Event`、`Lock/RLock`；
- 虚拟环境/依赖管理（`pip`、`requirements.txt`）。

### 本项目里的例子

- `core/store.py`：`RLock` + `with self._lock, self._conn`；
- `core/conversation.py`：daemon 线程、停止事件、确认等待；
- `core/tools.py`：函数当参数、JSON Schema、异常转结果；
- `ui/*.py`：类组合、信号声明。

### 小实验

1. 写一个线程安全的计数器；
2. 写一个“超时 3 秒就放弃”的 `Event` 示例；
3. 用 `dataclass` 定义 `ScreenContext` 的简化版。

### 资源

- Python 官方教程：https://docs.python.org/3/tutorial/
- Python 类型提示：https://docs.python.org/3/library/typing.html
- `threading`：https://docs.python.org/3/library/threading.html

---

## 3. Qt / PySide6：事件循环与线程边界（1–2 周）

这是桌面应用最重要的底层知识。

### 必须理解

1. **事件循环**：`QApplication.exec()` 是一个 while 循环，不断取事件、分发到控件；
2. **Signal/Slot**：对象间解耦；跨线程默认是 **QueuedConnection**，槽在主线程执行；
3. **对象树与所有权**：parent 负责析构；`deleteLater` 的安全删除；
4. **QTimer**：单次/周期任务；为什么截图前要 `singleShot(180, ...)`；
5. **线程规则**：QWidget 只能在主线程创建/修改；工作线程发信号；
6. **QSS**：类似 CSS 的样式表；选择器、objectName、动态属性；
7. **自定义绘制**：`QPainter`（桌宠、图标）；
8. **无边框窗口**：`FramelessWindowHint`、`startSystemMove`、`QSizeGrip`。

### 对应源码

- `app.py`：`QApplication`、`QTimer` 轮询热键队列；
- `ui/main_window.py`：`_TitleBar`、`stack`、Signal 声明、`agent_step`；
- `ui/pet_window.py`：透明窗口、拖动、`QPainter`；
- `ui/capture_overlay.py`：全屏透明遮罩 + 鼠标框选；
- `ui/theme.py`：QSS。

### 关键实验

1. 写一个 QDialog，点按钮后启动线程，线程 `sleep(2)` 后发信号更新 label；
2. 故意在工作线程里 `label.setText(...)`，观察崩溃/警告；
3. 写一个 `QTimer` 每秒更新倒计时；
4. 用 QSS 改按钮颜色，理解 `objectName`。

### 资源

- Qt for Python 文档：https://doc.qt.io/qtforpython-6/
- 事件系统：https://doc.qt.io/qt-6/eventsandfilters.html
- Signal/Slot：https://doc.qt.io/qt-6/signalsandslots.html
- QThread：https://doc.qt.io/qt-6/qthread.html

---

## 4. HTTP、JSON 与 LLM API（1 周）

### 必须理解

- HTTP 方法/状态码/headers/body；
- JSON 序列化；
- 认证：`Authorization: Bearer <key>`；
- 超时、重试、错误分类（401/429/5xx/网络）；
- **Chat Completions 的消息格式**：
  - `system`：角色/规则；
  - `user` / `assistant`：对话；
  - `tool`：工具结果；
- **视觉输入**：图片 base64 放进 user content；
- **SSE 流式**：`data: {...}` 逐行解析；
- **token 与上下文窗口**：max_tokens、截断、成本；
- **思考模式**：`reasoning_content` 可能吃光预算，导致 content 为空。

### 对应源码

`core/llm.py`：

- `DeepSeekClient._payload`：`thinking`、`temperature`、`max_tokens`；
- `stream_chat`：SSE 解析；
- `chat_with_tools`：非流式工具调用；
- `image_block`：视觉消息。

### 实验

1. 用 `requests` 手写一个最小 chat 请求（不带 SDK）；
2. 打印 `usage`，算一次问答大概多少 token；
3. 用 `curl` 发一个带图片的请求；
4. 解析 SSE：逐行打印 `delta.content`。

### 资源

- DeepSeek API：https://api-docs.deepseek.com/
- OpenAI Chat API：https://platform.openai.com/docs/api-reference/chat
- SSE（MDN）：https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

---

## 5. Agent 与 Function Calling（1–2 周，核心）

### 必须理解

1. **LLM 本身不会执行工具**：它只输出“我想调用某个函数 + 参数”；
2. **工具描述就是 prompt**：`description` 和参数 schema 决定模型会不会用对；
3. **循环**：
   ```
   model → tool_calls → 本地执行 → tool 消息 → model → … → 最终文本
   ```
4. **消息角色必须配对**：assistant 的 tool_calls 和 tool 消息的 `tool_call_id`；
5. **并行工具调用**：一次返回多个 tool_calls；
6. **停止条件**：无 tool_calls / 最大步数 / 用户停止；
7. **错误恢复**：工具失败作为结果回填，让模型换方案；
8. **危险操作**：确认、超时、拒绝；
9. **Agent 设计模式**：ReAct、Plan-and-Execute、Reflection、Router；
10. **评测**：任务成功率、步数、延迟、成本、工具误用率。

### 对应源码

- `core/conversation.py`：完整循环；
- `core/tools.py`：`ToolSpec` / `ToolRegistry.execute`；
- `core/word.py`：真实副作用工具；
- `ui/main_window.py`：工具卡片渲染；
- `tests/test_flow.py::test_tool_calls_persisted_in_meta`。

### 实验

1. 用 20 行代码实现一个只有 `get_time` 工具的 Agent；
2. 加一个会抛异常的工具，观察模型如何恢复；
3. 给工具加 `dangerous=True`，实现确认；
4. 把最大步数改成 1，观察任务失败方式。

### 资源

- OpenAI Function Calling：https://platform.openai.com/docs/guides/function-calling
- Anthropic《Building effective agents》：https://www.anthropic.com/research/building-effective-agents
- MCP 协议：https://modelcontextprotocol.io/

---

## 6. 记忆、RAG 与 Prompt（1 周）

### 必须区分

- **短期上下文**：本次对话的 messages；
- **长期记忆**：跨会话保存的偏好/知识点；
- **检索**：关键词 vs 向量（embedding）；
- **整理/合并**：去重、冲突消解、摘要；
- **Prompt 注入**：外部内容不能当指令；
- **上下文预算**：不是越多越好，噪声会降低效果。

### 本项目实现

`core/memory.py`：

- 中文 bigram + 词重合度筛选 top 5；
- `build_context(question)` 拼提示词；
- `consolidate()` 让 LLM 输出 JSON 记忆并合并相似项。

这是“轻量 RAG”，不是向量数据库。升级路径：

```
关键词检索 → embedding + 向量库（sqlite-vec / chroma / faiss）
           → rerank → 按课程/主题分层
```

### 实验

1. 给记忆加一个“来源会话”展示；
2. 用 `sentence-transformers` 做最小语义检索 demo；
3. 构造一条无关记忆，验证不会被注入。

### 资源

- RAG 原始论文：https://arxiv.org/abs/2005.11401
- SQLite 向量扩展：https://github.com/asg017/sqlite-vec
- Prompt Engineering Guide：https://www.promptingguide.ai/

---

## 7. SQLite 与数据建模（3–5 天）

### 必须理解

- 表/主键/索引/外键；
- `INSERT/UPDATE/SELECT/DELETE`；
- 事务与 `with conn`；
- WAL 模式（读写并发更好）；
- 参数化查询防注入；
- 迁移（加列/加表）；
- 连接与线程（`check_same_thread=False` + 锁）。

### 对应源码

`core/store.py`：

- `SCHEMA`；
- `_ensure_columns`；
- `add_message(meta=...)`；
- notes/memories CRUD；
- `save_capture` 文件路径。

### 实验

1. 用 SQL 查出“每个会话有多少条消息”；
2. 给 notes 加一个 `pinned` 排序；
3. 写一个迁移：给 sessions 加 `title` 列并回填。

### 资源

- SQLite 文档：https://www.sqlite.org/docs.html
- WAL：https://www.sqlite.org/wal.html
- Python sqlite3：https://docs.python.org/3/library/sqlite3.html

---

## 8. Windows 桌面集成（1 周）

### 8.1 Win32 基础

- 窗口句柄 HWND、窗口标题、进程 id；
- `GetForegroundWindow`、`GetWindowTextW`、`GetWindowThreadProcessId`；
- 全局热键 `RegisterHotKey` + 消息循环；
- 屏幕抓取（Qt `QScreen.grabWindow`）；
- DPI 感知：物理像素 vs 逻辑像素。

对应：`core/context.py`、`core/hotkey.py`、`core/capture.py`、`ui/capture_overlay.py`。

### 8.2 ctypes

- 定义函数签名、结构体、缓冲区；
- 错误处理 `use_last_error`；
- 调用 user32/dwmapi。

### 8.3 COM 自动化（Word）

- COM 对象、ProgID、`GetActiveObject` / `Dispatch`；
- 线程里 `pythoncom.CoInitialize()`；
- `Selection`、`InlineShapes.AddPicture`、`TypeText`；
- 不替换用户文档，只操作当前光标。

对应：`core/word.py`。

### 8.4 剪贴板

- 图片位图 vs 文件列表；
- `PIL.ImageGrab.grabclipboard()`。

### 实验

1. 打印当前前台窗口标题/进程名；
2. 注册一个热键，按下弹 message box；
3. 抓屏保存 PNG；
4. 用 COM 往一个临时 Word 文档插图片（不要动用户文档）。

### 资源

- Win32 API：https://learn.microsoft.com/en-us/windows/win32/api/
- COM 入门：https://learn.microsoft.com/en-us/windows/win32/com/component-object-model--com--portal
- pywin32：https://pywin32.readthedocs.io/
- DPI：https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows

---

## 9. 软件工程与产品化（持续）

### 必须会

- 测试金字塔：单元 / 集成 / 手工冒烟；
- 用 fake 替代外部 API；
- 日志分级与上下文；
- 配置与密钥分离；
- Git 分支/提交/回滚；
- 代码审查与重构；
- 打包（PyInstaller / Inno Setup）；
- 安全：密钥、权限、插件信任、prompt injection。

### 对应源码/工具

- `tests/`：50 项测试；
- `data/app.log`：日志；
- `.gitignore`：排除 config/data；
- `README.md`：使用文档；
- `docs/`：架构与阅读指南。

### 练习

1. 给一个工具写单元测试；
2. 用 `git` 做一次功能分支 + 合并；
3. 用 PyInstaller 打一个 exe（先只打最小 demo）；
4. 写一份 CHANGELOG。

---

## 10. 8 周计划（可直接照做）

| 周 | 主题 | 学 | 做 | 产出 |
| --- | --- | --- | --- | --- |
| 1 | Python + 数据层 | 类型/异常/线程/SQLite | 读 `config.py/store.py`；SQL 练习 | 能解释四张表 |
| 2 | Qt 基础 | 事件循环/信号槽/QTimer/QSS | 读 `main_window/theme`；写小窗口 | 一个可交互小 GUI |
| 3 | HTTP + LLM | JSON/SSE/视觉/token | 读 `llm.py`；手写请求 | 命令行 chat demo |
| 4 | Agent | Function Calling/循环/确认 | 读 `conversation/tools`；加工具 | 自己的小 Agent |
| 5 | 记忆 + Prompt | 检索/合并/上下文预算 | 读 `memory.py`；改检索 | 记忆评测表 |
| 6 | 数据/插件/安全 | 迁移/插件/确认/信任 | 读 `store/plugins`；写插件 | 可安装插件 |
| 7 | Windows 集成 | Win32/ctypes/COM/DPI | 读 `context/hotkey/word`；写脚本 | Word 插图工具 |
| 8 | 整合/重构/打包 | 测试/日志/打包 | 加一个小功能 + 测试 + 文档 | 可交付版本 |

每天固定节奏：

- 30 分钟读官方文档；
- 40 分钟读本项目对应代码；
- 30 分钟写实验；
- 10 分钟记笔记（画数据流）。

---

## 11. 进阶主题（做完 8 周后）

1. **流式 Agent**：工具结束后流式输出最终答案，降低首字延迟；
2. **上下文预算管理**：按 token 截断历史/记忆，摘要压缩；
3. **多 Agent / 子 Agent**：任务分解、并行、结果汇总；
4. **MCP**：标准化工具接入；
5. **评测体系**：构造 30 个真实学习任务，量化成功率/步数/成本；
6. **可观测性**：每步耗时、token、工具错误率、trace id；
7. **插件沙箱**：子进程 + 权限声明 + 资源限制；
8. **本地模型**：Ollama / vLLM，离线可用；
9. **多模态**：音频转写、视频理解、OCR；
10. **打包与更新**：安装包、签名、自动更新。

---

## 12. 推荐资源（少而精）

### 官方文档（优先）

- Python：https://docs.python.org/3/
- Qt for Python：https://doc.qt.io/qtforpython-6/
- Qt 事件系统：https://doc.qt.io/qt-6/eventsandfilters.html
- SQLite：https://www.sqlite.org/docs.html
- DeepSeek API：https://api-docs.deepseek.com/
- OpenAI Function Calling：https://platform.openai.com/docs/guides/function-calling
- Microsoft Win32：https://learn.microsoft.com/en-us/windows/win32/api/
- pywin32：https://pywin32.readthedocs.io/
- MCP：https://modelcontextprotocol.io/

### 书/长文

- 《Fluent Python》（深入 Python 对象模型/并发）
- 《Designing Data-Intensive Applications》（数据系统思维）
- Anthropic《Building effective agents》
- RAG 论文：https://arxiv.org/abs/2005.11401

### 练习平台

- LeetCode（基础算法，不必刷太多）
- 自己项目的 issues 列表（最有效）

---

## 13. 学习方法的三个建议

1. **每读一个模块，画一张数据流图**：输入、输出、线程、失败路径。
2. **每学一个概念，写一个最小实验**：20–50 行，能跑就行。
3. **每改一个功能，补一个测试 + 更新文档**：这是从“会写”到“能维护”的分水岭。

---

## 14. 这个项目最值得你深入的三件事

1. **Agent 循环**（`conversation.py`）：这是所有 Agent 产品的心脏；
2. **工具协议**（`tools.py`）：决定 Agent 的能力边界；
3. **线程/信号/确认**（`main_window.py` + `controller.py`）：决定桌面 Agent 是否稳定。

把这三件事吃透，再换任何 GUI/模型/工具生态，你都能快速搭出下一个 Agent。
