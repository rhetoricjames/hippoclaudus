"""Entity tagging tests — single, batch, LLM failure handling."""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from tests.conftest import MOCK_TAG_RESPONSE

from hippoclaudus.db_bridge import MemoryDB, Memory
from hippoclaudus.tagger import run_tag_single, run_tag_all


# ---------------------------------------------------------------------------
# run_tag_single
# ---------------------------------------------------------------------------

class TestTagSingle:

    def test_tag_single_memory(self, populated_db):
        """Tag a specific memory — should merge old + new tags."""
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        target_id = memories[0]["id"]
        original_tags = memories[0]["tags"]
        db.close()

        with patch("hippoclaudus.tagger.tag_memory") as mock_llm:
            mock_llm.return_value = json.loads(MOCK_TAG_RESPONSE)
            run_tag_single("mock-model", populated_db, target_id)

        db = MemoryDB(populated_db)
        updated = db.get_all_memories()
        target = [m for m in updated if m["id"] == target_id][0]
        db.close()

        # Original tags should still be present
        for t in original_tags.split(","):
            t = t.strip()
            if t:
                assert t in target["tags"], f"Original tag '{t}' missing after merge"

    def test_nonexistent_memory_id(self, populated_db):
        """Tagging a nonexistent ID should not crash."""
        with patch("hippoclaudus.tagger.tag_memory") as mock_llm:
            run_tag_single("mock-model", populated_db, 99999)
            mock_llm.assert_not_called()

    def test_llm_failure(self, populated_db):
        """LLM returning None should not crash."""
        db = MemoryDB(populated_db)
        target_id = db.get_all_memories()[0]["id"]
        db.close()

        with patch("hippoclaudus.tagger.tag_memory") as mock_llm:
            mock_llm.return_value = None
            run_tag_single("mock-model", populated_db, target_id)


# ---------------------------------------------------------------------------
# run_tag_all
# ---------------------------------------------------------------------------

class TestTagAll:

    def test_skips_well_tagged(self, populated_db):
        """Memories with 5+ tags should be skipped."""
        # Give one memory 6 tags so it's clearly above the >= 5 threshold
        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        db.update_tags(memories[0]["content_hash"], "a,b,c,d,e,f")
        db.close()

        with patch("hippoclaudus.tagger.tag_memory") as mock_llm:
            mock_llm.return_value = json.loads(MOCK_TAG_RESPONSE)
            run_tag_all("mock-model", populated_db)

            # The populated_db has 5 memories. Memory #1 (James/Dana funding)
            # already has 5 tags ("james,dana,decue,funding,strategy"), which
            # hits the >= 5 skip threshold. Plus the one we gave 6 tags above.
            # So 2 are skipped, 3 are tagged.
            assert mock_llm.call_count == 3

    def test_suggested_tags_as_string(self, populated_db):
        """Handle suggested_tags as comma-separated string instead of list."""
        with patch("hippoclaudus.tagger.tag_memory") as mock_llm:
            mock_llm.return_value = {
                "people": ["James"],
                "projects": [],
                "tools": [],
                "topics": [],
                "suggested_tags": "james,leadership,strategy",  # string, not list
            }
            run_tag_all("mock-model", populated_db)

        db = MemoryDB(populated_db)
        memories = db.get_all_memories()
        db.close()

        # At least one memory should now have "james" as a tag
        any_has_james = any("james" in (m["tags"] or "") for m in memories)
        assert any_has_james

    def test_empty_db(self, tmp_db):
        """Empty database should not crash."""
        with patch("hippoclaudus.tagger.tag_memory") as mock_llm:
            run_tag_all("mock-model", tmp_db)
            mock_llm.assert_not_called()
