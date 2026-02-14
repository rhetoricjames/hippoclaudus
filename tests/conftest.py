"""Shared fixtures for the Hippoclaudus test suite."""

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MCP_ROOT = Path(__file__).parent.parent  # /Users/.../mcp-memory

DEFAULT_MODEL = "mlx-community/Mistral-7B-Instruct-v0.3-4bit"


# ---------------------------------------------------------------------------
# Temporary database that mirrors the real schema
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_db(tmp_path):
    """Create a fresh SQLite DB with the exact same schema as memory.db."""
    db_path = str(tmp_path / "test_memory.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO metadata (key, value) VALUES ('distance_metric', 'cosine');

        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            tags TEXT,
            memory_type TEXT,
            metadata TEXT,
            created_at REAL,
            updated_at REAL,
            created_at_iso TEXT,
            updated_at_iso TEXT,
            deleted_at REAL DEFAULT NULL
        );
        CREATE INDEX idx_content_hash ON memories(content_hash);
        CREATE INDEX idx_created_at ON memories(created_at);
        CREATE INDEX idx_memory_type ON memories(memory_type);
        CREATE INDEX idx_deleted_at ON memories(deleted_at);

        CREATE TABLE memory_graph (
            source_hash TEXT NOT NULL,
            target_hash TEXT NOT NULL,
            similarity REAL NOT NULL,
            connection_types TEXT NOT NULL,
            metadata TEXT,
            created_at REAL NOT NULL,
            relationship_type TEXT DEFAULT 'related',
            PRIMARY KEY (source_hash, target_hash)
        );
        CREATE INDEX idx_graph_source ON memory_graph(source_hash);
        CREATE INDEX idx_graph_target ON memory_graph(target_hash);
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def populated_db(tmp_db):
    """tmp_db pre-loaded with 5 sample memories of different types."""
    import sys
    sys.path.insert(0, str(MCP_ROOT))
    from hippoclaudus.db_bridge import MemoryDB, Memory

    db = MemoryDB(tmp_db)
    samples = [
        Memory(
            content="James and Dana discussed DeCue funding strategy for Q1",
            tags="james,dana,decue,funding,strategy",
            memory_type="observation",
            metadata={"source": "test"},
        ),
        Memory(
            content="[State Delta] Migrated infrastructure from iMac to Mac Mini M4",
            tags="infrastructure,mac-mini,migration,state-delta",
            memory_type="state_delta",
            metadata={"entities": {"people": ["James"], "projects": ["DeCue"], "tools": ["Mac Mini"]},
                       "open_threads": ["Phase 3 planning"], "source": "hippo-consolidate"},
        ),
        Memory(
            content="Seth proposed using Rust for the backend rewrite",
            tags="seth,rust,backend,proposal",
            memory_type="observation",
            metadata={"source": "test"},
        ),
        Memory(
            content="Vera asked about internship timeline at Blue Shirt IR",
            tags="vera,blue-shirt-ir,internship",
            memory_type="observation",
            metadata={"source": "test"},
        ),
        Memory(
            content="Dana recommended a plain-spoken communication approach for investor decks",
            tags="dana,communication,investor,decue",
            memory_type="observation",
            metadata={"source": "test"},
        ),
    ]
    for m in samples:
        db.store_memory(m)
        time.sleep(0.01)  # Ensure distinct timestamps for ordering tests
    db.close()
    return tmp_db


@pytest.fixture
def sample_session_log(tmp_path):
    """Create a minimal Session_Summary_Log.md for testing parsers."""
    log = tmp_path / "Session_Summary_Log.md"
    log.write_text(
        "# Session Summary Log\n\n---\n\n"
        "## 2026-02-07 -- Session 1\n\n"
        "### Context\nFirst test session.\n\n"
        "### What We Covered\n- Tested the database\n- Built the CLI\n\n"
        "## 2026-02-08 -- Session 2\n\n"
        "### Context\nSecond test session.\n\n"
        "### What We Covered\n- Implemented consolidation\n- Ran Mistral inference\n\n"
        "### Follow-ups\n- Write tests\n"
    )
    return log


@pytest.fixture
def empty_session_log(tmp_path):
    """Session log with no session entries."""
    log = tmp_path / "Session_Summary_Log.md"
    log.write_text("# Session Summary Log\n\n---\n")
    return log


@pytest.fixture
def open_questions_file(tmp_path):
    """Sample Open_Questions_Blockers.md."""
    oq = tmp_path / "Open_Questions_Blockers.md"
    oq.write_text(
        "# Open Questions\n\n"
        "- Should we use embedding-based compaction?\n"
        "- When to schedule automated consolidation?\n"
    )
    return oq


@pytest.fixture
def long_term_dir(tmp_path):
    """Create a fake long-term directory with relationship files."""
    lt = tmp_path / "long-term"
    lt.mkdir()
    (lt / "Claude_Relationships_James.md").write_text(
        "# James\n\nJames is the founder of DeCue Technologies.\n"
        "He communicates directly and values shipping.\n"
    )
    (lt / "Claude_Relationships_Dana.md").write_text(
        "# Dana\n\nDana is the CSO of DeCue and James's wife.\n"
    )
    return lt


# ---------------------------------------------------------------------------
# Mock LLM response constants
# ---------------------------------------------------------------------------
MOCK_CONSOLIDATION_RESPONSE = json.dumps({
    "state_delta": "Infrastructure migrated from iMac to Mac Mini. All MCP services confirmed working.",
    "entities": {
        "people": ["James"],
        "projects": ["DeCue", "Hippoclaudus"],
        "tools": ["Mac Mini M4", "MLX"]
    },
    "security_context": "none",
    "emotional_signals": "positive, productive energy",
    "open_threads": ["Phase 3 planning", "Automated scheduling"]
})

MOCK_TAG_RESPONSE = json.dumps({
    "people": ["James", "Dana"],
    "projects": ["DeCue"],
    "tools": ["Python", "SQLite"],
    "topics": ["memory management", "architecture"],
    "suggested_tags": ["james", "dana", "decue", "python", "sqlite", "memory-management"]
})

MOCK_MERGE_RESPONSE = json.dumps({
    "relationship": "duplicate",
    "keep": "B",
    "merged_content": "",
    "reasoning": "Memory B is a more recent version of the same information."
})

MOCK_COMM_PROFILE_RESPONSE = json.dumps({
    "tone": "direct, analytical",
    "priorities": ["shipping product", "technical excellence"],
    "decision_style": "data-driven with gut checks",
    "response_patterns": "quick responses, iterative",
    "key_phrases": ["ship it", "what's the blocker"],
    "working_relationship": "collaborative, high trust"
})

MOCK_PREDICT_RESPONSE = (
    "# PRELOAD -- Session Briefing\n"
    "Generated: 2026-02-08 20:00 UTC\n\n"
    "## Active Context\nWorking on Hippoclaudus test suite.\n\n"
    "## Unresolved Threads\n- Phase 3 planning\n\n"
    "## Suggested First Moves\n- Run the test suite\n"
)
