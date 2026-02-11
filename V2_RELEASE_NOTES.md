# Hippoclaudus v2 — Release Notes

**Version:** 1.1.0
**Date:** February 2026

---

## Summary

Hippoclaudus v1 shipped the core architecture: a three-tier memory system for Claude using markdown files, an MCP semantic database, and a conversation archive scanner. It worked, but setup was manual (six discrete steps), there was no way to verify your installation, the conversation scanner used a flat keyword list with no category context, and the documentation assumed macOS.

v2 closes those gaps. It adds a local AI engine for automated memory management (consolidation, deduplication, tagging, session prediction, relationship profiling), cross-platform LLM inference (MLX on Apple Silicon, llama-cpp-python on Windows/Linux), automated installation, a diagnostic tool, category-aware conversation scoring, an ad-hoc search mode, externalized keyword configuration, cross-platform documentation, MCP database integration into the update protocol, and project governance files for outside contributors.

---

## Local AI Engine (`hippoclaudus/` Python Package)

The headline addition in v2. A Python package that runs a local LLM on-device to automate memory management tasks that would otherwise require manual effort or burning Claude API tokens.

### Architecture

The package uses a **dual-backend inference system**:

- **MLX** (Apple Silicon): Native Metal acceleration via `mlx-lm`. Loads HuggingFace safetensors format. Fastest path on M-series chips.
- **llama-cpp-python** (cross-platform): GGUF quantized model inference. Supports Windows (NVIDIA CUDA), Linux (CUDA), macOS (Metal), and CPU-only fallback.

Backend is auto-detected at import time. On Apple Silicon, MLX is preferred if installed; otherwise falls back to llama-cpp-python. All downstream modules (`consolidator`, `compactor`, `tagger`, `predictor`, `comm_profiler`) call the unified `run_prompt()` interface and are backend-agnostic.

### Modules

**`llm.py` — Multi-Backend Inference Dispatcher**
- `detect_backend()` — auto-detects MLX or llama-cpp-python
- `run_prompt(model_name, prompt, max_tokens, temp)` — unified interface, routes to the right backend
- `extract_json(text)` — extracts JSON from LLM output, handles markdown code fences
- Prompt templates for consolidation, entity tagging, and communication profiling
- Model caching: loaded once, reused across calls

**`db_bridge.py` — Direct SQLite Bridge**
- Reads and writes directly to `memory.db` alongside the running MCP server
- Uses WAL mode and busy timeouts to avoid lock contention
- `Memory` dataclass mirrors the MCP memory service schema
- Read ops: `get_all_memories()`, `get_memory_by_hash()`, `search_by_tag()`, `get_stats()`
- Write ops: `store_memory()`, `update_tags()`, `store_graph_edge()`
- `parse_latest_session()` — extracts the most recent session entry from Session_Summary_Log.md

**`consolidator.py` — Session Compression**
- Reads the latest session from Session_Summary_Log.md
- Runs it through the local LLM to extract a structured State Delta:
  - `state_delta`: 50-100 word dense summary of what changed
  - `entities`: people, projects, tools mentioned
  - `security_context`: any MNPI or regulated data discussed
  - `emotional_signals`: detected tone (frustration, excitement, urgency)
  - `open_threads`: unresolved items
- Stores the State Delta in memory.db with entity-derived tags
- Includes `run_reflection()` dry-run mode that displays without storing

**`compactor.py` — Memory Deduplication**
- Computes Jaccard (token-overlap) similarity between all memory pairs
- Pairs above the threshold (default 0.3) are sent to the LLM for evaluation
- LLM classifies each pair as: `duplicate`, `superseded`, `related`, or `distinct`
- For duplicates/superseded: soft-deletes the older or less complete entry
- For merge decisions: creates a new consolidated memory, soft-deletes both originals
- Supports `dry_run` mode for preview

**`tagger.py` — Entity Extraction**
- Runs memories through the LLM to extract people, projects, tools, topics
- Merges extracted tags with existing tags (deduplicates, normalizes)
- `run_tag_single(memory_id)` — tag one memory
- `run_tag_all()` — batch-tag all memories with sparse tags (skips well-tagged ones with 5+ tags)

