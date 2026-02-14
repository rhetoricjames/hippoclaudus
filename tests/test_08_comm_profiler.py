"""Communication profile analysis tests."""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from tests.conftest import MOCK_COMM_PROFILE_RESPONSE

from hippoclaudus.db_bridge import MemoryDB, Memory
from hippoclaudus.comm_profiler import run_comm_profile


# ---------------------------------------------------------------------------
# Mocked tests
# ---------------------------------------------------------------------------

class TestCommProfileMocked:

    def test_profile_with_relationship_file(self, populated_db, long_term_dir):
        """Should find James's relationship file and include it in excerpts."""
        with patch("hippoclaudus.comm_profiler.analyze_comm_profile") as mock_llm:
            mock_llm.return_value = json.loads(MOCK_COMM_PROFILE_RESPONSE)
            run_comm_profile("mock-model", populated_db, "James", long_term_dir)

            # LLM should have been called
            mock_llm.assert_called_once()
            # The excerpts argument should include relationship file content
            call_args = mock_llm.call_args
            excerpts = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("excerpts", "")
            assert "RELATIONSHIP FILE" in excerpts
            assert "founder" in excerpts.lower() or "DeCue" in excerpts

    def test_no_data_found(self, tmp_db, long_term_dir):
        """Person with no memories and no relationship file → no LLM call."""
        # Store a memory that doesn't reference "Zara"
        db = MemoryDB(tmp_db)
        db.store_memory(Memory(content="Unrelated content about weather"))
        db.close()

        with patch("hippoclaudus.comm_profiler.analyze_comm_profile") as mock_llm:
            run_comm_profile("mock-model", tmp_db, "Zara", long_term_dir)
            mock_llm.assert_not_called()

    def test_case_insensitive_file_match(self, populated_db, long_term_dir):
        """Searching for 'james' (lowercase) should find Claude_Relationships_James.md."""
        with patch("hippoclaudus.comm_profiler.analyze_comm_profile") as mock_llm:
            mock_llm.return_value = json.loads(MOCK_COMM_PROFILE_RESPONSE)
            run_comm_profile("mock-model", populated_db, "james", long_term_dir)
            # Should still find the file via case-insensitive glob fallback
            mock_llm.assert_called_once()

    @pytest.mark.xfail(reason="Known: substring match — 'Dana' matches 'Canada' in content")
    def test_substring_false_positive(self, tmp_db, long_term_dir):
        """Searching for 'Dan' could match 'Canada' in content."""
        db = MemoryDB(tmp_db)
        db.store_memory(Memory(content="The company expanded to Canada for new markets"))
        db.close()

        with patch("hippoclaudus.comm_profiler.analyze_comm_profile") as mock_llm:
            mock_llm.return_value = json.loads(MOCK_COMM_PROFILE_RESPONSE)
            run_comm_profile("mock-model", tmp_db, "Dan", long_term_dir)
            # Ideally shouldn't be called, but "Dan" is substring of "Canada"
            mock_llm.assert_not_called()

    def test_llm_failure(self, populated_db, long_term_dir):
        """LLM returning None should not crash."""
        with patch("hippoclaudus.comm_profiler.analyze_comm_profile") as mock_llm:
            mock_llm.return_value = None
            run_comm_profile("mock-model", populated_db, "James", long_term_dir)
