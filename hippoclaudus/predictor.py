"""Predictor — generates PRELOAD.md for next session startup.

Analyzes recent session logs, open questions, relationship staleness,
and active threads to produce a context-dense briefing document that
Claude can read at session start to hit the ground running.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import click

from hippoclaudus.db_bridge import MemoryDB
from hippoclaudus.llm import run_prompt, extract_json


PREDICT_PROMPT = """You are a session preparation system. Given the following context about an ongoing collaboration, generate a dense briefing for the next session.

RECENT SESSION LOG:
{session_text}

OPEN QUESTIONS:
{open_questions}

RECENT STATE DELTAS:
{state_deltas}

Generate a briefing document in this exact format:

# PRELOAD — Session Briefing
Generated: {timestamp}

## Active Context
[2-3 sentences: what we're in the middle of, what was happening when last session ended]

## Unresolved Threads
[Bulleted list of open items requiring attention]

## Key People State
[For each person mentioned recently: last known status, any pending interactions]

## Suggested First Moves
[2-3 concrete actions to start the next session productively]

## Emotional/Relational Notes
[Any interpersonal dynamics, frustrations, or sensitivities to be aware of]

Return the document as plain text (NOT JSON). Use markdown formatting."""


def run_predict(model_name: str, db_path: str, session_log: Path, open_questions: Path, output: Path):
    """Generate PRELOAD.md for next session."""
    click.echo("=== Hippoclaudus Predict ===")

    # 1. Read session log
    session_text = ""
    if session_log.exists():
        text = session_log.read_text()
        # Get last 2 sessions for context
        sections = text.split("\n## ")
        recent = sections[-2:] if len(sections) > 2 else sections[1:]
        session_text = "\n## ".join(recent)
    else:
        session_text = "(no session log found)"

    # 2. Read open questions
    oq_text = ""
    if open_questions.exists():
        oq_text = open_questions.read_text()
    else:
        oq_text = "(no open questions file found)"

    # 3. Read recent state deltas from DB
    db = MemoryDB(db_path)
    memories = db.get_all_memories(limit=100)
    state_deltas = [m for m in memories if m.get("memory_type") == "state_delta"]
    delta_text = ""
    for sd in state_deltas[:5]:  # Last 5 state deltas
        delta_text += f"- {sd['content'][:200]}\n"
    if not delta_text:
        delta_text = "(no state deltas yet)"
    db.close()

    # 4. Generate briefing
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    click.echo(f"Generating briefing from {len(state_deltas)} state deltas...")

    prompt = PREDICT_PROMPT.format(
        session_text=session_text[:3000],  # Cap to avoid context overflow
        open_questions=oq_text[:2000],
        state_deltas=delta_text,
        timestamp=now,
    )
    response = run_prompt(model_name, prompt, max_tokens=1024, temp=0.3)

    # 5. Write PRELOAD.md
    output.write_text(response)
    click.echo(f"\nPRELOAD.md written to: {output}")
    click.echo(f"Length: {len(response)} chars")
    click.echo("\n--- Preview ---")
    click.echo(response[:500])
    if len(response) > 500:
        click.echo("...")
