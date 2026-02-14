"""Consolidation pipeline tests — mocked LLM + real Mistral."""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from tests.conftest import MOCK_CONSOLIDATION_RESPONSE, MCP_ROOT as CONF_ROOT

from hippoclaudus.db_bridge import MemoryDB, Memory
from hippoclaudus.consolidator import run_consolidation, run_reflection


# ---------------------------------------------------------------------------
# Mocked pipeline
# ---------------------------------------------------------------------------

class TestConsolidationMocked:

    def test_full_pipeline(self, tmp_db, sample_session_log):
        """Mocked LLM → should store a state_delta memory."""
        with patch("hippoclaudus.consolidator.consolidate_session") as mock_llm:
            mock_llm.return_value = json.loads(MOCK_CONSOLIDATION_RESPONSE)
            run_consolidation(
                model_name="mock-model",
                db_path=tmp_db,
                session_log=sample_session_log,
            )

        db = MemoryDB(tmp_db)
        memories = db.get_all_memories()
        db.close()

        assert len(memories) == 1
        assert memories[0]["memory_type"] == "state_delta"
        assert "[State Delta]" in memories[0]["content"]
        assert "state-delta" in memories[0]["tags"]

    def test_empty_log_exits(self, tmp_db, empty_session_log):
        """Empty session log → no LLM call, no memory stored."""
        with patch("hippoclaudus.consolidator.consolidate_session") as mock_llm:
            run_consolidation(
                model_name="mock-model",
                db_path=tmp_db,
                session_log=empty_session_log,
            )
            mock_llm.assert_not_called()

        db = MemoryDB(tmp_db)
        assert db.get_memory_count() == 0
        db.close()

    def test_llm_returns_none(self, tmp_db, sample_session_log):
        """LLM failure → nothing stored."""
        with patch("hippoclaudus.consolidator.consolidate_session") as mock_llm:
            mock_llm.return_value = None
            run_consolidation(
                model_name="mock-model",
                db_path=tmp_db,
                session_log=sample_session_log,
            )

        db = MemoryDB(tmp_db)
        assert db.get_memory_count() == 0
        db.close()

    def test_tags_from_entities(self, tmp_db, sample_session_log):
        """Tags should be built from entities in the LLM response."""
        with patch("hippoclaudus.consolidator.consolidate_session") as mock_llm:
            mock_llm.return_value = json.loads(MOCK_CONSOLIDATION_RESPONSE)
            run_consolidation(
                model_name="mock-model",
                db_path=tmp_db,
                session_log=sample_session_log,
            )

        db = MemoryDB(tmp_db)
        memories = db.get_all_memories()
        db.close()

        tags = memories[0]["tags"]
        assert "james" in tags
        assert "hippoclaudus" in tags or "decue" in tags
        assert "state-delta" in tags

    def test_missing_entity_keys(self, tmp_db, sample_session_log):
        """LLM response missing entity sub-keys should still work."""
        with patch("hippoclaudus.consolidator.consolidate_session") as mock_llm:
            mock_llm.return_value = {
                "state_delta": "Something happened",
                "entities": {},  # no people/projects/tools
                "open_threads": [],
            }
            run_consolidation(
                model_name="mock-model",
                db_path=tmp_db,
                session_log=sample_session_log,
            )

        db = MemoryDB(tmp_db)
        memories = db.get_all_memories()
        db.close()

        assert len(memories) == 1
        assert "state-delta" in memories[0]["tags"]


# ---------------------------------------------------------------------------
# Reflection (dry run)
# ---------------------------------------------------------------------------

class TestReflectionMocked:

    def test_reflection_no_store(self, sample_session_log):
        """Reflection should NOT store anything — it's a dry run."""
        with patch("hippoclaudus.consolidator.consolidate_session") as mock_llm:
            mock_llm.return_value = json.loads(MOCK_CONSOLIDATION_RESPONSE)
            # run_reflection doesn't take db_path — it never writes
            run_reflection(
                model_name="mock-model",
                session_log=sample_session_log,
            )
            mock_llm.assert_called_once()


# ---------------------------------------------------------------------------
# Real Mistral
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestConsolidationReal:

    def test_full_pipeline_real(self, tmp_db, sample_session_log):
        """Real Mistral inference for consolidation."""
        run_consolidation(
            model_name="mlx-community/Mistral-7B-Instruct-v0.3-4bit",
            db_path=tmp_db,
            session_log=sample_session_log,
        )

        db = MemoryDB(tmp_db)
        memories = db.get_all_memories()
        db.close()

        assert len(memories) >= 1
        assert memories[0]["memory_type"] == "state_delta"
