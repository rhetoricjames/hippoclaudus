#!/usr/bin/env python3
"""
Hippoclaudus Doctor — Diagnostic Tool
Checks that your persistent memory architecture is properly configured.

Usage:
  python3 doctor.py                          # Auto-detect base path
  python3 doctor.py --base-path ~/Claude     # Specify base path
"""

import argparse
import json
import os
import platform
import subprocess
import sys


def check_mark(passed):
    return "✓" if passed else "✗"


def find_claude_config():
    """Find the Claude Desktop config file based on platform."""
    system = platform.system()
    if system == "Darwin":
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return os.path.join(appdata, "Claude", "claude_desktop_config.json")
    else:  # Linux
        return os.path.expanduser("~/.config/claude/claude_desktop_config.json")


def find_base_path():
    """Try to auto-detect the base path from Claude Desktop config."""
    config_path = find_claude_config()
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
            memory_config = config.get("mcpServers", {}).get("memory", {})
            db_path = memory_config.get("env", {}).get("MCP_MEMORY_SQLITE_PATH", "")
            if db_path:
                # Walk up from .../mcp-memory/data/memory.db to base
                base = os.path.dirname(os.path.dirname(os.path.dirname(db_path)))
                if os.path.exists(base):
                    return base
        except (json.JSONDecodeError, KeyError):
            pass

    # Common defaults
    for candidate in ["~/Claude", "~/claude", "~/Desktop/Claude"]:
        expanded = os.path.expanduser(candidate)
        if os.path.exists(os.path.join(expanded, "mcp-memory")):
            return expanded

    return None


