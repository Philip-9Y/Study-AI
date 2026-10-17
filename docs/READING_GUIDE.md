# 源码阅读指南

> 目标：不是“从第一行读到最后一行”，而是能回答：
> **一次点击之后，数据在哪些模块之间流动？为什么这样设计？如果我要改，改哪里？**

---

## 0. 先跑起来

### 环境

```powershell
cd "D:\deepseek harness workplace\usually\Study-AI"
python -m pip install -r requirements.txt
```

`config.json` 里填 DeepSeek API Key（或设置环境变量 `DEEPSEEK_API_KEY`）。

### 两种启动方式

```powershell
# 正常启动
python app.py

# 自检：注册热键，1.6 秒后自动退出（不真的收消息）
python app.py --check
```

### 测试（不弹窗）

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest discover -s tests -t . -v
```

### 日志与数据

- 运行日志：`data/app.log`
- 数据库：`data/bili_ask.db`（SQLite）
- 截图：`data/captures/YYYY-MM-DD/`
- 配置：`config.json`（不要提交/外发）

---

## 1. 阅读方法

### 1.1 先画主线，再看细节

这个项目只有一条主链路：

```
UI 输入 → Controller → ConversationAgent → LLM/Tools → Store → UI 渲染
```

其他模块都是这条线的分支：

- 截图：Controller 先抓图/建会话，再进同一条 Agent 链；
- 记忆：Agent 构建 prompt 时读，整理时写；
- 笔记：Agent 工具写 / 笔记页直接写；
- 插件：往 ToolRegistry 里加工具；
- 桌宠/热键：只是触发 Controller 的入口。

### 1.2 用“断点 + 数据”验证理解

推荐在以下位置打断点（PyCharm / VS Code）：

| 断点 | 看什么 |
| --- | --- |
| `Controller.send_text` | sid 是否为空、文本、上下文 |
| `ConversationAgent._build_messages` | system prompt、历史条数、是否带图片、记忆是否注入 |
| `ConversationAgent._run` 的 `chat_with_tools` 返回 | content、tool_calls、finish_reason |
| `ToolRegistry.execute` | 工具名、参数、返回值、异常 |
| `ConversationAgent._run` 的保存消息处 | meta.steps 的 JSON |
| `MainWindow.agent_step` | 工具卡片如何被追加 |

### 1.3 读代码时一直问三个问题

1. **数据从哪来？**（参数/数据库/信号）
2. **它在哪个线程？**（主线程 / Agent 线程 / 热键线程）
3. **失败会怎样？**（异常、超时、空回答、工具拒绝）

---

## 2. 推荐阅读顺序

> 按 6 个阶段读，每阶段 1–3 小时。不要一上来啃 `main_window.py`。

### 阶段 1：入口与装配（约 1 小时）

读 `app.py`：

- `main()` 里组件创建顺序；
- 单实例 `QLocalServer` 如何实现；
- 热键线程如何把事件放进 `queue.Queue`，主线程 `QTimer` 轮询；
- 托盘菜单、退出清理；
- `--check` 模式。

要能回答：

- 为什么 `ContextWatcher` 要在 `Controller` 之前创建？
- 关闭窗口为什么不是退出？`quit_app` 做了哪些清理？
- App 启动时 `main_window` 和 `pet` 谁先显示？

### 阶段 2：数据与配置（约 1.5 小时）

读 `core/config.py`、`core/store.py`。

重点：

- 四张表：`sessions / messages / notes / memories`；
- `messages.meta` 存工具步骤；
- `_ensure_columns()` 怎么做迁移；
- `save_capture` 的路径规则；
- `RLock` 包住哪些写操作。

练习：

```powershell
python - <<'PY'
import sqlite3
conn = sqlite3.connect(r"data/bili_ask.db")
for row in conn.execute("select id, role, substr(content,1,40), meta is not null from messages order by id desc limit 10"):
    print(row)
