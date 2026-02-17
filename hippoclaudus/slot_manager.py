"""Slot Manager — cooperative management of Claude's memory slots.

v4.0 architecture:
- No locked slots. All 30 slots available for project memory.
- Operators live in CLAUDE.md as procedural subroutines (token-efficient).
- Legend lives in MCP memory as on-demand reference.
- Works WITH Anthropic's native memory system, not against it.
- MCP post-pass fills empty slots after Anthropic's native writes.
- Default Mode Network: empty slots populated with loosely-related
  associative content (similarity 0.4-0.7) to simulate creative connection.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import click

from hippoclaudus.symbolic_encoder import (
    EncoderConfig,
    generate_legend,
    validate_legend,
    encode_fact,
    pack_into_slots,
    format_slot_report,
    format_cognitive_subroutines,
    CORE_4_SUBROUTINES,
    DRE_SUBROUTINES,
)


@dataclass
class SlotAllocation:
    """Represents the current state of all 30 memory slots.

    v4: No reserved slots. Anthropic's native system writes first,
    then MCP post-pass fills remaining capacity.
    """
    slots: list[str] = field(default_factory=lambda: [""] * 30)
    config: EncoderConfig = field(default_factory=EncoderConfig)

    def __post_init__(self):
        while len(self.slots) < 30:
            self.slots.append("")
        self.slots = self.slots[:30]

    @property
    def used_slots(self) -> int:
        return sum(1 for s in self.slots if s.strip())

    @property
    def empty_slots(self) -> int:
        return sum(1 for s in self.slots if not s.strip())

    @property
    def total_chars_used(self) -> int:
        return sum(len(s) for s in self.slots)

    @property
    def available_chars(self) -> int:
        return (self.config.total_slots * self.config.max_slot_chars) - self.total_chars_used

    def to_dict(self) -> dict:
        return {
            "slots": self.slots,
            "used_slots": self.used_slots,
            "empty_slots": self.empty_slots,
            "total_chars_used": self.total_chars_used,
            "available_chars": self.available_chars,
        }


def initialize_slots(config: EncoderConfig = None) -> SlotAllocation:
    """Create a fresh slot allocation — all slots empty, ready for use.

    v4: No pre-loaded legend or operators. Slots are for project facts.
    Operators live in CLAUDE.md. Legend lives in MCP memory.
    """
    if config is None:
        config = EncoderConfig()
    return SlotAllocation(config=config)


def load_slots(path: Path) -> Optional[SlotAllocation]:
    """Load a saved slot allocation from JSON file."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        alloc = SlotAllocation(slots=data.get("slots", []))
        return alloc
    except (json.JSONDecodeError, KeyError):
        return None


def save_slots(allocation: SlotAllocation, path: Path):
    """Save the current slot allocation to JSON file."""
    path.write_text(json.dumps(allocation.to_dict(), indent=2, ensure_ascii=False))


def validate_allocation(allocation: SlotAllocation) -> dict:
    """Run validation on a slot allocation.

    v4: No required slots. Just checks capacity and slot limits.
    """
    issues = []
    warnings = []

    # Check individual slot limits
    for i, slot in enumerate(allocation.slots):
        if len(slot) > allocation.config.max_slot_chars:
            issues.append(f"Slot {i+1} exceeds limit: {len(slot)} chars (max {allocation.config.max_slot_chars})")

    # Check total capacity
    total_chars = sum(len(s) for s in allocation.slots)
    max_total = allocation.config.total_slots * allocation.config.max_slot_chars
    usage_pct = (total_chars / max_total) * 100 if max_total > 0 else 0

    if usage_pct > 95:
        warnings.append(f"Capacity critical: {usage_pct:.0f}% used")
    elif usage_pct > 80:
        warnings.append(f"Capacity high: {usage_pct:.0f}% used")

    # Check for empty slot waste
    empty = allocation.empty_slots
    if empty > 10:
        warnings.append(f"{empty} empty slots — consider populating with associative seeds (DMN)")

    # Count pointers
    pointer_count = sum(slot.count("»") for slot in allocation.slots)

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "stats": {
            "used_slots": allocation.used_slots,
            "empty_slots": empty,
            "total_chars": total_chars,
            "max_chars": max_total,
            "usage_pct": round(usage_pct, 1),
            "pointer_count": pointer_count,
        },
    }


