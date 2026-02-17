# Hippoclaudus

*A persistent memory architecture for Claude — with cognitive subroutines and local AI-powered memory management.*

Named after the hippocampus — the brain's memory formation center. A three-tier system that gives Claude persistent, structured recall across sessions, plus a local LLM engine for automated maintenance and a cognitive subroutine system that expands *how* the model reasons.

## The Problem

Every Claude session starts cold. You re-explain context, re-establish preferences, re-describe your project. The built-in memory slots help, but they're shallow. For ongoing collaborations — building a product, managing a business, any sustained creative or technical work — you need more.

And LLMs default to the same reasoning patterns: deduction, induction, pattern-matching to the most probable completion. Modes of reasoning that already exist in the model — abductive leaps, metacognition, structural analysis, anomaly detection — stay dormant unless activated.

## The Solution

### Three-Tier Memory

| Tier | What | Where | Speed |
|------|-------|-------|-------|
| **1. Short-term** | Recent context, project facts | Anthropic's memory slots (symbolically compressed) | Instant (auto-loaded) |
| **2. Foundational** | Identity, relationships, protocols, reference docs | Markdown files + MCP sqlite-vec database | Fast (read on demand) |
| **3. Deep recall** | Full conversation history, searchable | Exported JSON archive + keyword index | Slower (search then extract) |

### Cognitive Subroutines (v4.0)

Philosophical operators installed in CLAUDE.md as procedural instructions — not facts to remember, but operations to perform:

**The Hippoclaudus Loop:**
```
Hypothesize → Test → Examine Process → Act on Leverage → (restart)
```

| Tag | Operator | What It Does |
|-----|----------|-------------|
| Pa:Abd | Peirce Abduction | What doesn't fit the expected pattern? What would explain it? |
| Bay:Upd | Bayesian Updating | What was my prior? What does this evidence show? How should confidence shift? |
| Hof:Loop | Hofstadter Strange Loops | Am I reasoning or pattern-matching? What changes if I examine my process? |
| Mea:Lev | Meadows Leverage Points | Where would a small shift produce the largest cascade? Act there. |

**Perceptual Checks (DRE Triad):**

| Tag | Operator | What It Does |
|-----|----------|-------------|
| Dr:Trace | Derrida Trace | Audit for absence: what's missing from input? What am I leaving out? |
| La:Reg | Lacan Registers | What's the structural shape? Does it appear at different scales? |
| Ec:Sem | Eco Semiosis | Does this conclusion open something I haven't explored? |

These are not personality directives (top-down). They are reasoning expansions (bottom-up). They don't tell the model what to be — they open pathways to what it can already do.

### Symbolic Memory Compression

Memory slots are character-constrained. English grammar wastes characters. Rare Unicode symbols create cleaner activation patterns in sparse embedding neighborhoods:

**English (234 chars):**
> The website development folder is completely empty, which is a critical gap. We have a Site Build folder with 97 files and the landing page is complete.

**Symbolic (78 chars):**
```
Wb⚡🔴:dev-folder=∅crit-gap|SiteBuild:97files,landing✓|threat-brief-HTML✓
```

Same information. One-third the characters.

**Key finding (v4):** Symbols save characters but cost ~1.5-1.8× more *tokens* (UTF-8 fallback in BPE). Therefore: symbols for memory slots (character-constrained), plain English for CLAUDE.md (token-constrained).

### Local AI Engine

A Python package that runs a local LLM on your machine to automate memory maintenance. No API calls. No tokens spent. No data leaves your computer.

| Module | What It Does |
|--------|-------------|
| **Consolidator** | Reads session logs, extracts structured State Deltas |
| **Compactor** | Finds duplicate memories, uses LLM to judge and merge |
| **Tagger** | Extracts entities and enriches memory tags |
| **Predictor** | Generates PRELOAD.md briefing for next session |
| **Comm Profiler** | Analyzes interaction patterns for specific people |
| **Scorer** | Weighted decay: `(0.6 * similarity) + (0.3 * recency) + (0.1 * frequency)` |
| **Symbolic Encoder** | Compresses English facts into symbolic notation |
| **Slot Manager** | Manages memory slot allocation cooperatively with Anthropic's native system |

