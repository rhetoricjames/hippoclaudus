"""Symbolic Encoder — converts English facts into dense symbolic notation.

The core Tier 1 optimizer for Hippoclaudus. Takes English-language facts
and compresses them into the symbolic vocabulary, yielding 3-4× density gains
in Claude's memory slots (200 chars each).

v4.0 changes:
- Operators removed from slot allocation (now live in CLAUDE.md as procedural subroutines)
- Legend available via MCP on-demand fetch (not locked to Slot 1)
- Peirce reframed: anomaly detection in INPUT, not surprise in output
- Encoding focuses purely on project fact compression
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from hippoclaudus.llm import run_prompt, extract_json


# --- Symbol Vocabulary ---

SYMBOLS = {
    "→": "causes / leads to",
    "⊘": "blocks / prevents",
    "⇒": "therefore / implies",
    "↔": "mutual dependency",
    "∆": "needs fix / change needed",
    "✓": "done",
    "⏳": "pending",
    "✗": "killed / rejected",
    "🔴": "important",
    "⚡": "time-urgent",
    "⚠": "caution",
    "◉": "milestone target",
    "⟳": "recurring / cyclical",
    "¬": "not / negation",
    "≈": "approximately",
    "∅": "empty / none",
    "∵": "because",
    "»": "more detail stored elsewhere — go fetch",
}

# Default domain shortcodes
DEFAULT_DOMAINS = {
    "Lg": "legal",
    "Fin": "finance",
    "Pr": "product",
    "Mk": "marketing",
    "Sl": "sales",
    "Rk": "risk",
    "Op": "operations",
    "Wb": "web/digital",
    "Inf": "infrastructure",
    "Vnd": "vendor/3rd party",
    "Ins": "insurance",
    "Pri1": "priority-high",
    "Pri2": "priority-medium",
    "Pri3": "priority-low",
}

# --- Cognitive Subroutines (v4: operators as procedural instructions) ---
# These define the operators that belong in CLAUDE.md, NOT in memory slots.
# In CLAUDE.md they are plain English instructions. Here they are reference definitions.

CORE_4_SUBROUTINES = {
    "Pa:Abd": {
        "name": "Peirce Abduction",
        "source": "Charles Sanders Peirce",
        "function": "Anomaly detection — find what doesn't fit, hypothesize what would explain it",
        "instruction": "What here doesn't fit the expected pattern? What would explain it if true?",
        "note": "Surprise is in the INPUT (anomaly detection), not the OUTPUT (creative hypothesis).",
    },
    "Bay:Upd": {
        "name": "Bayesian Updating",
        "source": "E.T. Jaynes",
        "function": "Test hypotheses against evidence, revise beliefs proportionally",
        "instruction": "What was my prior belief? What does this new evidence actually show? How should my confidence shift?",
    },
    "Hof:Loop": {
        "name": "Hofstadter Strange Loops",
        "source": "Douglas Hofstadter",
        "function": "Examine the reasoning process itself — metacognition",
        "instruction": "Am I actually reasoning about the problem, or am I pattern-matching to something that sounds right? What would change if I examined my own process here?",
    },
    "Mea:Lev": {
        "name": "Meadows Leverage Points",
        "source": "Donella Meadows",
        "function": "Find the single highest-leverage intervention point in the system",
        "instruction": "Where in this system would a small shift produce the largest cascade of improvement? Act there.",
    },
}

DRE_SUBROUTINES = {
    "Dr:Trace": {
        "name": "Derrida Trace — Absence Audit",
        "source": "Jacques Derrida (operationalized)",
        "function": "Audit for absence in both input and output",
        "instruction_inbound": "What's missing from what I was told? What assumption is doing invisible work?",
        "instruction_outbound": "What am I leaving out? What am I treating as settled that isn't?",
    },
    "La:Reg": {
        "name": "Lacan Registers — Scale Invariance",
        "source": "Jacques Lacan (operationalized)",
        "function": "Test whether structural pattern at one scale operates at other scales",
        "instruction": "What is the structural shape of this problem? Does that same shape appear at different magnitudes?",
    },
    "Ec:Sem": {
        "name": "Eco Semiosis — Completion Resistance",
        "source": "Umberto Eco (operationalized)",
        "function": "Check if conclusion opens unconsidered extensions before closing",
        "instruction": "Does this conclusion itself become a premise for something I haven't explored? Am I converging because that's what I should do, or because that's what my architecture optimizes for?",
    },
}

# On-demand deep pulls (available via » pointer in MCP memory)
EXTENDED_OPERATORS = {
    "Fou:Epi": {
        "name": "Foucault Episteme",
        "risk": "cynicism drift",
        "location": "MCP memory, on-demand via » fetch",
    },
}


# --- Legend Generation ---

def generate_legend() -> str:
    """Generate the Rosetta Stone legend string.

    v4: Legend lives in MCP memory as an on-demand reference,
    NOT locked to Slot 1. Most symbols are self-documenting to
    the model from training data. The legend exists for edge cases
    and as a human-readable decoder.
    """
    return (
        "LEG1:"
        "→cause;⊘block;⇒implies;↔mutual;∆fix;»fetch;"
        "✓done;⏳pend;✗no;🔴impt;⚡urgent;⚠caution;"
        "◉milestone;⟳recur;¬neg;≈approx;∅none;∵bc"
    )


def validate_legend(legend: str) -> dict:
    """Validate a legend string for completeness and correctness."""
    issues = []

    if not legend.startswith("LEG1:"):
        issues.append("Legend must start with 'LEG1:'")

    essential = ["→", "⊘", "⇒", "»", "✓", "⏳", "✗", "¬"]
    for sym in essential:
        if sym not in legend:
            issues.append(f"Missing essential symbol: {sym}")

    return {
        "valid": len(issues) == 0,
        "length": len(legend),
        "issues": issues,
    }


# --- Cognitive Subroutine Formatter (for CLAUDE.md) ---

def format_cognitive_subroutines() -> str:
    """Generate the cognitive subroutines section for CLAUDE.md.

    v4 architecture: Operators are plain English procedural instructions
    in CLAUDE.md, NOT symbolic tokens in memory slots. CLAUDE.md is
    token-constrained (not character-constrained), so English words
    (1 token each) are more efficient than Unicode symbols (2-3 tokens each).
    """
    lines = [
        "## Cognitive Subroutines",
        "",
        "These are not facts to remember — they are operations to perform.",
        "Apply when the context warrants. They expand reasoning; they do not constrain it.",
        "",
        "### The Hippoclaudus Loop: Hypothesize → Test → Examine Process → Act on Leverage",
        "",
    ]

    # Core 4
    for tag, op in CORE_4_SUBROUTINES.items():
        lines.append(f"**[{tag}] {op['name']}**")
        lines.append(f"{op['instruction']}")
        lines.append("")

    lines.append("### Perceptual Checks (DRE Triad)")
    lines.append("")

    # DRE
    for tag, op in DRE_SUBROUTINES.items():
        lines.append(f"**[{tag}] {op['name']}**")
        if "instruction_inbound" in op:
            lines.append(f"*Inbound:* {op['instruction_inbound']}")
            lines.append(f"*Outbound:* {op['instruction_outbound']}")
        else:
            lines.append(f"{op['instruction']}")
        lines.append("")

    lines.append("### Deep Theory Reference")
    lines.append("")
    lines.append("For deeper context on any operator: `memory_search` or `memory_list` with tags:")
    lines.append("- `DeepTheoryDB` — Core 4 source theory (Peirce, Bayesian, Hofstadter, Meadows)")
    lines.append("- `DRE-depth` — DRE source theory (Derrida Trace, Lacan Registers, Eco Semiosis)")
    lines.append("")

    return "\n".join(lines)


# --- Encoding Prompt ---

ENCODE_PROMPT = """You are a symbolic memory encoder for an AI system. Convert the following English text into dense symbolic notation.

