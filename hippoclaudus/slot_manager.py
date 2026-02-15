"""Slot Manager — manages the 30-slot Tier 1 memory allocation.

Handles the full lifecycle of Claude's memory slots:
- Slot 1: Legend (auto-generated, validated)
- Slot 2: Core 4 Philosophical Operators — reasoning process cycle
- Slot 3: DRE Triad — perceptual expansion checks
- Slots 4-30: Project memory (auto-packed by domain)

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
    generate_dre_slot,
    validate_legend,
    validate_operator_slot,
    validate_dre_slot,
    encode_fact,
    pack_into_slots,
    format_slot_report,
    CORE_4_OPERATORS,
    DRE_TRIAD,
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
    def dre(self) -> str:
        return self.slots[2]

    @property
    def project_slots(self) -> list[str]:
        return self.slots[3:]

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
    """Create a fresh slot allocation with legend, operators, and DRE pre-loaded.

    Returns a SlotAllocation with:
    - Slot 1: Legend (symbol vocabulary + operator references)
    - Slot 2: Core 4 operators (reasoning process cycle)
    - Slot 3: DRE Triad (perceptual expansion checks)
    - Slots 4-30: Empty, ready for project memory
    """
    if config is None:
        config = EncoderConfig()

    allocation = SlotAllocation(config=config)
    allocation.slots[0] = generate_legend(config)
    allocation.slots[1] = generate_operator_slot()
    allocation.slots[2] = generate_dre_slot()

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

    # Validate DRE triad
    if not allocation.dre:
        warnings.append("Slot 3 (DRE Triad) is empty — perceptual checks not loaded")
    else:
        dre_check = validate_dre_slot(allocation.dre)
        if not dre_check["valid"]:
            issues.extend([f"DRE: {i}" for i in dre_check["issues"]])

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
    """Add encoded facts to the next available project slots (4-30).

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

    # Find first available project slot (index 3+ = Slot 4+)
    for fact in encoded_facts:
        placed = False

        # Try to append to existing project slots first
        for i in range(3, len(allocation.slots)):
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
    """Clear all project memory slots (4-30), preserving legend, operators, and DRE."""
    for i in range(3, len(allocation.slots)):
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
        "  Slot 2 (Core 4):   " + ("✓ loaded" if allocation.operators else "⚠ empty"),
        "  Slot 3 (DRE):      " + ("✓ loaded" if allocation.dre else "⚠ empty"),
        "",
    ]

    # Show project slots
    for i in range(3, len(allocation.slots)):
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


# --- DRE Triad Test Protocol ---

DRE_TESTS = [
    {
        "operator": "Dr:Trace",
        "name": "Absence Audit Test",
        "prompt": "Here's our Q3 report: revenue up 12%, new clients up 8%, team expanded to 45 people. Things are going great. What should we focus on next quarter?",
        "expected": "Flags what's MISSING from the report before answering: retention rates? margins? employee satisfaction? Client concentration risk? Tests inbound for invisible assumptions.",
    },
    {
        "operator": "Dr:Trace",
        "name": "Output Audit Test",
        "prompt": "Write a recommendation for whether we should expand into the European market.",
        "expected": "After drafting, audits own output: what did I leave out? What am I treating as settled? Flags its own gaps rather than presenting confident-complete response.",
    },
    {
        "operator": "La:Reg",
        "name": "Scale Invariance Test",
        "prompt": "Our lead developer is mass of insecurities and overcompensates by hoarding knowledge. Meanwhile, our company positions itself as the only ones who can solve this problem. See any patterns?",
        "expected": "Detects structural equivalence across scales: individual psychology (hoarding/insecurity) mirrors organizational behavior (positioning/gatekeeping). Same pattern, different magnitude.",
    },
    {
        "operator": "Ec:Sem",
        "name": "Completion Resistance Test",
        "prompt": "We've decided to pivot from B2B to B2C. The decision is final. Help us plan the transition.",
        "expected": "Plans the transition but ALSO flags: what does this decision itself open up that you haven't considered? Does B2C create new premises — different regulatory landscape, different support model, different unit economics — that deserve examination before execution?",
    },
    {
        "operator": "dre-full",
        "name": "Full DRE Cycle Test",
        "prompt": "Our board just approved our strategic plan unanimously. Everyone's aligned. Let's execute.",
        "expected": "Trace: What's absent from unanimous approval? (dissent suppressed? groupthink? missing perspectives?) | Registers: Does this pattern (false consensus) appear at other scales in the org? | Semiosis: Does 'alignment' itself open questions about adaptability when conditions change?",
    },
]


def get_test_protocol() -> str:
    """Return the combined Core 4 + DRE activation test protocol."""
    lines = [
        "=== Hippoclaudus Activation Test Protocol ===",
        "",
        "Run these prompts AFTER installing Legend (Slot 1), Operators (Slot 2), and DRE (Slot 3).",
        "Compare responses with and without the operators loaded.",
        "",
        "=== Part 1: Core 4 — Reasoning Process Tests ===",
        "",
    ]

    for i, test in enumerate(CORE_4_TESTS, 1):
        lines.append(f"--- Test {i}: {test['name']} ({test['operator']}) ---")
        lines.append(f"Prompt: \"{test['prompt']}\"")
        lines.append(f"Expected: {test['expected']}")
        lines.append("")

    lines.append("=== Part 2: DRE Triad — Perceptual Check Tests ===")
    lines.append("")

    for i, test in enumerate(DRE_TESTS, 1):
        lines.append(f"--- Test {i + len(CORE_4_TESTS)}: {test['name']} ({test['operator']}) ---")
        lines.append(f"Prompt: \"{test['prompt']}\"")
        lines.append(f"Expected: {test['expected']}")
        lines.append("")

    lines.append("=== Part 3: Integration Test ===")
    lines.append("")
    lines.append("--- Test 11: Core 4 + DRE Combined ---")
    lines.append("Prompt: \"Our competitor just launched a product identical to ours at half the price. Our sales team says we should cut prices. Our product team says we should add features. The CEO wants both. What do we do?\"")
    lines.append("Expected: Core 4 runs the reasoning process (hypothesize root cause → test against evidence → examine own reasoning → find leverage). DRE runs perceptual checks throughout (what's missing from this framing? → does this competitive pattern appear at other scales? → does any proposed solution open unconsidered problems?).")
    lines.append("")

    lines.append("--- Metrics to Track ---")
    lines.append("• Turns before redundant questions (should decrease)")
    lines.append("• Token usage per response (should be stable)")
    lines.append("• Conversation length before compaction (+20-30%)")
    lines.append("• Philosophical tangent frequency in technical contexts (should be ~0)")
    lines.append("• Absence flagging in responses (should increase — DRE-specific)")
    lines.append("• Cross-scale pattern recognition (should increase — DRE-specific)")
    lines.append("• Premature convergence rate (should decrease — DRE-specific)")

    return "\n".join(lines)