**`predictor.py` — Next-Session Briefing**
- Reads recent session logs, open questions, and state deltas from memory.db
- Generates `PRELOAD.md` — a context-dense briefing document:
  - Active context (what we're in the middle of)
  - Unresolved threads
  - Key people state (last known status, pending interactions)
  - Suggested first moves
  - Emotional/relational notes
- Claude reads this at session start to hit the ground running

**`scoring.py` — Weighted Decay Scoring**
- Composite formula: `Score = (0.6 * cosine_sim) + (0.3 * recency_decay) + (0.1 * access_freq)`
- Exponential recency decay with configurable half-life (default 14 days)
- Log-scaled access frequency (saturates around 50 accesses)
- All weights are configurable via `ScoringWeights` dataclass

**`comm_profiler.py` — Relationship Analysis**
- Searches memories and relationship files for references to a specific person
- Runs the LLM to extract: tone, priorities, decision style, response patterns, key phrases, working relationship dynamics
- Outputs a structured communication profile

---

## New Files

### `install.sh` — Automated Installer

Replaces the six-step manual setup with a single command. The script:

1. Creates the full directory structure (`mcp-memory/long-term`, `working`, `data`, `conversations`)
2. Detects Python 3 and creates a virtual environment
3. Installs `mcp-memory-service` into the venv
4. Copies all templates to their correct locations
5. Substitutes actual paths into `CLAUDE.md` (platform-aware `sed`)
6. Prints the exact MCP config JSON the user needs to paste, pre-filled with their paths

Accepts an optional base path argument (defaults to `~/Claude`). Handles macOS and Linux; Windows users still follow the manual steps in the writeup (which now include Windows-specific instructions).

### `doctor.py` — Diagnostic Tool

A pass/fail health checker that validates the entire installation. Checks:

- **Python version** (requires 3.10+)
- **Directory structure** — all four required subdirectories exist
- **Key files** — CLAUDE.md, INDEX.md, Total_Update_Protocol.md, all three working memory templates
- **MCP memory database** — `memory.db` exists, reports size
- **Python environment** — venv exists, `mcp-memory-service` is importable
- **Claude Desktop config** — config file exists, memory server is configured, command path is valid, database path is valid
- **Conversation archive** (optional) — `conversations.json`, index, scanner, and extractor scripts

Auto-detects the base path by reading the Claude Desktop config file, falling back to common defaults (`~/Claude`, `~/Desktop/Claude`). Cross-platform: macOS, Linux, Windows.

### `CHANGELOG.md`

Follows Keep a Changelog format. Documents v1.0.0 (initial release) and v1.1.0 (this release) with Added/Changed sections.

### `CONTRIBUTING.md`

Contribution guidelines built around the five design principles as hard constraints:

1. **Selective loading** — no bulk-loading at session start
2. **Signal over noise** — no padding, no "just in case" fields
3. **Memory hygiene** — every new storage mechanism must include a pruning path
4. **Human in the loop** — Tier 3 stays manual by design
5. **Local first** — no external services, no cloud dependencies

Lists what's welcomed (bug fixes, template improvements, cross-platform support, doctor improvements) and what will be rejected (external service dependencies, UI layers, complexity for flexibility's sake).

### `templates/keywords.yaml`

Externalized keyword configuration for the conversation scanner. Previously, keywords were hardcoded in `scan_conversations.py`. Now they live in a YAML file organized by category:

- `technical` — architecture, deployment, database, api, migration, refactor, infrastructure
- `decisions` — decision, pivot, strategy, tradeoff, chose, decided
- `relationships` — placeholder names (users replace with their own)
- `projects` — placeholder names (users replace with their own)
- `milestones` — shipped, released, completed, milestone, launched, deadline
- `meta` — memory, mcp, persistence, identity, hippoclaudus

The scanner loads this file automatically. If `keywords.yaml` isn't present or the `yaml` Python module isn't installed, it falls back to built-in defaults via a manual YAML parser (no new dependencies required).

### `templates/Infrastructure_Notes.md`

