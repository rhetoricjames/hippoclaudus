# Hippoclaudus v4.1 — Installer Design

**Date:** 2026-02-17
**Author:** James Palczynski + Morpheus (Claude)
**Status:** Approved

---

## Problem

Hippoclaudus is a multi-component system: Python package, MCP memory server, template files, CLAUDE.md configuration, local LLM backend, and a conversation archive. The current `install.sh` handles directory creation and venv setup but leaves manual steps — editing JSON config files, customizing CLAUDE.md, understanding dependencies. This is a barrier for the growing number of Claude users who are not experienced with code-based installations.

The installer must make the full Hippoclaudus installation achievable via a single CLI command, with the user (or their Claude) approving permission prompts along the way.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Install mechanism | `pip install hippoclaudus` then `hippo install` | Standard Python packaging; Claude Code users have Python |
| Target audience | Claude Code users (Python 3.10+ assumed present) | Graceful error + instructions if Python missing |
| MCP config handling | Auto-merge with `.bak` backup | Config edit is the #1 friction point; backup provides safety net |
| CLAUDE.md | Generic template on install; `hippo personalize` for customization | Keeps install fast; personalization is opt-in |
| LLM backend | Optional via `hippo install --with-llm` | Core memory system valuable alone; 4GB model download is a momentum-killer |
| Uninstall | `hippo uninstall` restores config from `.bak`, double-confirms memory deletion | Never silently delete user data |
| Cross-platform | macOS + Linux + Windows from day one | Public release demands full coverage |

## Commands

```
hippo install              Full guided installation
hippo install --with-llm   Install + download LLM backend
hippo install --path PATH  Custom install location
hippo uninstall            Tear down, restore configs from .bak
hippo personalize          Conversational CLAUDE.md customization
hippo install-llm          Add LLM backend after initial install
hippo doctor               Health check (existing)
hippo status               Memory health (existing)
```

## Platform Detection

A `platform.py` module resolves all OS-specific paths:

