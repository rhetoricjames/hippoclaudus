# tests/test_12_personalizer.py
"""Tests for interactive CLAUDE.md personalization."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPersonalizerBlocks:
    """PERSONALIZE block detection and replacement."""

    def test_find_personalize_blocks(self):
        from hippoclaudus.personalizer import find_personalize_blocks
        content = "# Header\n<!-- PERSONALIZE: identity -->\nsome text\n<!-- END PERSONALIZE -->\nfooter"
        blocks = find_personalize_blocks(content)
        assert len(blocks) >= 1
        assert blocks[0]["tag"] == "identity"

    def test_replace_personalize_block(self):
        from hippoclaudus.personalizer import replace_personalize_block
        content = "before\n<!-- PERSONALIZE: identity -->\nold content\n<!-- END PERSONALIZE -->\nafter"
        result = replace_personalize_block(content, "identity", "new content")
        assert "new content" in result
        assert "old content" not in result
        assert "before" in result
        assert "after" in result

    def test_replace_preserves_unmatched_blocks(self):
        from hippoclaudus.personalizer import replace_personalize_block
        content = (
            "<!-- PERSONALIZE: identity -->\nid stuff\n<!-- END PERSONALIZE -->\n"
            "<!-- PERSONALIZE: people -->\npeople stuff\n<!-- END PERSONALIZE -->"
        )
        result = replace_personalize_block(content, "identity", "new id")
        assert "new id" in result
        assert "people stuff" in result


class TestGenerateBlocks:
    """Generate content for personalization blocks."""

    def test_generate_identity_block(self):
        from hippoclaudus.personalizer import generate_identity_block
        result = generate_identity_block(
            user_name="Jane",
            persona_name="Atlas",
            work_type="data science",
        )
        assert "Jane" in result
        assert "Atlas" in result
        assert "data science" in result

    def test_generate_identity_block_no_persona(self):
        from hippoclaudus.personalizer import generate_identity_block
        result = generate_identity_block(
            user_name="Jane",
            persona_name=None,
            work_type="engineering",
        )
        assert "Jane" in result
        assert "persona" not in result.lower() or "no specific persona" in result.lower()

    def test_generate_people_block(self):
        from hippoclaudus.personalizer import generate_people_block
        people = [
            {"name": "Alice", "relationship": "manager", "role": "Engineering Director"},
            {"name": "Bob", "relationship": "colleague", "role": "Backend Engineer"},
        ]
        result = generate_people_block(people)
        assert "Alice" in result
        assert "Bob" in result
        assert "manager" in result

    def test_generate_people_block_empty(self):
        from hippoclaudus.personalizer import generate_people_block
        result = generate_people_block([])
        assert isinstance(result, str)  # Should return something, even if minimal

    def test_generate_machine_block(self):
        from hippoclaudus.personalizer import generate_machine_block
        result = generate_machine_block("MacBook Pro M3, primary development machine")
        assert "MacBook" in result
