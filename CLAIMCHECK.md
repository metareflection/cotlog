# Claimcheck for FOL

Round-trip verification of natural language ↔ first-order logic faithfulness, adapted from the [claimcheck](../claimcheck) approach for Dafny specifications.

## Core Idea

Formalization (NL → FOL) inevitably makes choices: it resolves ambiguities, drops qualifiers, changes quantifier scope. These choices are often invisible — the FOL "looks right" but subtly differs from the original.

Claimcheck detects these discrepancies via **round-trip comparison**:

1. **Formalize**: NL → FOL (via LLM, or use existing gold annotations)
2. **Informalize**: FOL → English (a different LLM call that does NOT see the original NL)
3. **Compare**: original NL vs back-translated English — where they differ, the formalization lost or changed something

The back-translation is the key: because it's produced from the FOL alone, any gap between it and the original NL reveals a real formalization choice, not an LLM hallucination.

## Usage

### LLM mode (formalize, then round-trip)

```bash
# On custom examples
uv run python -m cotlog.claimcheck --mode llm --data examples/refine-examples.jsonl -v

# On FOLIO validation set
uv run python -m cotlog.claimcheck --mode llm --limit 20 -v
```

### Gold mode (round-trip on existing FOL annotations)

Skips the formalize step — uses gold FOL from the dataset directly. Tests whether the gold annotations faithfully capture the NL.

```bash
# Check FOLIO's own gold annotations
uv run python -m cotlog.claimcheck --mode gold --limit 20 -v
```

### Options

```
--mode MODE        llm (default) or gold
--data PATH        JSONL file (default: FOLIO validation set)
--model NAME       LLM model: sonnet (default), haiku, opus
--limit N          Max examples
--output-dir DIR   Directory for result files (default: results/)
-v, --verbose      Print per-example details
```

### Output

Each run writes a JSONL file to `results/claimcheck_{mode}_{timestamp}.jsonl` with per-statement verdicts, FOL, back-translations, and discrepancy categories.

Each discrepancy is classified by category and severity (structural or surface).

Structural categories (real logic errors):
- **wrong-connective**: ∧/∨/→/↔/⊕ confusion
- **converse**: implication direction reversed
- **wrong-quantifier**: ∀/∃ confusion or missing restriction that changes domain
- **wrong-property**: FOL captures a completely different property or relation
- **wrong-arity**: wrong argument count or swapped argument order

Surface categories (inherent FOL limitations):
- **predicate-naming**: predicate name doesn't capture full NL meaning
- **missing-guard**: implicit type restriction absent
- **modality-loss**: deontic/epistemic nuance dropped
- **tense-loss**: temporal distinctions lost

## Results

### Custom examples (LLM mode, 10 examples)

```
Total statements: 52
Faithful: 39
Discrepancies: 13
Faithfulness rate: 75%
```

Discrepancies found were substantive:
- "signed by the author" → `Signed(x)` — dropped "by the author" (missing-aspect)
- "must file a quarterly report" → `FilesQuarterlyReport(x)` — deontic "must" flattened to factual "does" (missing-aspect, FOL expressivity limit)
- "the committee approved" → `Approved(x)` — dropped the agent (missing-aspect)
- "driving lessons" → `TookLessons(x)` — lost qualifier (weakened)
- Type-guard additions: FOL adds `Restaurant(x)` or `Book(x)` guards that NL leaves implicit (strengthened)

### FOLIO gold annotations — v1 flat comparator (50 examples / 338 statements)

The initial comparator treated all discrepancies equally:

```
Total statements: 338
Faithful: 199
Discrepancies: 139
Faithfulness rate: 59%

Discrepancy categories:
  weakened: 36
  wrong-property: 33
  strengthened: 23
  missing-aspect: 15
  scope-change: 13
```

**The 41% discrepancy rate was misleading.** Most flagged issues were predicate-naming noise (e.g., `TalentShows(x)` read literally as "x is a talent show"), not real logic errors. The flat comparator couldn't distinguish the two.

### FOLIO gold annotations — v2 two-tier comparator (10 examples / 73 statements)

