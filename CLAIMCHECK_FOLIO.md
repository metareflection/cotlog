# Claimcheck FOLIO Results

Full run of the two-tier comparator on the FOLIO validation set (204 examples, gold FOL annotations).

## Summary

```
Total statements: 1292
Faithful: 926
Structural errors: 279
Surface noise: 87
Faithfulness rate (structural only): 78%
Faithfulness rate (all discrepancies): 72%
```

The two-tier comparator separates **structural** errors (real logic bugs that could change truth values) from **surface** noise (inherent FOL expressivity losses). The headline number is 78% — about 22% of gold FOL statements have structural faithfulness issues.

For comparison, the v1 flat comparator on 50 examples reported 59% faithfulness with no structural/surface distinction. The two-tier approach both raises the meaningful number (by filtering noise) and makes it more trustworthy (by categorizing what it finds).

## Structural errors (279)

These are real logic errors in the gold FOL annotations.

```
wrong-property: 112
wrong-connective: 60
wrong-quantifier: 38
wrong-arity: 8
converse: 3
```

### wrong-property (112)

The FOL captures a completely different property or relation than the original NL. This is the largest category and includes:

- **Statement misalignment**: Gold FOL statements shifted relative to NL premises (e.g., Example 9's turkey types, where the FOL for premise N corresponds to premise N+1). These are dataset formatting bugs.
- **Semantic mismatch**: `¬Love(mia, emma)` for "Mia's favorite season is not the same as Emma's" — completely wrong predicate.
- **Conjunction/disjunction errors**: "There are four seasons: Spring, Summer, Fall, and Winter" formalized as `Season(spring) ∨ Season(summer) ∨ ...` (disjunction) instead of conjunction.

### wrong-connective (60)

∧/∨/→/↔/⊕ confusion. The most systematic error in FOLIO:

- **XOR vs biconditional**: "James is either (A and B) or (neither A nor B)" encodes a biconditional (A ↔ B), but FOLIO uses `A ⊕ B` (exclusive or), which has opposite truth conditions.
- **Inclusive vs exclusive or**: "Employees will either have lunch in the company or at home" — likely exclusive, formalized as inclusive ∨.

### wrong-quantifier (38)

∀/∃ confusion or missing restrictions that change the domain:

- **Existential for definitional**: "Monkeypox is a disease caused by..." → `∃x (...)` instead of a universal/definitional claim.
- **Missing domain restriction that matters**: "All employees who..." → `∀x (P(x) → Q(x))` where dropping the `Employee(x)` guard changes the logical domain (not just a closed-world convention).

### wrong-arity (8)

Predicate has wrong number of arguments or swapped argument order.

### converse (3)

Implication direction reversed: "A implies B" formalized as "B implies A".

## Surface noise (87)

These are inherent FOL expressivity losses, not annotation errors.

```
missing-guard: 45
predicate-naming: 28
tense-loss: 9
modality-loss: 5
```

- **missing-guard (45)**: Implicit type restriction absent — "all employees who..." without `Employee(x)` guard. Defensible in closed-world settings where the domain is understood.
- **predicate-naming (28)**: Predicate name doesn't capture full NL meaning — `TalentShows(x)` for "performs in school talent shows often." The predicate is opaque shorthand, not a semantic claim.
- **tense-loss (9)**: Temporal distinctions lost — FOL is atemporal.
- **modality-loss (5)**: Deontic/epistemic nuance dropped — "must file" → "files." FOL has no modality.

## Caveats

1. **Repeated premises inflate counts.** FOLIO reuses premise sets across multiple conclusions (e.g., the monkeypox story appears in examples 6-8). Each example is counted independently, so the same FOL error in a shared premise is counted once per example it appears in.

2. **False negatives are unquantified.** The round-trip can only catch errors that produce a visible English difference after informalization. Subtle quantifier scope errors, symmetric predicate swaps, or logically distinct but NL-similar structures may slip through.

3. **Comparator classification has noise.** 5 structural items had `category: none` — the comparator flagged a mismatch but didn't assign a category. These default to surface severity under the conservative assumption.

## Method

- Mode: gold (uses FOLIO's gold FOL annotations, no LLM formalization)
- Model: default (sonnet)
- Dataset: FOLIO validation set, 204 examples, 1292 total statements
- Comparator: two-tier (structural vs surface), see `claimcheck.py`
