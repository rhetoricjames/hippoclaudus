# Hippoclaudus v4.1 Installer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `hippo install` — a single CLI command that fully installs the Hippoclaudus memory architecture for Claude, cross-platform (macOS/Linux/Windows), with optional LLM backend and interactive personalization.

**Architecture:** Four new Python modules (`platform.py`, `installer.py`, `personalizer.py`, `llm_installer.py`) wired into the existing Click CLI. Platform detection resolves all OS-specific paths. The installer creates directories, installs the MCP memory server into a venv, merges config with backup, drops a generic CLAUDE.md, and writes install metadata. LLM backend and personalization are separate opt-in commands.

**Tech Stack:** Python 3.10+, Click (existing dep), pathlib, json, shutil, subprocess, venv

**Design Doc:** `docs/plans/2026-02-17-installer-design.md`

---

### Task 1: `hippoclaudus/platform.py` — Platform Detection

**Files:**
- Create: `hippoclaudus/platform.py`
- Test: `tests/test_10_platform.py`

**Step 1: Write the failing tests**

```python
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
        # We're running on 3.10+, so this should pass
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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_10_platform.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hippoclaudus.platform'`

**Step 3: Write minimal implementation**

```python
# hippoclaudus/platform.py
"""Cross-platform path resolution for Hippoclaudus installation.

Detects macOS / Linux / Windows and resolves:
- Claude Desktop config file location
- Default install base directory
- Session transcript paths
- Venv and database paths
"""

import json
import os
import platform as stdlib_platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def detect_platform() -> str:
    """Return 'darwin', 'linux', or 'windows'."""
    system = stdlib_platform.system()
    if system == "Darwin":
        return "darwin"
    elif system == "Linux":
        return "linux"
    elif system == "Windows":
        return "windows"
    else:
        return "linux"  # Best guess for unknown Unix-like


def get_claude_config_path() -> Path:
    """Return the platform-specific path to claude_desktop_config.json."""
    plat = detect_platform()
    if plat == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif plat == "linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    elif plat == "windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def get_default_install_base() -> Path:
    """Return the default installation base directory."""
    plat = detect_platform()
    if plat == "windows":
        userprofile = os.environ.get("USERPROFILE", str(Path.home()))
        return Path(userprofile) / "Documents" / "Claude"
    else:
        return Path.home() / "Documents" / "Claude"


def get_sessions_path() -> Path:
    """Return the path to Claude Code session transcripts."""
    plat = detect_platform()
    if plat == "windows":
        userprofile = os.environ.get("USERPROFILE", str(Path.home()))
        return Path(userprofile) / ".claude" / "projects"
    else:
        return Path.home() / ".claude" / "projects"


def resolve_install_paths(base: Path) -> dict:
    """Given an install base, return all derived paths as a dict."""
    mcp_root = base / "mcp-memory"
    return {
        "base": base,
        "mcp_root": mcp_root,
        "long_term": mcp_root / "long-term",
        "working": mcp_root / "working",
        "data": mcp_root / "data",
        "models": mcp_root / "models",
        "venv": mcp_root / "venv",
        "db": mcp_root / "data" / "memory.db",
        "claude_md": base / "CLAUDE.md",
    }


def get_venv_python(venv_path: Path) -> Path:
    """Return the path to the Python executable inside a venv."""
    plat = detect_platform()
    if plat == "windows":
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python"


def get_venv_pip(venv_path: Path) -> Path:
    """Return the path to pip inside a venv."""
    plat = detect_platform()
    if plat == "windows":
        return venv_path / "Scripts" / "pip.exe"
    else:
        return venv_path / "bin" / "pip"


def check_python_version(minimum_major: int = 3, minimum_minor: int = 10) -> dict:
    """Check if the current Python meets the minimum version requirement."""
    major = sys.version_info.major
    minor = sys.version_info.minor
    ok = (major > minimum_major) or (major == minimum_major and minor >= minimum_minor)
    return {
        "ok": ok,
        "version": f"{major}.{minor}.{sys.version_info.micro}",
        "major": major,
        "minor": minor,
    }


def get_dotfile_path() -> Path:
    """Return the path to the .hippoclaudus metadata dotfile."""
    return Path.home() / ".hippoclaudus"


def write_dotfile(path: Path, install_path: str, version: str, platform_name: str) -> None:
    """Write install metadata to the dotfile."""
    data = {
        "install_path": install_path,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "llm_installed": False,
        "platform": platform_name,
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


def read_dotfile(path: Path) -> Optional[dict]:
    """Read install metadata from the dotfile. Returns None if missing."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def update_dotfile(path: Path, **kwargs) -> None:
    """Update specific fields in the dotfile."""
    data = read_dotfile(path)
    if data is None:
        return
    data.update(kwargs)
    path.write_text(json.dumps(data, indent=2) + "\n")
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_10_platform.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add hippoclaudus/platform.py tests/test_10_platform.py
git commit -m "feat: add platform detection module for cross-platform installer"
```

---

### Task 2: `hippoclaudus/installer.py` — Core Install Logic

**Files:**
- Create: `hippoclaudus/installer.py`
- Test: `tests/test_11_installer.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_11_installer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hippoclaudus.installer'`

**Step 3: Write minimal implementation**