PY
```

### 阶段 3：模型与消息格式（约 1.5 小时）

读 `core/llm.py`。

重点：

- OpenAI 兼容的消息结构：`system / user / assistant / tool`；
- `image_block` 如何把 base64 图片放进 `user` content；
- `thinking=False` 为什么重要；
- `chat_with_tools` 的请求体：`tools`、`tool_choice`；
- `stream_chat` 与 SSE 的解析（即使当前主流程不用，也值得理解）。

要能回答：

- `tool_calls` 和 `role="tool"` 的关系？
- 为什么 `finish_reason=length` 可能返回空 content？
- 图片 token 大概怎么计费/占上下文？

### 阶段 4：Agent 核心（约 2–3 小时，最重要）

读 `core/conversation.py`，配合 `core/tools.py`。

顺序：

1. `_build_messages`：system prompt 里有什么？
2. `_run`：循环、最大步数、工具调用、结果回填；
3. `_ask_confirmation`：如何阻塞等待主线程；
4. `finished/failed` 信号如何回到 UI；
5. `ToolRegistry.execute`：JSON 参数、异常处理。

练习（非常推荐）：

> 在 `core/tools.py` 加一个 `add_numbers(a, b)` 工具，重启 App，对 Agent 说“帮我算 123+456”，观察工具卡片和最终回答。

### 阶段 5：流程编排与截图（约 1.5 小时）

读 `core/controller.py`。

重点：

- `start_capture` 的隐藏/恢复主窗口逻辑；
- 框选回调 `_on_region_selected`；
- `_submit_screenshot` 建会话；
- `send_text` 与 Agent 的衔接；
- 为什么 Controller 不直接调用 LLM。

### 阶段 6：UI 与渲染（约 3 小时）

读 `ui/main_window.py`：

- 自定义无边框标题栏 `_TitleBar`；
- `stack`：对话 / 笔记 / 记忆；
- `open_session` 如何从数据库重建消息和工具卡片；
- `agent_started/step/finished/failed` 如何更新界面；
- `_send` → `message_sent` 信号；
- 笔记/记忆页的返回按钮。

读 `ui/answer_render.py`：

- 为什么公式要渲染成 PNG？
- matplotlib mathtext 不支持 `aligned/cases`，代码怎么拆？
- pygments 高亮、markdown 表格、内联样式；
- 缓存键为什么包含主题颜色。

读 `ui/notes_pane.py`、`memory_pane.py`：

- 笔记自动保存的防抖；
- 记忆卡片如何发出启停/编辑/删除信号。

---

## 3. 三条调用链（必须能自己走一遍）

### 链 A：文字任务 + 工具

```
MainWindow._send
→ message_sent
→ Controller.send_text
→ Store.create_session/add_message
→ MainWindow.open_session
→ ConversationAgent.run
→ _build_messages
→ DeepSeekClient.chat_with_tools
→ ToolRegistry.execute
→ Store.add_message(assistant, meta)
→ finished
→ MainWindow.agent_finished
```

### 链 B：截图提问

```
HotkeyManager / PetWindow
→ Controller.start_capture
→ grab_primary_screen
→ CaptureOverlay.selected
→ _on_region_selected
→ QuestionDialog
→ Store.save_capture
→ Store.create_session(image_path, context)
→ ConversationAgent.run
```

### 链 C：笔记

```
Agent 工具 create_note
→ Store.add_note
→ Controller._on_agent_finished → MainWindow.refresh_notes
→ NotesPane.refresh
→ 用户编辑 → save_note → Store.update_note
```

---

## 4. 调试技巧

### 4.1 用假 LLM 跑流程

`tests/test_flow.py` 里的 `ScriptedLLM` 是模板：

```python
class ScriptedLLM:
    def chat_with_tools(self, messages, tools, tool_choice="auto"):
        return {"role": "assistant", "content": "固定回答"}
