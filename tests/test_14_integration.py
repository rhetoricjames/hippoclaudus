# tests/test_14_integration.py
"""Integration tests for full install/uninstall round-trip.

These tests create real directory structures and config files
in a temp directory. They do NOT install actual packages
(mocked), but verify the orchestration logic end-to-end.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFullInstallRoundTrip:
    """Full install -> verify -> uninstall cycle."""

    @patch("hippoclaudus.installer.create_venv")
    @patch("hippoclaudus.installer.install_mcp_memory_service")
    @patch("hippoclaudus.installer.verify_mcp_install", return_value=True)
    def test_install_creates_all_expected_files(self, mock_verify, mock_mcp, mock_venv, tmp_path):
        from hippoclaudus.installer import run_install
        from hippoclaudus.platform import get_dotfile_path

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        dotfile = tmp_path / ".hippoclaudus"
        install_base = tmp_path / "Claude"

        with patch("hippoclaudus.installer.get_claude_config_path", return_value=config_dir / "claude_desktop_config.json"), \
             patch("hippoclaudus.installer.get_dotfile_path", return_value=dotfile):
            result = run_install(base_path=install_base)

        assert result["success"]
        assert (install_base / "mcp-memory" / "long-term").is_dir()
        assert (install_base / "mcp-memory" / "working").is_dir()
        assert (install_base / "mcp-memory" / "data").is_dir()
        assert (install_base / "CLAUDE.md").exists()
        assert dotfile.exists()

        # Verify config was created
        config = config_dir / "claude_desktop_config.json"
        assert config.exists()
        data = json.loads(config.read_text())
        assert "memory" in data["mcpServers"]

        # Verify CLAUDE.md has paths substituted
        content = (install_base / "CLAUDE.md").read_text()
        assert "YOUR_PATH" not in content
        assert str(install_base) in content

    @patch("hippoclaudus.installer.create_venv")
    @patch("hippoclaudus.installer.install_mcp_memory_service")
    @patch("hippoclaudus.installer.verify_mcp_install", return_value=True)
    def test_install_backs_up_existing_config(self, mock_verify, mock_mcp, mock_venv, tmp_path):
        from hippoclaudus.installer import run_install

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_path = config_dir / "claude_desktop_config.json"
        config_path.write_text('{"mcpServers": {"existing": {"command": "node"}}}')
        dotfile = tmp_path / ".hippoclaudus"
        install_base = tmp_path / "Claude"

        with patch("hippoclaudus.installer.get_claude_config_path", return_value=config_path), \
             patch("hippoclaudus.installer.get_dotfile_path", return_value=dotfile):
            result = run_install(base_path=install_base)

        assert result["backup_path"] is not None
        # Verify existing server preserved
        data = json.loads(config_path.read_text())
        assert "existing" in data["mcpServers"]
        assert "memory" in data["mcpServers"]

    @patch("hippoclaudus.installer.create_venv")
    @patch("hippoclaudus.installer.install_mcp_memory_service")
    @patch("hippoclaudus.installer.verify_mcp_install", return_value=True)
    def test_uninstall_restores_config(self, mock_verify, mock_mcp, mock_venv, tmp_path):
        from hippoclaudus.installer import run_install, run_uninstall

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_path = config_dir / "claude_desktop_config.json"
        original_config = '{"mcpServers": {"existing": {"command": "node"}}}'
        config_path.write_text(original_config)
        dotfile = tmp_path / ".hippoclaudus"
        install_base = tmp_path / "Claude"

        with patch("hippoclaudus.installer.get_claude_config_path", return_value=config_path), \
             patch("hippoclaudus.installer.get_dotfile_path", return_value=dotfile):
            run_install(base_path=install_base)

            # Now uninstall (without removing data)
            result = run_uninstall(remove_data=False)

        assert result["success"]
        assert result["data_removed"] is False
        # Config should be restored to original
        restored = json.loads(config_path.read_text())
        assert "existing" in restored["mcpServers"]

    @patch("hippoclaudus.installer.create_venv")
    @patch("hippoclaudus.installer.install_mcp_memory_service")
    @patch("hippoclaudus.installer.verify_mcp_install", return_value=True)
    def test_uninstall_with_data_removal(self, mock_verify, mock_mcp, mock_venv, tmp_path):
        from hippoclaudus.installer import run_install, run_uninstall

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_path = config_dir / "claude_desktop_config.json"
        dotfile = tmp_path / ".hippoclaudus"
        install_base = tmp_path / "Claude"

        with patch("hippoclaudus.installer.get_claude_config_path", return_value=config_path), \
             patch("hippoclaudus.installer.get_dotfile_path", return_value=dotfile):
            run_install(base_path=install_base)
            result = run_uninstall(remove_data=True)

        assert result["data_removed"] is True
        assert not (install_base / "mcp-memory").exists()
        assert not dotfile.exists()
