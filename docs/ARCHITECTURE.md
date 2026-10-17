# B站学习助手 · 架构说明

> 版本：2026-10-17 浅色版（对话式 Agent）
> 适用读者：项目作者本人、想维护/扩展这个项目的开发者。

---

## 1. 项目定位

这是一个 **Windows 桌面学习 Agent**，把三件事放在同一个对话里：

1. **看视频时提问**：截图框选 B 站画面 → 问 AI；
2. **让 Agent 干活**：查视频、读文件、写笔记、把图片插入 Word；
3. **长期积累**：对话历史、长期记忆、可视化笔记库。

它不是一个“套壳聊天框”，而是一个完整的 **LLM + 工具调用 + 本地数据 + 桌面 GUI** 应用。

技术栈：

| 层 | 选型 |
| --- | --- |
| 语言 | Python 3.13 |
| GUI | PySide6（Qt 6） |
| LLM | DeepSeek / OpenAI 兼容 Chat Completions + Function Calling |
| 数据 | SQLite（WAL）+ 本地文件 |
| 渲染 | markdown + pygments + matplotlib mathtext |
| Windows | ctypes / Win32、Word COM（pywin32） |
| 测试 | unittest + Qt offscreen |

---

## 2. 运行拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py（主进程）                       │
│                                                             │
│  QApplication（主线程，Qt 事件循环）                          │
│   ├─ MainWindow（对话 / 笔记 / 记忆 / 插件入口）               │
│   ├─ Controller（业务编排）                                   │
│   ├─ ConversationAgent（Agent 循环，工作线程里跑）             │
│   ├─ PetWindow（桌宠，独立窗口）                               │
│   ├─ ContextWatcher（QTimer 记录前台窗口）                     │
│   ├─ HotkeyManager（独立线程，Win32 全局热键）                 │
│   └─ QSystemTrayIcon（托盘常驻）                              │
│                                                             │
│  Store（SQLite，RLock 保护）                                  │
│  Config（config.json）                                       │
│  ToolRegistry（内置工具 + 插件工具）                           │
│  PluginManager（plugins/ + data/plugins/）                    │
└─────────────────────────────────────────────────────────────┘
```

要点：

- **Qt 主线程只做 UI 和轻量调度**；LLM 请求、工具执行在 `ConversationAgent` 的工作线程里。
- 工作线程通过 **Qt Signal** 把 `step / finished / failed` 发回主线程，UI 不直接跨线程改控件。
- 危险工具确认：工作线程发 `confirmation_requested`，主线程弹 `QMessageBox`，再用 `threading.Event` 唤醒工作线程。
- SQLite 连接 `check_same_thread=False`，所有写操作用 `threading.RLock` 串行化。

---

## 3. 目录与模块职责

```
bili-ask/
├── app.py                     # 入口：单实例、QApplication、组件装配、热键、托盘、退出
├── core/                      # 与界面无关的业务核心
│   ├── config.py              # 配置读写（config.json）
│   ├── store.py               # SQLite：会话/消息/笔记/记忆 + 迁移
│   ├── llm.py                 # DeepSeek/OpenAI 兼容客户端、流式、tool calling
│   ├── conversation.py        # ★ 对话式 Agent：消息构建、工具循环、持久化
│   ├── controller.py          # 业务流程：截图/文字 → Agent → UI 回调
│   ├── tools.py               # ToolRegistry + 内置工具定义
│   ├── word.py                # Word COM 自动化（插入图片/文字）
│   ├── context.py             # 前台窗口/视频上下文、ContextWatcher
│   ├── capture.py             # 抓屏、裁剪
│   ├── hotkey.py              # Win32 全局热键线程
│   ├── memory.py              # 长期记忆检索、整理、合并
│   ├── bilibili.py            # B 站视频信息查询（API + 标题兜底）
│   ├── plugins.py             # 插件发现/安装/启用/卸载
│   └── agent.py               # 旧版独立 AgentRunner（保留但新流程不用）
├── ui/
│   ├── main_window.py         # ★ 主窗口：无边框标题栏、会话、对话流、输入框
│   ├── notes_pane.py          # 笔记页：列表 + 编辑器
│   ├── memory_pane.py         # 记忆页
│   ├── answer_render.py       # Markdown/公式/代码 → 富文本 HTML
│   ├── theme.py               # 浅色 QSS 主题
│   ├── pet_window.py          # 桌宠窗口、拖动、全屏隐藏
│   ├── pet_art.py             # 程序化绘制路飞、应用图标
│   ├── capture_overlay.py     # 框选遮罩
│   ├── question_dialog.py     # 截图后提问弹窗
│   ├── settings_dialog.py     # 设置
│   ├── plugins_dialog.py      # 插件管理
│   ├── utils.py               # 时间格式、文本截断、Pixmap 转换
│   ├── agent_pane.py          # 旧 Agent 任务页（新 UI 不用）
│   └── answer_panel.py        # 旧浮动回答面板（新 UI 不用）
├── plugins/study_notes/       # 内置示例插件
├── tests/                     # 50 项单元 + 流程测试
├── assets/                    # 图标、截图
├── data/                      # 运行时数据（gitignore）
├── config.json                # 配置（gitignore，含 API Key）
└── legacy/                    # 旧 Tk 版本
```

> 标 ★ 的是阅读源码时最值得先读的两个文件。

---

## 4. 数据模型（SQLite）

数据库：`data/bili_ask.db`，WAL 模式。

### sessions（一次对话）

| 字段 | 含义 |
| --- | --- |
| `id` | 会话 id（uuid hex） |
| `created_at` | 创建时间（ISO） |
| `question` | 首条用户消息（也用作会话标题） |
| `image_path` | 首张截图相对路径（可空） |
| `model` | 生成时使用的模型 |
| `context` | 首轮屏幕上下文快照 |

### messages（消息）

| 字段 | 含义 |
| --- | --- |
| `id` | 自增 |
| `session_id` | 所属会话 |
| `role` | `user` / `assistant` |
| `content` | 文本（Markdown） |
| `created_at` | 时间 |
| `elapsed_s` | 生成耗时 |
| `image_path` | 消息图片（可空，通常截图在首条用户消息） |
| `meta` | JSON：`{"steps":[工具调用/结果/计划]}`，用于历史回放工具卡片 |

### notes（笔记）

`id, created_at, updated_at, title, content, tags, source_session, pinned`

- Agent 的 `create_note`、对话里的「存为笔记」都写这张表；
- 笔记页直接编辑这张表，与 Agent 共享同一份数据。

### memories（长期记忆）

`id, created_at, updated_at, content, tags, sources, enabled`

- `enabled=0` 的记忆不参与检索；
- `sources` 记录来源会话，便于追溯。

迁移方式：`Store._ensure_columns()` 用 `PRAGMA table_info` 检查缺列并 `ALTER TABLE`。**没有版本号迁移框架**，加字段时沿用这个模式。

---

## 5. 核心流程

### 5.1 文字任务（对话即 Agent）

```
用户输入
  → MainWindow._send()
  → Signal message_sent(sid, text)
  → Controller.send_text()
      ├─ 无 sid：Store.create_session(question, context)
      ├─ Store.add_message(sid, "user", text)
      ├─ MainWindow.open_session(sid)        # 重新载入历史
      └─ ConversationAgent.run(sid)
  → 工作线程 ConversationAgent._run()
      ├─ _build_messages(sid)                # system + 上下文 + 记忆 + 历史(+截图)
      ├─ client.chat_with_tools(messages, tools)
      ├─ 有 tool_calls → 执行工具 → 结果回填 messages → 下一步
      └─ 无 tool_calls → Store.add_message(assistant, meta=steps)
  → Signal finished(sid, text)
  → MainWindow.agent_finished()              # 渲染最终答案