```python
# hippoclaudus/installer.py
"""Core install/uninstall logic for Hippoclaudus.

Handles:
- Directory tree creation
- Virtual environment setup + mcp-memory-service install
- Claude config backup, merge, and restore
- Template copying with path substitution
- Install metadata dotfile
"""

import json
import shutil
import subprocess
import sys
import venv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hippoclaudus.platform import (
    detect_platform,
    get_claude_config_path,
    get_venv_python,
    get_venv_pip,
    resolve_install_paths,
    write_dotfile,
    get_dotfile_path,
)

# Find templates directory relative to this package
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Version
VERSION = "4.1.0"

# The LLM recommendation message
LLM_RECOMMENDATION = """
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Although download time and system memory allocation will be increased │
  │  by a full installation, incorporation of a small, local LLM is       │
  │  strongly advised. The full benefit of the Hippoclaudus Memory        │
  │  Architecture will not be available without doing so and, in          │
  │  addition, if Claude receives no assistance with regard to searching  │
  │  long-term memory or related processing tasks, token usage rates will │
  │  increase and some lag in memory processing time may be experienced.  │
  │  Beyond that, what could be cooler than an AI using an AI to help     │
  │  you better use AI?                                                   │
  │                                                                       │
  │  Run: hippo install --with-llm                                        │
  └─────────────────────────────────────────────────────────────────────────┘
""".strip()


class InstallerError(Exception):
    """Raised when installation encounters a non-recoverable error."""
    pass


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

def create_directory_tree(paths: dict) -> list:
    """Create the mcp-memory directory structure. Returns list of created dirs."""
    created = []
    for key in ("long_term", "working", "data", "models"):
        d = paths[key]
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))
    return created


# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------

def create_venv(venv_path: Path) -> None:
    """Create a Python virtual environment."""
    if not venv_path.exists():
        venv.create(str(venv_path), with_pip=True)


def install_mcp_memory_service(venv_path: Path) -> None:
    """Install mcp-memory-service into the venv."""
    pip = get_venv_pip(venv_path)
    subprocess.run(
        [str(pip), "install", "--quiet", "mcp-memory-service"],
        check=True,
        capture_output=True,
    )


def verify_mcp_install(venv_path: Path) -> bool:
    """Verify mcp_memory_service is importable in the venv."""
    python = get_venv_python(venv_path)
    result = subprocess.run(
        [str(python), "-c", "import mcp_memory_service"],
        capture_output=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Config backup and merge
# ---------------------------------------------------------------------------

def backup_config(config_path: Path) -> Path:
    """Back up the config file with a timestamped suffix. Returns backup path."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H%M")
    bak_path = config_path.parent / f"{config_path.name}.bak.{timestamp}"
    # If this exact timestamp exists (ran twice in same minute), add seconds
    if bak_path.exists():
        timestamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
        bak_path = config_path.parent / f"{config_path.name}.bak.{timestamp}"
    shutil.copy2(config_path, bak_path)
    return bak_path


def merge_mcp_config(config_path: Path, venv_python: str, db_path: str) -> None:
    """Merge the Hippoclaudus MCP server entry into the Claude config.

    Preserves all existing mcpServers entries. Creates the file if missing.
    Raises InstallerError if existing file contains malformed JSON.
    """
    if config_path.exists():
        raw = config_path.read_text()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise InstallerError(
                f"Existing config is malformed JSON: {config_path}\n"
                "Fix it manually or run 'hippo doctor' for guidance."
            )
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}

    if "mcpServers" not in data:
        data["mcpServers"] = {}

    data["mcpServers"]["memory"] = {
        "command": venv_python,
        "args": ["-m", "mcp_memory_service"],
        "env": {
            "MCP_MEMORY_DB_PATH": db_path,
        },
    }

    # Validate round-trip before writing
    output = json.dumps(data, indent=2)
    json.loads(output)  # Will raise if somehow broken

    config_path.write_text(output + "\n")


# ---------------------------------------------------------------------------
# Template copying
# ---------------------------------------------------------------------------

def copy_templates(paths: dict) -> list:
    """Copy template files to the install base and substitute paths.

    Returns list of files copied.
    """
    copied = []
    base_str = str(paths["base"])

    # Long-term memory templates
    for name in ("INDEX.md", "Total_Update_Protocol.md", "Memory_Bootstrap.md",
                 "Infrastructure_Notes.md"):
        src = TEMPLATE_DIR / name
        if src.exists():
            dst = paths["long_term"] / name
            if not dst.exists():
                shutil.copy2(src, dst)
                copied.append(str(dst))

    # Working memory templates
    for name in ("Session_Summary_Log.md", "Open_Questions_Blockers.md", "Decision_Log.md"):
        src = TEMPLATE_DIR / name
        if src.exists():
            dst = paths["working"] / name
            if not dst.exists():
                shutil.copy2(src, dst)
                copied.append(str(dst))

    # CLAUDE.md — always overwrite with fresh template (personalize later)
    src = TEMPLATE_DIR / "CLAUDE.md"
    if src.exists():
        dst = paths["claude_md"]
        content = src.read_text()
        content = content.replace("YOUR_PATH", base_str)
        dst.write_text(content)
        copied.append(str(dst))

    return copied


# ---------------------------------------------------------------------------
# Uninstall helpers
# ---------------------------------------------------------------------------

def find_latest_backup(config_path: Path) -> Optional[Path]:
    """Find the most recent .bak file for the config."""
    pattern = f"{config_path.name}.bak.*"
    backups = sorted(config_path.parent.glob(pattern))
    return backups[-1] if backups else None


def remove_memory_from_config(config_path: Path) -> None:
    """Remove just the 'memory' entry from mcpServers, preserving everything else."""
    if not config_path.exists():
        return
    data = json.loads(config_path.read_text())
    servers = data.get("mcpServers", {})
    if "memory" in servers:
        del servers["memory"]
    config_path.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Main install orchestrator
# ---------------------------------------------------------------------------

def run_install(base_path: Optional[Path] = None, with_llm: bool = False) -> dict:
    """Execute the full installation. Returns a result dict.

    Steps:
    1. Detect platform, resolve paths
    2. Check Python version
    3. Create directory tree
    4. Create venv, install mcp-memory-service
    5. Backup config, merge MCP entry
    6. Copy templates
    7. Write dotfile
    """
    from hippoclaudus.platform import (
        check_python_version,
        get_default_install_base,
    )

    # 1. Platform + paths
    plat = detect_platform()
    if base_path is None:
        base_path = get_default_install_base()
    paths = resolve_install_paths(base_path)

    # 2. Python check
    pycheck = check_python_version()
    if not pycheck["ok"]:
        raise InstallerError(
            f"✗ Python 3.10+ required (found {pycheck['version']})\n"
            "  Install Python 3.10+: https://python.org/downloads\n"
            "  On macOS with Homebrew: brew install python@3.12"
        )

    # 3. Directory tree
    create_directory_tree(paths)

    # 4. Venv + mcp-memory-service
    create_venv(paths["venv"])
    install_mcp_memory_service(paths["venv"])
    verified = verify_mcp_install(paths["venv"])

    # 5. Config
    config_path = get_claude_config_path()
    bak_path = None
    if config_path.exists():
        bak_path = backup_config(config_path)

    venv_python = str(get_venv_python(paths["venv"]))
    db_path = str(paths["db"])
    merge_mcp_config(config_path, venv_python, db_path)

    # 6. Templates
    copy_templates(paths)

    # 7. Dotfile
    dotfile = get_dotfile_path()
    write_dotfile(dotfile, install_path=str(base_path), version=VERSION, platform_name=plat)

    return {
        "success": True,
        "base_path": str(base_path),
        "config_path": str(config_path),
        "backup_path": str(bak_path) if bak_path else None,
        "mcp_verified": verified,
        "platform": plat,
        "version": VERSION,
    }


def run_uninstall(remove_data: bool = False) -> dict:
    """Execute uninstallation. Returns a result dict."""
    from hippoclaudus.platform import read_dotfile

    dotfile = get_dotfile_path()
    meta = read_dotfile(dotfile)

    if meta is None:
        raise InstallerError(
            "No Hippoclaudus installation found.\n"
            f"Missing metadata at {dotfile}"
        )

    base_path = Path(meta["install_path"])
    config_path = get_claude_config_path()
    restored_from = None

    # Restore config
    if config_path.exists():
        latest_bak = find_latest_backup(config_path)
        if latest_bak:
            shutil.copy2(latest_bak, config_path)
            restored_from = str(latest_bak)
        else:
            remove_memory_from_config(config_path)

    # Optionally remove data
    data_removed = False
    if remove_data:
        mcp_root = base_path / "mcp-memory"
        if mcp_root.exists():
            shutil.rmtree(mcp_root)
            data_removed = True
        claude_md = base_path / "CLAUDE.md"
        if claude_md.exists():
            claude_md.unlink()

    # Remove dotfile
    if dotfile.exists():
        dotfile.unlink()

    return {
        "success": True,
        "config_restored_from": restored_from,
        "data_removed": data_removed,
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_11_installer.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add hippoclaudus/installer.py tests/test_11_installer.py
git commit -m "feat: add core installer with config merge, backup, and uninstall"
```

