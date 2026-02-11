# Hippoclaudus: Building Persistent Memory for Claude

## Why This Exists

If you use Claude for anything sustained — building a product, running a business, a long-term creative project — you've hit the wall. Every session starts fresh. You re-explain who you are, what you're working on, what was decided last time. The 30 built-in memory slots help with basics, but they're shallow. They can't hold the texture of a months-long collaboration.

This is a system that solves that. It uses Claude's existing tools — MCP servers, file access, CLAUDE.md auto-loading — to give Claude a structured, three-tier memory that persists across sessions and scales from "what did we decide yesterday" to "find that conversation from three months ago where we discussed the database architecture."

No custom code beyond two Python scripts. No external services. Everything runs locally on your machine.

---

## The Architecture

### Tier 1: Short-Term Memory (Anthropic's 30 Slots)

This is what Claude already gives you. Thirty memory items that persist across sessions within a project. Good for:
- Your name and communication preferences
- Current project status
- Active decisions and recent context

**Limitation:** Shallow. 30 items can't hold the depth of a real working relationship. They also have no structure — it's a flat list.

**Role in the system:** Fast recall of the most recent and most frequently needed context. Think of it as working memory — what you'd keep in your head during a conversation.

### Tier 2: Foundational Memory (Markdown Files + MCP Database)

This is where Hippoclaudus adds real value. A directory of markdown files on your local machine, accessible to Claude through MCP file access or Claude Code's native file tools.

**Structure:**
```
mcp-memory/
├── long-term/          # Things that change slowly
│   ├── INDEX.md        # Master catalog — Claude reads this first
│   ├── Total_Update_Protocol.md  # Legacy — see local AI engine
│   ├── Infrastructure_Notes.md
│   ├── Relationship_Alice.md
│   ├── Relationship_Bob.md
│   └── Project_Alpha_Reference.md
├── working/            # Things that accumulate between sessions
│   ├── Session_Summary_Log.md
│   ├── Open_Questions_Blockers.md
│   └── Decision_Log.md
└── data/
    └── memory.db       # MCP sqlite-vec database (semantic search)
```

**Long-term files** hold things that evolve slowly: who the key people are, what the project is about, infrastructure details, reference material. The local AI engine's consolidator and compactor handle updates automatically after sessions.

**Working memory files** accumulate session-to-session: what happened, what's unresolved, what was decided. They reset periodically when you export your conversation history (creating a fresh baseline).

**The MCP database** adds semantic search — Claude can store and retrieve memories by meaning, not just by file path. This is optional but powerful for "find anything I've stored about X" queries.

