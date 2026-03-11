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

Discrepancy categories:
- **weakened**: FOL says less than the original
- **strengthened**: FOL says more than the original
- **scope-change**: quantifier scope or domain differs
- **missing-aspect**: original has a nuance the FOL dropped
- **wrong-property**: FOL captures a different property entirely

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

### FOLIO gold annotations (gold mode, 50 examples / 338 statements)

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

**41% of gold-annotated FOL statements have detectable faithfulness issues.** The discrepancies are systematic:

1. **Predicate compression** (weakened, missing-aspect): FOLIO packs rich NL into compact predicate names. `TalentShows(x)` for "performs in school talent shows often", `Love(emma, summer)` for "Emma's favorite season is summer" (drops the superlative), `Meetings(x)` for "schedules meetings with their customers" (drops "with customers").

2. **Missing domain guards** (scope-change, strengthened): "All employees who..." → `∀x (P(x) → Q(x))` without an `Employee(x)` guard. "All students who want..." → `∀x (WantlongVacation(x) → ...)` without a `Student(x)` guard. The restriction to a subclass is lost.

3. **XOR vs biconditional confusion** (wrong-property): "James is either (A and B) or (neither A nor B)" encodes a biconditional (A ↔ B), but FOLIO uses `A ⊕ B` (exclusive or between individual properties), which has opposite semantics — it means exactly one is true, not both-or-neither.

4. **Conjunction/disjunction errors** (wrong-property): "There are four seasons: Spring, Summer, Fall, and Winter" is formalized as `Season(spring) ∨ Season(summer) ∨ ...` — a disjunction (at least one is a season) instead of conjunction (all four are seasons).

5. **Converse confusion** (wrong-property): "Composers write music pieces" (composer → writes) is formalized as `∀x∀y (MusicPiece(x) ∧ WrittenBy(x,y) → Composer(y))` (written-by → composer), which is the converse.

6. **Semantic mismatch** (wrong-property): "Mia's favorite season is not the same as Emma's" → `¬Love(mia, emma)` ("Mia does not love Emma") — completely wrong property.

These aren't LLM errors — they're real losses in the gold annotations that have been invisible because FOLIO evaluation only checks entailment labels, not per-premise faithfulness.

Note: some discrepancies may be false positives (the comparator being overly strict about phrasing differences). But the structural issues — XOR/biconditional confusion, converse implications, conjunction/disjunction errors — are genuine bugs in the gold annotations that could affect entailment correctness.

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
- **Comparator** (`claimcheck.py`): LLM compares original NL vs back-translation, reports discrepancies with categories