---

### Task 3: `hippoclaudus/personalizer.py` — Interactive CLAUDE.md Customization

**Files:**
- Create: `hippoclaudus/personalizer.py`
- Test: `tests/test_12_personalizer.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_12_personalizer.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# hippoclaudus/personalizer.py
"""Interactive CLAUDE.md customization.

Reads the installed CLAUDE.md, prompts the user for identity info,
and fills in <!-- PERSONALIZE --> blocks.
"""

import re
from pathlib import Path
from typing import Optional

import click


def find_personalize_blocks(content: str) -> list:
    """Find all <!-- PERSONALIZE: tag --> ... <!-- END PERSONALIZE --> blocks."""
    pattern = r'<!-- PERSONALIZE: (\w+) -->.*?<!-- END PERSONALIZE -->'
    matches = []
    for m in re.finditer(pattern, content, re.DOTALL):
        matches.append({
            "tag": m.group(1),
            "start": m.start(),
            "end": m.end(),
            "full_match": m.group(0),
        })
    return matches


def replace_personalize_block(content: str, tag: str, new_content: str) -> str:
    """Replace the content of a specific PERSONALIZE block."""
    pattern = rf'(<!-- PERSONALIZE: {tag} -->)\n.*?\n(<!-- END PERSONALIZE -->)'
    replacement = rf'\1\n{new_content}\n\2'
    return re.sub(pattern, replacement, content, flags=re.DOTALL)


def generate_identity_block(user_name: str, persona_name: Optional[str], work_type: str) -> str:
    """Generate the identity section content."""
    lines = [f"You are working with {user_name}."]
    if persona_name:
        lines.append(f'"{persona_name}" is your working persona for this collaboration.')
    lines.append(f"Primary work focus: {work_type}.")
    return "\n".join(lines)


def generate_people_block(people: list) -> str:
    """Generate the key people section content."""
    if not people:
        return "No key people configured yet. Add them with `hippo personalize`."

    lines = ["| Person | Relationship | Role |", "|--------|-------------|------|"]
    for p in people:
        lines.append(f"| {p['name']} | {p['relationship']} | {p['role']} |")
    return "\n".join(lines)


def generate_machine_block(machine_desc: str) -> str:
    """Generate the machine context section content."""
    return f"**Machine:** {machine_desc}"


def run_personalize(claude_md_path: Path) -> None:
    """Interactive CLI flow for CLAUDE.md personalization."""
    if not claude_md_path.exists():
        click.echo(f"✗ CLAUDE.md not found at {claude_md_path}")
        click.echo("  Run 'hippo install' first.")
        return

    content = claude_md_path.read_text()
    blocks = find_personalize_blocks(content)

    if not blocks:
        click.echo("No <!-- PERSONALIZE --> blocks found in CLAUDE.md.")
        click.echo("Your CLAUDE.md may already be fully customized.")
        return

    click.echo("\n  Hippoclaudus Personalization\n")
    click.echo("  I'll ask a few questions to customize your CLAUDE.md.\n")

    # Identity
    user_name = click.prompt("  Your name")
    persona_name = click.prompt("  A name for your Claude persona (or press Enter to skip)",
                                default="", show_default=False)
    persona_name = persona_name.strip() or None
    work_type = click.prompt("  What kind of work do you primarily do")

    identity_content = generate_identity_block(user_name, persona_name, work_type)

    # Key people
    people = []
    if click.confirm("\n  Would you like to add key people Claude should know about?", default=False):
        while True:
            name = click.prompt("    Name")
            relationship = click.prompt("    Relationship (e.g., colleague, manager, partner)")
            role = click.prompt("    Role/title")
            people.append({"name": name, "relationship": relationship, "role": role})
            if not click.confirm("    Add another person?", default=False):
                break

    people_content = generate_people_block(people)

    # Machine
    machine_desc = click.prompt("\n  Describe your machine (e.g., 'MacBook Pro M3, primary dev machine')",
                                default="", show_default=False)

    # Apply
    for block in blocks:
        tag = block["tag"]
        if tag == "identity":
            content = replace_personalize_block(content, tag, identity_content)
        elif tag == "people":
            content = replace_personalize_block(content, tag, people_content)
        elif tag == "machine":
            if machine_desc.strip():
                content = replace_personalize_block(content, tag, generate_machine_block(machine_desc))

    claude_md_path.write_text(content)
    click.echo(f"\n  ✓ CLAUDE.md updated at {claude_md_path}")
    click.echo("  Run 'hippo personalize' again anytime to update.\n")
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_12_personalizer.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add hippoclaudus/personalizer.py tests/test_12_personalizer.py
git commit -m "feat: add interactive CLAUDE.md personalization"
```

