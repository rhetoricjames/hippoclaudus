"""Entity tagger — LLM-powered entity extraction and tag enrichment for memories.

Reads memories from memory.db, runs them through the local LLM to extract
entities (people, projects, tools, topics), and updates their tags.
"""

import json

import click

from hippoclaudus.db_bridge import MemoryDB
from hippoclaudus.llm import tag_memory


def run_tag_single(model_name: str, db_path: str, memory_id: int):
    """Tag a single memory by ID."""
    click.echo(f"=== Tagging Memory #{memory_id} ===")

    db = MemoryDB(db_path)
    memories = db.get_all_memories(limit=1000)
    target = None
    for m in memories:
        if m["id"] == memory_id:
            target = m
            break

    if not target:
        click.echo(f"Memory #{memory_id} not found.")
        db.close()
        return

    click.echo(f"Content: {target['content'][:120]}...")
    click.echo(f"Current tags: {target['tags'] or '(none)'}")

    # Run LLM tagging
    click.echo(f"\nExtracting entities via LLM...")
    result = tag_memory(model_name, target["content"])

    if not result:
        click.echo("LLM failed to produce valid JSON.")
        db.close()
        return

    # Display results
    click.echo(f"\nEntities found:")
    for category in ["people", "projects", "tools", "topics"]:
        items = result.get(category, [])
        if items:
            click.echo(f"  {category}: {', '.join(items)}")

    # Merge existing tags with new suggested tags
    existing = set(t.strip() for t in (target["tags"] or "").split(",") if t.strip())
    suggested = result.get("suggested_tags", [])
    if isinstance(suggested, str):
        suggested = [t.strip() for t in suggested.split(",") if t.strip()]
    new_tags = set(t.lower().replace(" ", "-") for t in suggested if t)
    merged = sorted(existing | new_tags)
    merged_str = ",".join(merged)

    click.echo(f"\nMerged tags: {merged_str}")

    # Update in DB
    db.update_tags(target["content_hash"], merged_str)
    db.close()
    click.echo("Tags updated.")


def run_tag_all(model_name: str, db_path: str):
    """Tag all memories that have sparse or no tags."""
    click.echo("=== Tagging All Memories ===")

    db = MemoryDB(db_path)
    memories = db.get_all_memories(limit=1000)

    if not memories:
        click.echo("No memories found.")
        db.close()
        return

    click.echo(f"Found {len(memories)} memories. Processing...\n")

    tagged_count = 0
    for m in memories:
        existing_tags = [t.strip() for t in (m["tags"] or "").split(",") if t.strip()]

        # Skip if already well-tagged (5+ tags)
        if len(existing_tags) >= 5:
            click.echo(f"  [{m['id']}] Already tagged ({len(existing_tags)} tags) — skipping")
            continue

        click.echo(f"  [{m['id']}] Tagging: {m['content'][:80]}...")

        result = tag_memory(model_name, m["content"])
        if not result:
            click.echo(f"         LLM failed — skipping")
            continue

        # Merge tags
        existing = set(t.strip() for t in existing_tags if t)
        suggested = result.get("suggested_tags", [])
        if isinstance(suggested, str):
            suggested = [t.strip() for t in suggested.split(",") if t.strip()]
        new_tags = set(t.lower().replace(" ", "-") for t in suggested if t)
        merged = sorted(existing | new_tags)
        merged_str = ",".join(merged)

        db.update_tags(m["content_hash"], merged_str)
        added = new_tags - existing
        click.echo(f"         Added: {', '.join(added) if added else '(no new tags)'}")
        tagged_count += 1

    db.close()
    click.echo(f"\nTagged {tagged_count} memories.")