def run_checks(base_path):
    """Run all diagnostic checks."""
    results = []
    all_passed = True

    print("")
    print("╔══════════════════════════════════════╗")
    print("║       Hippoclaudus Doctor            ║")
    print("╚══════════════════════════════════════╝")
    print("")
    print(f"Base path: {base_path}")
    print(f"Platform:  {platform.system()} {platform.release()}")
    print(f"Python:    {sys.version.split()[0]}")
    print("")

    # --- Python Version ---
    py_ok = sys.version_info >= (3, 10)
    results.append(("Python 3.10+", py_ok,
                     f"Python {sys.version_info.major}.{sys.version_info.minor}" if py_ok
                     else f"Python {sys.version_info.major}.{sys.version_info.minor} — need 3.10+"))

    # --- Directory Structure ---
    print("Directory Structure")
    print("─" * 40)
    dirs = {
        "mcp-memory/long-term": "Long-term memory",
        "mcp-memory/working": "Working memory",
        "mcp-memory/data": "Database directory",
        "mcp-memory/conversations": "Conversation archive",
    }
    for subdir, label in dirs.items():
        path = os.path.join(base_path, subdir)
        exists = os.path.isdir(path)
        if not exists:
            all_passed = False
        print(f"  {check_mark(exists)} {label}: {subdir}")

    # --- Key Files ---
    print("")
    print("Key Files")
    print("─" * 40)

    claude_md = os.path.join(base_path, "CLAUDE.md")
    exists = os.path.isfile(claude_md)
    has_content = exists and os.path.getsize(claude_md) > 100
    if not has_content:
        all_passed = False
    print(f"  {check_mark(has_content)} CLAUDE.md {'(exists, has content)' if has_content else '(missing or empty)' if not exists else '(exists but looks empty)'}")

    index_md = os.path.join(base_path, "mcp-memory/long-term/INDEX.md")
    exists = os.path.isfile(index_md)
    has_content = exists and os.path.getsize(index_md) > 50
    if not has_content:
        all_passed = False
    print(f"  {check_mark(has_content)} INDEX.md {'(exists, has content)' if has_content else '(missing or empty)'}")

    protocol = os.path.join(base_path, "mcp-memory/long-term/Total_Update_Protocol.md")
    exists = os.path.isfile(protocol)
    if not exists:
        all_passed = False
    print(f"  {check_mark(exists)} Total_Update_Protocol.md")

    working_files = [
        "mcp-memory/working/Session_Summary_Log.md",
        "mcp-memory/working/Open_Questions_Blockers.md",
        "mcp-memory/working/Decision_Log.md",
    ]
    for wf in working_files:
        path = os.path.join(base_path, wf)
        exists = os.path.isfile(path)
        if not exists:
            all_passed = False
        print(f"  {check_mark(exists)} {os.path.basename(wf)}")

    # --- MCP Memory Database ---
    print("")
    print("MCP Memory Database")
    print("─" * 40)

    db_path = os.path.join(base_path, "mcp-memory/data/memory.db")
    db_exists = os.path.isfile(db_path)
    print(f"  {check_mark(db_exists)} memory.db {'exists' if db_exists else 'not found'}")
    if db_exists:
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"    Size: {size_mb:.2f} MB")

    # --- Virtual Environment ---
    print("")
    print("Python Environment")
    print("─" * 40)

    venv_python = os.path.join(base_path, "mcp-memory/venv/bin/python")
    if platform.system() == "Windows":
        venv_python = os.path.join(base_path, "mcp-memory/venv/Scripts/python.exe")

    venv_exists = os.path.isfile(venv_python)
    if not venv_exists:
        all_passed = False
    print(f"  {check_mark(venv_exists)} Virtual environment {'found' if venv_exists else 'not found'}")

    if venv_exists:
        try:
            result = subprocess.run(
                [venv_python, "-c", "import mcp_memory_service; print(mcp_memory_service.__version__ if hasattr(mcp_memory_service, '__version__') else 'installed')"],
                capture_output=True, text=True, timeout=10
            )
            mcp_ok = result.returncode == 0
            if not mcp_ok:
                all_passed = False
            print(f"  {check_mark(mcp_ok)} mcp-memory-service {'(' + result.stdout.strip() + ')' if mcp_ok else 'NOT INSTALLED'}")
            if not mcp_ok and result.stderr:
                print(f"    Error: {result.stderr.strip()[:200]}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            all_passed = False
            print(f"  ✗ mcp-memory-service (could not verify)")

    # --- Claude Desktop Config ---
    print("")
    print("Claude Desktop Config")
    print("─" * 40)

    config_path = find_claude_config()
    config_exists = os.path.isfile(config_path)
    print(f"  {check_mark(config_exists)} Config file {'found' if config_exists else 'not found'}")
    if config_exists:
        print(f"    Path: {config_path}")
    else:
        all_passed = False

    if config_exists:
        try:
            with open(config_path) as f:
                config = json.load(f)

            memory_config = config.get("mcpServers", {}).get("memory", {})
            has_memory = bool(memory_config)
            if not has_memory:
                all_passed = False
            print(f"  {check_mark(has_memory)} Memory server {'configured' if has_memory else 'NOT configured'}")

            if has_memory:
                cmd = memory_config.get("command", "")
                cmd_valid = os.path.isfile(cmd)
                if not cmd_valid:
                    all_passed = False
                print(f"  {check_mark(cmd_valid)} Command path {'valid' if cmd_valid else 'INVALID: ' + cmd}")

                env_db = memory_config.get("env", {}).get("MCP_MEMORY_SQLITE_PATH", "")
                env_dir_valid = os.path.isdir(os.path.dirname(env_db)) if env_db else False
                if not env_dir_valid:
                    all_passed = False
                print(f"  {check_mark(env_dir_valid)} DB path {'valid' if env_dir_valid else 'INVALID: ' + env_db}")

        except json.JSONDecodeError:
            all_passed = False
            print(f"  ✗ Config file has invalid JSON")

    # --- Conversation Archive ---
    print("")
    print("Conversation Archive (Optional)")
    print("─" * 40)

    conv_json = os.path.join(base_path, "mcp-memory/conversations/conversations.json")
    conv_exists = os.path.isfile(conv_json)
    print(f"  {check_mark(conv_exists)} conversations.json {'found' if conv_exists else 'not found (export from claude.ai)'}")
    if conv_exists:
        size_mb = os.path.getsize(conv_json) / (1024 * 1024)
        print(f"    Size: {size_mb:.1f} MB")

    conv_index = os.path.join(base_path, "mcp-memory/conversations/conversation_index.md")
    index_exists = os.path.isfile(conv_index)
    print(f"  {check_mark(index_exists)} conversation_index.md {'found' if index_exists else 'not found (run scan_conversations.py)'}")

    scanner = os.path.join(base_path, "mcp-memory/conversations/scan_conversations.py")
    scanner_exists = os.path.isfile(scanner)
    print(f"  {check_mark(scanner_exists)} scan_conversations.py")

    extractor = os.path.join(base_path, "mcp-memory/conversations/extract_conversations.py")
    extractor_exists = os.path.isfile(extractor)
    print(f"  {check_mark(extractor_exists)} extract_conversations.py")

    # --- Summary ---
    print("")
    print("═" * 40)
    if all_passed:
        print("  ✓ All checks passed! Hippoclaudus is ready.")
    else:
        print("  ✗ Some checks failed. Review the issues above.")
    print("═" * 40)
    print("")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Hippoclaudus Doctor — Diagnostic Tool")
    parser.add_argument("--base-path", help="Base path for Hippoclaudus installation")
    args = parser.parse_args()

    if args.base_path:
        base_path = os.path.expanduser(args.base_path)
    else:
        base_path = find_base_path()
        if not base_path:
            print("Could not auto-detect Hippoclaudus installation.")
            print("Please specify: python3 doctor.py --base-path ~/Claude")
            sys.exit(1)

    if not os.path.isdir(base_path):
        print(f"Error: {base_path} is not a directory")
        sys.exit(1)

    passed = run_checks(base_path)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