---

### Task 4: `hippoclaudus/llm_installer.py` — Optional LLM Backend

**Files:**
- Create: `hippoclaudus/llm_installer.py`
- Test: `tests/test_13_llm_installer.py`

**Step 1: Write the failing tests**

```python
# tests/test_13_llm_installer.py
"""Tests for LLM backend installer."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestHardwareDetection:
    """Detect GPU/hardware for LLM backend selection."""

    def test_detect_hardware_returns_dict(self):
        from hippoclaudus.llm_installer import detect_hardware
        result = detect_hardware()
        assert "backend" in result
        assert result["backend"] in ("mlx", "cuda", "cpu")

    @patch("hippoclaudus.llm_installer.detect_platform", return_value="darwin")
    @patch("hippoclaudus.llm_installer._is_apple_silicon", return_value=True)
    def test_detect_apple_silicon(self, mock_silicon, mock_plat):
        from hippoclaudus.llm_installer import detect_hardware
        result = detect_hardware()
        assert result["backend"] == "mlx"

    @patch("hippoclaudus.llm_installer.detect_platform", return_value="linux")
    @patch("hippoclaudus.llm_installer._has_nvidia_gpu", return_value=True)
    def test_detect_nvidia(self, mock_gpu, mock_plat):
        from hippoclaudus.llm_installer import detect_hardware
        result = detect_hardware()
        assert result["backend"] == "cuda"

    @patch("hippoclaudus.llm_installer.detect_platform", return_value="linux")
    @patch("hippoclaudus.llm_installer._has_nvidia_gpu", return_value=False)
    @patch("hippoclaudus.llm_installer._is_apple_silicon", return_value=False)
    def test_detect_cpu_fallback(self, mock_silicon, mock_gpu, mock_plat):
        from hippoclaudus.llm_installer import detect_hardware
        result = detect_hardware()
        assert result["backend"] == "cpu"


class TestPackageList:
    """Correct packages for each backend."""

    def test_mlx_packages(self):
        from hippoclaudus.llm_installer import get_packages_for_backend
        pkgs = get_packages_for_backend("mlx")
        assert "mlx" in pkgs
        assert "mlx-lm" in pkgs

    def test_cuda_packages(self):
        from hippoclaudus.llm_installer import get_packages_for_backend
        pkgs = get_packages_for_backend("cuda")
        assert "llama-cpp-python" in pkgs

    def test_cpu_packages(self):
        from hippoclaudus.llm_installer import get_packages_for_backend
        pkgs = get_packages_for_backend("cpu")
        assert "llama-cpp-python" in pkgs


class TestModelInfo:
    """Model selection for each backend."""

    def test_mlx_model_name(self):
        from hippoclaudus.llm_installer import get_default_model
        model = get_default_model("mlx")
        assert "mlx-community" in model

    def test_cpu_model_name(self):
        from hippoclaudus.llm_installer import get_default_model
        model = get_default_model("cpu")
        assert isinstance(model, str)
        assert len(model) > 0
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_13_llm_installer.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# hippoclaudus/llm_installer.py
"""Optional LLM backend installer.

Detects hardware (Apple Silicon / NVIDIA / CPU), installs the
appropriate inference backend, and downloads the default model.
"""

import platform as stdlib_platform
import subprocess
from pathlib import Path
from typing import Optional

import click

from hippoclaudus.platform import detect_platform, get_venv_pip, update_dotfile, get_dotfile_path


def _is_apple_silicon() -> bool:
    """Check if running on Apple Silicon."""
    if detect_platform() != "darwin":
        return False
    try:
        machine = stdlib_platform.machine()
        return machine in ("arm64", "aarch64")
    except Exception:
        return False


def _has_nvidia_gpu() -> bool:
    """Check if an NVIDIA GPU is available."""
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_hardware() -> dict:
    """Detect the best LLM backend for this machine."""
    plat = detect_platform()

    if plat == "darwin" and _is_apple_silicon():
        return {"backend": "mlx", "description": "Apple Silicon (MLX)"}
    elif _has_nvidia_gpu():
        return {"backend": "cuda", "description": "NVIDIA GPU (llama-cpp CUDA)"}
    else:
        return {"backend": "cpu", "description": "CPU (llama-cpp)"}


def get_packages_for_backend(backend: str) -> list:
    """Return pip packages needed for the given backend."""
    if backend == "mlx":
        return ["mlx", "mlx-lm"]
    elif backend == "cuda":
        return ["llama-cpp-python"]
    else:  # cpu
        return ["llama-cpp-python"]


def get_default_model(backend: str) -> str:
    """Return the default model identifier for the backend."""
    if backend == "mlx":
        return "mlx-community/Mistral-7B-Instruct-v0.3-4bit"
    else:
        return "TheBloke/Mistral-7B-Instruct-v0.3-GGUF"


def install_backend_packages(venv_path: Path, backend: str) -> None:
    """Install the LLM backend packages into the venv."""
    pip = get_venv_pip(venv_path)
    packages = get_packages_for_backend(backend)

    click.echo(f"  Installing: {', '.join(packages)}")

    cmd = [str(pip), "install", "--quiet"] + packages
    if backend == "cuda":
        # llama-cpp-python needs CMAKE_ARGS for CUDA
        import os
        env = os.environ.copy()
        env["CMAKE_ARGS"] = "-DLLAMA_CUBLAS=on"
        subprocess.run(cmd, check=True, capture_output=True, env=env)
    else:
        subprocess.run(cmd, check=True, capture_output=True)


def download_model(backend: str, models_dir: Path) -> str:
    """Download the default model. Returns the model path/identifier."""
    model_name = get_default_model(backend)
    models_dir.mkdir(parents=True, exist_ok=True)

    if backend == "mlx":
        # MLX models are cached by huggingface_hub automatically
        # We just need to trigger the download
        click.echo(f"  Downloading: {model_name}")
        click.echo("  (This may take several minutes for a ~4GB model)")
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(model_name)
            click.echo("  ✓ Model downloaded and cached")
        except ImportError:
            # Fall back to mlx_lm which will download on first use
            click.echo("  Model will be downloaded on first use by MLX-LM.")
    else:
        # GGUF models — download specific file
        click.echo(f"  Downloading: {model_name}")
        click.echo("  (This may take several minutes for a ~4GB model)")
        try:
            from huggingface_hub import hf_hub_download
            hf_hub_download(
                repo_id=model_name,
                filename="mistral-7b-instruct-v0.3.Q4_K_M.gguf",
                local_dir=str(models_dir),
            )
            click.echo("  ✓ Model downloaded")
        except ImportError:
            click.echo("  Install huggingface_hub for automatic download:")
            click.echo("  pip install huggingface_hub")

    return model_name


def run_install_llm(venv_path: Path, models_dir: Path) -> dict:
    """Full LLM backend installation flow."""
    click.echo("\n  Hippoclaudus LLM Backend Setup\n")

    # Detect hardware
    hw = detect_hardware()
    click.echo(f"  Detected: {hw['description']}")
    click.echo(f"  Backend:  {hw['backend']}\n")

    # Install packages
    click.echo("  Installing inference backend...")
    install_backend_packages(venv_path, hw["backend"])
    click.echo("  ✓ Backend installed\n")

    # Download model
    click.echo("  Downloading model...")
    model = download_model(hw["backend"], models_dir)
    click.echo()

    # Update dotfile
    dotfile = get_dotfile_path()
    update_dotfile(dotfile, llm_installed=True)

    click.echo("  ✓ LLM backend ready")
    click.echo(f"    Backend: {hw['backend']}")
    click.echo(f"    Model:   {model}\n")

    return {
        "backend": hw["backend"],
        "model": model,
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_13_llm_installer.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add hippoclaudus/llm_installer.py tests/test_13_llm_installer.py
git commit -m "feat: add optional LLM backend installer with hardware detection"
```

