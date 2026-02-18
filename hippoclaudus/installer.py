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

    # CLAUDE.md -- always overwrite with fresh template (personalize later)
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
            f"Python 3.10+ required (found {pycheck['version']})\n"
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
