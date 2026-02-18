# Hippoclaudus — Legacy Models & Historical Documentation

> This file consolidates all pre-v4.1 design documents, specs, and release notes.
> These represent the evolution of Hippoclaudus from v1.0 through v3.0.
> The current architecture is documented in `V4_SPEC.md`, `V4_1_SPEC.md`, and the `CHANGELOG.md`.

---

# Table of Contents

1. [Original Architecture Writeup (v1.0)](#original-architecture-writeup-v10)
2. [v2 Release Notes (v1.1.0)](#v2-release-notes-v110)
3. [v3.0 Specification — Symbolic Compression & Philosophical Operators](#v30-specification)
4. [X Thread Draft — Launch Announcement](#x-thread-draft)
5. [Legacy Scripts](#legacy-scripts)

---

<a id="original-architecture-writeup-v10"></a>
# Original Architecture Writeup (v1.0)

*Originally: `WRITEUP.md` — February 2026*

## Why This Exists

If you use Claude for anything sustained — building a product, running a business, a long-term creative project — you've hit the wall. Every session starts fresh. You re-explain who you are, what you're working on, what was decided last time. The 30 built-in memory slots help with basics, but they're shallow. They can't hold the texture of a months-long collaboration.

This is a system that solves that. It uses Claude's existing tools — MCP servers, file access, CLAUDE.md auto-loading — to give Claude a structured, three-tier memory that persists across sessions and scales from "what did we decide yesterday" to "find that conversation from three months ago where we discussed the database architecture."

## The Architecture

### Tier 1: Short-Term Memory (Anthropic's 30 Slots)
This is what Claude already gives you. Thirty memory items that persist across sessions within a project. Good for your name, communication preferences, current project status, active decisions.

**Role in the system:** Fast recall of the most recent and most frequently needed context. Think of it as working memory.

### Tier 2: Foundational Memory (Markdown Files + MCP Database)
A directory of markdown files on your local machine, accessible to Claude through MCP file access or Claude Code's native file tools.

**Structure:**
```
mcp-memory/
├── long-term/          # Things that change slowly
│   ├── INDEX.md        # Master catalog — Claude reads this first
│   ├── Relationship_Alice.md
│   └── Project_Alpha_Reference.md
├── working/            # Things that accumulate between sessions
│   ├── Session_Summary_Log.md
│   ├── Open_Questions_Blockers.md
│   └── Decision_Log.md
└── data/
    └── memory.db       # MCP sqlite-vec database (semantic search)
```

**The key design choice:** Selective loading. Claude does NOT read everything at session start. It reads the INDEX (so it knows what's available), reads working memory (so it knows what happened recently), and reads deeper files only when the conversation needs them.

### Tier 3: Deep Recall (Conversation Archive)
Your full conversation history with Claude, exported from claude.ai, indexed, and searchable. Intentionally slow and human-in-the-loop.

## Design Principles

1. **Selective loading, not context dumping.** Load the index, load working memory, read deeper only when needed.
2. **Signal over noise.** If nothing changed, don't pad entries for completeness.
3. **Three speeds for three needs.** Instant (memory slots), fast (file reads), slow (archive search).
4. **Memory hygiene is non-negotiable.** Without pruning, memory systems degrade.
5. **Human in the loop for deep recall.** Keeps you aware of what's being recalled.

---

<a id="v2-release-notes-v110"></a>
# v2 Release Notes (v1.1.0)

*Originally: `V2_RELEASE_NOTES.md` — February 2026*

## Summary

v1 shipped the core architecture: a three-tier memory system for Claude. v2 closes the gaps with a local AI engine for automated memory management.

## Local AI Engine (`hippoclaudus/` Python Package)

A Python package that runs a local LLM on-device to automate memory management tasks.

### Dual-Backend Inference
- **MLX** (Apple Silicon): Native Metal acceleration via `mlx-lm`
- **llama-cpp-python** (cross-platform): GGUF quantized model inference with CUDA/Metal/CPU support

### Modules

| Module | Function |
|--------|----------|
| `llm.py` | Multi-backend inference dispatcher |
| `db_bridge.py` | Direct SQLite bridge to memory.db with WAL mode |
| `consolidator.py` | Session → State Delta compression |
| `compactor.py` | LLM-powered duplicate detection and merging |
| `tagger.py` | Entity extraction and tag enrichment |
| `predictor.py` | Next-session PRELOAD.md briefing generator |
| `scoring.py` | Weighted decay relevance scoring |
| `comm_profiler.py` | Relationship pattern analysis |

### New Files

- **`install.sh`** — Automated installer (single command replaces 6-step manual setup)
- **`doctor.py`** — Diagnostic tool (pass/fail health checker)
- **`CHANGELOG.md`** — Version tracking
- **`CONTRIBUTING.md`** — Contribution guidelines
- **`keywords.yaml`** — Externalized keyword config for conversation scanner

> **Note:** Both `install.sh` and `doctor.py` were superseded in v4.1 by `hippo install`.

---

<a id="v30-specification"></a>
# v3.0 Specification — Symbolic Compression & Philosophical Operators

*Originally: `V3_SPEC.md` — February 14, 2026*

## Overview

v3.0 introduces two major upgrades:

1. **Symbolic Memory Compression** — Dense Unicode notation expanding capacity from ~40 facts to ~140 facts across 30 memory slots
2. **Philosophical Operator Engine** — Compressed operators that reshape *how* the LLM reasons

Both features were designed through a three-way discussion between Claude/Morpheus, Google Gemini (Pro mode), and xAI Grok (Expert mode), with James Palczynski adjudicating.

## Symbolic Memory Compression

### Core Insight
Claude processes memory slots through parallel attention — every token activates simultaneously. Grammar is waste. Rare Unicode symbols create cleaner activation patterns in sparse embedding neighborhoods.

### Symbol Vocabulary

| Symbol | Meaning |
|--------|---------|
| `→` | causes / leads to |
| `⊘` | blocks / prevents |
| `⇒` | therefore / implies |
| `↔` | mutual dependency |
| `∆` | needs fix |
| `✓` | done |
| `⏳` | pending |
| `✗` | killed / rejected |
| `🔴` | important |
| `⚡` | time-urgent |
| `»` | more detail stored elsewhere |

### Compression Example

**English (234 chars):**
> The website development folder is completely empty, which is a critical gap. We have a Site Build folder with 97 files and the landing page is complete.

**Symbolic (78 chars):**
```
Wb⚡🔴:dev-folder=∅crit-gap|SiteBuild:97files,landing✓
```

### Measured Results

| Metric | Before | After |
|--------|--------|-------|
| Facts per 30 slots | 35-45 | 120-140 |
| Context searches at start | 3-5 | 0-1 |
| Conversation length | Baseline | +20-30% |

## Philosophical Operator Engine

### The Core 4 — The Hippoclaudus Loop

```
Peirce → Bayesian → Hofstadter → Meadows → (restart)
Hypothesize → Test → Examine Process → Act on Leverage
```

1. **Pa:Abduct (Peirce)** — Generate surprising hypotheses from observations
2. **Bay:Update (Bayesian)** — Test hypotheses against evidence, revise beliefs
3. **Hof:Loop (Hofstadter)** — Examine the reasoning process itself (metacognition)
4. **Mea:Lever (Meadows)** — Find highest-leverage intervention point, act

### The DRE Triad — Perceptual Expansion

Origin: James Palczynski's practitioner vision. Distinct from and complementary to Core 4.

```
Trace (backward) → Registers (across) → Semiosis (forward)
Audit absence → Test scale invariance → Resist premature closure
```

1. **Dr:Trace (Derrida)** — Audit for absence in both input and output
2. **La:Reg (Lacan)** — Test whether structural patterns persist across scales
3. **Ec:Sem (Eco)** — Before closing, check if conclusion opens unconsidered extensions

### How Core 4 and DRE Interact

- Trace opens questions → Bayesian Update tests which absences matter
- Semiosis resists closure → Meadows forces action at highest-impact point
- Registers abstract across scales → Peirce generates testable hypotheses
- All three expand perception → Hofstadter examines if expansion is genuine insight

Core 4 is the process engine. DRE is the perceptual engine. Together: perceive more, then reason well about what you perceive.

### What Was Cut and Why

| Concept | Cut Reason |
|---------|------------|
| Foucault (power/knowledge) | Cynicism drift risk |
| Shannon (surprisal) | Overlaps Bayesian implicitly |
| Deleuze (rhizome) | Too vague to operationalize |
| Popper (falsifiability) | Less native to LLMs than Bayesian |

> **Note:** v4.0 moved operators from memory slots to CLAUDE.md as procedural instructions, based on the finding that declarative slot storage doesn't reliably activate as reasoning procedures. See `V4_SPEC.md`.

---

<a id="x-thread-draft"></a>
# X Thread Draft — Launch Announcement

*Originally: `x_thread.md` — February 2026*

> Draft X/Twitter thread for Hippoclaudus launch. Not yet posted.

**Tweet 1 (Hook):** I gave Claude a hippocampus. Every session starts cold — I got tired of it. So I built a three-tier persistent memory architecture. It's called Hippoclaudus.

**Tweet 2 (Architecture):** Tier 1: Short-term (30 memory slots). Tier 2: Foundational (markdown files + MCP semantic database). Tier 3: Deep recall (full conversation history, indexed and searchable).

**Tweet 3 (Key Insight):** The breakthrough: CLAUDE.md. A file in your project root that Claude Code auto-loads. Put your memory bootstrap there — Claude wakes up knowing it has a memory system.

**Tweet 4 (Selective Loading):** Claude does NOT read everything at startup. It reads an INDEX, reads working memory, and pulls deeper files only when needed. Context windows stay clean.

**Tweet 5 (Memory Hygiene):** Memory without maintenance rots. So there's a Total Update protocol and a local AI engine that handles consolidation, deduplication, and tagging.

**Tweet 6 (Deep Recall):** Export your conversation history from claude.ai. Run a Python scanner. Now Claude can search months of history and extract specific conversations on demand.

**Tweet 7 (Requirements):** Claude Pro or Team, Python 3.10+, mcp-memory-service. No external services. Everything runs locally.

**Tweet 8 (CTA):** I open-sourced it. Templates, scripts, setup guide. GitHub: [LINK]. Tag @AnthropicAI and @ClaudeAI.

**Tweet 9 (Closing):** Named after the hippocampus — the brain's memory formation center. Because the best AI assistant is one that remembers.

---

<a id="legacy-scripts"></a>
# Legacy Scripts

## `install.sh` (Superseded by `hippo install`)

Shell-based installer that created the directory structure, set up a venv, installed mcp-memory-service, copied templates, and printed MCP config JSON. macOS/Linux only. Replaced by the cross-platform Python installer in v4.1.

## `doctor.py` (Superseded by `hippo install`)

Pass/fail diagnostic tool that validated the installation: Python version, directory structure, key files, MCP database, venv health, Claude Desktop config, and conversation archive. Replaced by the installer's built-in verification in v4.1.

---

*This file consolidates historical documentation from Hippoclaudus v1.0 through v3.0.*
*Current architecture: see `V4_SPEC.md` and `V4_1_SPEC.md`.*
