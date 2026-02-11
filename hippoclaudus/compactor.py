"""Compactor — merge duplicate and superseded memories.

Finds memories with high semantic overlap, uses the local LLM to determine
which are duplicates or superseded, and merges them into consolidated entries.
"""

import json
from datetime import datetime, timezone

import click

from hippoclaudus.db_bridge import MemoryDB, Memory
from hippoclaudus.llm import run_prompt, extract_json


MERGE_PROMPT = """You are a memory deduplication system. Given these two memories, determine if they should be merged.

MEMORY A (created {date_a}):
{content_a}

MEMORY B (created {date_b}):
{content_b}

Analyze and return a JSON object:
{{
  "relationship": "duplicate" | "superseded" | "related" | "distinct",
  "keep": "A" | "B" | "merge",
  "merged_content": "If keep is 'merge', provide the merged text. Otherwise empty string.",
  "reasoning": "Brief explanation of your decision"
}}

Rules:
- "duplicate": Nearly identical information. Keep the newer one.
- "superseded": One updates/replaces the other. Keep the newer/more complete one.
- "related": Similar topic but distinct information. Keep both.
- "distinct": Unrelated. Keep both.

Return ONLY the JSON object."""


def _similarity_simple(a: str, b: str) -> float:
    """Quick token-overlap similarity (no embeddings needed)."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)  # Jaccard similarity


def run_compact(model_name: str, db_path: str, dry_run: bool = False, threshold: float = 0.3):
    """Find and merge duplicate/superseded memories."""
    click.echo(f"=== Hippoclaudus Compact {'(dry run)' if dry_run else ''} ===")

    db = MemoryDB(db_path)
    memories = db.get_all_memories(limit=1000)

    if len(memories) < 2:
        click.echo("Not enough memories to compare.")
        db.close()
        return

    click.echo(f"Comparing {len(memories)} memories (threshold: {threshold})...\n")

    # Find candidate pairs with token overlap above threshold
    candidates = []
    for i in range(len(memories)):
        for j in range(i + 1, len(memories)):
            sim = _similarity_simple(memories[i]["content"], memories[j]["content"])
            if sim >= threshold:
                candidates.append((memories[i], memories[j], sim))

    if not candidates:
        click.echo("No candidate pairs found above similarity threshold.")
        db.close()
        return

    click.echo(f"Found {len(candidates)} candidate pair(s).\n")

    merged_count = 0
    for mem_a, mem_b, sim in candidates:
        click.echo(f"--- Pair (similarity: {sim:.2f}) ---")
        click.echo(f"  A [{mem_a['id']}]: {mem_a['content'][:80]}...")
        click.echo(f"  B [{mem_b['id']}]: {mem_b['content'][:80]}...")

        # Ask LLM to evaluate
        prompt = MERGE_PROMPT.format(
            date_a=mem_a.get("created_at_iso", "unknown"),
            content_a=mem_a["content"],
            date_b=mem_b.get("created_at_iso", "unknown"),
            content_b=mem_b["content"],
        )
        response = run_prompt(model_name, prompt, max_tokens=512, temp=0.1)
        result = extract_json(response)

        if not result:
            click.echo("  LLM failed to evaluate — skipping")
            continue

        relationship = result.get("relationship", "distinct")
        keep = result.get("keep", "both")
        reasoning = result.get("reasoning", "")

        click.echo(f"  Verdict: {relationship} (keep: {keep})")
        click.echo(f"  Reason: {reasoning}")

        if relationship in ("duplicate", "superseded") and not dry_run:
            if keep == "A":
                # Soft-delete B
                _soft_delete(db, mem_b["content_hash"])
                click.echo(f"  -> Soft-deleted [{mem_b['id']}]")
                merged_count += 1
            elif keep == "B":
                _soft_delete(db, mem_a["content_hash"])
                click.echo(f"  -> Soft-deleted [{mem_a['id']}]")
                merged_count += 1
            elif keep == "merge":
                merged_content = result.get("merged_content", "")
                if merged_content:
                    # Store merged, soft-delete both originals
                    merged_tags = _merge_tags(mem_a.get("tags", ""), mem_b.get("tags", ""))
                    new_mem = Memory(
                        content=merged_content,
                        tags=merged_tags,
                        memory_type="note",
                        metadata={"source": "hippo-compact", "merged_from": [mem_a["content_hash"][:16], mem_b["content_hash"][:16]]},
                    )
                    row_id = db.store_memory(new_mem)
                    _soft_delete(db, mem_a["content_hash"])
                    _soft_delete(db, mem_b["content_hash"])
                    click.echo(f"  -> Merged into new memory #{row_id}, soft-deleted originals")
                    merged_count += 1
        elif dry_run and relationship in ("duplicate", "superseded"):
            click.echo(f"  -> Would {keep} (dry run)")

        click.echo()

    db.close()
    click.echo(f"Compact complete. {merged_count} merge(s) performed.")


def _soft_delete(db: MemoryDB, content_hash: str):
    """Soft-delete a memory by setting deleted_at."""
    import time
    now = time.time()
    db.conn.execute(
        "UPDATE memories SET deleted_at = ? WHERE content_hash = ?",
        (now, content_hash),
    )
    db.conn.commit()


def _merge_tags(tags_a: str, tags_b: str) -> str:
    """Merge two comma-separated tag strings, deduplicating."""
    all_tags = set()
    for t in (tags_a or "").split(","):
        t = t.strip()
        if t:
            all_tags.add(t)
    for t in (tags_b or "").split(","):
        t = t.strip()
        if t:
            all_tags.add(t)
    return ",".join(sorted(all_tags))
