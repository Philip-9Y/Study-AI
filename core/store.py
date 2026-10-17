"""本地存储：SQLite（会话 / 消息）+ 截图文件。

data/
  bili_ask.db
  captures/YYYY-MM-DD/HHMMSS_fff.png
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    question TEXT NOT NULL,
    image_path TEXT,
    model TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    elapsed_s REAL,
    image_path TEXT,
    meta TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    source_session TEXT,
    pinned INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC);
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    sources TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at DESC);
"""


def _iso(when: datetime | None = None) -> str:
    return (when or datetime.now()).isoformat(timespec="seconds")


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.captures_dir = self.data_dir / "captures"
        self.captures_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "bili_ask.db"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        session_columns = [row[1] for row in self._conn.execute("PRAGMA table_info(sessions)")]
        if "context" not in session_columns:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN context TEXT")
        message_columns = [row[1] for row in self._conn.execute("PRAGMA table_info(messages)")]
        if "meta" not in message_columns:
            self._conn.execute("ALTER TABLE messages ADD COLUMN meta TEXT")
        self._conn.commit()

    # ------------------------------------------------------------------ 图片
    def save_capture(self, img: Image.Image, when: datetime | None = None) -> str:
        when = when or datetime.now()
        day_dir = self.captures_dir / when.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        path = day_dir / (when.strftime("%H%M%S_%f")[:-3] + ".png")
        img.save(path, format="PNG")
        return path.relative_to(self.data_dir).as_posix()

    def image_abspath(self, rel_path: str | None) -> Path | None:
        if not rel_path:
            return None
        path = (self.data_dir / rel_path).resolve()
        try:
            path.relative_to(self.data_dir.resolve())
        except ValueError:
            return None
        return path if path.exists() else None

    # ------------------------------------------------------------------ 会话
    def create_session(
        self,
        question: str,
        image_path: str | None = None,
        model: str | None = None,
        when: datetime | None = None,
        context: str | None = None,
    ) -> str:
        sid = uuid.uuid4().hex[:12]
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions (id, created_at, question, image_path, model, context)"
                " VALUES (?,?,?,?,?,?)",
                (sid, _iso(when), question, image_path, model, context),
            )
        return sid

    def get_session(self, sid: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        return dict(row) if row else None

    def list_sessions(self, query: str = "", limit: int = 300) -> list[dict]:
        query = (query or "").strip()
        if query:
            like = f"%{query}%"
            rows = self._conn.execute(
                """
                SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count
                FROM sessions s
                WHERE s.question LIKE ? OR s.id IN (
                    SELECT session_id FROM messages WHERE content LIKE ?
                )
                ORDER BY s.created_at DESC, s.rowid DESC LIMIT ?
                """,
                (like, like, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count
                FROM sessions s ORDER BY s.created_at DESC, s.rowid DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_session(self, sid: str) -> str | None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT image_path FROM sessions WHERE id = ?", (sid,)
            ).fetchone()
            self._conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
            self._conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
        return row["image_path"] if row else None

    def session_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------ 消息
    def add_message(
        self,
        sid: str,
        role: str,
        content: str,
        image_path: str | None = None,
        elapsed_s: float | None = None,
        when: datetime | None = None,
        meta: str | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at, elapsed_s, image_path, meta)"
                " VALUES (?,?,?,?,?,?,?)",
                (sid, role, content, _iso(when), elapsed_s, image_path, meta),
            )

    def get_messages(self, sid: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? AND role IN ('user','assistant') ORDER BY id",
            (sid,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_session_ids(self, limit: int = 40) -> list[str]:
        rows = self._conn.execute(
            "SELECT id FROM sessions ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        return [row["id"] for row in rows]

    # ------------------------------------------------------------------ 笔记
    def add_note(
        self,
        title: str,
        content: str,
        tags: str = "",
        source_session: str | None = None,
        when: datetime | None = None,
    ) -> str:
        nid = uuid.uuid4().hex[:12]
        now = _iso(when)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO notes (id, created_at, updated_at, title, content, tags, source_session, pinned)"
                " VALUES (?,?,?,?,?,?,?,0)",
                (nid, now, now, title, content, tags, source_session),
            )
        return nid

    def update_note(
        self,
        nid: str,
        title: str | None = None,
        content: str | None = None,
        tags: str | None = None,
    ) -> None:
        fields = []
        values = []
        if title is not None:
            fields.append("title = ?")
            values.append(title)
        if content is not None:
            fields.append("content = ?")
            values.append(content)
        if tags is not None:
            fields.append("tags = ?")
            values.append(tags)
        if not fields:
            return
        fields.append("updated_at = ?")
        values.append(_iso())
        values.append(nid)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE notes SET {', '.join(fields)} WHERE id = ?", values)

    def get_note(self, nid: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM notes WHERE id = ?", (nid,)).fetchone()
        return dict(row) if row else None

    def list_notes(self, query: str = "") -> list[dict]:
        query = (query or "").strip()
        if query:
            like = f"%{query}%"
            rows = self._conn.execute(
                "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?"
                " ORDER BY updated_at DESC, rowid DESC",
                (like, like, like),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM notes ORDER BY updated_at DESC, rowid DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_note(self, nid: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM notes WHERE id = ?", (nid,))

    # ------------------------------------------------------------------ 记忆
    def add_memory(self, content: str, tags: str = "", sources: str = "") -> str:
        mid = uuid.uuid4().hex[:12]
        now = _iso()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO memories (id, created_at, updated_at, content, tags, sources, enabled)"
                " VALUES (?,?,?,?,?,?,1)",
                (mid, now, now, content, tags, sources),
            )
        return mid

    def update_memory(
        self,
        mid: str,
        content: str | None = None,
        tags: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        fields = []
        values = []
        if content is not None:
            fields.append("content = ?")
            values.append(content)
        if tags is not None:
            fields.append("tags = ?")
            values.append(tags)
        if enabled is not None:
            fields.append("enabled = ?")
            values.append(1 if enabled else 0)
        if not fields:
            return
        fields.append("updated_at = ?")
        values.append(_iso())
        values.append(mid)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE memories SET {', '.join(fields)} WHERE id = ?", values)

    def get_memory(self, mid: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM memories WHERE id = ?", (mid,)).fetchone()
        return dict(row) if row else None

    def list_memories(self, query: str = "", include_disabled: bool = True) -> list[dict]:
        query = (query or "").strip()
        conditions = []
        params: list = []
        if not include_disabled:
            conditions.append("enabled = 1")
        if query:
            conditions.append("(content LIKE ? OR tags LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._conn.execute(
            f"SELECT * FROM memories {where} ORDER BY updated_at DESC, rowid DESC", params
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, mid: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM memories WHERE id = ?", (mid,))

    def memory_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM memories").fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------ 迁移
    def import_legacy_jsonl(self, path: Path) -> int:
        """把旧版 notes.jsonl 导入 SQLite；已有数据则跳过。"""
        path = Path(path)
        if self.session_count() > 0 or not path.exists():
            return 0
        groups: dict[str, list[dict]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = str(record.get("session") or record.get("ts") or uuid.uuid4().hex[:12])
            groups.setdefault(sid, []).append(record)

        imported = 0
        for sid, records in groups.items():
            records.sort(key=lambda r: str(r.get("ts", "")))
            first = records[0]
            when = _parse_dt(first.get("ts"))
            new_sid = self.create_session(
                str(first.get("question") or ""),
                first.get("image"),
                first.get("model"),
                when=when,
            )
            for record in records:
                record_when = _parse_dt(record.get("ts"))
                question = str(record.get("question") or "")
                answer = str(record.get("answer") or "")
                if question:
                    self.add_message(new_sid, "user", question, when=record_when)
                if answer:
                    self.add_message(
                        new_sid, "assistant", answer, elapsed_s=record.get("elapsed_s"), when=record_when
                    )
            imported += 1
        return imported

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
