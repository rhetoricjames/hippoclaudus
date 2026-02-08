# Claude Code — Core Instructions

## About This File
This file is automatically loaded into every Claude Code session that runs from this directory. It tells Claude about the persistent memory system and how to use it.

Edit the paths below to match your setup.

## Memory Architecture

You have a three-tier persistent memory system.

### Tier 1: Short-Term (Anthropic's 30 memory slots)
- Session-to-session recall of recent context
- Managed via `memory_user_edits`
- Pruned during Total Updates

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

## Total Update Command

When the user says **"Total Update"**, execute the protocol defined in:
`mcp-memory/long-term/Total_Update_Protocol.md`

Report completion of each layer. If a layer has no changes, say so and move on.

## Conversation Archive Search

When you need to recall a specific past conversation:
1. Read `mcp-memory/conversations/conversation_index.md` to locate it
2. Ask the user to run `extract_conversations.py` with the relevant index number
3. Or search `conversation_index.json` programmatically for keyword matches