```

### 5.2 截图提问

```
Ctrl+Alt+Q / 双击桌宠 / 点「截图提问」
  → Controller.start_capture()
      ├─ ContextWatcher.best() 记录屏幕上下文
      ├─ 隐藏主窗口（如果可见）
      ├─ grab_primary_screen()
      └─ CaptureOverlay 全屏框选
  → 用户框选 → QuestionDialog 输入问题
  → Store.save_capture()（可关）
  → Store.create_session(question, image_path, context)
  → Store.add_message(user, question, image_path)
  → MainWindow.open_session()
  → ConversationAgent.run(sid)
  → 后续与 5.1 相同；首条用户消息会带图片块
```

> 截图只在唤起时抓一次，不做后台录屏。

### 5.3 Agent 工具循环（伪代码）

`core/conversation.py` 的核心：

```python
messages = [system_prompt] + history
for step in range(max_steps):           # 默认 8
    message = client.chat_with_tools(messages, tools)
    if not message.tool_calls:
        save_assistant(message.content, meta=steps)
        emit finished
        return
    if message.content:
        emit step("assistant", text)
    for call in message.tool_calls:
        emit step("tool_call", name, args)
        if spec.dangerous:
            allowed = ask_main_thread_via_signal()   # 90s 超时
            if not allowed:
                result = "用户拒绝了这次操作"
        else:
            result = registry.execute(name, args)
        emit step("tool_result", name, ok, summary)
        messages.append(tool_result_message)
