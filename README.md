# Hippoclaudus

*A persistent memory architecture for Claude — with local AI-powered memory management.*

Named after the hippocampus — the brain's memory formation center. A three-tier system that gives Claude persistent, structured recall across sessions, plus a local LLM engine that consolidates, tags, deduplicates, and predicts memory needs — all running on your machine.

## The Problem

Every Claude session starts cold. You re-explain context, re-establish preferences, re-describe your project. The built-in 30 memory slots help, but they're shallow. For ongoing collaborations — building a product, managing a business, any sustained creative or technical work — you need more.

And as memory accumulates, it rots without maintenance — duplicates pile up, tags stay sparse, stale entries crowd out signal. Manual pruning doesn't scale.

## The Solution

A layered memory architecture using Claude's existing infrastructure, plus a local AI engine for automated memory management:

| Tier | What | Where | Speed |
|------|-------|-------|-------|
| **1. Short-term** | Recent context, preferences, active threads | Anthropic's 30 memory slots | Instant (auto-loaded) |
| **2. Foundational** | Identity, relationships, protocols, reference docs | Markdown files + MCP sqlite-vec database | Fast (read on demand) |
| **3. Deep recall** | Full conversation history, searchable | Exported JSON archive + keyword index | Slower (search then extract) |

The key insight: a `CLAUDE.md` file in your project root auto-loads into every Claude Code session. Put your memory bootstrap protocol there, and Claude knows how to use the entire system without being told.

## Local AI Engine

Hippoclaudus includes a Python package that runs a local LLM on your machine to automate memory maintenance. No API calls. No tokens spent. No data leaves your computer.

| Module | What It Does |
|--------|-------------|
| **Consolidator** | Reads session logs, extracts structured State Deltas (what changed, entities, open threads, emotional signals), stores them in memory.db |
| **Compactor** | Finds duplicate/superseded memories via token overlap, uses LLM to judge and merge or soft-delete |
| **Tagger** | Extracts entities (people, projects, tools, topics) from memories and enriches their tags |
| **Predictor** | Generates a PRELOAD.md briefing for the next session — active context, unresolved threads, suggested first moves |
| **Comm Profiler** | Analyzes interaction patterns for a specific person — tone, decision style, key phrases, relationship dynamics |
| **Scorer** | Weighted decay formula: `(0.6 * semantic_similarity) + (0.3 * recency_decay) + (0.1 * access_frequency)` |

**Cross-platform inference:**
- **Apple Silicon (macOS):** MLX — native Metal acceleration, fastest path on M-series chips
- **Windows/Linux (NVIDIA):** llama-cpp-python with CUDA — GPU-accelerated GGUF inference
- **CPU fallback:** llama-cpp-python runs on any machine, GPU optional

Backend is auto-detected. Install the right package for your platform and Hippoclaudus handles the rest.

## What's Included

```
hippoclaudus/
├── README.md                          # You're reading it
├── WRITEUP.md                         # Full explanation + detailed setup guide
├── CHANGELOG.md                       # Version history
├── CONTRIBUTING.md                    # How to contribute (design constraints)
├── V2_RELEASE_NOTES.md                # Detailed v2 changes
├── install.sh                         # Automated installer (macOS/Linux)
├── doctor.py                          # Diagnostic tool — verify your setup
├── hippoclaudus/                      # Local AI engine (Python package)
│   ├── __init__.py
│   ├── llm.py                         # Multi-backend inference (MLX + llama.cpp)
│   ├── db_bridge.py                   # Direct SQLite bridge to memory.db
│   ├── consolidator.py                # Session → State Delta compression
│   ├── compactor.py                   # Duplicate detection and merging
│   ├── tagger.py                      # LLM-powered entity extraction
│   ├── predictor.py                   # Next-session briefing generator
│   ├── scoring.py                     # Weighted decay relevance scoring
│   └── comm_profiler.py               # Relationship pattern analysis
├── templates/
│   ├── CLAUDE.md                      # Drop into your project root (auto-loads in Claude Code)
│   ├── Memory_Bootstrap.md            # Upload to Claude Desktop project knowledge bases
│   ├── Total_Update_Protocol.md       # 11-layer memory hygiene protocol
│   ├── Infrastructure_Notes.md        # Environment and tooling tracker
│   ├── INDEX.md                       # Master index template for long-term memory
│   ├── Session_Summary_Log.md         # Working memory: session tracking
│   ├── Open_Questions_Blockers.md     # Working memory: unresolved items
│   ├── Decision_Log.md               # Working memory: decision history
│   ├── keywords.yaml                  # Customizable keyword config for scanner
│   ├── scan_conversations.py          # Tier 3: index your conversation export
│   └── extract_conversations.py       # Tier 3: pull specific conversations on demand
```

