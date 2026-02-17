# Changelog

All notable changes to Hippoclaudus will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [4.0.0] - 2026-02-16

### Added
- **Cognitive Subroutines in CLAUDE.md** — operators are now plain English procedural instructions, not symbolic tokens in memory slots. CLAUDE.md loads every turn with high attention weight, making it the correct architecture for behavioral activation.
- **V4_SPEC.md** — full architectural specification documenting all v4 design decisions
- **Token economics analysis** — documented that Unicode symbols cost 2-3 tokens each (UTF-8 fallback in BPE) vs. 1 token per English word. Symbols save characters but cost ~1.5-1.8× more tokens. Decision: symbols for memory slots (character-constrained), English for CLAUDE.md (token-constrained).
- **Cooperative slot management** — Anthropic's native memory system writes first, MCP post-pass fills remaining capacity, end-of-session directive captures context before compaction
- **Default Mode Network (DMN)** — empty slots populated with loosely-related content (similarity 0.4-0.7) for associative creative connection
- **`format_cognitive_subroutines()`** in symbolic_encoder.py — generates the CLAUDE.md subroutines section programmatically
- **Lexical attention engineering** — sparse synonym selection for higher attention weight at same token cost

### Changed
- **Operators moved from memory slots to CLAUDE.md** — the core architectural change. Memory slots are declarative storage (model treats contents as facts); CLAUDE.md is procedural (loaded as instructions). Operators need procedural placement.
- **Peirce Abduction corrected** — from "generate surprising hypotheses" (output-focused) to "what doesn't fit the expected pattern?" (input-focused anomaly detection). Surprise is in the INPUT, not the OUTPUT.
- **Legend relocated** from locked Slot 1 to MCP memory (on-demand fetch via `memory_search`). Most symbols are self-documenting from training data.
- **All 30 slots now available** — no reserved slots for legend, operators, or DRE. Cooperative management replaces locked allocation.
- **slot_manager.py rewritten** — removed all reserved slot logic, added `empty_slots` property, DMN capacity warnings, cooperative Anthropic-first philosophy
- **symbolic_encoder.py rewritten** — removed `generate_operator_slot()`, `generate_dre_slot()`, added `CORE_4_SUBROUTINES` and `DRE_SUBROUTINES` dicts with corrected framing, added `format_cognitive_subroutines()`
- **templates/CLAUDE.md updated** — includes full Cognitive Subroutines section with The Hippoclaudus Loop and DRE Triad
- **README.md rewritten** — v4 architecture, cognitive subroutines as primary feature, token economics, updated design principles
- **Unicode markers in CLAUDE.md** — used as attention amplifiers (🔴 > "IMPORTANT"), not compression. Strategic placement creates attention landmarks.

### Removed
- Locked slot allocation (Slots 1-3 no longer reserved)
- `generate_operator_slot()` and `generate_dre_slot()` functions
- Operator slot validation functions
- V2_RELEASE_NOTES.md and WRITEUP.md references from file tree

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
- MCP memory database integration (consolidator stores State Deltas with entity-derived tags)
- Cross-platform instructions in WRITEUP.md (macOS, Linux, Windows)
- Comprehensive `.gitignore` protecting user data from accidental commits

### Changed
- Total Update Protocol replaced by local AI engine (file retained as legacy reference)
- `scan_conversations.py` now supports `keywords.yaml` with category-level scoring
- CLAUDE.md template now includes MCP memory tool instructions
- README rewritten to cover local AI engine, cross-platform backends, and updated file tree

## [1.0.0] - 2026-02-08

### Added
- Initial release
- Three-tier memory architecture (short-term, foundational, deep recall)
- CLAUDE.md template for Claude Code auto-loading
- Memory Bootstrap template for Claude Desktop projects
- Total Update Protocol (manual memory hygiene checklist — later superseded by local AI engine in v1.1.0)
- INDEX.md master catalog template
- Working memory templates (Session Summary, Open Questions, Decision Log)
- `scan_conversations.py` — conversation archive indexer
- `extract_conversations.py` — on-demand conversation extractor
- WRITEUP.md — full architecture explanation and setup guide
- README.md — quick start guide