```

关键限制：

- 最多 8 步，防止死循环；
- 工具结果截断到 6000 字符（`tool` 消息）；
- 最终回答保存 `meta.steps`，历史回放时能重建工具卡片；
- 工具异常不会中断整个 Agent（会变成失败结果回填，模型可换方案）。

### 5.4 危险工具确认

```
工作线程                       主线程
  | confirmation_requested(...)  |
  |----------------------------->| QMessageBox.question(...)
  |  waiter.wait(90s)            |
  |<-----------------------------| agent.resolve_confirmation(id, allowed)
  | 继续执行/拒绝                 |
```

实现：`ConversationAgent._ask_confirmation()` + `Controller._on_confirmation()`。

### 5.5 记忆整理

```
用户点「整理」
  → Controller.consolidate_memories()
  → 后台线程 MemoryManager.consolidate(最近20个会话)
      ├─ 读最近消息
      ├─ 让 LLM 输出 JSON 记忆数组
      ├─ 与已有记忆做相似度合并（SequenceMatcher >= 0.72）
      └─ 写入 memories
  → Signal memory_changed → 刷新记忆页
```

### 5.6 笔记

- 手动：笔记页「新建 / 编辑 / 保存 / 删除 / 导出 .md」；
- 对话：回答右上角「存为笔记」→ `Controller.create_note_from_message()`；
- Agent：工具 `create_note` 直接写 `notes` 表；
- 三个入口共用同一张表，所以随时可以改。

### 5.7 插件加载

```
app.py
  → PluginManager.load_all()
      ├─ 扫描 plugins/（内置）
      ├─ 扫描 data/plugins/（用户安装）
      ├─ 读 plugin.json（enabled、name、version…）
      ├─ import tool.py
      └─ tool.register(registry)  # 注册 ToolSpec
