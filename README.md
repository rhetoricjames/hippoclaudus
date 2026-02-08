# Hippoclaudus

*A persistent memory architecture for Claude.*

Named after the hippocampus — the brain's memory formation center. A three-tier system that gives Claude persistent, structured recall across sessions, using tools that already exist.

## The Problem

Every Claude session starts cold. You re-explain context, re-establish preferences, re-describe your project. The built-in 30 memory slots help, but they're shallow. For ongoing collaborations — building a product, managing a business, any sustained creative or technical work — you need more.

## The Solution

A layered memory architecture using Claude's existing infrastructure:

| Tier | What | Where | Speed |
|------|-------|-------|-------|
| **1. Short-term** | Recent context, preferences, active threads | Anthropic's 30 memory slots | Instant (auto-loaded) |
| **2. Foundational** | Identity, relationships, protocols, reference docs | Markdown files + MCP sqlite-vec database | Fast (read on demand) |
| **3. Deep recall** | Full conversation history, searchable | Exported JSON archive + keyword index | Slower (search then extract) |

The key insight: a `CLAUDE.md` file in your project root auto-loads into every Claude Code session. Put your memory bootstrap protocol there, and Claude knows how to use the entire system without being told.

## What's Included

```
hippoclaudus/
├── README.md                          # You're reading it
├── WRITEUP.md                         # Full explanation + detailed setup guide
├── templates/
│   ├── CLAUDE.md                      # Drop into your project root (auto-loads in Claude Code)
│   ├── Memory_Bootstrap.md            # Upload to Claude Desktop project knowledge bases
│   ├── Total_Update_Protocol.md       # 10-layer memory hygiene protocol
│   ├── INDEX.md                       # Master index template for long-term memory
│   ├── Session_Summary_Log.md         # Working memory: session tracking
│   ├── Open_Questions_Blockers.md     # Working memory: unresolved items
│   ├── Decision_Log.md               # Working memory: decision history
│   ├── scan_conversations.py          # Tier 3: index your conversation export
│   └── extract_conversations.py       # Tier 3: pull specific conversations on demand
```

## Quick Start

### 1. Create the directory structure

```bash
mkdir -p ~/Claude/mcp-memory/{long-term,working,data}
```

### 2. Install the MCP memory server

```bash
cd ~/Claude/mcp-memory
python -m venv venv
source venv/bin/activate
pip install mcp-memory-service
```

### 3. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the equivalent on your platform:

```json
{
  "mcpServers": {
    "memory": {
      "command": "/full/path/to/mcp-memory/venv/bin/python",
      "args": ["-m", "mcp_memory_service.server"],
      "env": {
        "MCP_MEMORY_STORAGE_BACKEND": "sqlite_vec",
        "MCP_MEMORY_SQLITE_PATH": "/full/path/to/mcp-memory/data/memory.db"
      }
    }
  }
}
```

### 4. Copy the templates

Copy the templates into your directory structure:

```bash
cp templates/INDEX.md ~/Claude/mcp-memory/long-term/
cp templates/Total_Update_Protocol.md ~/Claude/mcp-memory/long-term/
cp templates/Session_Summary_Log.md ~/Claude/mcp-memory/working/
cp templates/Open_Questions_Blockers.md ~/Claude/mcp-memory/working/
cp templates/Decision_Log.md ~/Claude/mcp-memory/working/
```

### 5. Drop CLAUDE.md into your project root

```bash
cp templates/CLAUDE.md ~/Claude/
```

Edit it to reflect your actual paths and context.

### 6. (Optional) Export and index your conversation history

This unlocks Tier 3 — deep recall across your full Claude history.

```bash
mkdir ~/Claude/mcp-memory/conversations/
cp templates/scan_conversations.py ~/Claude/mcp-memory/conversations/
cp templates/extract_conversations.py ~/Claude/mcp-memory/conversations/
```

Export your data from claude.ai:
1. Go to claude.ai > Profile (bottom-left) > Settings > Account
2. Click "Export Data"
3. Wait for the email with the download link
4. Download and unzip the export
5. Move `conversations.json` into `~/Claude/mcp-memory/conversations/`

Customize keywords and build the index:
```bash
# Edit scan_conversations.py — replace HIGH_VALUE_KEYWORDS with YOUR terms
cd ~/Claude/mcp-memory/conversations/
python3 scan_conversations.py
```

Extract specific conversations after reviewing the index:
```bash
python3 extract_conversations.py 12 45 78        # By index number
python3 extract_conversations.py --range 10-20    # A range
```

See WRITEUP.md for the full detailed setup guide.

## How It Works in Practice

**Session start:** Claude reads `CLAUDE.md`, which tells it the memory system exists and where everything lives. It reads the INDEX to know what's available, checks working memory for recent context and open items.

**During a session:** Claude reads deeper files only when relevant — relationship context when discussing people, infrastructure notes when debugging tools, identity documents when the conversation warrants it.

**Session end ("Total Update"):** You say "Total Update" and Claude executes a structured 10-layer refresh — updating memory slots, revising long-term files if substance changed, appending to the session log, pruning stale entries.

**Deep recall:** When you reference something from months ago, Claude searches the conversation index, locates the relevant conversation, and extracts it.

## Design Principles

1. **Selective loading** — Don't dump everything into context at startup. Load the index, load working memory, read deeper on demand.
2. **Signal over noise** — The Total Update protocol explicitly says: don't pad entries for completeness. If nothing changed, say so.
3. **Three speeds** — Instant (memory slots), fast (file reads), slow (archive search). Match the retrieval method to the need.
4. **Memory hygiene** — Without pruning, memory rots. The Total Update protocol includes explicit pruning as a required step.
5. **Human in the loop** — The conversation archive search involves asking the user to run extraction scripts. This is intentional — it keeps the human aware of what's being recalled.

## Requirements

- Claude Pro or Team plan (for Claude Code / Claude Desktop with MCP)
- Python 3.10+ (for the MCP memory server)
- `mcp-memory-service` package
- macOS, Linux, or Windows with MCP support

## License

MIT — use it however you want.
