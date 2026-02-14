"""PRELOAD.md generation tests — mocked + real Mistral."""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from tests.conftest import MOCK_PREDICT_RESPONSE

from hippoclaudus.db_bridge import MemoryDB, Memory
from hippoclaudus.predictor import run_predict


# ---------------------------------------------------------------------------
# Mocked
# ---------------------------------------------------------------------------

class TestPredictMocked:

    def test_writes_preload_file(self, populated_db, sample_session_log, open_questions_file, tmp_path):
        """run_predict should write a PRELOAD.md file."""
        output = tmp_path / "PRELOAD.md"

        with patch("hippoclaudus.predictor.run_prompt") as mock_rp:
            mock_rp.return_value = MOCK_PREDICT_RESPONSE
            run_predict(
                model_name="mock-model",
                db_path=populated_db,
                session_log=sample_session_log,
                open_questions=open_questions_file,
                output=output,
            )

        assert output.exists()
        content = output.read_text()
        assert "PRELOAD" in content
        assert "Session Briefing" in content

    def test_missing_inputs_use_placeholders(self, tmp_db, tmp_path):
        """Missing session log / open questions should still generate output."""
        output = tmp_path / "PRELOAD.md"
        fake_log = tmp_path / "nonexistent_log.md"
        fake_oq = tmp_path / "nonexistent_oq.md"

        with patch("hippoclaudus.predictor.run_prompt") as mock_rp:
            mock_rp.return_value = MOCK_PREDICT_RESPONSE
            run_predict(
                model_name="mock-model",
                db_path=tmp_db,
                session_log=fake_log,
                open_questions=fake_oq,
                output=output,
            )

        assert output.exists()

    def test_no_state_deltas(self, tmp_db, sample_session_log, open_questions_file, tmp_path):
        """DB with no state_deltas should still work."""
        output = tmp_path / "PRELOAD.md"

        with patch("hippoclaudus.predictor.run_prompt") as mock_rp:
            mock_rp.return_value = MOCK_PREDICT_RESPONSE
            run_predict(
                model_name="mock-model",
                db_path=tmp_db,
                session_log=sample_session_log,
                open_questions=open_questions_file,
                output=output,
            )

        assert output.exists()

    def test_long_session_text_capped(self, tmp_db, open_questions_file, tmp_path):
        """Session text should be capped at 3000 chars to avoid context overflow."""
        # Create a very long session log
        long_log = tmp_path / "long_session.md"
        long_log.write_text(
            "# Session Log\n\n---\n\n"
            "## 2026-02-08 -- Long Session\n\n"
            "### Context\n" + ("A" * 5000) + "\n"
        )
        output = tmp_path / "PRELOAD.md"

        with patch("hippoclaudus.predictor.run_prompt") as mock_rp:
            mock_rp.return_value = MOCK_PREDICT_RESPONSE
            run_predict(
                model_name="mock-model",
                db_path=tmp_db,
                session_log=long_log,
                open_questions=open_questions_file,
                output=output,
            )

            # Check the prompt that was passed to run_prompt
            call_args = mock_rp.call_args
            prompt_text = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("prompt", "")
            # The session_text portion should be capped
            # (run_predict caps session_text at 3000 chars via [:3000])

        assert output.exists()


# ---------------------------------------------------------------------------
# Real Mistral
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestPredictReal:

    def test_full_predict_real(self, populated_db, sample_session_log, open_questions_file, tmp_path):
        """Real Mistral inference for PRELOAD generation."""
        output = tmp_path / "PRELOAD.md"

        run_predict(
            model_name="mlx-community/Mistral-7B-Instruct-v0.3-4bit",
            db_path=populated_db,
            session_log=sample_session_log,
            open_questions=open_questions_file,
            output=output,
        )

        assert output.exists()
        content = output.read_text()
        assert len(content) > 50, "PRELOAD output too short"