```

插件是 **本机可执行 Python 代码**，当前没有沙箱；只安装信任的插件。安装支持文件夹和 zip，卸载会删目录。

---

## 6. 模块详解

### 6.1 app.py：装配与生命周期

- 单实例：`QLocalServer` 名 `bili-ask-single-v4`；重复启动只唤醒已有窗口；
- 高 DPI：`PassThrough`；
- 浅色主题、应用图标 `assets/luffy_v3.ico`；
- 创建顺序：
  `Config → Store → ContextWatcher → ToolRegistry → PluginManager → MemoryManager → ConversationAgent → MainWindow → Controller → PetWindow → Tray → HotkeyManager`；
- 主窗口居中，避免恢复到一个已离开屏幕的位置；
- 热键：`Q 截图 / A 对话 / H 主界面 / S 设置 / X 退出`；
- 关闭窗口 = 隐藏到托盘；退出走托盘/`Ctrl+Alt+X`，`shutdown()` 停 Agent、热键、托盘、DB。

### 6.2 core/controller.py：业务编排

职责：

- 截图流程（抓屏、遮罩、裁剪、提问弹窗、建会话）；
- 文字消息入口 `send_text`；
- 把 Agent 的 `started/step/finished/failed` 转成 MainWindow 调用；
- 危险工具确认弹窗；
- 笔记创建、记忆整理/启停/编辑/删除、设置、删除会话、退出清理。

它 **不直接调用 LLM**，LLM 只在 `ConversationAgent` 里。

### 6.3 core/conversation.py：真正的 Agent

| 方法 | 作用 |
| --- | --- |
| `run(sid)` | 启动工作线程，防重入 |
| `_build_messages(sid)` | system + 屏幕上下文 + 相关记忆 + 全部历史（首条用户消息附截图） |
| `_run(sid, task, stop_event)` | 工具循环、持久化、发信号 |
| `stop(sid)` | 设置停止事件 |
| `_ask_confirmation` | 危险工具确认 |
| `resolve_confirmation` | 主线程回填确认结果 |

`CHAT_SYSTEM_PROMPT` 定义：先结论后步骤、Markdown/LaTeX、何时记笔记/插入 Word、不要编造工具结果。

### 6.4 core/llm.py：模型客户端

- `DeepSeekClient` 兼容 OpenAI Chat Completions；
- 默认 `thinking=False`（DeepSeek 思考模式会吃光 `max_tokens` 导致空回答）；
- `chat_with_tools(messages, tools)`：非流式，返回 assistant 消息（含 `tool_calls`）；
- `stream_chat(...)`：流式（旧版问答/浮动面板使用，目前主流程不用）；
- `encode_image`：截图转 base64；`image_block` 构造视觉消息块。

### 6.5 core/tools.py：工具注册表

```python
ToolSpec(
    name="insert_image_to_word",
    description="...",
    parameters={...JSON Schema...},
    func=...,
    dangerous=True,
)
```

`ToolRegistry`：

- `register(spec, source=...)`：内置/插件工具统一注册；
- `specs()`：转成 API 的 tools 数组；
- `execute(name, args)`：解析 JSON 参数、执行函数、异常转失败结果；
- `get(name)`：查 ToolSpec（确认时看 dangerous）。

当前内置工具（15 个）：

`get_screen_context, get_bilibili_video, get_current_time, list_directory, read_text_file, write_text_file, create_note, list_notes, get_word_status, insert_image_to_word, insert_screenshot_to_word, insert_clipboard_image_to_word, insert_text_to_word, open_path, extract_bvid`

### 6.6 core/word.py：Word COM

- `_get_word_app()`：优先 `GetActiveObject("Word.Application")`，失败尝试 `KWps.Application`，再 `Dispatch`；
- `_active_document()`：必须有打开的文档和光标位置；
- `insert_image_to_word(path, caption)`：`Selection.InlineShapes.AddPicture(...)` + 图注；
- `insert_screenshot_to_word`：抓当前屏幕再插入；
- `insert_clipboard_image_to_word`：`ImageGrab.grabclipboard()` 支持位图或复制的图片文件；
- `insert_text_to_word`：`Selection.TypeText`；
- 线程内 `pythoncom.CoInitialize()`；只写当前光标，不替换文档。

### 6.7 core/context.py：上下文

`ScreenContext`：窗口标题、进程名、进程 id、视频标题、是否 B 站、BV 号等。

- `get_foreground_context()`：Win32 取前台窗口/进程；
- `_fill_video()`：从浏览器标题里解析 B 站视频名；
- `ContextWatcher`：QTimer 定时记录“最后一个不是本程序的前台窗口”，这样截图时主窗口/桌宠抢焦点也不会丢视频标题；
- `best()`：当前前台是外部窗口就用当前，否则用最近外部快照，否则返回空（避免把自己的窗口当上下文）。

### 6.8 core/memory.py：长期记忆

- 检索：中文 bigram + 词重合度，取最相关 5 条；
- `build_context(question)`：拼成提示词片段；
- `consolidate(session_ids)`：让 LLM 输出 JSON 记忆，与旧记忆相似合并；
- 记忆默认启用，可手动停用/编辑/删除。

关键词检索 ≠ 向量检索；当前没有 embedding。后续可以替换为向量库，但接口（`build_context`）不用变。

### 6.9 core/store.py：数据层

- 初始化建表 + `_ensure_columns` 迁移；
- 会话/消息/笔记/记忆 CRUD；
- `save_capture` 截图落盘到 `data/captures/YYYY-MM-DD/`；
- `import_legacy_jsonl` 导入旧笔记；
- WAL + RLock。

### 6.10 ui/ 层

- `main_window.py`：无边框浅色标题栏、侧边会话列表、对话流、工具卡片、输入框、笔记/记忆页切换；
- `notes_pane.py`：列表 + 编辑器 + 自动保存（1.2s 防抖）；
- `memory_pane.py`：记忆卡片、启停、编辑、删除；
- `answer_render.py`：先把代码/公式/数学环境抽出来，Markdown 转 HTML，再用 pygments 高亮、matplotlib 渲染公式 PNG（data URI），最后内联样式；
- `theme.py`：浅色 QSS；`pet_window.py` / `pet_art.py`：桌宠与图标；
- `capture_overlay.py` / `question_dialog.py`：框选和提问。

> 旧 UI（`agent_pane.py`、`answer_panel.py`）和旧 `core/agent.py` 已不在主流程，保留是为了兼容旧测试/参考，可以后续删除。

---

## 7. 并发与线程模型（重点）

| 工作 | 所在线程 | 说明 |
| --- | --- | --- |
| GUI 事件、控件更新 | Qt 主线程 | 所有 QWidget 操作必须在这里 |
| 热键监听 | `HotkeyManager` 线程 | Win32 消息循环，事件经 `queue.Queue` 回到主线程轮询 |
| Agent LLM + 工具 | 每个会话一个线程 | `ConversationAgent._run` |
| 记忆整理 | 单独线程 | `Controller.consolidate_memories` |
| 截图抓屏 | 主线程（QTimer 延迟后） | 抓屏本身很快；遮罩在主线程 |

跨线程规则：

1. 工作线程 **只发 Signal**，不直接碰控件；
2. 主线程通过 `QTimer`/信号槽处理；
3. 确认弹窗用 `threading.Event` 阻塞工作线程，主线程弹窗；
4. SQLite 写操作用 RLock；不要在持有锁时做网络请求。

常见坑：

- 在 worker 里 `QMessageBox` → 崩/卡死；
- 在 worker 里更新 `QLabel` → 未定义行为；
- `threading.Event.wait()` 没有超时 → 永久卡住（当前 90s）；
- COM 线程未 `CoInitialize` → 调用失败。

---

## 8. 关键设计取舍

| 决策 | 原因 | 代价 |
| --- | --- | --- |
| 对话即 Agent，不单独做任务页 | 用户心智统一，所有工具都在对话里 | 输入框要同时承担问答/任务 |
| 非流式工具循环 | 先拿到 tool_calls 再决定是否继续，逻辑简单可靠 | 最终回答要等工具跑完，首字延迟高 |
| 工具结果存 `meta.steps` | 历史可回放工具卡片 | 消息表 JSON 字段变大 |
| 关键词记忆检索 | 无额外模型/依赖，快 | 语义召回弱于向量检索 |
| 本地 SQLite + 文件 | 隐私、离线、简单 | 多端同步要自己做 |
| 插件进程内执行 | 开发简单，Python 生态直接复用 | 无沙箱，安全靠信任 |
| 浅色无边框标题栏 | 视觉统一，摆脱 Windows 深色标题栏 | 需要自己做拖动/最大化/尺寸调整 |

---

## 9. 安全与隐私

- API Key 只在 `config.json` / 环境变量；`config.json` 已 gitignore。
- 截图落本地 `data/captures/`，不会后台持续录屏。
- 危险工具（写文件、打开程序、插入 Word）带 `dangerous=True`，执行前确认。
- 插件是**本机代码**，没有沙箱；只安装信任的插件。
- 发到 LLM 的内容包括：当前问题、历史消息、截图（如有）、上下文和检索到的记忆；注意敏感信息。
- 分享项目/源码时不要带 `config.json` 和 `data/`；如果 Key 曾泄露，去平台轮换。

---

## 10. 已知限制与技术债

1. **Word 只支持当前打开的文档 + 光标插入**，不创建/排版整篇报告；WPS 兼容性 best-effort。
2. **B 站接口 412 风控**：视频识别主要靠窗口标题，详细信息需 BV 号/链接。
3. **非流式最终回答**：工具执行完才一次性显示，长任务等待感明显。
4. **关键词记忆**，没有 embedding/向量库。
5. **单进程插件无沙箱**，也没有插件签名/权限声明。
6. **`main_window.py` 偏大**（约 690 行），可拆成会话列表、对话流、输入框、标题栏组件。
7. **旧代码残留**：`core/agent.py`、`ui/agent_pane.py`、`ui/answer_panel.py` 不再被主流程使用。
8. **没有数据库版本号**，迁移靠 `ALTER TABLE` 探测。
9. **测试对 GUI 的覆盖有限**：主要覆盖流程/数据，视觉回归靠截图脚本。
10. **没有安装包/自动更新**，目前靠源码 + 快捷方式运行。

---

## 11. 扩展点

### 加一个工具（最快）

1. 在 `core/tools.py` 写函数；
2. `ToolSpec` 注册（危险操作加 `dangerous=True`）；
3. 在 `ConversationAgent` 的 system prompt 里补一句使用场景（可选）；
4. 写测试；
5. 重启 App。

### 加一个插件

`plugins/my_plugin/plugin.json` + `tool.py`：

```python
def register(registry):
    registry.register(ToolSpec(...), source="plugin:my_plugin")
