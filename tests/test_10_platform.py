# tests/test_10_platform.py
"""Tests for cross-platform path resolution."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPlatformDetection:
    """Platform detection returns correct OS string."""

    def test_detect_returns_string(self):
        from hippoclaudus.platform import detect_platform
        result = detect_platform()
        assert result in ("darwin", "linux", "windows")

    def test_detect_matches_current_os(self):
        from hippoclaudus.platform import detect_platform
        import platform as stdlib_platform
        result = detect_platform()
        if stdlib_platform.system() == "Darwin":
            assert result == "darwin"
        elif stdlib_platform.system() == "Linux":
            assert result == "linux"
        elif stdlib_platform.system() == "Windows":
            assert result == "windows"


class TestConfigPaths:
    """Config path resolution for each platform."""

    def test_claude_config_path_returns_path(self):
        from hippoclaudus.platform import get_claude_config_path
        result = get_claude_config_path()
        assert isinstance(result, Path)
        assert result.name == "claude_desktop_config.json"

    @patch("hippoclaudus.platform.detect_platform", return_value="darwin")
    def test_claude_config_path_darwin(self, mock):
        from hippoclaudus.platform import get_claude_config_path
        result = get_claude_config_path()
        assert "Application Support" in str(result)
        assert "Claude" in str(result)

    @patch("hippoclaudus.platform.detect_platform", return_value="linux")
    def test_claude_config_path_linux(self, mock):
        from hippoclaudus.platform import get_claude_config_path
        result = get_claude_config_path()
        assert ".config" in str(result)

    @patch("hippoclaudus.platform.detect_platform", return_value="windows")
    @patch("os.environ", {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"})
    def test_claude_config_path_windows(self, mock):
        from hippoclaudus.platform import get_claude_config_path
        result = get_claude_config_path()
        assert "AppData" in str(result) or "APPDATA" in str(result).upper()


class TestInstallPaths:
    """Install base path resolution."""

    def test_default_install_base_returns_path(self):
        from hippoclaudus.platform import get_default_install_base
        result = get_default_install_base()
        assert isinstance(result, Path)
        assert "Claude" in str(result)

    def test_resolve_install_paths(self):
        from hippoclaudus.platform import resolve_install_paths
        base = Path("/tmp/test-hippo")
        paths = resolve_install_paths(base)
        assert paths["base"] == base
        assert paths["mcp_root"] == base / "mcp-memory"
        assert paths["long_term"] == base / "mcp-memory" / "long-term"
        assert paths["working"] == base / "mcp-memory" / "working"
        assert paths["data"] == base / "mcp-memory" / "data"
        assert paths["venv"] == base / "mcp-memory" / "venv"
        assert paths["db"] == base / "mcp-memory" / "data" / "memory.db"
        assert paths["claude_md"] == base / "CLAUDE.md"


class TestPythonCheck:
    """Python version validation."""

    def test_check_python_version_succeeds(self):
        from hippoclaudus.platform import check_python_version
        result = check_python_version()
        assert result["ok"] is True

    def test_check_python_version_returns_version_info(self):
        from hippoclaudus.platform import check_python_version
        result = check_python_version()
        assert "version" in result
        assert "major" in result
        assert "minor" in result


class TestDotfile:
    """Install metadata dotfile read/write."""

    def test_write_and_read_dotfile(self, tmp_path):
        from hippoclaudus.platform import write_dotfile, read_dotfile
        dotfile = tmp_path / ".hippoclaudus"
        write_dotfile(dotfile, install_path="/tmp/test", version="4.1.0", platform_name="darwin")
        data = read_dotfile(dotfile)
        assert data["install_path"] == "/tmp/test"
        assert data["version"] == "4.1.0"
        assert data["platform"] == "darwin"
        assert "installed_at" in data
        assert data["llm_installed"] is False

    def test_read_missing_dotfile_returns_none(self, tmp_path):
        from hippoclaudus.platform import read_dotfile
        result = read_dotfile(tmp_path / ".hippoclaudus")
        assert result is None