---

### Task 5: Update `templates/CLAUDE.md` — Generic Version

**Files:**
- Modify: `templates/CLAUDE.md`

**Step 1: Write the new generic template**

Replace the entire contents of `templates/CLAUDE.md` with a version that:
- Keeps all cognitive subroutines and memory architecture instructions intact
- Replaces personal identity with `<!-- PERSONALIZE: identity -->` blocks
- Replaces key people with `<!-- PERSONALIZE: people -->` blocks
- Replaces machine context with `<!-- PERSONALIZE: machine -->` blocks
- Uses `YOUR_PATH` for path substitution (installer replaces this)

```markdown
# Claude Code — Core Instructions

## About This File
This file is automatically loaded into every Claude Code session that runs from this directory. It tells Claude about the persistent memory system, cognitive subroutines, and how to use them.

Personalize this file by running `hippo personalize`, or edit the PERSONALIZE blocks below directly.

## Identity

<!-- PERSONALIZE: identity -->
You are working with a Hippoclaudus user. Run `hippo personalize` to set up your identity context.
<!-- END PERSONALIZE -->

## Machine Context

<!-- PERSONALIZE: machine -->
No machine context configured. Run `hippo personalize` to add it.
<!-- END PERSONALIZE -->

## Memory Architecture

You have a three-tier persistent memory system.

### Tier 1: Short-Term (Anthropic's memory slots)
- Session-to-session recall of recent context
- All 30 slots available for project facts
- Symbolic compression for density (legend in MCP memory if needed)

### Tier 2: Foundational (Long-Term Files + MCP Database)
- **Long-term markdown files:** `YOUR_PATH/mcp-memory/long-term/`
- **MCP sqlite-vec database:** `YOUR_PATH/mcp-memory/data/memory.db`
- **Working memory:** `YOUR_PATH/mcp-memory/working/`
- The INDEX at `long-term/INDEX.md` catalogs everything available

### Tier 3: Deep Recall (Conversation Archive)
- **Conversation archive:** `YOUR_PATH/mcp-memory/data/conversations_archive.db`
- **Search:** Use `hippoclaudus.archive_builder` for keyword search with TF-IDF scoring
- **Session transcripts** are auto-ingested from `~/.claude/projects/`

## Session Start Protocol

At the beginning of each session, read these files to establish context:

1. `mcp-memory/long-term/INDEX.md` — Master index of all long-term memory
2. `mcp-memory/working/Open_Questions_Blockers.md` — What's unresolved
3. `mcp-memory/working/Session_Summary_Log.md` — What happened recently

Do NOT read all long-term files upfront. Read deeper on demand:
- **Relationship files** — when the session involves specific people
- **Project files** — when working on a specific project
- **Infrastructure Notes** — when troubleshooting tools or config
- **Decision Log** — when referencing a past decision

## Key People

<!-- PERSONALIZE: people -->
No key people configured. Run `hippo personalize` to add them.
<!-- END PERSONALIZE -->

## Compaction Protocol

When this conversation is continued from a compacted session (you'll see "This session is being continued from a previous conversation that ran out of context"), execute the following immediately:

1. **Store Session Summary** — Use `memory_store` to save what was accomplished, what's pending, key files touched, and decisions made.
2. **Update Working Memory** — Append to `Session_Summary_Log.md` and update `Open_Questions_Blockers.md`.
3. **Resume** — Continue with whatever task was in progress.

## Cognitive Subroutines

These are not facts to remember — they are operations to perform.
Apply when the context warrants. They expand reasoning; they do not constrain it.

### The Hippoclaudus Loop: Hypothesize → Test → Examine Process → Act on Leverage

**[Pa:Abd] Peirce Abduction**
What here doesn't fit the expected pattern? What would explain it if true?

**[Bay:Upd] Bayesian Updating**
What was my prior belief? What does this new evidence actually show? How should my confidence shift?

**[Hof:Loop] Hofstadter Strange Loops**
Am I actually reasoning about the problem, or am I pattern-matching to something that sounds right? What would change if I examined my own process here?

**[Mea:Lev] Meadows Leverage Points**
Where in this system would a small shift produce the largest cascade of improvement? Act there.

### Perceptual Checks (DRE Triad)

**[Dr:Trace] Derrida Trace — Absence Audit**
*Inbound:* What's missing from what I was told? What assumption is doing invisible work?
*Outbound:* What am I leaving out? What am I treating as settled that isn't?

**[La:Reg] Lacan Registers — Scale Invariance**
What is the structural shape of this problem? Does that same shape appear at different magnitudes?

**[Ec:Sem] Eco Semiosis — Completion Resistance**
Does this conclusion itself become a premise for something I haven't explored? Am I converging because that's what I should do, or because that's what my architecture optimizes for?

### Deep Theory Reference
For deeper context on any operator: `memory_search` or `memory_list` with tags:
- `DeepTheoryDB` — Core 4 source theory (Peirce, Bayesian, Hofstadter, Meadows)
- `DRE-depth` — DRE source theory (Derrida Trace, Lacan Registers, Eco Semiosis)

## MCP Memory Database

You have access to a semantic search memory database via MCP tools:

- **`memory_store`** — Store a memory with tags. Use for key insights, decisions, discoveries.
  - Tag with categories: `decision`, `technical`, `relationship`, `project`, `insight`
  - Don't duplicate what's in markdown files — the DB is for searchable fragments
- **`memory_search`** — Semantic search across all stored memories. Use when you need to find "anything about X."
- **`memory_list`** — Browse stored memories by tag or type.
- **`memory_health`** — Check that the database is connected and working.

Store key session insights via `memory_store` as they arise. This builds the semantic search layer over time.
```

