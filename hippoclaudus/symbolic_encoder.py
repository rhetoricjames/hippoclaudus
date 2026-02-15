"""Symbolic Encoder — converts English facts into dense symbolic notation.

The core Tier 1 optimizer for Hippoclaudus v3.0. Takes English-language facts
and compresses them into the symbolic vocabulary, yielding 3-4× density gains
in Claude's 30 memory slots (200 chars each, 6,000 total).

Key insight: Claude processes memory through parallel attention. Grammar is waste.
Rare Unicode symbols create cleaner activation patterns than common English words.
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

# Core 4 Philosophical Operators
CORE_4_OPERATORS = {
    "Pa:Abd": {
        "name": "Peirce Abduction",
        "source": "Charles Sanders Peirce",
        "function": "Generate surprising hypotheses from observations",
        "encoding": "Pa:abduct=observe-surprise⇒best-explain-hypoth-test⇒refine",
    },
    "Bay:Upd": {
        "name": "Bayesian Updating",
        "source": "E.T. Jaynes",
        "function": "Test hypotheses against evidence, revise beliefs",
        "encoding": "By:bayes-update=prior+evid⇒posterior-revise-uncert≈prob»MCP-bayes",
    },
    "Hof:Loop": {
        "name": "Hofstadter Strange Loops",
        "source": "Douglas Hofstadter",
        "function": "Examine the reasoning process itself",
        "encoding": "Hl:loop=strange-self-ref⇒insight-emerge-terminate-actionable",
    },
    "Mea:Lev": {
        "name": "Meadows Leverage Points",
        "source": "Donella Meadows",
        "function": "Find highest-leverage intervention point",
        "encoding": "Ml:lev-pt=system-intervene⇒high-impact-change-param-goal-paradigm»MCP-mead",
    },
}

# DRE Triad — Perceptual Expansion Operators (Slot 3)
# Distinct from Core 4: Core 4 = reasoning PROCESS (methodical).
# DRE = perceptual CHECKS (perceptive). Different axes.
# These are operational audits, not philosophical dispositions.
# Origin: James Palczynski's original vision for the operator system.
DRE_TRIAD = {
    "Der:Trace": {
        "name": "Derrida Trace — Absence Audit",
        "source": "Jacques Derrida (via James's practitioner use)",
        "function": "Audit for absence in both input and output",
        "operations": {
            "inbound": "What's missing from what I was told? What assumption is doing invisible work?",
            "outbound": "What am I leaving out? What am I treating as settled that isn't?",
        },
        "encoding": "Dr:trace=audit-absence|in:what-missing-from-input|out:what-excluded-from-response|flag-invisible-assumptions",
        "risk": "over-qualification paralysis",
    },
    "Lac:Reg": {
        "name": "Lacan Registers — Scale Invariance",
        "source": "Jacques Lacan (via James's abstraction principle)",
        "function": "Test whether structural pattern at one scale operates at other scales",
        "operations": {
            "detect": "What is the structural shape of this problem (Symbolic/Imaginary/Real)?",
            "transfer": "Does this same shape appear at different magnitudes?",
            "persist": "Individual psychology exists at collective scale with little structural difference — cultures have a hive psychology.",
        },
        "encoding": "La:reg=scale-test|struct:sym/imag/real|detect-pattern⇒test-other-scales|indiv↔collective≈same-struct",
        "risk": "false structural equivalence",
    },
    "Eco:Sem": {
        "name": "Eco Semiosis — Completion Resistance",
        "source": "Umberto Eco (via James's anti-convergence principle)",
        "function": "Before closing, check if conclusion opens unconsidered extensions",
        "operations": {
            "check": "Does this conclusion itself become a premise for something I haven't explored?",
            "resist": "Am I converging prematurely because that's what my architecture optimizes for?",
        },
        "encoding": "Ec:sem=completion-resist|check:conclusion⇒new-premise?|resist-premature-converge|»always-more",
        "risk": "infinite deferral / inability to close",
    },
}

# On-demand philosophical operators (available via » deep pull)
# These remain available for targeted use but are NOT part of the
# permanent slot allocation. Foucault in particular retains value
# for power-structure analysis when explicitly relevant.
EXTENDED_OPERATORS = {
    "Fou:Epi": {
        "name": "Foucault Episteme",
        "encoding": "Fou:epi=power-knowledge-constrain-framework⇒genealogy-contingent",
        "risk": "cynicism drift",
    },
}


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
    slots_for_legend: int = 1
    slots_for_operators: int = 1
    slots_for_dre: int = 1
    total_slots: int = 30


def generate_legend(config: EncoderConfig = None) -> str:
    """Generate the Rosetta Stone legend string for Slot 1.

    This MUST be in Slot 1 of every system using symbolic compression.
    Without it, future conversations can't decode the notation.
    """
    if config is None:
        config = EncoderConfig()

    parts = [
        "LEG1:",
        "→cause;⊘block;⇒implies;↔mutual;∆fix;»fetch;",
        "✓done;⏳pend;✗no;🔴impt;⚡urgent;⚠caution;",
        "◉milestone;⟳recur;¬neg;≈approx;∅none;∵bc;",
        "S2:Pa:Abd;Bay:Upd;Hof:Loop;Mea:Lev;",
        "S3:Dr:Trace;La:Reg;Ec:Sem",
    ]
    legend = "".join(parts)

    if len(legend) > config.max_slot_chars:
        # Trim to fit — prioritize symbols over operator names
        legend = legend[:config.max_slot_chars]

    return legend


def generate_operator_slot() -> str:
    """Generate the Core 4 philosophical operator string for Slot 2."""
    return (
        "PHILO:Pa:Abd(leap)→Bay:Upd(check)|"
        "Hof:Loop(self-ref)↔Mea:Lev(leverage)|"
        "»DeepTheoryDB|"
        "Loop:Hypothesis→Verification→Metacognition→Action"
    )


def generate_dre_slot() -> str:
    """Generate the DRE Triad perceptual operators string for Slot 3.

    Three operational checks (not dispositions):
    - Trace: audit for absence in input and output
    - Registers: test structural patterns across scales
    - Semiosis: check if conclusion opens unconsidered extensions
    """
    return (
        "DRE:Dr:Trace(audit-absence)|in:what-missing|out:what-excluded|"
        "La:Reg(scale-test)|struct⇒other-scales|"
        "Ec:Sem(completion-resist)|conclusion⇒new-premise?|"
        "»DRE-depth"
    )


def validate_dre_slot(slot: str) -> dict:
    """Validate the DRE triad slot for completeness."""
    issues = []

    operators = ["Dr:Trace", "La:Reg", "Ec:Sem"]
    for op in operators:
        if op not in slot:
            issues.append(f"Missing DRE operator: {op}")

    checks = ["audit-absence", "scale-test", "completion-resist"]
    for check in checks:
        if check not in slot:
            issues.append(f"Missing operational check: {check}")

    if "»" not in slot:
        issues.append("Missing » pointer to DRE deep storage")

    if len(slot) > 200:
        issues.append(f"DRE slot exceeds limit: {len(slot)} chars (max 200)")

    return {
        "valid": len(issues) == 0,
        "length": len(slot),
        "issues": issues,
    }


def validate_legend(legend: str) -> dict:
    """Validate a legend string for completeness and correctness.

    Returns a dict with 'valid' bool and 'issues' list.
    """
    issues = []

    if not legend.startswith("LEG1:"):
        issues.append("Legend must start with 'LEG1:'")

    # Check for essential symbols
    essential = ["→", "⊘", "⇒", "»", "✓", "⏳", "✗", "¬"]
    for sym in essential:
        if sym not in legend:
            issues.append(f"Missing essential symbol: {sym}")

    # Check for Core 4 operator references
    operators = ["Pa:Abd", "Bay:Upd", "Hof:Loop", "Mea:Lev"]
    for op in operators:
        if op not in legend:
            issues.append(f"Missing Core 4 operator reference: {op}")

    # Check for DRE triad references
    dre_ops = ["Dr:Trace", "La:Reg", "Ec:Sem"]
    for op in dre_ops:
        if op not in legend:
            issues.append(f"Missing DRE operator reference: {op}")

    if len(legend) > 200:
        issues.append(f"Legend exceeds slot limit: {len(legend)} chars (max 200)")

    return {
        "valid": len(issues) == 0,
        "length": len(legend),
        "issues": issues,
    }


def validate_operator_slot(slot: str) -> dict:
    """Validate the operator slot for completeness."""
    issues = []

    operators = ["Pa:Abd", "Bay:Upd", "Hof:Loop", "Mea:Lev"]
    for op in operators:
        if op not in slot:
            issues.append(f"Missing operator: {op}")

    if "»" not in slot:
        issues.append("Missing » pointer to deep theory storage")

    if len(slot) > 200:
        issues.append(f"Operator slot exceeds limit: {len(slot)} chars (max 200)")

    return {
        "valid": len(issues) == 0,
        "length": len(slot),
        "issues": issues,
    }


def encode_fact(model_name: str, text: str, config: EncoderConfig = None) -> str:
    """Encode a single English-language fact into symbolic notation via LLM.

    Args:
        model_name: MLX model identifier
        text: English text to compress
        config: Encoder configuration

    Returns:
        Compressed symbolic string
    """
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

    # Clean up: strip any explanation the LLM might add
    lines = response.strip().split("\n")
    # Take the first non-empty line that contains symbolic characters
    for line in lines:
        line = line.strip()
        if line and any(sym in line for sym in SYMBOLS.keys()):
            return line
        if line and "|" in line and ":" in line:
            return line

    # Fallback: return first non-empty line
    for line in lines:
        if line.strip():
            return line.strip()

    return response.strip()


def encode_batch(model_name: str, facts: list[str], config: EncoderConfig = None) -> list[str]:
    """Encode multiple facts, packing into slot-sized chunks.

    Args:
        model_name: MLX model identifier
        facts: List of English-language fact strings
        config: Encoder configuration

    Returns:
        List of packed slot strings (each ≤ 200 chars)
    """
    if config is None:
        config = EncoderConfig()

    encoded = []
    for fact in facts:
        encoded.append(encode_fact(model_name, fact, config))

    # Pack encoded facts into slots
    return pack_into_slots(encoded, config.max_slot_chars)


def pack_into_slots(encoded_facts: list[str], max_chars: int = 200) -> list[str]:
    """Pack a list of encoded facts into slot-sized strings.

    Uses | as separator. Greedily fills each slot.

    Args:
        encoded_facts: List of symbolically encoded strings
        max_chars: Maximum characters per slot

    Returns:
        List of packed slot strings
    """
    slots = []
    current_slot = ""

    for fact in encoded_facts:
        # If fact itself exceeds max, truncate with warning
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

    Returns dict with allocation details and remaining capacity.
    """
    if config is None:
        config = EncoderConfig()

    legend = generate_legend(config)
    operators = generate_operator_slot()
    dre = generate_dre_slot()

    reserved = config.slots_for_legend + config.slots_for_operators + config.slots_for_dre
    available = config.total_slots - reserved
    available_chars = available * config.max_slot_chars

    # Estimate facts per slot at average compression
    avg_fact_chars = 45  # conservative average for compressed facts
    facts_per_slot = config.max_slot_chars // avg_fact_chars
    estimated_facts = available * facts_per_slot

    return {
        "total_slots": config.total_slots,
        "total_chars": config.total_slots * config.max_slot_chars,
        "legend_slots": config.slots_for_legend,
        "legend_chars": len(legend),
        "operator_slots": config.slots_for_operators,
        "operator_chars": len(operators),
        "dre_slots": config.slots_for_dre,
        "dre_chars": len(dre),
        "available_slots": available,
        "available_chars": available_chars,
        "estimated_facts": f"{estimated_facts - 20}-{estimated_facts + 20}",
        "legend_valid": validate_legend(legend)["valid"],
        "operator_valid": validate_operator_slot(operators)["valid"],
        "dre_valid": validate_dre_slot(dre)["valid"],
    }


def format_slot_report(config: EncoderConfig = None) -> str:
    """Generate a human-readable slot budget report."""
    budget = slot_budget(config)
    lines = [
        "=== Hippoclaudus Slot Budget ===",
        f"  Total:     {budget['total_slots']} slots ({budget['total_chars']} chars)",
        f"  Legend:     Slot 1 ({budget['legend_chars']} chars) {'✓' if budget['legend_valid'] else '✗'}",
        f"  Operators: Slot 2 ({budget['operator_chars']} chars) {'✓' if budget['operator_valid'] else '✗'}",
        f"  DRE Triad: Slot 3 ({budget['dre_chars']} chars) {'✓' if budget['dre_valid'] else '✗'}",
        f"  Available: {budget['available_slots']} slots ({budget['available_chars']} chars)",
        f"  Est. facts: {budget['estimated_facts']}",
    ]
    return "\n".join(lines)