Template for tracking the user's specific environment: hardware, OS, MCP configuration, key paths, available tools, and known issues. Referenced by Layer 5 of the Total Update Protocol.

---

## Modified Files

### `scan_conversations.py` — Category-Aware Scoring + Ad-Hoc Search

**Before:** Flat keyword list. A conversation with 3 matches in the same topic area scored identically to one with 3 matches across different domains. Sorting was purely by keyword count. No way to search without running a full scan.

**After:**

- **Category-level scoring.** Keywords are grouped by category (technical, decisions, relationships, etc.). Conversations are ranked by category breadth first (how many *different* categories matched), then keyword count within categories. A conversation matching `technical + decisions + relationships` outranks one matching `technical` three times — because cross-category relevance signals a richer conversation.

- **Ad-hoc search mode.** `python3 scan_conversations.py --search "database migration"` scans all message text (not just a sample) for the specified terms and returns matching conversations with index numbers for extraction. No need to rebuild the full index just to find something specific.

- **External keyword loading.** Reads `keywords.yaml` if present; falls back to built-in defaults if not. Includes a manual YAML parser so the `PyYAML` package isn't required.

- **Refactored internals.** Extracted `load_conversations()`, `build_sample_text()`, and `extract_category_matches()` as standalone functions. Added `argparse` for the CLI interface. The readable markdown index now shows matches by category for each conversation.

### `WRITEUP.md` — Cross-Platform Documentation

The setup guide previously showed a single code block with a commented-out Windows line. Now provides:

- Separate installation blocks for macOS/Linux, Windows PowerShell, and Windows Command Prompt
- Platform-specific MCP config JSON (forward slashes vs. backslashes, `bin/python` vs. `Scripts/python.exe`)
- Config file locations in a clean table format
- Explicit callout of the common macOS-vs-Windows venv path gotcha
- Total Update Protocol section updated to reference the new 11-layer structure

### `templates/CLAUDE.md` — MCP Memory Instructions

Added a new section documenting the MCP memory database tools available to Claude:

- `memory_store` — when and how to store memories with category tags
- `memory_search` — semantic search across all stored memories
- `memory_list` — browsing by tag or type
- `memory_health` — connection verification

Also added the ad-hoc search capability to the conversation archive instructions (Step 4).

### `templates/Total_Update_Protocol.md` — New Layer 6

The protocol expanded from 10 to 11 layers. The new Layer 6 (MCP Memory Database) instructs Claude to:

- Store key session insights via `memory_store` with appropriate tags
- Categorize using tags: `decision`, `technical`, `relationship`, `project`, `insight`
- Use the database for searchable fragments, not full document duplication
- Build the semantic search layer incrementally over time

All subsequent layers renumbered accordingly (Ad Hoc Items became Layer 7, Decision Log became Layer 8, etc.).

### `.gitignore` — Comprehensive Protection

Expanded from a single entry (`x_thread.md`) to a full `.gitignore` covering:

- User data files (`.db`, `.json` exports, `extracted/` directory)
- Working memory content (user-generated markdown, while preserving templates)
- Long-term memory content (same pattern — templates tracked, user content ignored)
- Python artifacts (`venv/`, `__pycache__/`, `*.pyc`, egg-info, dist, build)
- Environment files (`.env`, `.env.local`)
- OS files (`.DS_Store`, `Thumbs.db`)
- IDE files (`.vscode/`, `.idea/`, swap files)

This prevents users from accidentally committing their personal memory data, database contents, or credentials when contributing back to the project.

---

## What This Means for Users

**New users** get a dramatically simpler onboarding: run `install.sh`, paste the config it generates, run `doctor.py` to verify. What was a 6-step manual process is now essentially 1 + verify.

**Existing users** upgrading from v1 should:
1. Copy `keywords.yaml` to their conversations directory and customize it
2. Re-run `scan_conversations.py` to get category-aware scoring
3. Update their `CLAUDE.md` with the new MCP memory instructions section
4. Update their `Total_Update_Protocol.md` to the 11-layer version
5. Run `doctor.py` to verify their installation is healthy

**Contributors** have clear guardrails via `CONTRIBUTING.md` and can validate their changes against `doctor.py`.
