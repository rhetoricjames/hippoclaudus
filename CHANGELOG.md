# Changelog

All notable changes to Hippoclaudus will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [1.1.0] - 2026-02-11

### Added
- **Local AI engine** (`hippoclaudus/` Python package) — 7 modules for automated memory management:
  - `llm.py` — multi-backend inference dispatcher (MLX for Apple Silicon, llama-cpp-python for Windows/Linux)
  - `db_bridge.py` — direct SQLite bridge to memory.db with WAL mode for safe concurrent access
  - `consolidator.py` — post-session compression into structured State Deltas
  - `compactor.py` — LLM-powered duplicate detection and memory merging
  - `tagger.py` — entity extraction and tag enrichment
  - `predictor.py` — next-session PRELOAD.md briefing generator
  - `scoring.py` — weighted decay relevance scoring (semantic + recency + access frequency)
  - `comm_profiler.py` — relationship pattern analysis for specific people
- Cross-platform LLM support: MLX (Apple Silicon/Metal) + llama-cpp-python (Windows CUDA, Linux CUDA, CPU fallback)
- `pyproject.toml` for pip-installable package
- `doctor.py` diagnostic tool — checks installation health with pass/fail checklist
- `install.sh` automated setup script — reduces setup from 6 steps to 1
- `keywords.yaml` configuration file — externalized keyword config for conversation scanner
- `CONTRIBUTING.md` with design principles as constraints for PRs
- `CHANGELOG.md` to track releases
- Infrastructure Notes template
- MCP memory database layer (Layer 6) in Total Update Protocol
- Cross-platform instructions in WRITEUP.md (macOS, Linux, Windows)
- Comprehensive `.gitignore` protecting user data from accidental commits

### Changed
- Total Update Protocol expanded from 10 to 11 layers (added MCP database step)
- `scan_conversations.py` now supports `keywords.yaml` with category-level scoring
- CLAUDE.md template now includes MCP memory tool instructions
- README rewritten to cover local AI engine, cross-platform backends, and updated file tree

## [1.0.0] - 2026-02-08

### Added
- Initial release
- Three-tier memory architecture (short-term, foundational, deep recall)
- CLAUDE.md template for Claude Code auto-loading
- Memory Bootstrap template for Claude Desktop projects
- Total Update Protocol (10-layer memory hygiene)
- INDEX.md master catalog template
- Working memory templates (Session Summary, Open Questions, Decision Log)
- `scan_conversations.py` — conversation archive indexer
- `extract_conversations.py` — on-demand conversation extractor
- WRITEUP.md — full architecture explanation and setup guide
- README.md — quick start guide
