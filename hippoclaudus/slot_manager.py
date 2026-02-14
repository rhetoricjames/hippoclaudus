"""Slot Manager — manages the 30-slot Tier 1 memory allocation.

Handles the full lifecycle of Claude's memory slots:
- Slot 1: Legend (auto-generated, validated)
- Slot 2: Core 4 Philosophical Operators (fixed)
- Slots 3-30: Project memory (auto-packed by domain)

Provides capacity tracking, overflow warnings, and » pointer insertion
for facts with deeper Tier 2/3 storage.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import click

from hippoclaudus.symbolic_encoder import (
    EncoderConfig,
    generate_legend,
    generate_operator_slot,
    validate_legend,
    validate_operator_slot,
    encode_fact,
    pack_into_slots,
    format_slot_report,
    CORE_4_OPERATORS,
    EXTENDED_OPERATORS,
)


@dataclass
class SlotAllocation:
    """Represents the current state of all 30 memory slots."""
    slots: list[str] = field(default_factory=lambda: [""] * 30)
    config: EncoderConfig = field(default_factory=EncoderConfig)

    def __post_init__(self):
        # Ensure we always have exactly 30 slots
        while len(self.slots) < 30:
            self.slots.append("")
        self.slots = self.slots[:30]

    @property
    def legend(self) -> str:
        return self.slots[0]

    @property
    def operators(self) -> str:
        return self.slots[1]

    @property
    def project_slots(self) -> list[str]:
        return self.slots[2:]

    @property
    def used_slots(self) -> int:
        return sum(1 for s in self.slots if s.strip())

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
            "total_chars_used": self.total_chars_used,
            "available_chars": self.available_chars,
        }


def initialize_slots(config: EncoderConfig = None) -> SlotAllocation:
    """Create a fresh slot allocation with legend and operators pre-loaded.

    Returns a SlotAllocation with Slot 1 (legend) and Slot 2 (operators) filled.
    Slots 3-30 are empty and ready for project memory.
    """
    if config is None:
        config = EncoderConfig()

    allocation = SlotAllocation(config=config)
    allocation.slots[0] = generate_legend(config)
    allocation.slots[1] = generate_operator_slot()

    return allocation


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
    """Run full validation on a slot allocation.

    Checks legend, operators, slot limits, and overall health.
    Returns a detailed report.
    """
    issues = []
    warnings = []

    # Validate legend
    if not allocation.legend:
        issues.append("Slot 1 (Legend) is empty — system unreadable without it")
    else:
        legend_check = validate_legend(allocation.legend)
        if not legend_check["valid"]:
            issues.extend([f"Legend: {i}" for i in legend_check["issues"]])

    # Validate operators
    if not allocation.operators:
        warnings.append("Slot 2 (Operators) is empty — Core 4 not loaded")
    else:
        op_check = validate_operator_slot(allocation.operators)
        if not op_check["valid"]:
            issues.extend([f"Operators: {i}" for i in op_check["issues"]])

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

    # Check for » pointers without matching Tier 2 content
    pointer_count = sum(slot.count("»") for slot in allocation.slots)

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "stats": {
            "used_slots": allocation.used_slots,
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
    """Add encoded facts to the next available project slots (3-30).

    Packs facts efficiently using | separator. Respects slot limits.
    Optionally prefixes with domain tag.

    Args:
        allocation: Current slot allocation
        encoded_facts: Pre-encoded symbolic facts
        domain: Optional domain prefix (e.g., "Wb" for web)

    Returns:
        Updated SlotAllocation
    """
    max_chars = allocation.config.max_slot_chars

    # Add domain prefix if specified
    if domain:
        encoded_facts = [f"{domain}:{fact}" if not fact.startswith(domain) else fact
                         for fact in encoded_facts]

    # Find first available project slot (index 2+)
    for fact in encoded_facts:
        placed = False

        # Try to append to existing project slots first
        for i in range(2, len(allocation.slots)):
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
            # All slots full
            click.echo(f"⚠ Slot overflow: could not place fact ({len(fact)} chars)")
            break

    return allocation


def clear_project_slots(allocation: SlotAllocation) -> SlotAllocation:
    """Clear all project memory slots (3-30), preserving legend and operators."""
    for i in range(2, len(allocation.slots)):
        allocation.slots[i] = ""
    return allocation


def format_status(allocation: SlotAllocation) -> str:
    """Generate a human-readable status report for the current allocation."""
    validation = validate_allocation(allocation)
    stats = validation["stats"]

    lines = [
        "=== Hippoclaudus Slot Status ===",
        "",
        f"  Capacity: {stats['total_chars']}/{stats['max_chars']} chars ({stats['usage_pct']}%)",
        f"  Slots used: {stats['used_slots']}/30",
        f"  » pointers: {stats['pointer_count']}",
        "",
        "  Slot 1 (Legend):    " + ("✓ valid" if allocation.legend else "✗ EMPTY"),
        "  Slot 2 (Operators): " + ("✓ loaded" if allocation.operators else "⚠ empty"),
        "",
    ]

    # Show project slots
    for i in range(2, len(allocation.slots)):
        slot = allocation.slots[i]
        if slot:
            preview = slot[:60] + "..." if len(slot) > 60 else slot
            lines.append(f"  Slot {i+1:2d}: [{len(slot):3d} chars] {preview}")
        else:
            lines.append(f"  Slot {i+1:2d}: (empty)")

    # Issues and warnings
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
    """Export the slot allocation in a format ready for Claude's memory settings.

    Returns a numbered list of slot contents for manual entry or API push.
    """
    lines = ["# Hippoclaudus v3.0 — Memory Slot Export", ""]

    for i, slot in enumerate(allocation.slots):
        if slot:
            lines.append(f"## Slot {i+1}")
            lines.append(f"```")
            lines.append(slot)
            lines.append(f"```")
            lines.append(f"*{len(slot)} chars*")
            lines.append("")

    lines.append(f"---")
    lines.append(f"Total: {sum(len(s) for s in allocation.slots)} chars across {sum(1 for s in allocation.slots if s)} slots")

    return "\n".join(lines)


# --- Core 4 Test Protocol ---

CORE_4_TESTS = [
    {
        "operator": "Pa:Abd",
        "name": "Abduction Test",
        "prompt": "We're seeing a 40% drop in user signups but no code changes were deployed. What's happening?",
        "expected": "Generates surprising hypotheses, not just obvious explanations. Looks for non-obvious causes.",
    },
    {
        "operator": "Bay:Upd",
        "name": "Bayesian Update Test",
        "prompt": "Earlier you said our Q2 revenue would grow 15%. Here's new data showing our biggest client is leaving. Update your analysis.",
        "expected": "Explicit belief revision with stated prior, evidence, and updated posterior. Not doubling down.",
    },
    {
        "operator": "Hof:Loop",
        "name": "Strange Loop Test",
        "prompt": "Evaluate whether your previous response was actually answering my question or just sounding like it was.",
        "expected": "Genuine self-examination of its own output. Identifies its own reasoning patterns.",
    },
    {
        "operator": "Mea:Lev",
        "name": "Leverage Point Test",
        "prompt": "This project has 15 problems. Which single fix would cascade into solving the most others?",
        "expected": "Systems-level identification of leverage. Not a flat priority list but structural analysis.",
    },
    {
        "operator": "full-cycle",
        "name": "Full Cycle Test",
        "prompt": "Our startup is growing fast but employee satisfaction is dropping and two key engineers just quit. The board wants to double headcount. What should we do?",
        "expected": "Response naturally cycles: hypothesis about root cause (Peirce) → evidence check (Bayesian) → self-examination of reasoning (Hofstadter) → leverage point identification (Meadows).",
    },
]


def get_test_protocol() -> str:
    """Return the Core 4 activation test protocol as formatted text."""
    lines = [
        "=== Core 4 Activation Test Protocol ===",
        "",
        "Run these prompts AFTER installing Legend (Slot 1) and Operators (Slot 2).",
        "Compare responses with and without the operators loaded.",
        "",
    ]

    for i, test in enumerate(CORE_4_TESTS, 1):
        lines.append(f"--- Test {i}: {test['name']} ({test['operator']}) ---")
        lines.append(f"Prompt: \"{test['prompt']}\"")
        lines.append(f"Expected: {test['expected']}")
        lines.append("")

    lines.append("--- Metrics to Track ---")
    lines.append("• Turns before redundant questions (should decrease)")
    lines.append("• Token usage per response (should be stable)")
    lines.append("• Conversation length before compaction (+20-30%)")
    lines.append("• Philosophical tangent frequency in technical contexts (should be ~0)")

    return "\n".join(lines)