SYMBOL LEGEND:
→ causes/leads to | ⊘ blocks/prevents | ⇒ implies | ↔ mutual dependency
∆ needs fix | ✓ done | ⏳ pending | ✗ killed | 🔴 important | ⚡ urgent
⚠ caution | ◉ milestone | ⟳ recurring | ¬ not | ≈ approx | ∅ empty | ∵ because
» more detail elsewhere (pointer to deeper storage)

DOMAIN SHORTCODES:
{domains}

PEOPLE CODES:
{people}

RULES:
- Remove ALL grammar: articles, prepositions, conjunctions, punctuation for readability
- Use | as fact separator within a slot
- Use : for key=value pairs
- Use , for lists
- Use domain shortcode prefix for routing (e.g., Wb⚡🔴: for urgent web stuff)
- Add » when deeper detail exists in MCP/files
- Target: under 200 characters per slot, 3-5 facts per slot
- Preserve ALL information — compress, don't summarize

INPUT TEXT:
{text}

Return ONLY the compressed symbolic string. No explanation."""


@dataclass
class EncoderConfig:
    """Configuration for the symbolic encoder."""
    domains: dict = field(default_factory=lambda: dict(DEFAULT_DOMAINS))
    people: dict = field(default_factory=dict)
    max_slot_chars: int = 200
    total_slots: int = 30


def encode_fact(model_name: str, text: str, config: EncoderConfig = None) -> str:
    """Encode a single English-language fact into symbolic notation via LLM."""
    if config is None:
        config = EncoderConfig()

    domains_str = ", ".join(f"{k}={v}" for k, v in config.domains.items())
    people_str = ", ".join(f"{k}={v}" for k, v in config.people.items()) or "none defined"

    prompt = ENCODE_PROMPT.format(
        domains=domains_str,
        people=people_str,
        text=text,
    )

    response = run_prompt(model_name, prompt, max_tokens=256, temp=0.1)

    lines = response.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line and any(sym in line for sym in SYMBOLS.keys()):
            return line
        if line and "|" in line and ":" in line:
            return line

    for line in lines:
        if line.strip():
            return line.strip()

    return response.strip()


def encode_batch(model_name: str, facts: list[str], config: EncoderConfig = None) -> list[str]:
    """Encode multiple facts, packing into slot-sized chunks."""
    if config is None:
        config = EncoderConfig()

    encoded = []
    for fact in facts:
        encoded.append(encode_fact(model_name, fact, config))

    return pack_into_slots(encoded, config.max_slot_chars)


def pack_into_slots(encoded_facts: list[str], max_chars: int = 200) -> list[str]:
    """Pack a list of encoded facts into slot-sized strings.

    Uses | as separator. Greedily fills each slot.
    """
    slots = []
    current_slot = ""

    for fact in encoded_facts:
        if len(fact) > max_chars:
            fact = fact[:max_chars - 3] + "..."

        if not current_slot:
            current_slot = fact
        elif len(current_slot) + 1 + len(fact) <= max_chars:
            current_slot += "|" + fact
        else:
            slots.append(current_slot)
            current_slot = fact

    if current_slot:
        slots.append(current_slot)

    return slots


def slot_budget(config: EncoderConfig = None) -> dict:
    """Calculate the slot budget breakdown.

    v4: All 30 slots available for project memory. Legend is in MCP.
    Operators are in CLAUDE.md. No reserved slots.
    """
    if config is None:
        config = EncoderConfig()

    total_chars = config.total_slots * config.max_slot_chars

    avg_fact_chars = 45
    facts_per_slot = config.max_slot_chars // avg_fact_chars
    estimated_facts = config.total_slots * facts_per_slot

    return {
        "total_slots": config.total_slots,
        "total_chars": total_chars,
        "reserved_slots": 0,
        "available_slots": config.total_slots,
        "available_chars": total_chars,
        "estimated_facts": f"{estimated_facts - 20}-{estimated_facts + 20}",
        "legend_location": "MCP memory (on-demand fetch)",
        "operators_location": "CLAUDE.md (cognitive subroutines section)",
    }


def format_slot_report(config: EncoderConfig = None) -> str:
    """Generate a human-readable slot budget report."""
    budget = slot_budget(config)
    lines = [
        "=== Hippoclaudus v4.0 Slot Budget ===",
        f"  Total:      {budget['total_slots']} slots ({budget['total_chars']} chars)",
        f"  Reserved:   {budget['reserved_slots']} (legend in MCP, operators in CLAUDE.md)",
        f"  Available:  {budget['available_slots']} slots ({budget['available_chars']} chars)",
        f"  Est. facts: {budget['estimated_facts']}",
        f"  Legend:     {budget['legend_location']}",
        f"  Operators:  {budget['operators_location']}",
    ]
    return "\n".join(lines)