| Resource | macOS | Linux | Windows |
|----------|-------|-------|---------|
| Claude config | `~/Library/Application Support/Claude/claude_desktop_config.json` | `~/.config/Claude/claude_desktop_config.json` | `%APPDATA%\Claude\claude_desktop_config.json` |
| Default install base | `~/Documents/Claude/` | `~/Documents/Claude/` | `%USERPROFILE%\Documents\Claude\` |
| Claude Code sessions | `~/.claude/projects/` | `~/.claude/projects/` | `%USERPROFILE%\.claude\projects\` |
| Python venv | `mcp-memory/venv/` | `mcp-memory/venv/` | `mcp-memory\venv\` |

All path construction uses `pathlib.Path`. Install base configurable via `--path` flag.

## Install Flow

### `hippo install`

1. **Platform detection** — `platform.py` detects OS, resolves all paths
2. **Python check** — verify 3.10+; clear error with install instructions if not
3. **Directory tree** — create `mcp-memory/{long-term,working,data}`
4. **Virtual environment** — create venv at `mcp-memory/venv/`, install `mcp-memory-service`
5. **Config backup** — copy `claude_desktop_config.json` to `.bak.{ISO-timestamp}` (never overwrite existing backups — stack them)
6. **Config merge** — read existing JSON (or `{}` if absent), add `mcpServers.memory` entry preserving all existing entries, validate round-trip before writing
7. **Template copy** — copy templates to install base, substitute paths in CLAUDE.md
8. **Install metadata** — write `~/.hippoclaudus` dotfile (install path, timestamp)
9. **Post-install output** — success summary + LLM recommendation message

### MCP Config Entry

```json
{
  "mcpServers": {
    "memory": {
      "command": "<venv_python_path>",
      "args": ["-m", "mcp_memory_service"],
      "env": {
        "MCP_MEMORY_DB_PATH": "<install_base>/mcp-memory/data/memory.db"
      }
    }
  }
}
```

### Config Error Handling

- Malformed existing JSON: don't touch it, print error, suggest `hippo doctor`
- File read-only or permission denied: explain what permission is needed
- File doesn't exist: create it with the MCP entry

### `hippo install --with-llm`

Runs full install above, then:

1. **Hardware detection** — Apple Silicon → MLX; NVIDIA GPU → llama-cpp-python CUDA; else → llama-cpp-python CPU
2. **Package install** — appropriate backend into the existing venv
3. **Model download** — default model with progress bar, stored in `mcp-memory/models/`
   - MLX: `mlx-community/Mistral-7B-Instruct-v0.3-4bit`
   - llama-cpp: equivalent GGUF quantization
4. **Confirmation** — print what was installed and where

Also available as standalone `hippo install-llm` after initial install.

### `hippo personalize`

Interactive CLI that customizes CLAUDE.md:

- Your name
- Preferred Claude persona name (or skip)
- Primary work type
- Key people (loop: name, relationship, role — add more? y/n)
- Machine description

Reads existing CLAUDE.md, fills `<!-- PERSONALIZE -->` blocks, writes back. Non-destructive, re-runnable.

### `hippo uninstall`

1. Read `~/.hippoclaudus` for install path
2. Restore `claude_desktop_config.json` from most recent `.bak` (show diff, or remove `memory` entry if no `.bak` found)
3. Prompt for memory removal:
   - "Remove the mcp-memory directory and all stored memories? This is irreversible." (default: no)
   - If yes: "These files have not been backed up by this process. If you have not backed them up elsewhere, they will be permanently lost. Are you sure you want to remove all of Claude's memories?" (second confirmation)
   - Only then delete
4. Remove CLAUDE.md (or just the Hippoclaudus blocks if user-modified)
5. Remove `~/.hippoclaudus` dotfile
6. Print confirmation of what was removed and what was kept

## CLAUDE.md Template (Generic)

The installed CLAUDE.md contains:

- Memory architecture instructions (all three tiers)
- Session start protocol
- Compaction protocol
- Cognitive subroutines (Core 4 loop + DRE Triad)
- All paths dynamically substituted

It does NOT contain:

- Personal identity, persona names
- Relationship files or key people
- Machine-specific context
- Any DeCue Technologies references

Clearly marked customization blocks:
```markdown
<!-- PERSONALIZE: Add your identity context here. Run 'hippo personalize' for guided setup. -->
```

## Post-Install Output

```
 Hippoclaudus v4.1 installed successfully

  Memory system:  ~/Documents/Claude/mcp-memory/
  CLAUDE.md:      ~/Documents/Claude/CLAUDE.md
  MCP config:     Updated (backup at claude_desktop_config.json.bak.2026-02-17T1430)

  Next steps:
  1. Restart Claude Desktop (or Claude Code) to load the MCP memory server
  2. Run 'hippo personalize' to customize CLAUDE.md with your identity and context
  3. Start a new Claude session - the memory system is active

  +-----------------------------------------------------------------------+
  |  Although download time and system memory allocation will be increased |
  |  by a full installation, incorporation of a small, local LLM is       |
  |  strongly advised. The full benefit of the Hippoclaudus Memory        |
  |  Architecture will not be available without doing so and, in          |
  |  addition, if Claude receives no assistance with regard to searching  |
  |  long-term memory or related processing tasks, token usage rates will |
  |  increase and some lag in memory processing time may be experienced.  |
  |  Beyond that, what could be cooler than an AI using an AI to help     |
  |  you better use AI?                                                   |
  |                                                                       |
  |  Run: hippo install --with-llm                                        |
  +-----------------------------------------------------------------------+
```

## Error Output

Human-readable, one action per error:

```
 Python 3.10+ required (found 3.8.10)
  Install Python 3.10+: https://python.org/downloads
  On macOS with Homebrew: brew install python@3.12
```

## Module Structure

### New Modules

| Module | Purpose |
|--------|---------|
| `hippoclaudus/installer.py` | Core install/uninstall logic |
| `hippoclaudus/platform.py` | OS detection, config paths, path resolution |
| `hippoclaudus/personalizer.py` | Interactive CLAUDE.md customization |
| `hippoclaudus/llm_installer.py` | `--with-llm` backend setup and model download |

### Modified Modules

| Module | Change |
|--------|--------|
| `hippoclaudus/cli.py` | Add install/uninstall/personalize/install-llm commands |
| `templates/CLAUDE.md` | Generic version with PERSONALIZE blocks, no personal context |
| `pyproject.toml` | Version bump to 4.1.0, add entry points |
| `hippoclaudus/__init__.py` | Version bump to 4.1.0 |

### Existing Modules (Unchanged)

`archive_builder.py`, `llm.py`, `db_bridge.py`, `consolidator.py`, `compactor.py`, `tagger.py`, `predictor.py`, `scoring.py`, `comm_profiler.py`, `symbolic_encoder.py`, `slot_manager.py`

## Install Metadata (`.hippoclaudus`)

Written to `~/.hippoclaudus` during install:

```json
{
  "install_path": "/Users/jane/Documents/Claude",
  "installed_at": "2026-02-17T14:30:00Z",
  "version": "4.1.0",
  "llm_installed": false,
  "platform": "darwin"
}
```

Used by `hippo uninstall` and `hippo doctor` to locate the installation.
