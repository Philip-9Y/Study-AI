# Study-AI 整体代码框架

> 目标：用 10 分钟建立全局地图，知道每个模块在系统里的位置、依赖方向、数据怎么流动。
> 更细的线程/数据流见 [ARCHITECTURE.md](ARCHITECTURE.md)，阅读顺序见 [READING_GUIDE.md](READING_GUIDE.md)。

---

## 1. 一句话架构

**UI 只负责显示和收输入；Controller 负责流程；ConversationAgent 负责思考和调工具；ToolRegistry 是手脚；Store 是记忆；Qt 信号槽把线程和界面接起来。**

```
用户
 ↓
MainWindow（UI）
 ↓ Signal / 方法调用
Controller（流程编排）
 ↓
ConversationAgent（Agent 循环，工作线程）
 ├─ DeepSeekClient（LLM / tool calling）
 ├─ ToolRegistry（工具/插件）
 └─ Store（SQLite 持久化）
 ↓ Signal
MainWindow（渲染工具卡片 + 最终答案）
```

---

## 2. 分层框架

```
┌──────────────────────────────────────────────────────────┐
│ 表现层 ui/                                                │
│ MainWindow  对话/会话/输入框/页面切换                       │
│ NotesPane   笔记页      MemoryPane 记忆页                  │
│ PetWindow   桌宠        Dialogs    设置/插件/提问/框选      │
│ Theme/QSS   样式        AnswerRender Markdown/公式/代码     │
└──────────────────────────▲───────────────────────────────┘
                           │ Qt Signal / 方法调用
┌──────────────────────────┴───────────────────────────────┐
│ 编排层 core/controller.py                                 │
│ 截图流程、文字消息、Agent 回调、危险工具确认、笔记/记忆入口   │
└──────────────────────────▲───────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────┐
│ Agent 层 core/conversation.py                             │
│ 构建 messages、工具循环、结果回填、持久化、发信号            │
└──────────────▲──────────────────────────▲────────────────┘
               │                          │
┌──────────────┴──────────┐   ┌───────────┴────────────────┐
│ 模型层 core/llm.py       │   │ 工具层 core/tools.py       │
│ Chat / 视觉 / tool call  │   │ 内置工具 + 插件 + Word COM │
└──────────────────────────┘   └───────────┬────────────────┘
                                           │
┌──────────────────────────────────────────┴────────────────┐
│ 数据/系统层                                                │
│ Store(SQLite)  Memory  Context  Hotkey  Capture  Word      │
└───────────────────────────────────────────────────────────┘
```

**依赖方向很重要：**

- `ui` 可以调用 Controller，但不直接调 LLM；
- `Controller` 不直接调 LLM，只调 Agent；
- `ConversationAgent` 不碰任何 QWidget；
- `Store` 不依赖 UI；
- 工具只通过 `ToolRegistry` 暴露给 Agent。

---

## 3. 启动流程（app.py）

```
QApplication
 → Config（config.json）
 → Store（data/bili_ask.db）
 → ContextWatcher（记录前台窗口）
 → ToolRegistry（build_default_registry）
 → PluginManager.load_all()（plugins/ + data/plugins/）
 → MemoryManager（长期记忆）
 → ConversationAgent（store + config + registry + memory）
 → MainWindow（store + config）
 → Controller（store + config + main + agent + watcher）
 → PetWindow（桌宠）
 → QSystemTrayIcon / HotkeyManager
 → main_window.show_and_raise()
 → app.exec()
```

关键点：

- 单实例：`QLocalServer`；
- 热键线程把事件放进 `queue.Queue`，主线程 `QTimer` 轮询；
- 关闭窗口 = 隐藏到托盘，不是退出；
- 退出时 `controller.shutdown()` 停 Agent、热键、DB。

---

## 4. 核心类与职责

| 类 | 文件 | 职责 | 不应该做什么 |
| --- | --- | --- | --- |
| `MainWindow` | `ui/main_window.py` | 显示会话/消息/笔记/记忆，收输入，发起截图；渲染工具卡片和答案 | 不直接请求 LLM、不直接写 SQL |
| `Controller` | `core/controller.py` | 截图/文字流程、建会话、确认弹窗、记忆/笔记入口、UI 回调 | 不实现 Agent 循环 |
| `ConversationAgent` | `core/conversation.py` | 构建 messages、跑工具循环、持久化、发 step/finished 信号 | 不创建/修改 QWidget |
| `DeepSeekClient` | `core/llm.py` | HTTP 请求、消息格式、tool calling、流式、图片编码 | 不关心数据库/UI |
| `ToolRegistry` | `core/tools.py` | 注册/查找/执行工具，JSON 参数解析，异常转失败结果 | 不决定何时调用工具（模型决定） |
| `ToolSpec` | `core/tools.py` | 工具名、描述、JSON Schema、执行函数、是否危险 | — |
| `Store` | `core/store.py` | 会话/消息/笔记/记忆 CRUD，截图路径，迁移 | 不含业务判断 |
| `MemoryManager` | `core/memory.py` | 记忆检索、拼 prompt、LLM 整理/合并 | 不直接改 UI |
| `ContextWatcher` | `core/context.py` | 定时记录最后一个外部前台窗口，供截图时使用 | 不做 OCR |
| `PluginManager` | `core/plugins.py` | 扫描/安装/启停插件，往 registry 注册工具 | 不执行具体工具逻辑 |
| `Word` 工具 | `core/word.py` | COM 操作当前 Word 文档：插图/文字/剪贴板 | 不排版整篇文档 |