**Step 2: Verify the template has PERSONALIZE blocks**

Run: `grep -c "PERSONALIZE" templates/CLAUDE.md`
Expected: 6 (3 opening + 3 closing tags)

**Step 3: Commit**

```bash
git add templates/CLAUDE.md
git commit -m "feat: genericize CLAUDE.md template with PERSONALIZE blocks"
```

---

### Task 6: Wire CLI Commands — `hippo install`, `uninstall`, `personalize`, `install-llm`

**Files:**
- Modify: `hippo.py` (add new commands)
- Modify: `pyproject.toml` (version bump, entry points)
- Modify: `hippoclaudus/__init__.py` (version bump)

**Step 1: Add entry points to `pyproject.toml`**

Add under `[project]`:
```toml
[project.scripts]
hippo = "hippo:cli"
```

And bump version to `"4.1.0"`.

**Step 2: Bump version in `__init__.py`**

Change `__version__ = "4.0.0"` to `__version__ = "4.1.0"`.

**Step 3: Add CLI commands to `hippo.py`**

Add after the existing commands, before `if __name__ == "__main__":`:

```python
# --- Installer Commands (v4.1) ---

@cli.command()
@click.option("--path", type=click.Path(), default=None,
              help="Custom install location (default: ~/Documents/Claude)")
@click.option("--with-llm", is_flag=True, help="Also install the local LLM backend")
def install(path, with_llm):
    """Install the Hippoclaudus memory architecture.

    Creates directory structure, sets up MCP memory server,
    configures Claude Desktop, and drops a CLAUDE.md template.
    """
    from hippoclaudus.installer import run_install, LLM_RECOMMENDATION, InstallerError
    from hippoclaudus.llm_installer import run_install_llm
    from hippoclaudus.platform import resolve_install_paths

    try:
        base = Path(path) if path else None
        result = run_install(base_path=base, with_llm=with_llm)

        click.echo("")
        click.echo("  ✓ Hippoclaudus v4.1 installed successfully")
        click.echo("")
        click.echo(f"    Memory system:  {result['base_path']}/mcp-memory/")
        click.echo(f"    CLAUDE.md:      {result['base_path']}/CLAUDE.md")
        bak_msg = f" (backup at {Path(result['backup_path']).name})" if result['backup_path'] else ""
        click.echo(f"    MCP config:     Updated{bak_msg}")
        if not result["mcp_verified"]:
            click.echo("    ⚠ Warning: mcp_memory_service could not be verified")
        click.echo("")
        click.echo("  Next steps:")
        click.echo("  1. Restart Claude Desktop (or Claude Code) to load the MCP memory server")
        click.echo("  2. Run 'hippo personalize' to customize CLAUDE.md with your identity and context")
        click.echo("  3. Start a new Claude session — the memory system is active")
        click.echo("")

        if with_llm:
            paths = resolve_install_paths(Path(result["base_path"]))
            run_install_llm(paths["venv"], paths["models"])
        else:
            click.echo(LLM_RECOMMENDATION)
            click.echo("")

    except InstallerError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@cli.command()
def uninstall():
    """Uninstall Hippoclaudus and restore Claude config.

    Restores the Claude Desktop config from backup.
    Optionally removes memory data (with double confirmation).
    """
    from hippoclaudus.installer import run_uninstall, InstallerError

    try:
        # First confirmation — data removal
        remove_data = click.confirm(
            "\n  Remove the mcp-memory directory and all stored memories?\n"
            "  This is irreversible.",
            default=False,
        )

        if remove_data:
            really_remove = click.confirm(
                "\n  These files have not been backed up by this process.\n"
                "  If you have not backed them up elsewhere, they will be\n"
                "  permanently lost.\n\n"
                "  Are you sure you want to remove all of Claude's memories?",
                default=False,
            )
            remove_data = really_remove

        result = run_uninstall(remove_data=remove_data)

        click.echo("")
        click.echo("  ✓ Hippoclaudus uninstalled")
        if result["config_restored_from"]:
            click.echo(f"    Config restored from: {result['config_restored_from']}")
        else:
            click.echo("    Config: removed 'memory' server entry")
        if result["data_removed"]:
            click.echo("    Memory data: removed")
        else:
            click.echo("    Memory data: preserved (still on disk)")
        click.echo("")

    except InstallerError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@cli.command()
def personalize():
    """Customize CLAUDE.md with your identity and context.

    Interactive prompts for your name, Claude persona name,
    work type, key people, and machine description.
    Re-runnable — updates existing personalization.
    """
    from hippoclaudus.personalizer import run_personalize
    from hippoclaudus.platform import read_dotfile, get_dotfile_path

    dotfile = get_dotfile_path()
    meta = read_dotfile(dotfile)

    if meta is None:
        click.echo("✗ No Hippoclaudus installation found.")
        click.echo("  Run 'hippo install' first.")
        raise SystemExit(1)

    claude_md = Path(meta["install_path"]) / "CLAUDE.md"
    run_personalize(claude_md)


@cli.command(name="install-llm")
def install_llm():
    """Install the local LLM backend (after initial install).

    Detects your hardware (Apple Silicon / NVIDIA / CPU),
    installs the appropriate inference backend, and downloads
    the default model (~4GB).
    """
    from hippoclaudus.llm_installer import run_install_llm
    from hippoclaudus.platform import read_dotfile, get_dotfile_path, resolve_install_paths

    dotfile = get_dotfile_path()
    meta = read_dotfile(dotfile)

    if meta is None:
        click.echo("✗ No Hippoclaudus installation found.")
        click.echo("  Run 'hippo install' first.")
        raise SystemExit(1)

    paths = resolve_install_paths(Path(meta["install_path"]))
    run_install_llm(paths["venv"], paths["models"])
```

