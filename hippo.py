#!/usr/bin/env python3
"""Hippoclaudus CLI — memory management powered by local LLM inference.

Commands:
    consolidate   Post-session memory compression
    reflect       Generate State Delta from recent sessions
    predict       Generate PRELOAD.md for next session
    tag           Entity-tag existing memories
    compact       Merge duplicate/superseded memories
    status        Show memory health, relationship staleness, open threads
    comm-profile  Analyze communication patterns for a person

v3.0 Commands:
    encode        Convert English facts to symbolic notation
    slots         Manage Tier 1 slot allocation (legend, operators, project memory)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import click

# Root of the mcp-memory tree
MCP_ROOT = Path(__file__).parent
LONG_TERM = MCP_ROOT / "long-term"
WORKING = MCP_ROOT / "working"
DATA = MCP_ROOT / "data"
DB_PATH = DATA / "memory.db"

# Default MLX model
DEFAULT_MODEL = "mlx-community/Mistral-7B-Instruct-v0.3-4bit"
FALLBACK_MODEL = "mlx-community/Phi-3.5-mini-instruct-4bit"


@click.group()
@click.option("--model", default=DEFAULT_MODEL, help="MLX model to use for inference")
@click.option("--db", default=str(DB_PATH), help="Path to memory.db")
@click.pass_context
def cli(ctx, model, db):
    """Hippoclaudus — local LLM-powered memory management."""
    ctx.ensure_object(dict)
    ctx.obj["model_name"] = model
    ctx.obj["db_path"] = db


# --- Phase 1 Commands ---

@cli.command()
@click.pass_context
def consolidate(ctx):
    """Post-session memory compression.

    Reads the latest session from Session_Summary_Log.md,
    generates a State Delta via local LLM, creates embedding,
    and stores in memory.db with entity tags.
    """
    from hippoclaudus.consolidator import run_consolidation
    run_consolidation(
        model_name=ctx.obj["model_name"],
        db_path=ctx.obj["db_path"],
        session_log=WORKING / "Session_Summary_Log.md",
    )


@cli.command()
@click.pass_context
def reflect(ctx):
    """Generate State Delta from recent sessions (dry run — no DB write)."""
    from hippoclaudus.consolidator import run_reflection
    run_reflection(
        model_name=ctx.obj["model_name"],
        session_log=WORKING / "Session_Summary_Log.md",
    )


# --- Phase 2 Commands ---

@cli.command()
@click.option("--memory-id", type=int, help="Tag a specific memory by ID")
@click.option("--all", "tag_all", is_flag=True, help="Tag all under-tagged memories")
@click.pass_context
def tag(ctx, memory_id, tag_all):
    """Entity-tag existing memories using local LLM.

    Use --memory-id to tag one memory, or --all to tag all
    memories with fewer than 5 tags.
    """
    from hippoclaudus.tagger import run_tag_single, run_tag_all

    if memory_id:
        run_tag_single(ctx.obj["model_name"], ctx.obj["db_path"], memory_id)
    elif tag_all:
        run_tag_all(ctx.obj["model_name"], ctx.obj["db_path"])
    else:
        click.echo("Specify --memory-id <ID> or --all")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be merged without changing anything")
@click.option("--threshold", type=float, default=0.3, help="Jaccard similarity threshold (default: 0.3)")
@click.pass_context
def compact(ctx, dry_run, threshold):
    """Merge duplicate/superseded memories.

    Finds memories with high token overlap, uses LLM to determine
    if they're duplicates or superseded, and merges them.
    Soft-deletes originals (recoverable).
    """
    from hippoclaudus.compactor import run_compact
    run_compact(ctx.obj["model_name"], ctx.obj["db_path"], dry_run=dry_run, threshold=threshold)


@cli.command()
@click.option("--output", type=click.Path(), default=None, help="Output path for PRELOAD.md")
@click.pass_context
def predict(ctx, output):
    """Generate PRELOAD.md for next session startup.

    Analyzes recent sessions, open questions, and state deltas
    to produce a context-dense briefing for the next session.
    """
    from hippoclaudus.predictor import run_predict

    if output is None:
        output = WORKING / "PRELOAD.md"
    else:
        output = Path(output)

    run_predict(
        model_name=ctx.obj["model_name"],
        db_path=ctx.obj["db_path"],
        session_log=WORKING / "Session_Summary_Log.md",
        open_questions=WORKING / "Open_Questions_Blockers.md",
        output=output,
    )


@cli.command()
@click.pass_context
def status(ctx):
    """Show memory health, relationship staleness, open threads."""
    from hippoclaudus.db_bridge import MemoryDB

    db = MemoryDB(ctx.obj["db_path"])
    stats = db.get_stats()
    memories = db.get_all_memories(limit=100)
    db.close()

    # Basic stats
    click.echo("=== Hippoclaudus Status ===")
    click.echo(f"  Memories:      {stats['memory_count']}")
    click.echo(f"  Graph edges:   {stats['graph_edges']}")
    click.echo(f"  DB size:       {stats['db_size_mb']:.1f} MB")

    # State delta count
    deltas = [m for m in memories if m.get("memory_type") == "state_delta"]
    click.echo(f"  State deltas:  {len(deltas)}")

    # Relationship file staleness
    click.echo(f"\n  Relationship Files:")
    for rel_file in sorted(LONG_TERM.glob("Claude_Relationships_*.md")):
        mtime = datetime.fromtimestamp(rel_file.stat().st_mtime, tz=timezone.utc)
        age_days = (datetime.now(timezone.utc) - mtime).days
        staleness = "fresh" if age_days < 7 else "stale" if age_days < 30 else "very stale"
        name = rel_file.stem.replace("Claude_Relationships_", "")
        click.echo(f"    {name:12s}  {age_days}d old ({staleness})")

    # Open threads from most recent state delta
    if deltas:
        latest = deltas[0]
        try:
            meta = json.loads(latest.get("metadata", "{}"))
            threads = meta.get("open_threads", [])
            if threads:
                click.echo(f"\n  Open Threads (from last consolidation):")
                for t in threads:
                    click.echo(f"    - {t}")
        except (json.JSONDecodeError, TypeError):
            pass

    # Open questions file
    oq_path = WORKING / "Open_Questions_Blockers.md"
    if oq_path.exists():
        click.echo(f"\n  Open questions file: {oq_path}")
    click.echo()


@cli.command(name="comm-profile")
@click.argument("person")
@click.pass_context
def comm_profile(ctx, person):
    """Analyze communication patterns for a person.

    Searches memories and relationship files for references to PERSON,
    then uses LLM to extract tone, decision style, and relationship dynamics.
    """
    from hippoclaudus.comm_profiler import run_comm_profile
    run_comm_profile(
        model_name=ctx.obj["model_name"],
        db_path=ctx.obj["db_path"],
        person=person,
        long_term=LONG_TERM,
    )


# --- Phase 3 (v3.0) Commands ---

@cli.command()
@click.argument("text", required=False)
@click.option("--file", "input_file", type=click.Path(exists=True), help="Encode facts from a text file (one per line)")
@click.option("--output", type=click.Path(), default=None, help="Write encoded output to file")
@click.option("--domain", default="", help="Domain shortcode prefix (e.g., Wb, Fin, Pr)")
@click.pass_context
def encode(ctx, text, input_file, output, domain):
    """Convert English facts into symbolic notation.

    Encode a single fact:
        hippo encode "The website dev folder is empty, critical gap"

    Encode from file:
        hippo encode --file facts.txt --output slots.txt

    With domain prefix:
        hippo encode --domain Wb "Landing page is complete"
    """
    from hippoclaudus.symbolic_encoder import encode_fact, encode_batch, pack_into_slots, EncoderConfig

    config = EncoderConfig()

    if text:
        # Single fact encoding
        click.echo(f"Encoding ({len(text)} chars)...")
        encoded = encode_fact(ctx.obj["model_name"], text, config)
        if domain:
            encoded = f"{domain}:{encoded}" if not encoded.startswith(domain) else encoded
        click.echo(f"\nOriginal:  {text}")
        click.echo(f"Encoded:   {encoded}")
        click.echo(f"Savings:   {len(text)} → {len(encoded)} chars ({100 - (len(encoded)*100//max(len(text),1))}% smaller)")

        if output:
            Path(output).write_text(encoded)
            click.echo(f"Written to: {output}")

    elif input_file:
        # Batch encoding from file
        facts = [line.strip() for line in Path(input_file).read_text().splitlines() if line.strip()]
        click.echo(f"Encoding {len(facts)} facts...")

        encoded_facts = []
        for i, fact in enumerate(facts, 1):
            enc = encode_fact(ctx.obj["model_name"], fact, config)
            if domain:
                enc = f"{domain}:{enc}" if not enc.startswith(domain) else enc
            encoded_facts.append(enc)
            click.echo(f"  [{i}/{len(facts)}] {enc[:80]}...")

        slots = pack_into_slots(encoded_facts)
        click.echo(f"\nPacked into {len(slots)} slots:")
        for i, slot in enumerate(slots):
            click.echo(f"  Slot {i+1}: [{len(slot):3d} chars] {slot[:80]}...")

        if output:
            Path(output).write_text("\n".join(slots))
            click.echo(f"\nWritten to: {output}")

    else:
        click.echo("Provide text to encode or use --file. Run 'hippo encode --help' for usage.")


@cli.group()
def slots():
    """Manage Tier 1 slot allocation (legend, operators, project memory)."""
    pass


@slots.command(name="status")
def slots_status():
    """Show current slot allocation and capacity."""
    from hippoclaudus.slot_manager import load_slots, initialize_slots, format_status

    slot_file = DATA / "slots.json"
    allocation = load_slots(slot_file)

    if allocation is None:
        click.echo("No slot allocation found. Initializing...")
        allocation = initialize_slots()
        click.echo("(Run 'hippo slots init' to save)\n")

    click.echo(format_status(allocation))


@slots.command(name="init")
@click.option("--force", is_flag=True, help="Overwrite existing allocation")
def slots_init(force):
    """Initialize slot allocation with legend, Core 4, and DRE triad.

    Creates slots.json with:
    - Slot 1: Legend (symbol vocabulary + operator references)
    - Slot 2: Core 4 operators (reasoning process cycle)
    - Slot 3: DRE Triad (perceptual expansion checks)
    - Slots 4-30: Empty, ready for project memory
    """
    from hippoclaudus.slot_manager import initialize_slots, save_slots, format_status

    slot_file = DATA / "slots.json"

    if slot_file.exists() and not force:
        click.echo(f"Slot allocation already exists at {slot_file}")
        click.echo("Use --force to overwrite.")
        return

    allocation = initialize_slots()
    save_slots(allocation, slot_file)
    click.echo("Slot allocation initialized.\n")
    click.echo(format_status(allocation))


@slots.command(name="legend")
def slots_legend():
    """Display and validate the current legend."""
    from hippoclaudus.symbolic_encoder import generate_legend, validate_legend

    legend = generate_legend()
    validation = validate_legend(legend)

    click.echo("=== Slot 1: Master Legend ===\n")
    click.echo(legend)
    click.echo(f"\nLength: {len(legend)} chars")
    click.echo(f"Valid:  {'✓' if validation['valid'] else '✗'}")

    if validation["issues"]:
        for issue in validation["issues"]:
            click.echo(f"  Issue: {issue}")


@slots.command(name="operators")
def slots_operators():
    """Display the Core 4 philosophical operators."""
    from hippoclaudus.symbolic_encoder import generate_operator_slot, validate_operator_slot, CORE_4_OPERATORS

    slot = generate_operator_slot()
    validation = validate_operator_slot(slot)

    click.echo("=== Slot 2: Core 4 Philosophical Operators ===\n")
    click.echo("The Hippoclaudus Loop:")
    click.echo("  Peirce → Bayesian → Hofstadter → Meadows → (restart)")
    click.echo("  Hypothesize → Test → Examine Process → Act on Leverage\n")

    for key, op in CORE_4_OPERATORS.items():
        click.echo(f"  {key}: {op['name']} ({op['source']})")
        click.echo(f"    {op['function']}")
        click.echo(f"    Encoding: {op['encoding']}")
        click.echo()

    click.echo(f"Slot string: {slot}")
    click.echo(f"Length: {len(slot)} chars")
    click.echo(f"Valid:  {'✓' if validation['valid'] else '✗'}")


@slots.command(name="dre")
def slots_dre():
    """Display the DRE Triad perceptual operators."""
    from hippoclaudus.symbolic_encoder import generate_dre_slot, validate_dre_slot, DRE_TRIAD

    slot = generate_dre_slot()
    validation = validate_dre_slot(slot)

    click.echo("=== Slot 3: DRE Triad — Perceptual Expansion Checks ===\n")
    click.echo("Three operational audits (not dispositions):")
    click.echo("  Trace (backward) → Registers (across) → Semiosis (forward)")
    click.echo("  Audit absence → Test scale invariance → Resist premature closure\n")

    for key, op in DRE_TRIAD.items():
        click.echo(f"  {key}: {op['name']}")
        click.echo(f"    Source: {op['source']}")
        click.echo(f"    Function: {op['function']}")
        for direction, desc in op["operations"].items():
            click.echo(f"    {direction}: {desc}")
        click.echo(f"    Risk: {op['risk']}")
        click.echo(f"    Encoding: {op['encoding']}")
        click.echo()

    click.echo(f"Slot string: {slot}")
    click.echo(f"Length: {len(slot)} chars")
    click.echo(f"Valid:  {'✓' if validation['valid'] else '✗'}")


@slots.command(name="export")
def slots_export():
    """Export slot allocation for Claude's memory settings."""
    from hippoclaudus.slot_manager import load_slots, initialize_slots, export_for_claude

    slot_file = DATA / "slots.json"
    allocation = load_slots(slot_file)

    if allocation is None:
        click.echo("No allocation found. Initializing with defaults...")
        allocation = initialize_slots()

    click.echo(export_for_claude(allocation))


@slots.command(name="test")
def slots_test():
    """Display the Core 4 + DRE activation test protocol."""
    from hippoclaudus.slot_manager import get_test_protocol
    click.echo(get_test_protocol())


@slots.command(name="budget")
def slots_budget():
    """Show detailed slot budget breakdown."""
    from hippoclaudus.symbolic_encoder import format_slot_report
    click.echo(format_slot_report())


if __name__ == "__main__":
    cli()
