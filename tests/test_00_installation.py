"""Health checks: imports, DB, model cache, Mistral inference.

Fast tests verify the modules import correctly and the live memory.db is sane.
Slow tests (marked @pytest.mark.slow) actually load Mistral and run inference.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure hippoclaudus is importable
MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))


# ---------------------------------------------------------------------------
# Fast: Module imports
# ---------------------------------------------------------------------------

class TestImports:
    """Every hippoclaudus module should import without error."""

    def test_import_llm(self):
        from hippoclaudus import llm
        assert hasattr(llm, "run_prompt")
        assert hasattr(llm, "extract_json")
        assert hasattr(llm, "get_model")

    def test_import_db_bridge(self):
        from hippoclaudus import db_bridge
        assert hasattr(db_bridge, "MemoryDB")
        assert hasattr(db_bridge, "Memory")

    def test_import_scoring(self):
        from hippoclaudus import scoring
        assert hasattr(scoring, "recency_decay")
        assert hasattr(scoring, "composite_score")

    def test_import_consolidator(self):
        from hippoclaudus import consolidator
        assert hasattr(consolidator, "run_consolidation")

    def test_import_tagger(self):
        from hippoclaudus import tagger
        assert hasattr(tagger, "run_tag_single")
        assert hasattr(tagger, "run_tag_all")

    def test_import_compactor(self):
        from hippoclaudus import compactor
        assert hasattr(compactor, "run_compact")
        assert hasattr(compactor, "_similarity_simple")

    def test_import_predictor(self):
        from hippoclaudus import predictor
        assert hasattr(predictor, "run_predict")

    def test_import_comm_profiler(self):
        from hippoclaudus import comm_profiler
        assert hasattr(comm_profiler, "run_comm_profile")

    def test_import_click(self):
        import click
        assert hasattr(click, "group")

    def test_import_mlx(self):
        import mlx.core
        assert hasattr(mlx.core, "array")

    def test_import_mlx_lm(self):
        from mlx_lm import load, generate
        assert callable(load)
        assert callable(generate)

    def test_import_sentence_transformers(self):
        import sentence_transformers
        assert hasattr(sentence_transformers, "SentenceTransformer")

    def test_version(self):
        import hippoclaudus
        assert hippoclaudus.__version__ == "0.1.0"


# ---------------------------------------------------------------------------
# Fast: Live memory.db sanity
# ---------------------------------------------------------------------------

class TestLiveDB:
    """Verify the production memory.db is present and sane."""

    LIVE_DB = MCP_ROOT / "data" / "memory.db"

    def test_db_exists(self):
        assert self.LIVE_DB.exists(), f"Live DB missing: {self.LIVE_DB}"

    def test_db_has_memories(self):
        import sqlite3
        conn = sqlite3.connect(str(self.LIVE_DB))
        count = conn.execute("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL").fetchone()[0]
        conn.close()
        assert count >= 3, f"Live DB has only {count} memories, expected >= 3"

    def test_db_wal_mode(self):
        import sqlite3
        conn = sqlite3.connect(str(self.LIVE_DB))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal", f"Expected WAL mode, got {mode}"

    def test_db_has_required_tables(self):
        import sqlite3
        conn = sqlite3.connect(str(self.LIVE_DB))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        for expected in ["memories", "memory_graph", "metadata"]:
            assert expected in tables, f"Missing table: {expected}"


# ---------------------------------------------------------------------------
# Fast: Mistral model files in cache
# ---------------------------------------------------------------------------

class TestModelCache:
    """Check that Mistral model files are present in HuggingFace cache."""

    HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"

    def test_mistral_cache_dir_exists(self):
        dirs = list(self.HF_CACHE.glob("models--mlx-community--Mistral*"))
        assert len(dirs) >= 1, "No Mistral model cache directory found"

    def test_mistral_has_safetensors(self):
        dirs = list(self.HF_CACHE.glob("models--mlx-community--Mistral*"))
        if not dirs:
            pytest.skip("No Mistral cache dir")
        # Look for safetensors in any snapshot
        safetensors = list(dirs[0].rglob("*.safetensors"))
        assert len(safetensors) >= 1, "No .safetensors files found in Mistral cache"


# ---------------------------------------------------------------------------
# Slow: Real Mistral inference
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestMistralInference:
    """These tests actually load and run Mistral-7B. ~30s per test."""

    MODEL = "mlx-community/Mistral-7B-Instruct-v0.3-4bit"

    def test_model_loads(self):
        from hippoclaudus.llm import get_model
        model, tokenizer = get_model(self.MODEL)
        assert model is not None
        assert tokenizer is not None

    def test_model_cache_reuse(self):
        from hippoclaudus.llm import get_model
        m1, t1 = get_model(self.MODEL)
        m2, t2 = get_model(self.MODEL)
        assert m1 is m2, "Model should be cached (same object)"
        assert t1 is t2, "Tokenizer should be cached (same object)"

    def test_simple_inference(self):
        from hippoclaudus.llm import run_prompt
        response = run_prompt(self.MODEL, "What is 2+2? Reply with just the number.", max_tokens=32)
        assert "4" in response, f"Expected '4' in response, got: {response}"

    def test_json_inference(self):
        from hippoclaudus.llm import run_prompt, extract_json
        response = run_prompt(
            self.MODEL,
            'Return a JSON object: {"color": "blue", "count": 3}. Return ONLY JSON.',
            max_tokens=64,
        )
        result = extract_json(response)
        assert result is not None, f"Failed to extract JSON from: {response}"

    def test_consolidation_prompt(self):
        from hippoclaudus.llm import consolidate_session
        session = "## 2026-02-08 -- Test Session\n### Context\nTested the database.\n### What We Covered\n- Built the CLI\n"
        result = consolidate_session(self.MODEL, session)
        assert result is not None, "Consolidation returned None"
        assert "state_delta" in result, f"Missing state_delta key in: {result}"

    def test_entity_tag_prompt(self):
        from hippoclaudus.llm import tag_memory
        result = tag_memory(self.MODEL, "James discussed DeCue funding strategy with Dana")
        assert result is not None, "Tag extraction returned None"
        # Should find at least some entities
        all_entities = []
        for cat in ["people", "projects", "tools", "topics"]:
            all_entities.extend(result.get(cat, []))
        assert len(all_entities) >= 1, f"No entities extracted from: {result}"

    def test_comm_profile_prompt(self):
        from hippoclaudus.llm import analyze_comm_profile
        excerpts = "James said 'ship it'. James prefers direct communication. James values speed."
        result = analyze_comm_profile(self.MODEL, "James", excerpts)
        assert result is not None, "Comm profile returned None"
        assert "tone" in result or "decision_style" in result, f"Missing profile keys in: {result}"
