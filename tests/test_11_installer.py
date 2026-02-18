# tests/test_11_installer.py
"""Tests for core installer logic."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDirectoryCreation:
    """Installer creates the correct directory structure."""

    def test_create_directory_tree(self, tmp_path):
        from hippoclaudus.installer import create_directory_tree
        from hippoclaudus.platform import resolve_install_paths
        paths = resolve_install_paths(tmp_path)
        create_directory_tree(paths)
        assert (tmp_path / "mcp-memory" / "long-term").is_dir()
        assert (tmp_path / "mcp-memory" / "working").is_dir()
        assert (tmp_path / "mcp-memory" / "data").is_dir()

    def test_create_directory_tree_idempotent(self, tmp_path):
        from hippoclaudus.installer import create_directory_tree
        from hippoclaudus.platform import resolve_install_paths
        paths = resolve_install_paths(tmp_path)
        create_directory_tree(paths)
        create_directory_tree(paths)  # Should not raise
        assert (tmp_path / "mcp-memory" / "data").is_dir()


class TestConfigMerge:
    """Config file backup and merge logic."""

    def test_backup_config_creates_bak_file(self, tmp_path):
        from hippoclaudus.installer import backup_config
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text('{"mcpServers": {}}')
        bak_path = backup_config(config_path)
        assert bak_path.exists()
        assert ".bak." in bak_path.name
        assert bak_path.read_text() == '{"mcpServers": {}}'

    def test_backup_config_does_not_overwrite_existing(self, tmp_path):
        from hippoclaudus.installer import backup_config
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text('{"version": 1}')
        bak1 = backup_config(config_path)
        config_path.write_text('{"version": 2}')
        bak2 = backup_config(config_path)
        assert bak1 != bak2
        assert bak1.read_text() == '{"version": 1}'
        assert bak2.read_text() == '{"version": 2}'

    def test_merge_mcp_config_adds_memory_server(self, tmp_path):
        from hippoclaudus.installer import merge_mcp_config
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text('{}')
        merge_mcp_config(config_path, venv_python="/usr/bin/python", db_path="/tmp/memory.db")
        data = json.loads(config_path.read_text())
        assert "mcpServers" in data
        assert "memory" in data["mcpServers"]
        assert data["mcpServers"]["memory"]["command"] == "/usr/bin/python"

    def test_merge_mcp_config_preserves_existing_servers(self, tmp_path):
        from hippoclaudus.installer import merge_mcp_config
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text('{"mcpServers": {"other-server": {"command": "node"}}}')
        merge_mcp_config(config_path, venv_python="/usr/bin/python", db_path="/tmp/memory.db")
        data = json.loads(config_path.read_text())
        assert "other-server" in data["mcpServers"]
        assert "memory" in data["mcpServers"]

    def test_merge_mcp_config_creates_file_if_missing(self, tmp_path):
        from hippoclaudus.installer import merge_mcp_config
        config_path = tmp_path / "claude_desktop_config.json"
        merge_mcp_config(config_path, venv_python="/usr/bin/python", db_path="/tmp/memory.db")
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "memory" in data["mcpServers"]

    def test_merge_mcp_config_rejects_malformed_json(self, tmp_path):
        from hippoclaudus.installer import merge_mcp_config, InstallerError
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text('{"broken": json}')
        with pytest.raises(InstallerError, match="malformed"):
            merge_mcp_config(config_path, venv_python="/usr/bin/python", db_path="/tmp/memory.db")

    def test_merge_validates_roundtrip(self, tmp_path):
        from hippoclaudus.installer import merge_mcp_config
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text('{"mcpServers": {"x": {"command": "y"}}}')
        merge_mcp_config(config_path, venv_python="/usr/bin/python", db_path="/tmp/memory.db")
        # Verify the file is valid JSON
        data = json.loads(config_path.read_text())
        assert isinstance(data, dict)


class TestTemplateCopy:
    """Template copying and path substitution."""

    def test_copy_templates(self, tmp_path):
        from hippoclaudus.installer import copy_templates
        from hippoclaudus.platform import resolve_install_paths
        paths = resolve_install_paths(tmp_path)
        # Create dirs first
        for d in [paths["long_term"], paths["working"], paths["data"]]:
            d.mkdir(parents=True, exist_ok=True)
        copy_templates(paths)
        assert (paths["long_term"] / "INDEX.md").exists()
        assert (paths["working"] / "Session_Summary_Log.md").exists()
        assert (paths["working"] / "Open_Questions_Blockers.md").exists()
        assert (paths["working"] / "Decision_Log.md").exists()
        assert paths["claude_md"].exists()

    def test_claude_md_paths_substituted(self, tmp_path):
        from hippoclaudus.installer import copy_templates
        from hippoclaudus.platform import resolve_install_paths
        paths = resolve_install_paths(tmp_path)
        for d in [paths["long_term"], paths["working"], paths["data"]]:
            d.mkdir(parents=True, exist_ok=True)
        copy_templates(paths)
        content = paths["claude_md"].read_text()
        assert "YOUR_PATH" not in content
        assert str(tmp_path) in content


class TestUninstallConfigRestore:
    """Uninstaller config restoration."""

    def test_find_latest_backup(self, tmp_path):
        from hippoclaudus.installer import find_latest_backup
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text("{}")
        # Create two backups
        (tmp_path / "claude_desktop_config.json.bak.2026-02-17T1400").write_text('{"v": 1}')
        (tmp_path / "claude_desktop_config.json.bak.2026-02-17T1500").write_text('{"v": 2}')
        latest = find_latest_backup(config_path)
        assert latest is not None
        assert "1500" in latest.name

    def test_remove_memory_server_from_config(self, tmp_path):
        from hippoclaudus.installer import remove_memory_from_config
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text('{"mcpServers": {"memory": {"command": "x"}, "other": {"command": "y"}}}')
        remove_memory_from_config(config_path)
        data = json.loads(config_path.read_text())
        assert "memory" not in data["mcpServers"]
        assert "other" in data["mcpServers"]
