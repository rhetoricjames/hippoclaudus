"""JSON extraction edge cases, prompt templates, model cache."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from hippoclaudus.llm import extract_json, CONSOLIDATION_PROMPT, ENTITY_TAG_PROMPT, COMM_PROFILE_PROMPT


# ---------------------------------------------------------------------------
# extract_json — happy paths
# ---------------------------------------------------------------------------

class TestExtractJsonHappy:

    def test_clean_json(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_code_fenced_json(self):
        text = '```json\n{"name": "test", "count": 42}\n```'
        result = extract_json(text)
        assert result == {"name": "test", "count": 42}

    def test_code_fenced_no_lang(self):
        text = '```\n{"status": "ok"}\n```'
        result = extract_json(text)
        assert result == {"status": "ok"}

    def test_surrounded_by_text(self):
        text = 'Here is the result:\n{"answer": 42}\nHope this helps!'
        result = extract_json(text)
        assert result == {"answer": 42}

    def test_nested_json(self):
        data = {"outer": {"inner": [1, 2, 3]}, "flag": True}
        text = f"Result: {json.dumps(data)}"
        result = extract_json(text)
        assert result == data

    def test_empty_object(self):
        result = extract_json("{}")
        assert result == {}

    def test_json_with_newlines(self):
        text = '{\n  "key": "value",\n  "list": [1, 2]\n}'
        result = extract_json(text)
        assert result == {"key": "value", "list": [1, 2]}

    def test_json_with_escaped_quotes(self):
        text = '{"message": "He said \\"hello\\""}'
        result = extract_json(text)
        assert result is not None
        assert "hello" in result["message"]


# ---------------------------------------------------------------------------
# extract_json — failure modes
# ---------------------------------------------------------------------------

class TestExtractJsonFailures:

    def test_no_json(self):
        result = extract_json("This is just plain text with no JSON at all.")
        assert result is None

    def test_invalid_json(self):
        result = extract_json("{invalid: json, no quotes}")
        assert result is None

    def test_empty_string(self):
        result = extract_json("")
        assert result is None

    def test_single_quotes_invalid(self):
        """Python dicts use single quotes, JSON doesn't."""
        result = extract_json("{'key': 'value'}")
        assert result is None

    @pytest.mark.xfail(reason="Known: Greedy regex grabs both objects as one invalid block")
    def test_two_json_objects(self):
        """Two JSON objects in one string — greedy regex may grab both."""
        text = '{"a": 1} and also {"b": 2}'
        result = extract_json(text)
        # Ideally returns first one, but greedy regex grabs everything from first { to last }
        assert result == {"a": 1}

    def test_array_not_object(self):
        """extract_json only looks for objects {}, not arrays []."""
        result = extract_json("[1, 2, 3]")
        assert result is None

    def test_just_braces(self):
        result = extract_json("{not valid json at all}")
        assert result is None


# ---------------------------------------------------------------------------
# extract_json — stress tests
# ---------------------------------------------------------------------------

class TestExtractJsonStress:

    def test_very_large_json(self):
        """1000-key JSON object should still parse."""
        data = {f"key_{i}": f"value_{i}" for i in range(1000)}
        text = json.dumps(data)
        result = extract_json(text)
        assert result is not None
        assert len(result) == 1000

    def test_deeply_nested(self):
        """Deeply nested structure."""
        data = {"level": 0}
        current = data
        for i in range(1, 20):
            current["child"] = {"level": i}
            current = current["child"]
        text = json.dumps(data)
        result = extract_json(text)
        assert result is not None
        assert result["level"] == 0


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

class TestPromptTemplates:

    def test_consolidation_prompt_formats(self):
        """CONSOLIDATION_PROMPT should format without error."""
        result = CONSOLIDATION_PROMPT.format(session_text="Test session content")
        assert "Test session content" in result
        assert "state_delta" in result

    def test_entity_tag_prompt_formats(self):
        result = ENTITY_TAG_PROMPT.format(content="James discussed DeCue")
        assert "James discussed DeCue" in result
        assert "people" in result

    def test_comm_profile_prompt_formats(self):
        result = COMM_PROFILE_PROMPT.format(person="James", excerpts="some excerpts")
        assert "James" in result
        assert "some excerpts" in result

    def test_prompt_injection_braces(self):
        """Input with curly braces shouldn't cause KeyError."""
        # The templates use {{ }} for literal braces, so regular {text} in input is fine
        # as long as we only .format() the right keys
        result = CONSOLIDATION_PROMPT.format(session_text="Data: {foo: bar, baz: 123}")
        assert "{foo: bar" in result

    def test_prompt_special_characters(self):
        """Input with special chars shouldn't break formatting."""
        weird_input = 'Content with "quotes" and\nnewlines\tand\ttabs'
        result = ENTITY_TAG_PROMPT.format(content=weird_input)
        assert "quotes" in result


# ---------------------------------------------------------------------------
# Model cache mock
# ---------------------------------------------------------------------------

class TestModelCacheMock:

    def test_cache_loads_once(self):
        """get_model should call load() only once per model name."""
        import hippoclaudus.llm as llm_module
        # Save and reset cache
        old_cache = llm_module._model_cache.copy()
        llm_module._model_cache.clear()

        mock_model = MagicMock()
        mock_tokenizer = MagicMock()

        with patch.object(llm_module, "load", return_value=(mock_model, mock_tokenizer)) as mock_load:
            m1, t1 = llm_module.get_model("test-model")
            m2, t2 = llm_module.get_model("test-model")

            mock_load.assert_called_once_with("test-model")
            assert m1 is m2
            assert t1 is t2

        # Restore cache
        llm_module._model_cache.clear()
        llm_module._model_cache.update(old_cache)

    def test_different_models_cached_separately(self):
        """Different model names should have separate cache entries."""
        import hippoclaudus.llm as llm_module
        old_cache = llm_module._model_cache.copy()
        llm_module._model_cache.clear()

        mock_a = (MagicMock(), MagicMock())
        mock_b = (MagicMock(), MagicMock())

        with patch.object(llm_module, "load", side_effect=[mock_a, mock_b]) as mock_load:
            llm_module.get_model("model-a")
            llm_module.get_model("model-b")
            assert mock_load.call_count == 2

        llm_module._model_cache.clear()
        llm_module._model_cache.update(old_cache)