The comparator was rewritten to classify each discrepancy as **structural** (real logic error that could change truth values) or **surface** (inherent FOL expressivity loss):

```
Total statements: 73
Faithful: 29
Structural errors: 40
Surface noise: 4
Faithfulness rate (structural only): 45%
Faithfulness rate (all discrepancies): 40%

Structural categories:
  wrong-property: 15
  wrong-connective: 9
  wrong-quantifier: 9

Surface categories:
  predicate-naming: 2
  missing-guard: 1
  modality-loss: 1
```

**The two-tier split works** — surface noise is small and correctly classified. Predicate-naming issues like `Meetings(x)` for "schedules meetings with customers" now land in the surface bucket instead of inflating the error count.

**But the structural rate is still high (55%).** This is partly real and partly an artifact of the sample:

1. **Repeated premises**: Examples 6-8 share the same monkeypox story (same gold FOL), so the same `wrong-quantifier` errors (existential where universal is meant) are counted three times.

2. **Statement misalignment**: Example 9 has gold FOL statements shifted relative to the NL premises, causing a cascade of `wrong-property` flags. This is a genuine dataset bug.

3. **Real connective errors**: XOR vs biconditional confusion (`⊕` where `↔` is meant) is correctly caught across multiple examples.

**Structural error categories explained:**

- **wrong-connective**: ∧/∨/→/↔/⊕ confusion. Most common: "A and B or neither A nor B" (biconditional) formalized as `A ⊕ B` (exclusive or), which has opposite semantics.
- **wrong-quantifier**: ∀/∃ confusion. Common in FOLIO: definitional claims ("Monkeypox is a disease caused by...") formalized as existential claims (`∃x`).
- **wrong-property**: FOL captures a completely different property. Includes statement misalignment bugs and semantic mismatches like `¬Love(mia, emma)` for "different favorite seasons."

**Surface noise categories explained:**

- **predicate-naming**: Predicate name doesn't capture full NL meaning — the predicate is opaque shorthand, not a semantic claim.
- **missing-guard**: Implicit type restriction absent (e.g., "all employees who..." without `Employee(x)` guard) — defensible in closed-world settings.
- **modality-loss**: Deontic/epistemic nuance dropped ("must file" → "files", "feel tired" → "is tired") — FOL has no modality.
- **tense-loss**: Temporal distinctions lost — FOL is atemporal.

A full run on all 50 examples (or the full 204 validation set) is needed to get stable numbers. The structural rate should settle lower once the repeated-premise inflation is accounted for.

## Comparison with the Refinement Loop

This project initially implemented a refinement loop (see [REFINE.md](REFINE.md)) that tried to iteratively improve NL by surfacing ambiguities through formalization. That approach had problems:

- The LLM surfacer hallucinated ambiguities ("permanently located on Main Street")
- Refinement wasn't monotonic (could make things worse)
- The stability metric was either too coarse or too noisy

Claimcheck avoids these issues by grounding everything in the round-trip: the FOL is a concrete artifact, the back-translation is produced from it alone, and the comparison detects real differences rather than speculated ones. No prover needed, no stability measurement, no iterative loop — just two LLM calls per example.

## Architecture

```
NL premises          FOL (from LLM or gold)       Back-translated English
─────────────       ──────────────────────       ──────────────────────────
"All employees       ∀x (Meeting(x) →             "For all x, if x is a
who schedule a  ──→  AppearInCompany(x))     ──→  meeting, then x appears
meeting..."                                       in company."
                                                        │
                          ┌─────────────────────────────┘
                          ▼
                    COMPARE: "employees who schedule"
                         vs "if x is a meeting"
                         → wrong-property: subject changed
```

Components:
- **Formalizer** (`fol_gen.py`): LLM translates NL → FOL (skipped in gold mode)
- **Informalizer** (`claimcheck.py`): LLM translates FOL → English without seeing original NL
- **Comparator** (`claimcheck.py`): LLM compares original NL vs back-translation, classifies discrepancies as structural (logic errors) or surface (expressivity losses)
