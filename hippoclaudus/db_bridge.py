"""Database bridge for Hippoclaudus — direct SQLite read/write to existing memory.db.

Designed to coexist safely with the running MCP memory server.
Uses WAL mode and short transactions to avoid lock contention.
"""

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Memory:
    """Mirrors the MCP memory service schema."""
    content: str
    content_hash: str = ""
    tags: str = ""
    memory_type: str = "note"
    metadata: dict = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0
    created_at_iso: str = ""
    updated_at_iso: str = ""
    id: Optional[int] = None

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.created_at_iso:
            from datetime import datetime, timezone
            self.created_at_iso = datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()
        if not self.updated_at_iso:
            from datetime import datetime, timezone
            self.updated_at_iso = datetime.fromtimestamp(self.updated_at, tz=timezone.utc).isoformat()


class MemoryDB:
    """Direct SQLite access to memory.db, safe for concurrent use with MCP server."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        # WAL mode for concurrent reads
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # --- Read Operations ---

    def get_all_memories(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Fetch memories ordered by most recent first."""
        cursor = self.conn.execute(
            "SELECT * FROM memories WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_memory_by_hash(self, content_hash: str) -> Optional[dict]:
        """Fetch a single memory by its content hash."""
        cursor = self.conn.execute(
            "SELECT * FROM memories WHERE content_hash = ? AND deleted_at IS NULL",
            (content_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def search_by_tag(self, tag: str) -> list[dict]:
        """Find memories containing a specific tag."""
        cursor = self.conn.execute(
            "SELECT * FROM memories WHERE tags LIKE ? AND deleted_at IS NULL ORDER BY created_at DESC",
            (f"%{tag}%",),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_memory_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL")
        return cursor.fetchone()[0]

    def get_graph_edge_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM memory_graph")
        return cursor.fetchone()[0]

    def get_stats(self) -> dict:
        """Get overall memory database statistics."""
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        return {
            "memory_count": self.get_memory_count(),
            "graph_edges": self.get_graph_edge_count(),
            "db_size_mb": db_size / (1024 * 1024),
        }

    # --- Write Operations ---

    def store_memory(self, memory: Memory) -> int:
        """Insert a new memory. Returns the row ID."""
        metadata_json = json.dumps(memory.metadata) if memory.metadata else "{}"
        cursor = self.conn.execute(
            """INSERT INTO memories (content_hash, content, tags, memory_type, metadata,
               created_at, updated_at, created_at_iso, updated_at_iso)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                memory.content_hash,
                memory.content,
                memory.tags,
                memory.memory_type,
                metadata_json,
                memory.created_at,
                memory.updated_at,
                memory.created_at_iso,
                memory.updated_at_iso,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_tags(self, content_hash: str, tags: str):
        """Update tags on an existing memory."""
        now = time.time()
        from datetime import datetime, timezone
        now_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE memories SET tags = ?, updated_at = ?, updated_at_iso = ? WHERE content_hash = ?",
            (tags, now, now_iso, content_hash),
        )
        self.conn.commit()

    def store_graph_edge(self, source_hash: str, target_hash: str, similarity: float,
                         connection_types: str = "consolidation", relationship_type: str = "related"):
        """Add an edge to the memory graph."""
        now = time.time()
        self.conn.execute(
            """INSERT OR IGNORE INTO memory_graph
               (source_hash, target_hash, similarity, connection_types, metadata, created_at, relationship_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source_hash, target_hash, similarity, connection_types, "{}", now, relationship_type),
        )
        self.conn.commit()

    # --- Session Log Parsing ---

    @staticmethod
    def parse_latest_session(session_log_path: str) -> Optional[str]:
        """Extract the most recent session entry from Session_Summary_Log.md."""
        path = Path(session_log_path)
        if not path.exists():
            return None

        text = path.read_text()
        # Split on session headers (## YYYY-MM-DD)
        sections = text.split("\n## ")
        if len(sections) < 2:
            return None

        # Last section is the most recent session
        latest = "## " + sections[-1]
        return latest.strip()
