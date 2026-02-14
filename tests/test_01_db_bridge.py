"""Database CRUD, session log parser, graph edges, edge cases."""

import sqlite3
import sys
import time
from pathlib import Path

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from hippoclaudus.db_bridge import MemoryDB, Memory


# ---------------------------------------------------------------------------
# Memory dataclass
# ---------------------------------------------------------------------------

class TestMemoryDataclass:
    """Test the Memory dataclass auto-population."""

    def test_auto_hash(self):
        m = Memory(content="test content")
        assert len(m.content_hash) == 64  # SHA256 hex length

    def test_same_content_same_hash(self):
        m1 = Memory(content="identical")
        m2 = Memory(content="identical")
        assert m1.content_hash == m2.content_hash

    def test_different_content_different_hash(self):
        m1 = Memory(content="alpha")
        m2 = Memory(content="beta")
        assert m1.content_hash != m2.content_hash

    def test_auto_timestamps(self):
        before = time.time()
        m = Memory(content="timestamped")
        after = time.time()
        assert before <= m.created_at <= after
        assert before <= m.updated_at <= after
        assert m.created_at_iso != ""
        assert m.updated_at_iso != ""

    def test_explicit_hash_preserved(self):
        m = Memory(content="test", content_hash="custom_hash_123")
        assert m.content_hash == "custom_hash_123"

    def test_default_memory_type(self):
        m = Memory(content="test")
        assert m.memory_type == "note"


# ---------------------------------------------------------------------------
# Store and retrieve
# ---------------------------------------------------------------------------

class TestStoreRetrieve:

    def test_store_and_get_by_hash(self, tmp_db):
        db = MemoryDB(tmp_db)
        m = Memory(content="Hello world", tags="greeting,test", memory_type="note")
        row_id = db.store_memory(m)
        assert row_id > 0

        retrieved = db.get_memory_by_hash(m.content_hash)
        assert retrieved is not None
        assert retrieved["content"] == "Hello world"
        assert retrieved["tags"] == "greeting,test"
        db.close()

    def test_duplicate_hash_raises(self, tmp_db):
        db = MemoryDB(tmp_db)
        m = Memory(content="unique content")
        db.store_memory(m)
        with pytest.raises(sqlite3.IntegrityError):
            db.store_memory(m)
        db.close()

    def test_get_nonexistent_hash(self, tmp_db):
        db = MemoryDB(tmp_db)
        result = db.get_memory_by_hash("nonexistent_hash")
        assert result is None
        db.close()


# ---------------------------------------------------------------------------
# get_all_memories ordering, limit, offset
# ---------------------------------------------------------------------------

class TestGetAllMemories:

    def test_ordering_newest_first(self, populated_db):
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        # Last stored should come first (highest created_at)
        assert memories[0]["content"].startswith("Dana recommended")
        db.close()

    def test_limit(self, populated_db):
        db = MemoryDB(populated_db)
        memories = db.get_all_memories(limit=2)
        assert len(memories) == 2
        db.close()

    def test_offset(self, populated_db):
        db = MemoryDB(populated_db)
        all_mems = db.get_all_memories(limit=100)
        offset_mems = db.get_all_memories(limit=100, offset=2)
        assert len(offset_mems) == len(all_mems) - 2
        assert offset_mems[0]["id"] == all_mems[2]["id"]
        db.close()


# ---------------------------------------------------------------------------
# Tag operations
# ---------------------------------------------------------------------------

class TestTagOperations:

    def test_update_tags(self, populated_db):
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        target = memories[0]
        old_updated = target["updated_at"]

        time.sleep(0.01)
        db.update_tags(target["content_hash"], "new,tags,here")

        refreshed = db.get_memory_by_hash(target["content_hash"])
        assert refreshed["tags"] == "new,tags,here"
        assert refreshed["updated_at"] > old_updated
        db.close()

    def test_search_by_tag(self, populated_db):
        db = MemoryDB(populated_db)
        results = db.search_by_tag("james")
        assert len(results) >= 1
        db.close()

    def test_search_by_tag_no_match(self, populated_db):
        db = MemoryDB(populated_db)
        results = db.search_by_tag("xyznonexistent")
        assert len(results) == 0
        db.close()

    @pytest.mark.xfail(reason="Known bug: LIKE substring match — 'ai' matches 'plain'")
    def test_tag_substring_false_positive(self, populated_db):
        """Tags use SQL LIKE, so 'ai' matches 'plain-spoken'. This is a known limitation."""
        db = MemoryDB(populated_db)
        results = db.search_by_tag("ai")
        # "ai" is not a real tag on any memory, but LIKE %ai% will match
        # "plain" in "plain-spoken" if any tag contains "ai" as substring
        # With our sample data, "dana" contains no "ai" but let's check broader
        # Actually test with "an" which is substring of "dana"
        results = db.search_by_tag("an")
        # Should return 0 if exact match, but LIKE will match "dana"
        assert len(results) == 0, f"Expected 0 but got {len(results)} (LIKE substring bug)"
        db.close()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:

    def test_get_stats(self, populated_db):
        db = MemoryDB(populated_db)
        stats = db.get_stats()
        assert stats["memory_count"] == 5
        assert stats["graph_edges"] == 0
        assert stats["db_size_mb"] >= 0
        db.close()

    def test_memory_count(self, populated_db):
        db = MemoryDB(populated_db)
        assert db.get_memory_count() == 5
        db.close()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TestContextManager:

    def test_with_statement(self, tmp_db):
        with MemoryDB(tmp_db) as db:
            m = Memory(content="context manager test")
            db.store_memory(m)
            result = db.get_memory_by_hash(m.content_hash)
            assert result is not None


# ---------------------------------------------------------------------------
# Graph edges
# ---------------------------------------------------------------------------

class TestGraphEdges:

    def test_store_and_count(self, populated_db):
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        h1 = memories[0]["content_hash"]
        h2 = memories[1]["content_hash"]

        db.store_graph_edge(h1, h2, 0.85, "consolidation")
        assert db.get_graph_edge_count() == 1
        db.close()

    def test_duplicate_edge_ignored(self, populated_db):
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        h1 = memories[0]["content_hash"]
        h2 = memories[1]["content_hash"]

        db.store_graph_edge(h1, h2, 0.85)
        db.store_graph_edge(h1, h2, 0.99)  # INSERT OR IGNORE
        assert db.get_graph_edge_count() == 1
        db.close()


# ---------------------------------------------------------------------------
# Session log parser
# ---------------------------------------------------------------------------

class TestSessionLogParser:

    def test_parse_latest_session(self, sample_session_log):
        result = MemoryDB.parse_latest_session(str(sample_session_log))
        assert result is not None
        assert "Session 2" in result
        assert "Implemented consolidation" in result

    def test_parse_empty_log(self, empty_session_log):
        result = MemoryDB.parse_latest_session(str(empty_session_log))
        assert result is None

    def test_parse_nonexistent_file(self):
        result = MemoryDB.parse_latest_session("/nonexistent/path/log.md")
        assert result is None

    def test_parse_single_session(self, tmp_path):
        log = tmp_path / "single.md"
        log.write_text(
            "# Session Log\n\n---\n\n"
            "## 2026-02-08 -- Only Session\n\n"
            "### Context\nJust one session.\n"
        )
        result = MemoryDB.parse_latest_session(str(log))
        assert result is not None
        assert "Only Session" in result

    def test_parse_malformed_no_headers(self, tmp_path):
        log = tmp_path / "malformed.md"
        log.write_text("This is just plain text without any headers at all.\n")
        result = MemoryDB.parse_latest_session(str(log))
        assert result is None
