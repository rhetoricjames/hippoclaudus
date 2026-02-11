"""Communication profiler — analyze interaction patterns for a specific person.

Searches memories and session logs for references to a person,
then runs the local LLM to extract communication patterns, tone,
decision style, and relationship dynamics.
"""

import json
from pathlib import Path

import click

from hippoclaudus.db_bridge import MemoryDB
from hippoclaudus.llm import analyze_comm_profile


def run_comm_profile(model_name: str, db_path: str, person: str, long_term: Path):
    """Analyze communication patterns for a person."""
    click.echo(f"=== Communication Profile: {person} ===")

    # 1. Search memories for references to this person
    click.echo(f"Searching memories for '{person}'...")
    db = MemoryDB(db_path)
    all_memories = db.get_all_memories(limit=1000)
    relevant = [m for m in all_memories if person.lower() in m["content"].lower()]
    db.close()

    # 2. Search relationship files
    relationship_text = ""
    rel_file = long_term / f"Claude_Relationships_{person}.md"
    if rel_file.exists():
        relationship_text = rel_file.read_text()
        click.echo(f"Found relationship file: {rel_file.name}")
    else:
        # Try case-insensitive match
        for f in long_term.glob("Claude_Relationships_*.md"):
            if person.lower() in f.stem.lower():
                relationship_text = f.read_text()
                click.echo(f"Found relationship file: {f.name}")
                break

    # 3. Build excerpt collection
    excerpts = ""
    if relationship_text:
        excerpts += f"=== RELATIONSHIP FILE ===\n{relationship_text[:2000]}\n\n"

    if relevant:
        excerpts += f"=== MEMORIES ({len(relevant)} found) ===\n"
        for m in relevant[:10]:  # Cap at 10 most recent
            excerpts += f"- [{m.get('created_at_iso', 'unknown')}] {m['content'][:200]}\n"
    else:
        excerpts += "(no memories referencing this person)\n"

    if not relationship_text and not relevant:
        click.echo(f"No data found for '{person}'. Cannot generate profile.")
        return

    # 4. Run LLM analysis
    click.echo(f"Analyzing {len(relevant)} memories + relationship file...")
    result = analyze_comm_profile(model_name, person, excerpts)

    if not result:
        click.echo("LLM failed to produce valid analysis.")
        return

    # 5. Display profile
    click.echo(f"\n{'='*50}")
    click.echo(f"  COMMUNICATION PROFILE: {person}")
    click.echo(f"{'='*50}")
    click.echo(f"\n  Tone: {result.get('tone', 'unknown')}")
    click.echo(f"  Decision style: {result.get('decision_style', 'unknown')}")
    click.echo(f"  Response patterns: {result.get('response_patterns', 'unknown')}")

    priorities = result.get("priorities", [])
    if priorities:
        click.echo(f"\n  Priorities:")
        for p in priorities:
            click.echo(f"    - {p}")

    phrases = result.get("key_phrases", [])
    if phrases:
        click.echo(f"\n  Key phrases:")
        for p in phrases:
            click.echo(f"    - \"{p}\"")

    click.echo(f"\n  Working relationship:")
    click.echo(f"    {result.get('working_relationship', 'unknown')}")
    click.echo()