```

`ConversationAgent(..., llm_factory=lambda: fake)` 可以完全离线跑通 UI/DB 流程。

### 4.2 看数据库

- 推荐用 DB Browser for SQLite 打开 `data/bili_ask.db`；
- 重点看 `messages.meta` 的 JSON；
- 不要直接改正在运行 App 的 DB（WAL 锁）；先退出 App。

### 4.3 看日志

`data/app.log` 有启动、热键、错误；Agent 异常会 `LOGGER.exception`。

### 4.4 截图回归

```powershell
python tests/render_screenshots.py
```

生成 `assets/screenshot_*.png`，不弹窗、不抢焦点。改 UI 后对比截图。

### 4.5 只跑某个测试

```powershell
python -m unittest tests.test_flow.FlowTest.test_text_agent_conversation_and_followup -v
```

---

## 5. 建议的改造练习（由易到难）

| 难度 | 任务 | 改哪里 | 验收 |
| --- | --- | --- | --- |
| ★ | 加 `add_numbers` 工具 | `core/tools.py` | 对话里能调用并显示卡片 |
| ★ | 笔记页 Markdown 预览 | `ui/notes_pane.py` + `answer_render.py` | 编辑/预览切换 |
| ★★ | 设置里加「浅色/深色」开关 | `ui/theme.py` + `config.py` | 重启后保持 |
| ★★ | 笔记「存为笔记」带来源会话 | `controller.py` + `store.py` | notes.source_session 有值 |
| ★★ | Word 图注自动编号（图 1、图 2…） | `core/word.py` | 连续插入编号递增 |
| ★★★ | Excel 工具：把对话表格写入 xlsx | 新 `core/excel.py` + tools | openpyxl 生成文件 |
| ★★★ | 最终回答流式输出 | `conversation.py` + `llm.py` + UI | 工具结束后逐字显示 |
| ★★★ | 浏览器扩展拿 URL/字幕 | 新本地 HTTP 服务 + context | 会话 context 带 URL |
| ★★★★ | MCP 工具源 | 新 `core/mcp.py` | MCP Server 的工具出现在 registry |

每个练习都要求：**能跑、有测试、改 README**。

---

## 6. 常见坑

1. **Qt 跨线程更新控件**：Agent 线程只能发 Signal；直接 `setText` 会偶发崩溃。
2. **确认弹窗**：`QMessageBox` 必须在主线程；工作线程用 `threading.Event` 等。
3. **SQLite 多线程**：连接是 `check_same_thread=False`，写操作必须走 RLock；不要在外面绕开 Store 直接写。
4. **图片路径**：数据库里存相对 `data/` 的路径，显示时用 `Store.image_abspath`。
5. **公式缓存**：`data/math_cache` 的 key 包含颜色/主题；改配色后旧图会失效（新的 key）。
6. **Word COM**：必须已有打开的文档；线程里要 `CoInitialize`；不要同时开两个 Word 实例。
7. **DPI**：抓屏/坐标是物理像素；改多屏/缩放时要重新验证。
8. **B 站 412**：接口有风控，不要把它当稳定数据源。

---

## 7. 读完自检清单

- [ ] 能画出 App 启动时的组件创建顺序
- [ ] 能说出一次文字任务经过的 7 个关键函数
- [ ] 能解释 `messages.meta.steps` 的作用
- [ ] 能解释危险工具确认的线程同步
- [ ] 能自己加一个工具并让 Agent 调用
- [ ] 能说清 `ContextWatcher` 为什么存在
- [ ] 能修改主题颜色并重新生成截图
- [ ] 能定位“回答为空/一直思考中”的可能原因

做到 6 项以上，这个项目就可以独立维护了。

---

## 8. 建议阅读时间安排

| 天 | 内容 |
| --- | --- |
| Day 1 | app.py + config/store，跑测试、看 DB |
| Day 2 | llm.py + conversation.py，读通工具循环 |
| Day 3 | tools.py + 加一个工具 |
| Day 4 | controller.py + 截图流程 |
| Day 5 | main_window + answer_render |
| Day 6 | notes/memory/plugins，做一个小改动 |
| Day 7 | 复盘：画架构图，写一篇自己的笔记 |