> 旧版 `core/agent.py`、`ui/agent_pane.py`、`ui/answer_panel.py` 已不在主流程，可忽略。

---

## 5. 一次文字任务的数据流

```
① MainWindow._send()
      ↓ message_sent(sid, text)
② Controller.send_text()
      ├─ 无 sid：Store.create_session(question, context)
      ├─ Store.add_message(user)
      ├─ MainWindow.open_session(sid)     # 重载历史
      └─ ConversationAgent.run(sid)
③ ConversationAgent（worker thread）
      ├─ _build_messages(sid)
      │    ├─ system prompt
      │    ├─ 屏幕上下文
      │    ├─ 相关记忆
      │    ├─ 历史 user/assistant（首条可带截图）
      │    └─ 本次 user 消息
      ├─ DeepSeekClient.chat_with_tools()
      ├─ 有 tool_calls → ToolRegistry.execute()
      │       ├─ 危险工具 → 信号 → 主线程 QMessageBox → Event 唤醒
      │       └─ 结果回填 role=tool
      └─ 最终无 tool_calls
             ├─ Store.add_message(assistant, meta={"steps":...})
             └─ finished(sid, text)
④ MainWindow.agent_finished()
      └─ render_answer() → 最终富文本
```

**为什么要 `meta.steps`？**
把工具调用/结果存进消息，重新打开历史时才能重建工具卡片。

---

## 6. 一次截图任务的数据流

```
Ctrl+Alt+Q / 双击桌宠 / 点“截图提问”
 → Controller.start_capture()
     ├─ ContextWatcher.best() 记录屏幕上下文
     ├─ 隐藏主窗口（如可见）
     ├─ grab_primary_screen()
     └─ CaptureOverlay 全屏框选
 → 用户框选
 → QuestionDialog 输入问题
 → Store.save_capture()（可配置关闭）
 → Store.create_session(question, image_path, context)
 → Store.add_message(user, question, image)
 → MainWindow.open_session()
 → ConversationAgent.run()
 → 之后与文字任务相同
```

截图只在唤起时抓一次，不做后台录屏。

---

## 7. 线程与信号框架

| 工作 | 线程 | 说明 |
| --- | --- | --- |
| UI 事件、控件 | Qt 主线程 | 所有 QWidget 只能在这里改 |
| Agent LLM + 工具 | 每个会话一个 worker 线程 | `_run` |
| 全局热键 | `HotkeyManager` 线程 | Win32 消息循环 → `queue.Queue` |
| 记忆整理 | 单独线程 | `Controller.consolidate_memories` |
| SQLite | 主线程/worker 共用 | `check_same_thread=False` + `RLock` |

跨线程规则：

1. worker 只发 Signal；
2. 主线程槽里更新 UI；
3. 危险工具确认：worker 发 `confirmation_requested`，主线程弹窗，worker 用 `Event.wait(90)`；
4. 不要在 worker 里创建/修改 QWidget。

Agent 信号：

| 信号 | 参数 | 作用 |
| --- | --- | --- |
| `started` | `sid` | 开始生成 |
| `step` | `sid, dict` | 工具调用/结果/计划 |
| `finished` | `sid, text` | 最终答案（已入库） |
| `failed` | `sid, message` | 失败 |
| `confirmation_requested` | `request_id, tool, args_json` | 请求确认 |

---

## 8. 数据模型框架

```
sessions 1 ─── n messages
   │
   └─ context（首轮屏幕上下文）
   └─ image_path（首张截图）

notes     独立表：Agent/对话/笔记页共用
memories  独立表：启停、检索、整理
```

| 表 | 关键字段 | 用途 |
| --- | --- | --- |
| `sessions` | `id, created_at, question, image_path, model, context` | 一次对话 |
| `messages` | `session_id, role, content, image_path, elapsed_s, meta` | 消息 + 工具步骤 |
| `notes` | `title, content, tags, source_session, pinned` | 笔记 |
| `memories` | `content, tags, sources, enabled` | 长期记忆 |