## Quick Start

### Option A: Automated Install (macOS/Linux)

```bash
git clone https://github.com/rhetoricjames/hippoclaudus.git
cd hippoclaudus
bash install.sh
```

The installer creates the directory structure, sets up the Python environment, installs dependencies, copies templates, and tells you exactly what to paste into your Claude Desktop config.

Verify the installation:

```bash
python3 doctor.py
```

### Option B: Manual Install

See the step-by-step instructions in [WRITEUP.md](WRITEUP.md), which covers macOS, Linux, and Windows.

### Installing the Local AI Engine

The local AI engine requires a small LLM running on your machine. Install the backend for your platform:

**Apple Silicon (macOS):**
```bash
pip install mlx mlx-lm
```

**Windows/Linux (NVIDIA GPU):**
```bash
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
```

**Windows (PowerShell, NVIDIA GPU):**
```powershell
$env:CMAKE_ARGS="-DGGML_CUDA=on"; pip install llama-cpp-python
```

**Any platform (CPU only):**
```bash
pip install llama-cpp-python
```

Then install the Hippoclaudus package:
```bash
cd hippoclaudus
pip install -e .
```

MLX users point to a HuggingFace model name (e.g., `mlx-community/Phi-3-mini-4k-instruct-4bit`). llama.cpp users point to a GGUF file path.

### After Install

1. Edit `~/Claude/CLAUDE.md` to add your personal context (identity, key people, projects)
2. Customize `~/Claude/mcp-memory/conversations/keywords.yaml` with your own terms
3. (Optional) Export your conversation history from claude.ai and run `scan_conversations.py`

## How It Works in Practice

**Session start:** Claude reads `CLAUDE.md`, which tells it the memory system exists and where everything lives. It reads the INDEX to know what's available, checks working memory for recent context and open items.

**During a session:** Claude reads deeper files only when relevant — relationship context when discussing people, infrastructure notes when debugging tools, identity documents when the conversation warrants it. Key insights are stored to the MCP database for semantic search.

**Session end ("Total Update"):** You say "Total Update" and Claude executes a structured 11-layer refresh — updating memory slots, storing session insights to the semantic database, revising long-term files if substance changed, appending to the session log, pruning stale entries.

**Between sessions (local AI):** Run the consolidator to compress your session log into a State Delta. Run the compactor to deduplicate. Run the predictor to generate a PRELOAD.md briefing so your next session starts warm.

**Deep recall:** When you reference something from months ago, Claude searches the conversation index, locates the relevant conversation, and extracts it. Ad-hoc search is also available: `python3 scan_conversations.py --search "your terms"`.

## Design Principles

1. **Selective loading** — Don't dump everything into context at startup. Load the index, load working memory, read deeper on demand.
2. **Signal over noise** — The Total Update protocol explicitly says: don't pad entries for completeness. If nothing changed, say so.
3. **Three speeds** — Instant (memory slots), fast (file reads), slow (archive search). Match the retrieval method to the need.
4. **Memory hygiene** — Without pruning, memory rots. The Total Update protocol includes explicit pruning as a required step. The compactor automates it.
5. **Human in the loop** — The conversation archive search involves asking the user to run extraction scripts. This is intentional — it keeps the human aware of what's being recalled.
6. **Local first** — Everything runs on your machine. No external services, no cloud dependencies, no accounts to create. The local LLM runs entirely on-device.

## Requirements

- Claude Pro or Team plan (for Claude Code / Claude Desktop with MCP)
- Python 3.10+ (for the MCP memory server and local AI engine)
- `mcp-memory-service` package
- macOS, Linux, or Windows with MCP support
- For local AI engine: `mlx` + `mlx-lm` (Apple Silicon) or `llama-cpp-python` (cross-platform)

## License

MIT — use it however you want.
