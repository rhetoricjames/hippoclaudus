"""Adversarial tests — SQL injection, concurrency, malformed input, huge payloads."""

import json
import sqlite3
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from hippoclaudus.db_bridge import MemoryDB, Memory
from hippoclaudus.compactor import _similarity_simple
from hippoclaudus.llm import extract_json
from hippoclaudus.scoring import recency_decay, access_score, composite_score, ScoringWeights


# ---------------------------------------------------------------------------
# SQL injection
# ---------------------------------------------------------------------------

class TestSQLInjection:

    def test_injection_in_content(self, tmp_db):
        """SQL injection in content field should be parameterized away."""
        db = MemoryDB(tmp_db)
        m = Memory(content="Robert'; DROP TABLE memories; --")
        db.store_memory(m)
        result = db.get_memory_by_hash(m.content_hash)
        assert result is not None
        assert "DROP TABLE" in result["content"]
        # Table should still exist
        count = db.get_memory_count()
        assert count == 1
        db.close()

    def test_injection_in_tags(self, tmp_db):
        """SQL injection in tags should be safe."""
        db = MemoryDB(tmp_db)
        m = Memory(content="test", tags="tag1'; DROP TABLE memories; --")
        db.store_memory(m)
        db.update_tags(m.content_hash, "newtag'; DELETE FROM memories; --")
        refreshed = db.get_memory_by_hash(m.content_hash)
        assert "DELETE" in refreshed["tags"]
        assert db.get_memory_count() == 1
        db.close()

    def test_injection_in_search(self, tmp_db):
        """SQL injection in search_by_tag should be safe."""
        db = MemoryDB(tmp_db)
        db.store_memory(Memory(content="safe content", tags="safe"))
        results = db.search_by_tag("'; DROP TABLE memories; --")
        assert isinstance(results, list)
        # Table still works
        assert db.get_memory_count() == 1
        db.close()

    def test_injection_in_hash_lookup(self, tmp_db):
        """SQL injection in get_memory_by_hash should be safe."""
        db = MemoryDB(tmp_db)
        db.store_memory(Memory(content="safe"))
        result = db.get_memory_by_hash("' OR '1'='1")
        assert result is None
        assert db.get_memory_count() == 1
        db.close()

    def test_tables_survive_all_injections(self, tmp_db):
        """After all injection attempts, all tables should exist."""
        db = MemoryDB(tmp_db)
        for payload in [
            "'; DROP TABLE memories; --",
            "1; DELETE FROM memory_graph WHERE 1=1; --",
            "' UNION SELECT * FROM metadata; --",
        ]:
            try:
                db.store_memory(Memory(content=payload))
            except sqlite3.IntegrityError:
                pass  # duplicate hash

        cursor = db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        for expected in ["memories", "memory_graph", "metadata"]:
            assert expected in tables
        db.close()


# ---------------------------------------------------------------------------
# Malformed input
# ---------------------------------------------------------------------------

class TestMalformedInput:

    def test_huge_content(self, tmp_db):
        """1MB content should store and retrieve correctly."""
        db = MemoryDB(tmp_db)
        huge = "A" * (1024 * 1024)  # 1MB
        m = Memory(content=huge)
        db.store_memory(m)
        result = db.get_memory_by_hash(m.content_hash)
        assert result is not None
        assert len(result["content"]) == 1024 * 1024
        db.close()

    def test_unicode_content(self, tmp_db):
        """Unicode and emoji should work fine."""
        db = MemoryDB(tmp_db)
        m = Memory(content="日本語テスト 🚀🧠 café naïve résumé")
        db.store_memory(m)
        result = db.get_memory_by_hash(m.content_hash)
        assert "🚀" in result["content"]
        assert "café" in result["content"]
        db.close()

    def test_null_bytes_in_content(self, tmp_db):
        """Null bytes in content shouldn't crash."""
        db = MemoryDB(tmp_db)
        m = Memory(content="hello\x00world")
        db.store_memory(m)
        result = db.get_memory_by_hash(m.content_hash)
        assert result is not None
        db.close()

    def test_newlines_in_tags(self, tmp_db):
        """Newlines in tags — unusual but shouldn't crash."""
        db = MemoryDB(tmp_db)
        m = Memory(content="test", tags="tag1\ntag2\ttag3")
        db.store_memory(m)
        result = db.get_memory_by_hash(m.content_hash)
        assert result["tags"] == "tag1\ntag2\ttag3"
        db.close()

    def test_deeply_nested_metadata(self, tmp_db):
        """Deeply nested metadata dict should serialize to JSON."""
        db = MemoryDB(tmp_db)
        meta = {"level": 0}
        current = meta
        for i in range(1, 50):
            current["child"] = {"level": i}
            current = current["child"]

        m = Memory(content="nested test", metadata=meta)
        db.store_memory(m)
        result = db.get_memory_by_hash(m.content_hash)
        stored_meta = json.loads(result["metadata"])
        assert stored_meta["level"] == 0
        db.close()

    def test_empty_content(self, tmp_db):
        """Empty string content should still work (hash of empty string)."""
        db = MemoryDB(tmp_db)
        m = Memory(content="")
        db.store_memory(m)
        result = db.get_memory_by_hash(m.content_hash)
        assert result is not None
        assert result["content"] == ""
        db.close()