数据库：`data/bili_ask.db`，WAL，`Store._ensure_columns()` 做简单迁移。

---

## 9. 工具框架

```python
ToolSpec(
    name="insert_image_to_word",
    description="把图片插入当前 Word 文档光标处...",
    parameters={... JSON Schema ...},
    func=insert_image_to_word,
    dangerous=True,
)
```

`ToolRegistry`：

- `register(spec, source=...)`：内置工具和插件工具统一注册；
- `specs()`：转成 API 的 `tools` 数组；
- `execute(name, args)`：解析 JSON、执行、异常转失败结果；
- `get(name)`：确认时查看 `dangerous`。

工具来源：

```
core/tools.py          内置 15 个
plugins/*/tool.py      内置插件
data/plugins/*/tool.py 用户安装插件
```

---

## 10. 渲染框架

```
回答 Markdown
 ├─ 代码块 → pygments 高亮
 ├─ 公式 $$...$$ / $...$ → matplotlib mathtext → PNG data URI
 ├─ 表格/引用/标题 → markdown → HTML + 内联样式
 └─ QLabel/QTextBrowser 显示
```

缓存：

- `data/math_cache/`：公式 PNG；
- `render_answer` 的 LRU 缓存。

---

## 11. 如果我要改 X，动哪里

| 需求 | 修改位置 |
| --- | --- |
| 改主题/颜色 | `ui/theme.py`、`ui/answer_render.py` 的颜色常量 |
| 改主界面布局 | `ui/main_window.py` |
| 加一个工具 | `core/tools.py` + 测试 + system prompt 提示 |
| 加一个插件 | `plugins/<name>/plugin.json` + `tool.py` |
| 改 Agent 行为 | `core/conversation.py` 的 `CHAT_SYSTEM_PROMPT` / `_run` |
| 改记忆检索 | `core/memory.py` |
| 改数据库字段 | `core/store.py` 的 `SCHEMA` + `_ensure_columns` |
| 改截图流程 | `core/controller.py` + `ui/capture_overlay.py` |
| 改 Word 插入 | `core/word.py` |
| 换模型/供应商 | `core/llm.py` 或注入 `llm_factory` |
| 改笔记页 | `ui/notes_pane.py` |
| 改桌宠 | `ui/pet_window.py` / `ui/pet_art.py` |

---

## 12. 代码规模与重点

| 文件 | 行数级别 | 重要度 |
| --- | --- | --- |
| `ui/main_window.py` | ~690 | ★★★ 主界面，最大 |
| `core/store.py` | ~350 | ★★★ 数据 |
| `core/tools.py` | ~350 | ★★★ 工具 |
| `core/controller.py` | ~300 | ★★★ 流程 |
| `ui/answer_render.py` | ~260 | ★★ 渲染 |
| `core/conversation.py` | ~240 | ★★★ Agent 核心 |
| `core/llm.py` | ~200 | ★★ 模型 |
| `core/memory.py` | ~150 | ★★ 记忆 |
| `core/context.py` | ~160 | ★★ 上下文 |
| `core/word.py` | ~130 | ★★ Word |

---

## 13. 框架的优点与边界

**优点：**

- UI/业务/模型/工具边界清楚；
- 工具统一注册，内置和插件同协议；
- 工具步骤持久化，历史可回放；
- 数据本地化，隐私可控；
- 线程通过信号回主线程，符合 Qt 规则。

**边界/技术债：**

- 最终回答非流式；
- 记忆是关键词检索，不是向量；
- 插件无沙箱；
- `main_window.py` 偏大；
- 旧代码 `agent.py` / `agent_pane.py` / `answer_panel.py` 可删；
- 没有数据库版本号迁移框架；
- Word 只操作当前文档光标。

---

## 14. 5 分钟看懂框架的顺序

1. 看 `app.py` 的 `main()`：组件怎么创建；
2. 看 `ui/main_window.py` 的 `_build_ui` / `_send`：UI 怎么收输入；
3. 看 `core/controller.py` 的 `send_text`：流程怎么接；
4. 看 `core/conversation.py` 的 `_build_messages` / `_run`：Agent 怎么思考；
5. 看 `core/tools.py` 的 `ToolSpec` / `execute`：工具怎么执行；
6. 看 `core/store.py` 的 `add_message`：结果怎么保存。

---

## 15. 一句话记住

**MainWindow 是脸，Controller 是流程，ConversationAgent 是大脑，ToolRegistry 是手脚，Store 是记忆，Signal 是神经。**
