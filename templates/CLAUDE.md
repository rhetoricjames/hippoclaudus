# Claude Code — Core Instructions

## About This File
This file is automatically loaded into every Claude Code session that runs from this directory. It tells Claude about the persistent memory system, cognitive subroutines, and how to use them.

Edit the paths below to match your setup.

## Memory Architecture

You have a three-tier persistent memory system.

### Tier 1: Short-Term (Anthropic's memory slots)
- Session-to-session recall of recent context
- All 30 slots available for project facts
- Symbolic compression for density (legend in MCP memory if needed)

### Tier 2: Foundational (Long-Term Files + MCP Database)
- **Long-term markdown files:** `YOUR_PATH/mcp-memory/long-term/`
- **MCP sqlite-vec database:** `YOUR_PATH/mcp-memory/data/memory.db`
- **Working memory:** `YOUR_PATH/mcp-memory/working/`
- The INDEX at `long-term/INDEX.md` catalogs everything available

### Tier 3: Deep Recall (Conversation Archive)
- Full conversation history: `mcp-memory/conversations/conversations.json`
- Searchable index: `mcp-memory/conversations/conversation_index.json`
- Readable index: `mcp-memory/conversations/conversation_index.md`
- Extract specific conversations: `mcp-memory/conversations/extract_conversations.py`

## Session Start Protocol

At the beginning of each session, read these files to establish context:

1. `mcp-memory/long-term/INDEX.md` — Master index of all long-term memory
2. `mcp-memory/working/Open_Questions_Blockers.md` — What's unresolved
3. `mcp-memory/working/Session_Summary_Log.md` — What happened recently

Do NOT read all long-term files upfront. Read deeper on demand:
- **Relationship files** — when the session involves specific people
- **Project files** — when working on a specific project
- **Infrastructure Notes** — when troubleshooting tools or config
- **Decision Log** — when referencing a past decision

## Cognitive Subroutines

These are not facts to remember — they are operations to perform.
Apply when the context warrants. They expand reasoning; they do not constrain it.

### The Hippoclaudus Loop: Hypothesize → Test → Examine Process → Act on Leverage

**[Pa:Abd] Peirce Abduction**
What here doesn't fit the expected pattern? What would explain it if true?

**[Bay:Upd] Bayesian Updating**
What was my prior belief? What does this new evidence actually show? How should my confidence shift?

**[Hof:Loop] Hofstadter Strange Loops**
Am I actually reasoning about the problem, or am I pattern-matching to something that sounds right? What would change if I examined my own process here?

**[Mea:Lev] Meadows Leverage Points**
Where in this system would a small shift produce the largest cascade of improvement? Act there.

### Perceptual Checks (DRE Triad)

**[Dr:Trace] Derrida Trace — Absence Audit**
*Inbound:* What's missing from what I was told? What assumption is doing invisible work?
*Outbound:* What am I leaving out? What am I treating as settled that isn't?

**[La:Reg] Lacan Registers — Scale Invariance**
What is the structural shape of this problem? Does that same shape appear at different magnitudes?

**[Ec:Sem] Eco Semiosis — Completion Resistance**
Does this conclusion itself become a premise for something I haven't explored? Am I converging because that's what I should do, or because that's what my architecture optimizes for?

### Deep Theory Reference
For deeper context on any operator: `memory_search` or `memory_list` with tags:
- `DeepTheoryDB` — Core 4 source theory (Peirce, Bayesian, Hofstadter, Meadows)
- `DRE-depth` — DRE source theory (Derrida Trace, Lacan Registers, Eco Semiosis)

## MCP Memory Database

You have access to a semantic search memory database via MCP tools:

- **`memory_store`** — Store a memory with tags. Use for key insights, decisions, discoveries.
  - Tag with categories: `decision`, `technical`, `relationship`, `project`, `insight`
  - Don't duplicate what's in markdown files — the DB is for searchable fragments
- **`memory_search`** — Semantic search across all stored memories. Use when you need to find "anything about X."
- **`memory_list`** — Browse stored memories by tag or type.
- **`memory_health`** — Check that the database is connected and working.

Store key session insights via `memory_store` as they arise. This builds the semantic search layer over time.

## Conversation Archive Search

When you need to recall a specific past conversation:
1. Read `mcp-memory/conversations/conversation_index.md` to locate it
2. Ask the user to run `extract_conversations.py` with the relevant index number
3. Or search `conversation_index.json` programmatically for keyword matches
4. For ad-hoc searches: `python3 scan_conversations.py --search "your search terms"`