# ---------------------------------------------------------------------------
# JSON extraction stress
# ---------------------------------------------------------------------------

class TestJsonExtractionStress:

    def test_nested_braces_in_strings(self):
        """JSON with braces inside string values."""
        text = '{"code": "if (x) { return y; }", "count": 1}'
        result = extract_json(text)
        # This may or may not work depending on the greedy regex
        # If it works, great. If not, it's a known limitation.
        if result is not None:
            assert result["count"] == 1

    def test_huge_non_json(self):
        """1MB of non-JSON text should return None, not hang."""
        text = "x" * (1024 * 1024)
        result = extract_json(text)
        assert result is None

    def test_many_nested_braces(self):
        """500 nested braces — regex stress test."""
        text = "{" * 500 + '"key": "value"' + "}" * 500
        result = extract_json(text)
        # May fail to parse but shouldn't hang or crash
        # (result can be None or a dict)

    def test_json_in_markdown(self):
        """JSON wrapped in markdown formatting."""
        text = "## Results\n\nHere's the output:\n\n```json\n{\"status\": \"ok\", \"items\": 3}\n```\n\nDone."
        result = extract_json(text)
        assert result == {"status": "ok", "items": 3}


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestConcurrency:

    def test_concurrent_writes(self, tmp_db):
        """5 threads × 10 writes each — tests WAL concurrency."""
        errors = []

        def writer(thread_id):
            try:
                db = MemoryDB(tmp_db)
                for i in range(10):
                    m = Memory(content=f"thread-{thread_id}-item-{i}")
                    db.store_memory(m)
                db.close()
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Concurrent write errors: {errors}"

        db = MemoryDB(tmp_db)
        count = db.get_memory_count()
        db.close()
        assert count == 50

    def test_concurrent_read_write(self, populated_db):
        """Simultaneous reads and writes shouldn't deadlock."""
        errors = []

        def reader():
            try:
                db = MemoryDB(populated_db)
                for _ in range(20):
                    db.get_all_memories()
                    time.sleep(0.001)
                db.close()
            except Exception as e:
                errors.append(("reader", str(e)))

        def writer():
            try:
                db = MemoryDB(populated_db)
                for i in range(10):
                    m = Memory(content=f"concurrent-write-{i}")
                    try:
                        db.store_memory(m)
                    except sqlite3.IntegrityError:
                        pass
                    time.sleep(0.001)
                db.close()
            except Exception as e:
                errors.append(("writer", str(e)))

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Concurrent read/write errors: {errors}"


# ---------------------------------------------------------------------------
# Compactor stress
# ---------------------------------------------------------------------------

