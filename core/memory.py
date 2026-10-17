"""长期记忆：整理、合并、筛选与检索。

- 整理：把最近的问答交给模型压缩成若干条长期记忆，自动合并相似条目
- 筛选：提问时按关键词重合度挑出最相关的几条注入上下文
"""

from __future__ import annotations

import difflib
import json
import logging
import re

from core.config import Config
from core.llm import DeepSeekClient
from core.store import Store

LOGGER = logging.getLogger("biliask")

CONSOLIDATE_PROMPT = """你是学习助手的记忆整理器。下面是用户最近的问答记录。

请提取值得长期记住的信息，压缩成不超过 8 条记忆：
1. 用户的偏好和习惯（例如“代码截图希望用黑底”“报告模板用学校统一格式”）；
2. 反复出现的知识点、结论、易错点；
3. 正在进行的任务与进度。

忽略一次性细节、寒暄和临时问题。相似或重复的内容必须合并成一条。
每条记忆不超过 50 个字，用陈述句。

只输出 JSON 数组，不要输出其他内容，格式：
[{"content": "……", "tags": ["标签1", "标签2"]}]
"""


class MemoryManager:
    def __init__(self, store: Store, config: Config, llm_factory=None) -> None:
        self.store = store
        self.config = config
        self._llm_factory = llm_factory

    # ------------------------------------------------------------------ 检索
    @staticmethod
    def _grams(text: str) -> set[str]:
        text = (text or "").lower()
        grams = set(re.findall(r"[a-z0-9_]{2,}", text))
        han = re.findall(r"[\u4e00-\u9fff]", text)
        for index in range(len(han) - 1):
            grams.add(han[index] + han[index + 1])
        return grams

    def retrieve(self, question: str, limit: int = 5) -> list[dict]:
        question_grams = self._grams(question)
        if not question_grams:
            return []
        scored: list[tuple[int, str, dict]] = []
        for memory in self.store.list_memories("", include_disabled=False):
            memory_grams = self._grams(memory["content"] + " " + memory["tags"])
            overlap = len(question_grams & memory_grams)
            if overlap >= 1:
                scored.append((overlap, memory["updated_at"], memory))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [memory for _, _, memory in scored[:limit]]

    def build_context(self, question: str) -> str:
        memories = self.retrieve(question)
        if not memories:
            return ""
        return "\n".join(f"- {memory['content']}" for memory in memories)

    # ------------------------------------------------------------------ 整理
    def consolidate(self, session_ids: list[str], max_sessions: int = 20) -> dict:
        conversations = self._collect(session_ids[:max_sessions])
        if not conversations:
            return {"added": 0, "merged": 0, "error": "没有可整理的问答记录"}

        prompt = CONSOLIDATE_PROMPT + "\n\n" + "\n\n".join(conversations)
        try:
            client = self._client()
            answer = client.chat([{"role": "user", "content": prompt}])
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("整理记忆失败")
            return {"added": 0, "merged": 0, "error": str(exc)}

        items = self._parse_items(answer)
        if not items:
            return {"added": 0, "merged": 0, "error": "模型没有返回可用的记忆条目"}

        added = 0
        merged = 0
        existing = self.store.list_memories("")
        for item in items:
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            tags = ",".join(str(tag) for tag in (item.get("tags") or []) if str(tag).strip())[:80]
            match = self._find_similar(content, existing)
            if match is not None:
                if len(content) >= len(match["content"]):
                    self.store.update_memory(
                        match["id"],
                        content=content,
                        tags=tags or match["tags"],
                        enabled=True,
                    )
                    match["content"] = content
                else:
                    self.store.update_memory(match["id"], enabled=True)
                merged += 1
            else:
                new_id = self.store.add_memory(content, tags, ",".join(session_ids[:3]))
                existing.append({"id": new_id, "content": content, "tags": tags})
                added += 1
        return {"added": added, "merged": merged, "error": None}

    def _collect(self, session_ids: list[str]) -> list[str]:
        conversations = []
        for sid in session_ids:
            session = self.store.get_session(sid)
            messages = self.store.get_messages(sid)
            if not session or not messages:
                continue
            lines = [f"# 记录：{session['question'][:60]}"]
            for message in messages[:6]:
                role = "问" if message["role"] == "user" else "答"
                lines.append(f"{role}：{message['content'][:200]}")
            conversations.append("\n".join(lines))
        return conversations

    def _client(self):
        if self._llm_factory is not None:
            return self._llm_factory()
        return DeepSeekClient(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=self.config.model,
            max_tokens=900,
            temperature=0.2,
        )

    @staticmethod
    def _parse_items(answer: str) -> list[dict]:
        text = answer or ""
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                if isinstance(data, list):
                    return [item for item in data if isinstance(item, dict) and item.get("content")]
            except json.JSONDecodeError:
                pass
        # 兜底：按行解析
        items = []
        for line in text.splitlines():
            line = line.strip().lstrip("-•*0123456789.、 ").strip()
            if line and not line.startswith("{") and len(line) >= 4:
                items.append({"content": line[:60], "tags": []})
        return items[:12]

    @staticmethod
    def _find_similar(content: str, existing: list[dict]) -> dict | None:
        normalized = re.sub(r"\s+", "", content).lower()
        for memory in existing:
            other = re.sub(r"\s+", "", memory["content"]).lower()
            if not other:
                continue
            if normalized in other or other in normalized:
                return memory
            if difflib.SequenceMatcher(None, normalized, other).ratio() >= 0.72:
                return memory
        return None
