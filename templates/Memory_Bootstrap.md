# Claude Memory Bootstrap
*Upload this file to every Claude Project's knowledge base (on claude.ai).*

---

## Session Initialization

At the start of each session, before engaging with the user's first request, read the following files from the MCP filesystem to establish context:

1. **INDEX:** `mcp-memory/long-term/INDEX.md`
   - Master index of all long-term memory files
   - Tells you what's available and where

2. **Working Memory — Open Questions:** `mcp-memory/working/Open_Questions_Blockers.md`
   - Current unresolved items and blockers
   - Helps you pick up where we left off

3. **Working Memory — Session Summary Log:** `mcp-memory/working/Session_Summary_Log.md`
   - Recent session summaries
   - Provides continuity on what was just done

## When to Read Deeper

Do NOT read all long-term memory files at session start — that's wasteful. Instead:

- Read **relationship files** when the session involves specific people
- Read **project docs** when working on a specific project
- Read **Infrastructure Notes** when troubleshooting tools, MCP servers, or configs
- Read **Decision Log** when referencing a past decision or verifying something was settled

## Important

- Memory maintenance is handled by the local AI engine (consolidator, compactor, tagger, predictor) — see `Total_Update_Protocol.md` for the legacy-to-new mapping
- Conversation archive stays in cold storage — use the index to locate, extract on demand only

---

*This file should be uploaded to every Claude Project's knowledge base.*