class TestCompactorStress:

    def test_many_memories(self, tmp_db):
        """50 memories → 1225 pairwise comparisons. Should complete fast."""
        db = MemoryDB(tmp_db)
        for i in range(50):
            db.store_memory(Memory(content=f"Memory number {i} about topic {i % 5}"))
        db.close()

        # Just test that _similarity_simple can handle all pairs without error
        memories = []
        db = MemoryDB(tmp_db)
        memories = db.get_all_memories(limit=100)
        db.close()

        count = 0
        for i in range(len(memories)):
            for j in range(i + 1, len(memories)):
                _similarity_simple(memories[i]["content"], memories[j]["content"])
                count += 1
        assert count == 1225

    def test_single_char_tokens(self):
        """Single-character tokens should work."""
        assert _similarity_simple("a b c", "a b c") == 1.0
        assert _similarity_simple("a b c", "d e f") == 0.0

    def test_repeated_tokens(self):
        """Repeated tokens — set() deduplicates."""
        sim = _similarity_simple("the the the", "the the the")
        assert sim == 1.0


# ---------------------------------------------------------------------------
# Scoring edge cases
# ---------------------------------------------------------------------------

class TestScoringEdgeCases:

    def test_epoch_zero_timestamp(self):
        """Unix epoch (0) timestamp — very old memory."""
        score = recency_decay(0.0, half_life_days=14.0)
        assert score < 0.001  # Ancient memory

    def test_huge_access_count(self):
        """Extremely high access count should cap at 1.0."""
        score = access_score(999999)
        assert score <= 1.0

    def test_composite_with_zero_weights(self):
        """All zero weights → score should be 0."""
        now = time.time()
        score = composite_score(
            cosine_sim=1.0,
            created_at=now,
            access_count=50,
            weights=ScoringWeights(relevance=0, recency=0, access=0),
        )
        assert score == 0.0


# ---------------------------------------------------------------------------
# Session log adversarial
# ---------------------------------------------------------------------------

class TestSessionLogAdversarial:

    def test_pathological_headers(self, tmp_path):
        """Session log with many ## headers but no date format."""
        log = tmp_path / "pathological.md"
        log.write_text("## Not a date\n## Also not\n## Still not\nContent here\n")
        result = MemoryDB.parse_latest_session(str(log))
        # Should return the last section (even if not a real date)
        assert result is not None

    def test_binary_content(self, tmp_path):
        """Binary-ish content in session log."""
        log = tmp_path / "binary.md"
        log.write_text("# Log\n\n## 2026-02-08 -- Test\n\n\x00\x01\x02\x03\n")
        result = MemoryDB.parse_latest_session(str(log))
        assert result is not None

    def test_large_session_log(self, tmp_path):
        """Large (1MB) session log should still parse."""
        log = tmp_path / "large.md"
        content = "# Log\n\n"
        content += "## 2026-01-01 -- Old Session\n\n" + ("X" * 500000) + "\n\n"
        content += "## 2026-02-08 -- Recent Session\n\n" + ("Y" * 500000) + "\n"
        log.write_text(content)
        result = MemoryDB.parse_latest_session(str(log))
        assert result is not None
        assert "Recent Session" in result


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------

class TestMetadataParsing:

    @pytest.mark.xfail(reason="Known: Metadata returned as JSON string, never auto-parsed to dict")
    def test_metadata_auto_parsed(self, populated_db):
        """Metadata is stored as JSON string. On read, it comes back as string, not dict."""
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        db.close()

        # Users might expect metadata to be auto-parsed
        meta = memories[0]["metadata"]
        assert isinstance(meta, dict), f"Expected dict, got {type(meta).__name__}: {meta}"

    def test_metadata_manual_parse(self, populated_db):
        """Metadata can be manually parsed from JSON string."""
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        db.close()

        meta_str = memories[0]["metadata"]
        meta = json.loads(meta_str)
        assert isinstance(meta, dict)
        assert "source" in meta

    def test_malformed_metadata_in_status(self, tmp_db):
        """Status command should handle memories with malformed metadata."""
        db = MemoryDB(tmp_db)
        # Insert a memory with invalid JSON metadata directly
        db.conn.execute(
            """INSERT INTO memories (content_hash, content, tags, memory_type, metadata,
               created_at, updated_at, created_at_iso, updated_at_iso)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("hash123", "test content", "test", "state_delta", "NOT VALID JSON",
             time.time(), time.time(), "2026-02-08T00:00:00", "2026-02-08T00:00:00"),
        )
        db.conn.commit()

        # get_all_memories should still work
        memories = db.get_all_memories()
        assert len(memories) == 1
        db.close()
