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
        return "linux"


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
