# Long-Term Memory Index

## Purpose

This folder contains Claude's persistent memory — documents that encode relationship context, operational protocols, and reference material that should survive across sessions.

---

## Reference Documents

| File | Description |
|------|-------------|
| `Total_Update_Protocol.md` | Legacy reference — maps old manual protocol to new local AI engine modules |
| `Infrastructure_Notes.md` | Hardware, MCP config, tools, paths, known issues |

## Relationship Files

| File | Description |
|------|-------------|
| *(Add relationship files as you build them)* | |

## Project Documents

| File | Description |
|------|-------------|
| *(Add project-specific reference docs here)* | |

---

## Working Memory (in `../working/`)

These files accumulate between conversation archive exports, then reset.

| File | Description |
|------|-------------|
| `Decision_Log.md` | Decisions made, with date and rationale |
| `Open_Questions_Blockers.md` | Unresolved items, what we're waiting on |
| `Session_Summary_Log.md` | What each session covered, key outcomes, follow-ups |

---

## Conversation Archive (in `../conversations/`)

| File | Description |
|------|-------------|
| `conversations.json` | Raw Anthropic export |
| `conversation_index.json` | Structured index from scanner |
| `conversation_index.md` | Readable index for review |
| `scan_conversations.py` | Builds index from archive |
| `extract_conversations.py` | Extracts specific conversations on demand |

---

## How To Use This Library

**Session start:** Read this INDEX + working memory files.

**Deeper context needed:** Read relationship files, project docs, or Infrastructure Notes as relevant.

**Past conversation lookup:** Use `conversation_index.md` to locate, then run `extract_conversations.py` for specific indices.

**Memory maintenance:** Handled by the local AI engine — run the consolidator, compactor, tagger, and predictor after sessions.
