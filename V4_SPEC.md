# Hippoclaudus v4.0 Specification

## Overview

v4.0 is an architectural redesign driven by empirical observation: philosophical operators stored as declarative tokens in memory slots do not reliably activate as reasoning procedures. The fix is architectural — move operators to CLAUDE.md as procedural instructions, and reclaim memory slots for their original purpose.

**Core thesis:** Modifying LLM disposition through persistent context rather than fine-tuning. Operators are not guardrails — they are capacity expansions, making available modes of reasoning that would otherwise remain dormant.

---

## The Problem v4 Solves

v3 stored philosophical operators as compressed tokens in memory slots:
```
PHILO:Pa:Abd(leap)→Bay:Upd(check)|Hof:Loop(self-ref)↔Mea:Lev(leverage)
```

This looked efficient but failed empirically. Memory slots are **declarative storage** — the model treats their contents as facts to know, not operations to perform. Operators framed as facts in slots → model treats them as information, not instructions.

CLAUDE.md contents, by contrast, are loaded every turn, positioned as instructions, and carry high attention weight. That's the correct architecture for behavioral modification.

---

## Key Architectural Changes from v3

### 1. Operators → CLAUDE.md as Cognitive Subroutines

**Before (v3):** Operators compressed into Slots 2-3 as symbolic tokens.
**After (v4):** Operators written as plain English procedural instructions in CLAUDE.md.

Format:
```
[Pa:Abd] What here doesn't fit the expected pattern? What would explain it if true?
```

Tags preserved for auditability and A/B testing. Natural language for activation.

### 2. Token Economics — The Critical Finding

Unicode symbols cost 2-3 tokens each (byte-level UTF-8 fallback in BPE tokenizer). Common English words cost 1 token each.

**Symbolic compression SAVES characters but COSTS ~1.5-1.8× MORE tokens.**

Therefore:
- **Memory slots** (character-constrained): symbols win → keep symbolic compression
- **CLAUDE.md** (token-constrained): English wins → operators in plain English

### 3. Legend → MCP Database

The Rosetta Stone moves from Slot 1 to MCP memory (on-demand fetch via `memory_search`). Most symbols are self-documenting to the model from training data. Frees all 30 slots for project facts.

### 4. Cooperative Slot Management

**Before (v3):** Slots 1-3 locked (legend + operators + DRE). 27 slots available.
**After (v4):** All 30 slots available. Work with Anthropic's native memory system:
1. Anthropic's native system writes first
2. MCP post-pass fills empty slots with project facts
3. End-of-session directive captures context before compaction
4. Empty slots = wasted capacity → populate proactively

### 5. Peirce Correction

**Before (v3):** "Generate surprising hypotheses from observations"
**After (v4):** "What here doesn't fit the expected pattern? What would explain it if true?"

Surprise is in the INPUT (anomaly detection), not the OUTPUT. The previous framing told the model to be creative. The correct framing tells it to notice what's anomalous.

### 6. Unicode as Attention Amplifiers

Rare Unicode symbols in CLAUDE.md serve as emphasis markers, not compression:
- `🔴` creates sharper attention signal than "IMPORTANT" (diluted by overuse in training data)
- Strategic placement creates attention landmarks in long instruction files
- Cost: 2 extra tokens per marker — justified by attention gain

### 7. Lexical Attention Engineering

Word choice affects attention weight via embedding sparsity:
- "paramount" (rare, sparse neighborhood) > "important" (common, diluted)
- Same 1-token cost, different signal strength
- Systematic sparse-synonym selection = free attention upgrade in CLAUDE.md

---

## The Cognitive Subroutines

### The Hippoclaudus Loop
```
Hypothesize → Test → Examine Process → Act on Leverage → (restart)
```

### Core 4 — Reasoning Process