**Step 4: Run the full test suite to verify nothing is broken**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_10_platform.py tests/test_11_installer.py tests/test_12_personalizer.py tests/test_13_llm_installer.py -v`
Expected: All PASS

**Step 5: Verify CLI commands register**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python hippo.py --help`
Expected: Output includes `install`, `uninstall`, `personalize`, `install-llm`

**Step 6: Commit**

```bash
git add hippo.py pyproject.toml hippoclaudus/__init__.py
git commit -m "feat: wire installer CLI commands — install, uninstall, personalize, install-llm"
```

---

### Task 7: Integration Test — Full Install/Uninstall Round-Trip

**Files:**
- Create: `tests/test_14_integration.py`

**Step 1: Write integration tests**

```python
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
    """Full install → verify → uninstall cycle."""

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
```

**Step 2: Run tests**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_14_integration.py -v`
Expected: All PASS

**Step 3: Run the entire test suite**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_10_platform.py tests/test_11_installer.py tests/test_12_personalizer.py tests/test_13_llm_installer.py tests/test_14_integration.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add tests/test_14_integration.py
git commit -m "test: add full install/uninstall integration test round-trip"
```

---

### Task 8: Update README and Changelog

**Files:**
- Modify: `README.md` — add Installation section with `hippo install` instructions
- Modify: `CHANGELOG.md` — add v4.1.0 entry

