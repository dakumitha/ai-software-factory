"""Persistent Long-Term Memory and Progressive Disclosure Engine for Swarm Agents.

Inspired by claude-mem (https://github.com/thedotmack/claude-mem),
this module maintains cross-session memory and architectural decisions in SQLite.
It indexes tool observations, component interfaces, and bug resolutions, providing
progressive disclosure to coding agents so they retain continuity across monorepo tasks.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MemoryObservation:
    """A persistent memory entry recorded by a swarm agent."""
    job_id: str
    task_id: str
    category: str  # 'architecture', 'contract', 'bugfix', 'user_preference'
    summary: str
    details: str
    timestamp: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)


class AgentMemoryStore:
    """SQLite-backed long-term memory store with progressive disclosure search."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_job ON agent_memories(job_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_category ON agent_memories(category)")

    def record_memory(
        self,
        job_id: str,
        task_id: str,
        category: str,
        summary: str,
        details: str = "",
        tags: list[str] | None = None,
    ) -> int:
        """Record an architectural decision, component contract, or bug fix into persistent memory."""
        tags_json = json.dumps(tags or [])
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agent_memories (job_id, task_id, category, summary, details, tags_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, task_id, category, summary, details, tags_json, now),
            )
            return int(cursor.lastrowid)

    def query_memories(
        self,
        job_id: str | None = None,
        query: str = "",
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve memories matching search terms or categories."""
        sql = "SELECT * FROM agent_memories WHERE 1=1"
        params: list[Any] = []

        if job_id:
            sql += " AND job_id = ?"
            params.append(job_id)
        if category:
            sql += " AND category = ?"
            params.append(category)
        if query:
            sql += " AND (summary LIKE ? OR details LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "id": r["id"],
                    "job_id": r["job_id"],
                    "task_id": r["task_id"],
                    "category": r["category"],
                    "summary": r["summary"],
                    "details": r["details"],
                    "tags": json.loads(r["tags_json"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def get_progressive_context(self, job_id: str, prompt: str, max_items: int = 5) -> str:
        """Generate a concise memory context header using progressive disclosure.

        Injects relevant past decisions into agent prompts so subagents maintain consistency.
        """
        keywords = [w.lower() for w in prompt.split() if len(w) > 3][:6]
        memories = self.query_memories(job_id=job_id, limit=max_items)

        # Score relevance by keyword match
        scored: list[tuple[int, dict[str, Any]]] = []
        for m in memories:
            text = f"{m['summary']} {m['details']} {' '.join(m['tags'])}".lower()
            score = sum(1 for kw in keywords if kw in text)
            scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        relevant = [m for _, m in scored[:max_items]]

        if not relevant:
            return ""

        lines = ["--- [AGENT PERSISTENT MEMORY / PROGRESSIVE CONTEXT] ---"]
        for m in relevant:
            lines.append(f"• [{m['category'].upper()}] {m['summary']}")
            if m["details"]:
                lines.append(f"  Details: {m['details'][:160]}...")
        lines.append("--- [END MEMORY CONTEXT] ---\n")
        return "\n".join(lines)