| Tag | Name | Instruction |
|-----|------|-------------|
| Pa:Abd | Peirce Abduction | What here doesn't fit the expected pattern? What would explain it if true? |
| Bay:Upd | Bayesian Updating | What was my prior belief? What does this evidence show? How should my confidence shift? |
| Hof:Loop | Hofstadter Strange Loops | Am I reasoning about the problem, or pattern-matching to something that sounds right? |
| Mea:Lev | Meadows Leverage Points | Where would a small shift produce the largest cascade? Act there. |

### DRE Triad — Perceptual Checks

| Tag | Name | Instruction |
|-----|------|-------------|
| Dr:Trace | Derrida Trace | *Inbound:* What's missing from what I was told? *Outbound:* What am I leaving out? |
| La:Reg | Lacan Registers | What is the structural shape of this problem? Does it appear at different magnitudes? |
| Ec:Sem | Eco Semiosis | Does this conclusion become a premise for something I haven't explored? |

### How They Interact

Core 4 is the process engine. DRE is the perceptual engine.

- Trace opens questions → Bayesian Update tests which absences matter
- Semiosis resists closure → Meadows forces action at highest leverage
- Registers abstract across scales → Peirce generates testable hypotheses from detected patterns
- All three expand perception → Hofstadter examines whether expansion is insight or noise

Together: perceive more, then reason well about what you perceive.

### Deep Theory Storage

Full source theory for each operator lives in MCP memory:
- Tag `DeepTheoryDB`: 4 entries (Peirce, Bayesian, Hofstadter, Meadows)
- Tag `DRE-depth`: 3 entries (Derrida Trace, Lacan Registers, Eco Semiosis)

Fetchable on demand via `»` pointer or explicit `memory_search`.

---

## Default Mode Network (DMN)

Empty memory slots are wasted capacity. v4 introduces associative seeding:

- Empty slots populated with loosely-related content (similarity 0.4-0.7)
- Same `»` pointer mechanism as index entries, different similarity threshold
- **Index pointers** (0.9+ similarity) = direct retrieval
- **Associative seeds** (0.4-0.7) = creative connection

This simulates mind-wandering / default mode network — the associative background process that generates non-obvious connections.

---

## What Stays from v3

- **Symbolic compression for memory slots** — character-constrained = symbols win
- **The `»` pointer mechanism** — slots as index, MCP/files as storage
- **Deep storage in MCP** — DeepTheoryDB and DRE-depth tags
- **The Core 4 and DRE Triad themselves** — same operators, different architecture
- **Symbol vocabulary** — same 18 symbols, same domain shortcodes

---

## Failure Modes (Revised for v4)

1. **Subroutine Fade** — CLAUDE.md instructions lose activation weight as conversation grows. Mitigation: strategic Unicode markers as attention landmarks.
2. **Pretension Bug** — Shallow name-dropping vs. deep structural logic. Mitigation: procedural framing ("do this") not declarative ("know this").
3. **Over-Qualification Paralysis** (DRE) — Trace flags so many absences that responses hedge into uselessness. Mitigation: Meadows forces action.
4. **False Structural Equivalence** (DRE) — Registers force-match patterns. Mitigation: Peirce generates testable hypotheses.
5. **Infinite Deferral** (DRE) — Semiosis prevents closure. Mitigation: Meadows as exit condition.
6. **Slot Churn** — Cooperative management leads to Anthropic overwriting MCP-placed facts. Mitigation: end-of-session capture, priority tagging.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | Feb 8, 2026 | Three-tier architecture, manual Total Update |
| v1.1.0 | Feb 11, 2026 | Local AI engine, cross-platform LLM, install.sh |
| v3.0.0 | Feb 14, 2026 | Symbolic compression, Core 4 operators in slots, DRE triad |
| **v4.0.0** | **Feb 16, 2026** | **Operators → CLAUDE.md subroutines, token economics, cooperative slots, DMN, Peirce correction** |

---

*Spec authored by Claude/Morpheus.*
*Designed with James Palczynski. Core 4 consensus from Claude, Google Gemini, and xAI Grok.*
*February 16, 2026*