```

放到 `data/plugins/` 或在「插件」里安装。

### 加一个页面

1. 新建 `ui/xxx_pane.py`；
2. `MainWindow._build_main()` 加到 `self.stack`；
3. 侧边栏/底部导航加入口；
4. 业务放入 Controller 或独立类。

### 替换模型/供应商

实现与 `DeepSeekClient` 相同接口的客户端（`chat_with_tools`、`stream_chat`），注入 `ConversationAgent` 的 `llm_factory` 即可。

### MCP / 浏览器扩展

- MCP：把 MCP Server 的工具转成 `ToolSpec`，注册进同一个 registry；
- 浏览器扩展：读取当前标签 URL/字幕，POST 到本地小服务或写共享文件，再由 `ContextWatcher` 读取。

---

## 12. 测试策略

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest discover -s tests -t .
```

覆盖：

- `test_core.py`：配置、Store、会话/上下文、笔记 CRUD、消息 meta；
- `test_flow.py`：连续截图、取消、文字任务/追问、工具步骤持久化、导航、Word 工具注册；
- `test_memory.py`：记忆检索/整理/合并；
- `test_plugins.py`：插件加载/安装/卸载；
- `test_context.py`：前台上下文、B 站标题解析、BV 号；
- `test_render.py`：Markdown/公式/代码/表格/异常公式；
- `test_pet.py`：桌宠状态、双击；
- `agent.py` 旧测试：旧 AgentRunner（仍保留）。

测试用 `ScriptedLLM` / 临时 SQLite 目录，不访问真实 API。

---

## 13. 一句话总结

**App 是壳，Controller 是流程，ConversationAgent 是大脑，ToolRegistry 是手脚，Store 是记忆，Qt 信号槽把线程和界面接起来。**

理解这五者的边界，这个项目就掌握了。
