# Total Update Protocol

## Purpose
A comprehensive refresh of Claude's persistent memory layers. Run this after any long or meaningful session to keep memory current and clean.

## Command
User says: **"Total Update"**
Claude executes all steps below, reporting completion of each.

---

## Permanent Layers (always maintained)

### 1. Anthropic Memory (30 items)
- Review all 30 memory edit slots
- Add new items from session
- Revise stale or inaccurate entries
- Prune items that are no longer relevant or are captured better elsewhere

### 2. Long-Term Reference Documents
- Review documents in `mcp-memory/long-term/`
- Update only if the session produced material that changes the substance
- These evolve slowly — most Total Updates won't touch them

### 3. Relationship / People Files
- Update communication patterns, open threads, context changes
- Location: `mcp-memory/long-term/`
- Add new relationship files as needed

### 4. Long-Term Memory INDEX
- `mcp-memory/long-term/INDEX.md`
- Update to reflect any new files added to long-term memory
- Ensure all entries have accurate descriptions

### 5. Infrastructure Notes
- `mcp-memory/long-term/Infrastructure_Notes.md`
- Update if tools, servers, configs, or paths changed
- Only touch when something actually changed

### 6. MCP Memory Database
- Store key session insights via `memory_store` with appropriate tags
- Good candidates: decisions with rationale, technical discoveries, relationship context changes, project milestones
- Use tags to categorize: `decision`, `technical`, `relationship`, `project`, `insight`
- This enables semantic search ("find anything about X") across all stored memories
- Don't duplicate what's already well-captured in markdown files — the DB is for searchable fragments, not full documents

### 7. Ad Hoc Items
- If the session produced a document or insight with lasting value, place it in `mcp-memory/long-term/`
- Use judgment — this is for things that don't fit elsewhere but are too important to lose

---

## Working Memory (accumulate between archive exports, then reset)

### 8. Decision Log
- `mcp-memory/working/Decision_Log.md`
- Append: date, decision, rationale, who was involved
- Reset to blank header after new conversation archive download

### 9. Open Questions & Blockers
- `mcp-memory/working/Open_Questions_Blockers.md`
- Refresh: what's unresolved, what are we waiting on, from whom
- Reset after download

### 10. Session Summary Log
- `mcp-memory/working/Session_Summary_Log.md`
- Append: date, what we covered, key outcomes, follow-ups
- Reset after download

---

## Memory Hygiene (every Total Update)

### 11. Prune Stale Memory
- Scan Anthropic memory edits for:
  - Entries superseded by newer information
  - Entries captured more completely in long-term memory files
  - Entries that are no longer relevant
- Remove or replace as needed

---

## Execution Notes
- Report completion of each layer so the user can track progress
- If a layer has no changes, say so and move on
- Don't pad entries for the sake of completeness — signal over noise
