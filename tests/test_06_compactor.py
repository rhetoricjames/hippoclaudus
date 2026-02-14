"""Compactor tests — Jaccard similarity, merge logic, soft-delete, dry-run."""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from tests.conftest import MOCK_MERGE_RESPONSE

from hippoclaudus.db_bridge import MemoryDB, Memory
from hippoclaudus.compactor import _similarity_simple, _merge_tags, _soft_delete, run_compact


# ---------------------------------------------------------------------------
# Jaccard similarity
# ---------------------------------------------------------------------------

class TestJaccardSimilarity:

    def test_identical_strings(self):
        assert _similarity_simple("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert _similarity_simple("alpha beta", "gamma delta") == 0.0

    def test_partial_overlap(self):
        sim = _similarity_simple("the quick brown fox", "the lazy brown dog")
        assert 0.2 < sim < 0.6  # "the" and "brown" overlap

    def test_empty_strings(self):
        assert _similarity_simple("", "") == 0.0
        assert _similarity_simple("hello", "") == 0.0
        assert _similarity_simple("", "world") == 0.0

    def test_case_insensitive(self):
        assert _similarity_simple("Hello World", "hello world") == 1.0

    def test_symmetry(self):
        a, b = "foo bar baz", "bar baz qux"
        assert _similarity_simple(a, b) == _similarity_simple(b, a)

    def test_single_word(self):
        assert _similarity_simple("hello", "hello") == 1.0
        assert _similarity_simple("hello", "world") == 0.0


# ---------------------------------------------------------------------------
# _merge_tags
# ---------------------------------------------------------------------------

class TestMergeTags:

    def test_disjoint_tags(self):
        result = _merge_tags("a,b", "c,d")
        tags = set(result.split(","))
        assert tags == {"a", "b", "c", "d"}

    def test_overlapping_tags(self):
        result = _merge_tags("a,b,c", "b,c,d")
        tags = set(result.split(","))
        assert tags == {"a", "b", "c", "d"}

    def test_empty_tags(self):
        assert _merge_tags("", "") == ""
        result = _merge_tags("a,b", "")
        tags = set(result.split(","))
        assert tags == {"a", "b"}

    def test_none_tags(self):
        result = _merge_tags(None, "a,b")
        tags = set(result.split(","))
        assert tags == {"a", "b"}

    def test_whitespace_handling(self):
        result = _merge_tags(" a , b ", " b , c ")
        tags = set(result.split(","))
        assert tags == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# soft_delete
# ---------------------------------------------------------------------------

class TestSoftDelete:

    def test_soft_delete_marks_deleted(self, populated_db):
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        target_hash = memories[0]["content_hash"]

        _soft_delete(db, target_hash)

        # Should no longer appear in get_all_memories (filters deleted_at IS NULL)
        remaining = db.get_all_memories()
        hashes = [m["content_hash"] for m in remaining]
        assert target_hash not in hashes

        # But should still exist in raw query
        cursor = db.conn.execute("SELECT deleted_at FROM memories WHERE content_hash = ?", (target_hash,))
        row = cursor.fetchone()
        assert row is not None
        assert row["deleted_at"] is not None
        db.close()


# ---------------------------------------------------------------------------
# run_compact
# ---------------------------------------------------------------------------

class TestRunCompact:

    def _make_similar_db(self, tmp_db):
        """Create a DB with two very similar memories."""
        db = MemoryDB(tmp_db)
        db.store_memory(Memory(
            content="James discussed the DeCue funding strategy for Q1 planning",
            tags="james,decue,funding",
        ))
        time.sleep(0.01)
        db.store_memory(Memory(
            content="James discussed the DeCue funding strategy for Q1 execution",
            tags="james,decue,funding",
        ))
        db.close()

    def test_compact_finds_duplicates(self, tmp_db):
        """Two similar memories should be found and one soft-deleted."""
        self._make_similar_db(tmp_db)

        with patch("hippoclaudus.compactor.run_prompt") as mock_rp, \
             patch("hippoclaudus.compactor.extract_json") as mock_ej:
            mock_rp.return_value = MOCK_MERGE_RESPONSE
            mock_ej.return_value = json.loads(MOCK_MERGE_RESPONSE)

            run_compact("mock-model", tmp_db, dry_run=False, threshold=0.3)

        db = MemoryDB(tmp_db)
        remaining = db.get_all_memories()
        db.close()
        assert len(remaining) == 1  # One soft-deleted

    def test_dry_run_preserves_all(self, tmp_db):
        """Dry run should not delete anything."""
        self._make_similar_db(tmp_db)

        with patch("hippoclaudus.compactor.run_prompt") as mock_rp, \
             patch("hippoclaudus.compactor.extract_json") as mock_ej:
            mock_rp.return_value = MOCK_MERGE_RESPONSE
            mock_ej.return_value = json.loads(MOCK_MERGE_RESPONSE)

            run_compact("mock-model", tmp_db, dry_run=True, threshold=0.3)

        db = MemoryDB(tmp_db)
        remaining = db.get_all_memories()
        db.close()
        assert len(remaining) == 2  # Both preserved

    def test_merge_creates_new_memory(self, tmp_db):
        """When LLM says 'merge', a new combined memory should be created."""
        self._make_similar_db(tmp_db)

        merge_response = {
            "relationship": "duplicate",
            "keep": "merge",
            "merged_content": "James discussed the DeCue funding strategy for Q1 planning and execution",
            "reasoning": "Combining both perspectives",
        }

        with patch("hippoclaudus.compactor.run_prompt") as mock_rp, \
             patch("hippoclaudus.compactor.extract_json") as mock_ej:
            mock_rp.return_value = json.dumps(merge_response)
            mock_ej.return_value = merge_response

            run_compact("mock-model", tmp_db, dry_run=False, threshold=0.3)

        db = MemoryDB(tmp_db)
        remaining = db.get_all_memories()
        db.close()

        assert len(remaining) == 1
        assert "planning and execution" in remaining[0]["content"]

    def test_llm_failure_skips_pair(self, tmp_db):
        """LLM returning None should skip the pair, not crash."""
        self._make_similar_db(tmp_db)

        with patch("hippoclaudus.compactor.run_prompt") as mock_rp, \
             patch("hippoclaudus.compactor.extract_json") as mock_ej:
            mock_rp.return_value = "gibberish"
            mock_ej.return_value = None

            run_compact("mock-model", tmp_db, dry_run=False, threshold=0.3)

        db = MemoryDB(tmp_db)
        remaining = db.get_all_memories()
        db.close()
        assert len(remaining) == 2  # Both preserved since LLM failed

    def test_fewer_than_two_memories(self, tmp_db):
        """Should exit early with < 2 memories."""
        db = MemoryDB(tmp_db)
        db.store_memory(Memory(content="lonely memory"))
        db.close()

        with patch("hippoclaudus.compactor.run_prompt") as mock_rp:
            run_compact("mock-model", tmp_db, dry_run=False)
            mock_rp.assert_not_called()