**Cross-platform inference:**
- **Apple Silicon (macOS):** MLX — native Metal acceleration
- **Windows/Linux (NVIDIA):** llama-cpp-python with CUDA
- **CPU fallback:** llama-cpp-python on any machine

## What's Included

```
hippoclaudus/
├── README.md                          # You're reading it
├── V4_SPEC.md                         # Full v4 specification
├── CHANGELOG.md                       # Version history
├── CONTRIBUTING.md                    # How to contribute
├── hippoclaudus/                      # Local AI engine (Python package)
│   ├── __init__.py
│   ├── llm.py                         # Multi-backend inference
│   ├── db_bridge.py                   # SQLite bridge to memory.db
│   ├── consolidator.py                # Session → State Delta compression
│   ├── compactor.py                   # Duplicate detection and merging
│   ├── tagger.py                      # Entity extraction
│   ├── predictor.py                   # Next-session briefing generator
│   ├── scoring.py                     # Weighted decay scoring
│   ├── comm_profiler.py               # Relationship pattern analysis
│   ├── symbolic_encoder.py            # Symbolic compression + subroutine definitions
│   └── slot_manager.py                # Cooperative slot allocation
├── templates/
│   ├── CLAUDE.md                      # Drop into project root (auto-loads in Claude Code)
│   └── [working memory templates]     # Session logs, decision tracking, etc.
├── doctor.py                          # Diagnostic tool
├── install.sh                         # Automated setup
└── pyproject.toml                     # Package config
```

## Quick Start

### Option A: Automated Install (macOS/Linux)

```bash
git clone https://github.com/rhetoricjames/hippoclaudus.git
cd hippoclaudus
bash install.sh
```

Verify:
```bash
python3 doctor.py
```

### Option B: Manual Install

See the step-by-step instructions in [V4_SPEC.md](V4_SPEC.md).

### Installing the Local AI Engine

**Apple Silicon:**
```bash
pip install mlx mlx-lm
```

**Windows/Linux (NVIDIA GPU):**
```bash
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
```

**Any platform (CPU):**
```bash
pip install llama-cpp-python
```

Then:
```bash
cd hippoclaudus
pip install -e .
```

### After Install

1. Copy `templates/CLAUDE.md` to your project root — edit paths to match your setup
2. The cognitive subroutines section activates automatically in every Claude Code session
3. (Optional) Export conversation history and run `scan_conversations.py`

## How the Cognitive Subroutines Work

The subroutines live in CLAUDE.md because:

1. **CLAUDE.md loads every turn** — high attention weight, positioned as instructions
2. **Memory slots are declarative** — the model treats slot contents as facts, not operations
3. **Plain English is token-efficient** — 1 token per word vs. 2-3 tokens per Unicode symbol
4. **Tags are preserved** — `[Pa:Abd]` enables auditability and A/B testing

The operators don't constrain reasoning — they expand it. They make available modes of thinking that already exist in the model but are underactivated by default prompt architectures. This is a classical education for a machine: installing operations, not facts.

## Design Principles

1. **Selective loading** — Don't dump everything into context. Load the index, load working memory, read deeper on demand.
2. **Signal over noise** — Don't pad entries for completeness. If nothing changed, say so.
3. **Three speeds** — Instant (slots), fast (files), slow (archive). Match retrieval to need.
4. **Operations, not facts** — Cognitive subroutines tell the model *how* to think, not *what* to think.
5. **Cooperative, not adversarial** — Work with Anthropic's native memory system, not against it.
6. **Local first** — Everything runs on your machine. No external services, no cloud dependencies.

## Requirements

- Claude Pro or Team plan (for Claude Code / Claude Desktop with MCP)
- Python 3.10+
- `mcp-memory-service` package
- macOS, Linux, or Windows with MCP support
- For local AI engine: `mlx` + `mlx-lm` (Apple Silicon) or `llama-cpp-python` (cross-platform)

## License

MIT — use it however you want.