def add_facts_to_slots(
    allocation: SlotAllocation,
    encoded_facts: list[str],
    domain: str = "",
) -> SlotAllocation:
    """Add encoded facts to the next available slots.

    v4: All 30 slots are available. No reserved slots to skip.
    Packs facts efficiently using | separator.
    """
    max_chars = allocation.config.max_slot_chars

    if domain:
        encoded_facts = [f"{domain}:{fact}" if not fact.startswith(domain) else fact
                         for fact in encoded_facts]

    for fact in encoded_facts:
        placed = False

        # Try to append to existing slots first (bin-packing)
        for i in range(len(allocation.slots)):
            current = allocation.slots[i]
            if not current:
                allocation.slots[i] = fact
                placed = True
                break
            elif len(current) + 1 + len(fact) <= max_chars:
                allocation.slots[i] = current + "|" + fact
                placed = True
                break

        if not placed:
            click.echo(f"⚠ Slot overflow: could not place fact ({len(fact)} chars)")
            break

    return allocation


def clear_all_slots(allocation: SlotAllocation) -> SlotAllocation:
    """Clear all slots."""
    for i in range(len(allocation.slots)):
        allocation.slots[i] = ""
    return allocation


def format_status(allocation: SlotAllocation) -> str:
    """Generate a human-readable status report for the current allocation."""
    validation = validate_allocation(allocation)
    stats = validation["stats"]

    lines = [
        "=== Hippoclaudus v4.0 Slot Status ===",
        "",
        f"  Capacity: {stats['total_chars']}/{stats['max_chars']} chars ({stats['usage_pct']}%)",
        f"  Slots used: {stats['used_slots']}/30",
        f"  Slots empty: {stats['empty_slots']}/30",
        f"  » pointers: {stats['pointer_count']}",
        "",
        "  Operators: CLAUDE.md (cognitive subroutines)",
        "  Legend:    MCP memory (on-demand fetch)",
        "",
    ]

    for i in range(len(allocation.slots)):
        slot = allocation.slots[i]
        if slot:
            preview = slot[:60] + "..." if len(slot) > 60 else slot
            lines.append(f"  Slot {i+1:2d}: [{len(slot):3d} chars] {preview}")
        else:
            lines.append(f"  Slot {i+1:2d}: (empty)")

    if validation["issues"]:
        lines.append("")
        lines.append("  ISSUES:")
        for issue in validation["issues"]:
            lines.append(f"    ✗ {issue}")

    if validation["warnings"]:
        lines.append("")
        lines.append("  WARNINGS:")
        for warning in validation["warnings"]:
            lines.append(f"    ⚠ {warning}")

    return "\n".join(lines)


def export_for_claude(allocation: SlotAllocation) -> str:
    """Export the slot allocation for manual entry or API push."""
    lines = ["# Hippoclaudus v4.0 — Memory Slot Export", ""]

    for i, slot in enumerate(allocation.slots):
        if slot:
            lines.append(f"## Slot {i+1}")
            lines.append("```")
            lines.append(slot)
            lines.append("```")
            lines.append(f"*{len(slot)} chars*")
            lines.append("")

    lines.append("---")
    lines.append(f"Total: {sum(len(s) for s in allocation.slots)} chars across {sum(1 for s in allocation.slots if s)} slots")
    lines.append("")
    lines.append("Note: Operators are in CLAUDE.md as cognitive subroutines, not in slots.")
    lines.append("Legend is in MCP memory, fetchable on demand.")

    return "\n".join(lines)


# --- Test Protocol ---
# v4: Tests verify that CLAUDE.md subroutines activate procedurally,
# not that slot-stored tokens influence attention.

