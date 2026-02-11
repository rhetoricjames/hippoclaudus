"""Consolidator — post-session memory compression and State Delta generation.

This is the core Phase 2A feature: reads session logs, runs them through
the local LLM, and stores structured State Deltas in memory.db.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import click

from hippoclaudus.db_bridge import MemoryDB, Memory
from hippoclaudus.llm import consolidate_session


def run_consolidation(model_name: str, db_path: str, session_log: Path):
    """Full consolidation pipeline: parse session -> LLM -> store."""
    click.echo("=== Hippoclaudus Consolidation ===")

    # 1. Parse latest session
    click.echo("Reading latest session from log...")
    session_text = MemoryDB.parse_latest_session(str(session_log))
    if not session_text:
        click.echo("No session found in log. Nothing to consolidate.")
        return

    click.echo(f"Found session ({len(session_text)} chars)")

    # 2. Run through LLM
    click.echo(f"Running consolidation via {model_name}...")
    result = consolidate_session(model_name, session_text)

    if not result:
        click.echo("LLM failed to produce valid JSON. Raw output may need review.")
        return

    # 3. Format State Delta
    state_delta = result.get("state_delta", "")
    entities = result.get("entities", {})
    open_threads = result.get("open_threads", [])

    click.echo(f"\nState Delta:\n  {state_delta}")
    click.echo(f"\nEntities: {json.dumps(entities, indent=2)}")
    click.echo(f"\nOpen Threads: {open_threads}")

    # 4. Build tags from entities
    all_tags = []
    for category in ["people", "projects", "tools"]:
        all_tags.extend(entities.get(category, []))
    all_tags.append("state-delta")
    tags_str = ",".join(t.lower().replace(" ", "-") for t in all_tags if t)

    # 5. Store in memory.db
    click.echo("\nStoring State Delta in memory.db...")
    memory = Memory(
        content=f"[State Delta] {state_delta}",
        tags=tags_str,
        memory_type="state_delta",
        metadata={
            "entities": entities,
            "security_context": result.get("security_context", "none"),
            "emotional_signals": result.get("emotional_signals", "neutral"),
            "open_threads": open_threads,
            "source": "hippo-consolidate",
            "session_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
    )

    db = MemoryDB(db_path)
    row_id = db.store_memory(memory)
    db.close()

    click.echo(f"Stored as memory #{row_id} (hash: {memory.content_hash[:16]}...)")
    click.echo("Consolidation complete.")


def run_reflection(model_name: str, session_log: Path):
    """Generate and display a State Delta without storing it. Dry-run mode."""
    click.echo("=== Hippoclaudus Reflection (dry run) ===")

    session_text = MemoryDB.parse_latest_session(str(session_log))
    if not session_text:
        click.echo("No session found in log.")
        return

    click.echo(f"Reflecting on session ({len(session_text)} chars)...")
    result = consolidate_session(model_name, session_text)

    if not result:
        click.echo("LLM failed to produce valid JSON.")
        return

    click.echo(f"\nState Delta:\n  {result.get('state_delta', '(none)')}")
    click.echo(f"\nEntities: {json.dumps(result.get('entities', {}), indent=2)}")
    click.echo(f"\nSecurity: {result.get('security_context', 'none')}")
    click.echo(f"Emotional signals: {result.get('emotional_signals', 'neutral')}")
    click.echo(f"Open threads: {result.get('open_threads', [])}")
    click.echo("\n(Dry run — nothing stored)")