**The key design choice:** Selective loading. Claude does NOT read everything at session start. It reads the INDEX (so it knows what's available), reads working memory (so it knows what happened recently), and reads deeper files only when the conversation needs them. This keeps context windows clean and avoids wasting tokens on irrelevant background.

### Tier 3: Deep Recall (Conversation Archive)

Your full conversation history with Claude, exported from claude.ai, indexed, and searchable.

**Structure:**
```
mcp-memory/conversations/
├── conversations.json          # Raw export from Anthropic (~100-500MB)
├── conversation_index.json     # Structured index with keyword scoring
├── conversation_index.md       # Human-readable version
├── scan_conversations.py       # Builds the index
├── extract_conversations.py    # Pulls specific conversations on demand
└── extracted/                  # Individual conversations (created on demand)
```

**How it works:** You export your conversation history from claude.ai, run the scanner to build a keyword-scored index, then Claude can search that index when it needs to recall something from months ago. When it finds what it's looking for, you run the extractor to pull that specific conversation into a readable file.

This is intentionally slow and human-in-the-loop. You don't want Claude automatically pulling 500MB of history into context. You want it to identify what it needs, then surgically extract it.

---

## Detailed Setup Guide

### Step 1: Create the Directory Structure

Pick a location on your machine. The examples use `~/Claude/` but put it wherever makes sense for you.

```bash
mkdir -p ~/Claude/mcp-memory/long-term
mkdir -p ~/Claude/mcp-memory/working
mkdir -p ~/Claude/mcp-memory/data
mkdir -p ~/Claude/mcp-memory/conversations
```

### Step 2: Install the MCP Memory Server

This gives Claude a semantic search database — it can store memories with embeddings and retrieve them by meaning.

**macOS / Linux:**
```bash
cd ~/Claude/mcp-memory
python3 -m venv venv
source venv/bin/activate
pip install mcp-memory-service
```

**Windows (PowerShell):**
```powershell
cd ~\Claude\mcp-memory
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install mcp-memory-service
```

**Windows (Command Prompt):**
```cmd
cd %USERPROFILE%\Claude\mcp-memory
python -m venv venv
venv\Scripts\activate.bat
pip install mcp-memory-service
```

Verify it installed:
```bash
python -m mcp_memory_service.server --help
```

You should see usage info. If you get an ONNX warning, that's fine — it's an optional dependency.

### Step 3: Configure Claude Desktop

You need to tell Claude Desktop where the MCP memory server lives. Edit your config file:

The config file location depends on your platform:

| Platform | Config Path |
|----------|-------------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/claude/claude_desktop_config.json` |

Add the memory server configuration. Note the platform-specific differences in paths:

**macOS / Linux:**
```json
{
  "mcpServers": {
    "memory": {
      "command": "/FULL/PATH/TO/Claude/mcp-memory/venv/bin/python",
      "args": ["-m", "mcp_memory_service.server"],
      "env": {
        "MCP_MEMORY_STORAGE_BACKEND": "sqlite_vec",
        "MCP_MEMORY_SQLITE_PATH": "/FULL/PATH/TO/Claude/mcp-memory/data/memory.db"
      }
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "memory": {
      "command": "C:\\Users\\YOURNAME\\Claude\\mcp-memory\\venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_memory_service.server"],
      "env": {
        "MCP_MEMORY_STORAGE_BACKEND": "sqlite_vec",
        "MCP_MEMORY_SQLITE_PATH": "C:\\Users\\YOURNAME\\Claude\\mcp-memory\\data\\memory.db"
      }
    }
  }
}
```

**Important:** Use full absolute paths, not `~` or `$HOME` or environment variables. Replace the path placeholders with your actual paths.

**Common gotcha:** On macOS/Linux, the venv Python is at `venv/bin/python`. On Windows, it's `venv\Scripts\python.exe`. Get this wrong and the server won't start.

Restart Claude Desktop. Check Settings > Developer to verify the memory server shows as connected (green status, not "failed").

### Step 4: Copy the Template Files

From the Hippoclaudus templates directory:

```bash
# Long-term memory templates
cp templates/INDEX.md ~/Claude/mcp-memory/long-term/
cp templates/Total_Update_Protocol.md ~/Claude/mcp-memory/long-term/   # Legacy reference

# Working memory templates
cp templates/Session_Summary_Log.md ~/Claude/mcp-memory/working/
cp templates/Open_Questions_Blockers.md ~/Claude/mcp-memory/working/
cp templates/Decision_Log.md ~/Claude/mcp-memory/working/

# Conversation archive scripts
cp templates/scan_conversations.py ~/Claude/mcp-memory/conversations/
cp templates/extract_conversations.py ~/Claude/mcp-memory/conversations/
```

### Step 5: Set Up CLAUDE.md (The Bootstrap)

This is the most important step. `CLAUDE.md` is a special file that Claude Code automatically loads into its system prompt when you run it from that directory.

```bash
cp templates/CLAUDE.md ~/Claude/
```

Now edit `~/Claude/CLAUDE.md` to replace the placeholder paths with your actual paths. This file tells Claude:
- The memory system exists
- Where all the files live
- What to read at session start
- What to read on demand
- How the local AI engine handles memory maintenance

Every Claude Code session that starts from `~/Claude/` will automatically know about the entire memory system.

**For Claude Desktop (chat, not Code):** Upload `templates/Memory_Bootstrap.md` to your project's knowledge base. This serves the same purpose — telling Claude about the memory system — but through the project knowledge base instead of CLAUDE.md.

### Step 6: Export and Index Your Conversation History

This step is optional but unlocks Tier 3 (deep recall).

**Export your conversations:**
1. Go to claude.ai
2. Click your profile icon (bottom-left)
3. Go to Settings
4. Scroll to "Export Data" (under the Account section)
5. Click "Export"
6. You'll receive an email with a download link
7. Download and unzip the export
8. Move `conversations.json` to `~/Claude/mcp-memory/conversations/`

**Customize the scanner keywords:**

Edit `~/Claude/mcp-memory/conversations/scan_conversations.py` and replace the `HIGH_VALUE_KEYWORDS` list with terms relevant to your work — project names, people, technical terms, anything you'd want to find later.

**Build the index:**
```bash
cd ~/Claude/mcp-memory/conversations
python3 scan_conversations.py
```

This produces:
- `conversation_index.json` — Structured data Claude can search programmatically
- `conversation_index.md` — Human-readable index you can browse yourself

**Extract specific conversations:**

After reviewing the index (or having Claude search it), pull specific conversations:

```bash
python3 extract_conversations.py 12 45 78        # By index number
python3 extract_conversations.py --range 10-20    # A range
```

Extracted conversations appear in `conversations/extracted/` as readable markdown files.

### Step 7: Build Your Long-Term Memory

Start adding files to `mcp-memory/long-term/` as your collaboration deepens:

- **Relationship files** for key people you work with (communication style, context, role)
- **Project reference docs** for ongoing projects (architecture decisions, status, key details)
- **Infrastructure notes** for your tools and setup
- **Any document with lasting value** that you don't want to re-explain

Update `INDEX.md` whenever you add a new file so Claude can find it.

---

## Memory Maintenance (Local AI Engine)

Memory hygiene is critical — without it, stale entries accumulate, important things get lost, and the signal-to-noise ratio degrades. In v1, this was a manual process. In v2, the local AI engine handles it automatically.

After a session, run the engine's modules:

```bash
python -m hippoclaudus.consolidator   # Compress session into a State Delta
python -m hippoclaudus.compactor      # Find and merge duplicate memories
python -m hippoclaudus.tagger         # Enrich tags on sparse memories
python -m hippoclaudus.predictor      # Generate PRELOAD.md briefing for next session
```

The **consolidator** reads your latest session log and compresses it into a structured State Delta — a dense summary of what changed, who was mentioned, what's unresolved, and any emotional signals detected. This gets stored in memory.db with entity-derived tags.

The **compactor** computes token-overlap similarity between all memory pairs, sends high-similarity pairs to the local LLM for evaluation, and merges or soft-deletes duplicates and superseded entries.

The **tagger** runs memories through the LLM to extract people, projects, tools, and topics, enriching sparse tags so semantic search works better.

The **predictor** generates a PRELOAD.md briefing — active context, unresolved threads, key people state, suggested first moves — so your next session starts warm instead of cold.

Everything runs locally on your machine. No API calls. No tokens spent. No data leaves your computer.

---

## Design Principles

**Selective loading, not context dumping.** The biggest mistake would be loading everything at session start. That wastes tokens and pollutes context. Instead: load the index, load working memory, read deeper only when needed.

**Signal over noise.** If nothing changed, don't pad entries for completeness. The local AI engine follows this too — the consolidator only stores what actually changed. Memory should be high-signal.

**Three speeds for three needs.** Instant (memory slots) for what you need every session. Fast (file reads) for foundational context. Slow (archive search) for deep history. Match the retrieval method to the need.

**Memory hygiene is non-negotiable.** Without pruning, memory systems degrade. The compactor automates deduplication and the consolidator compresses sessions into dense State Deltas — pruning is built into the engine, not a manual chore.

**Human in the loop for deep recall.** The conversation archive search involves the user running extraction scripts. This is intentional — it keeps you aware of what's being recalled and prevents Claude from silently loading huge amounts of history.

---

## Tips From Experience

- **Don't over-index on the MCP database early.** The markdown files are more immediately useful. The semantic search database becomes valuable over time as you store more memories through it.

- **Keep your CLAUDE.md under 200 lines.** It gets loaded into every session — bloat here costs you context window everywhere.

- **The INDEX is everything.** Claude uses it to know what's available without reading every file. Keep it accurate.

- **Export your conversations every 4-6 weeks.** Re-run the scanner each time. This keeps your deep recall current.

- **Customize the scanner keywords aggressively.** The default keywords are generic — make them specific to YOUR work. The more specific, the better the signal.

- **Working memory resets are healthy.** When you export and re-index, reset the Session Summary Log, Decision Log, and Open Questions. This prevents accumulation of stale entries.

---

## What This Isn't

This isn't AGI memory. But with the local AI engine, it does automatically consolidate, deduplicate, tag, and predict — so it's more than just filing cabinets. The value comes from the structure and the automation that maintains it.

It also doesn't replace good prompting. You still need to tell Claude what you need. But instead of re-explaining your entire world every session, you tell it once, store it properly, and it picks up where you left off.

---

*Hippoclaudus was built out of necessity by someone who needed Claude to remember the texture of a long collaboration — not just the facts, but the decisions, the people, the context. If you're building something sustained with Claude, this might help you too.*