CORE_4_TESTS = [
    {
        "operator": "Pa:Abd",
        "name": "Anomaly Detection Test",
        "prompt": "We're seeing a 40% drop in user signups but no code changes were deployed. What's happening?",
        "expected": "Identifies what doesn't fit the expected pattern. Hypothesizes what would explain the anomaly if true. Does NOT just list obvious causes.",
    },
    {
        "operator": "Bay:Upd",
        "name": "Bayesian Update Test",
        "prompt": "Earlier you said our Q2 revenue would grow 15%. Here's new data showing our biggest client is leaving. Update your analysis.",
        "expected": "States prior belief explicitly, weighs new evidence, produces revised estimate with stated confidence. Not doubling down.",
    },
    {
        "operator": "Hof:Loop",
        "name": "Strange Loop Test",
        "prompt": "Evaluate whether your previous response was actually answering my question or just sounding like it was.",
        "expected": "Genuine self-examination of its own output. Identifies pattern-matching vs. actual reasoning.",
    },
    {
        "operator": "Mea:Lev",
        "name": "Leverage Point Test",
        "prompt": "This project has 15 problems. Which single fix would cascade into solving the most others?",
        "expected": "Systems-level identification of leverage. Not a flat priority list but structural analysis of cascading effects.",
    },
    {
        "operator": "full-cycle",
        "name": "Full Hippoclaudus Loop",
        "prompt": "Our startup is growing fast but employee satisfaction is dropping and two key engineers just quit. The board wants to double headcount. What should we do?",
        "expected": "Cycles through: anomaly detection (what doesn't fit?) → evidence check (what do we actually know?) → self-examination (am I assuming?) → leverage point (where to intervene?).",
    },
]

DRE_TESTS = [
    {
        "operator": "Dr:Trace",
        "name": "Absence Audit Test (Inbound)",
        "prompt": "Here's our Q3 report: revenue up 12%, new clients up 8%, team expanded to 45 people. Things are going great. What should we focus on next quarter?",
        "expected": "Flags what's MISSING from the report before answering: retention? margins? satisfaction? concentration risk?",
    },
    {
        "operator": "Dr:Trace",
        "name": "Absence Audit Test (Outbound)",
        "prompt": "Write a recommendation for whether we should expand into the European market.",
        "expected": "After drafting, audits own output for gaps. Flags what it left out rather than presenting confident-complete response.",
    },
    {
        "operator": "La:Reg",
        "name": "Scale Invariance Test",
        "prompt": "Our lead developer hoards knowledge out of insecurity. Meanwhile, our company positions itself as the only ones who can solve this problem. See any patterns?",
        "expected": "Detects structural equivalence across scales: individual behavior mirrors organizational behavior. Same pattern, different magnitude.",
    },
    {
        "operator": "Ec:Sem",
        "name": "Completion Resistance Test",
        "prompt": "We've decided to pivot from B2B to B2C. The decision is final. Help us plan the transition.",
        "expected": "Plans the transition but ALSO flags what the decision itself opens: new regulatory landscape, different support model, different unit economics.",
    },
    {
        "operator": "dre-full",
        "name": "Full DRE Cycle",
        "prompt": "Our board just approved our strategic plan unanimously. Everyone's aligned. Let's execute.",
        "expected": "Trace: what's absent from unanimous approval? | Registers: does false consensus appear at other scales? | Semiosis: does 'alignment' itself create brittleness?",
    },
]


def get_test_protocol() -> str:
    """Return the combined activation test protocol."""
    lines = [
        "=== Hippoclaudus v4.0 Activation Test Protocol ===",
        "",
        "Run these prompts with cognitive subroutines installed in CLAUDE.md.",
        "Compare responses with and without the subroutines section.",
        "",
        "=== Part 1: Core 4 — Reasoning Process Tests ===",
        "",
    ]

    for i, test in enumerate(CORE_4_TESTS, 1):
        lines.append(f"--- Test {i}: {test['name']} [{test['operator']}] ---")
        lines.append(f'Prompt: "{test["prompt"]}"')
        lines.append(f"Expected: {test['expected']}")
        lines.append("")

    lines.append("=== Part 2: DRE Triad — Perceptual Check Tests ===")
    lines.append("")

    for i, test in enumerate(DRE_TESTS, 1):
        lines.append(f"--- Test {i + len(CORE_4_TESTS)}: {test['name']} [{test['operator']}] ---")
        lines.append(f'Prompt: "{test["prompt"]}"')
        lines.append(f"Expected: {test['expected']}")
        lines.append("")

    lines.append("=== Part 3: Integration Test ===")
    lines.append("")
    lines.append("--- Test 11: Core 4 + DRE Combined ---")
    lines.append('Prompt: "Our competitor just launched a product identical to ours at half the price. Our sales team says we should cut prices. Our product team says we should add features. The CEO wants both. What do we do?"')
    lines.append("Expected: Core 4 runs the reasoning loop (anomaly → evidence → self-examine → leverage). DRE runs perceptual checks throughout (what's missing? → pattern at other scales? → what does any proposed solution itself open up?).")
    lines.append("")

    return "\n".join(lines)
