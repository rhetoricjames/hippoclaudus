# Total Update Protocol (Legacy)

> **This protocol has been superseded by the Hippoclaudus local AI engine.**
> The consolidator, compactor, tagger, and predictor modules now handle memory maintenance automatically. This file is retained for reference only.

---

## What Replaced It

The manual 11-layer checklist has been replaced by automated modules that run locally on your machine:

| Old Manual Step | New Automated Module |
|----------------|---------------------|
| Review & prune Anthropic memory slots | **Compactor** — deduplicates and merges overlapping memories |
| Update long-term docs | **Consolidator** — compresses sessions into structured State Deltas |
| Update relationship files | **Comm Profiler** — analyzes relationship patterns automatically |
| Update INDEX | *(Still manual — update when adding new files)* |
| Update Infrastructure Notes | *(Still manual — update when configs change)* |
| Store to MCP database | **Consolidator** — stores State Deltas with entity-derived tags |
| Decision Log, Open Questions, Session Summary | **Consolidator** — extracts decisions, open threads, and session outcomes |
| Prune stale memory | **Compactor** — Jaccard similarity + LLM evaluation to merge/soft-delete |
| Tag enrichment | **Tagger** — LLM-powered entity extraction across all memories |
| Next-session briefing | **Predictor** — generates PRELOAD.md with active context and suggested first moves |

## Running the Local AI Engine

After a session, run the modules:

```bash
# Compress the latest session into a State Delta
python -m hippoclaudus.consolidator

# Find and merge duplicate memories
python -m hippoclaudus.compactor

# Enrich tags on sparse memories
python -m hippoclaudus.tagger

# Generate a briefing for the next session
python -m hippoclaudus.predictor
```

## What's Still Manual

- **INDEX.md** — Update when you add new long-term files
- **Infrastructure Notes** — Update when your tools or configs change
- **Conversation archive** — Export from claude.ai and run the scanner periodically