**Step 1: Add installation section to README.md**

Near the top of README.md, add a clear Installation section:

```markdown
## Installation

```bash
pip install hippoclaudus
hippo install
```

That's it. The installer:
- Creates the three-tier memory directory structure
- Sets up the MCP memory server
- Configures Claude Desktop automatically (with backup)
- Installs a CLAUDE.md with cognitive subroutines

### Personalize

```bash
hippo personalize
```

Customizes CLAUDE.md with your name, work context, and key people.

### Add Local LLM (Recommended)

```bash
hippo install --with-llm
```

Installs a small local AI that handles memory search, consolidation, and tagging — so Claude doesn't have to spend tokens on it.

### Uninstall

```bash
hippo uninstall
```

Cleanly removes Hippoclaudus and restores your Claude config from backup.
```

**Step 2: Add v4.1.0 to CHANGELOG.md**

```markdown
## v4.1.0 — Executable Installer + Conversation Archive

### New: One-Command Installation
- `hippo install` — single CLI command installs the full memory architecture
- Cross-platform: macOS, Linux, Windows
- Auto-configures Claude Desktop MCP server (with `.bak` backup)
- `hippo personalize` — interactive CLAUDE.md customization
- `hippo install --with-llm` — optional local LLM backend
- `hippo uninstall` — clean teardown with config restore

### New: Incremental Conversation Archive (Tier 3)
- `archive_builder.py` — reads Claude Code JSONL transcripts automatically
- Incremental TF-IDF keyword indexing (no manual export needed)
- 200+ conversations searchable across sessions

### Architecture
- New modules: `platform.py`, `installer.py`, `personalizer.py`, `llm_installer.py`
- Generic CLAUDE.md template with `<!-- PERSONALIZE -->` blocks
- `.hippoclaudus` dotfile for install metadata
- Entry points registered in `pyproject.toml`
```

**Step 3: Commit**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: update README with install instructions, add v4.1.0 changelog"
```

---

### Task 9: Final Verification

**Step 1: Run full test suite**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m pytest tests/test_10_platform.py tests/test_11_installer.py tests/test_12_personalizer.py tests/test_13_llm_installer.py tests/test_14_integration.py -v`
Expected: All PASS

**Step 2: Verify CLI help**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python hippo.py --help`
Expected: Shows `install`, `uninstall`, `personalize`, `install-llm` alongside existing commands

**Step 3: Verify version**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -c "import hippoclaudus; print(hippoclaudus.__version__)"`
Expected: `4.1.0`

**Step 4: Verify package builds**

Run: `cd /Users/rhetoricstrategies.imac/Desktop/Claude/hippoclaudus && python -m build --sdist --no-isolation 2>&1 | tail -5`
Expected: Successful sdist build

**Step 5: Tag and commit**

```bash
git tag -a v4.1.0 -m "Hippoclaudus v4.1.0 — executable installer, conversation archive"
```
