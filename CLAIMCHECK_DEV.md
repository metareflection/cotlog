# Claimcheck: Next Steps

## What we have

A round-trip verification tool (NL → FOL → English → compare) that catches real faithfulness issues in FOL annotations. On 50 FOLIO gold examples: 59% faithfulness rate, with a mix of genuine logic errors and predicate-naming noise.

## Problem: noise vs signal

The comparator flags everything — real logic errors and harmless naming conventions alike. This inflates the discrepancy count and makes the tool hard to trust without manual review.

**Real errors** (affect logical correctness):
- Wrong connective: `∨` instead of `∧`, `⊕` instead of `↔`
- Converse implications: "A implies B" formalized as "B implies A"
- Semantic mismatch: completely wrong property (`¬Love(mia, emma)` for "different favorite seasons")
- Wrong quantifier: `∃` instead of `∀`, or missing quantifier restrictions

**Noise** (inherent FOL limitations or naming conventions):
- Predicate compression: `Signed(x)` for "signed by the author" — the FOL can't name predicates with full NL richness
- Missing domain guards: `∀x (P(x) → Q(x))` without `Employee(x)` — defensible in closed-world settings
- Deontic flattening: "must file" → `Files(x)` — FOL has no modality
- Tense loss: "has hosted" vs "hosted" — FOL is atemporal

## Proposal 1: Two-tier comparator

Split the comparison into structural and surface tiers:

**Structural check** (high signal): Only flag issues where the logical structure differs:
- Connective mismatch (∧/∨/→/↔/⊕)
- Quantifier scope or direction change
- Converse/inverse implications
- Wrong arity or argument order in predicates

**Surface check** (informational): Report but don't count as failures:
- Predicate name doesn't capture full NL meaning
- Missing type guards
- Modality/tense loss

This could be done by adjusting the comparator prompt to categorize severity, or by adding a post-processing step that filters by category. The structural issues are the ones that could flip entailment labels.

## Proposal 2: Validate against entailment labels

We have FOLIO gold labels (True/False/Uncertain) for each conclusion. For each discrepancy claimcheck finds, we can check: does fixing this discrepancy change the entailment label?

- If fixing a "wrong-property" discrepancy flips the label from True to False → confirmed real bug
- If fixing a "missing domain guard" doesn't change the label → noise for this example

This gives us a precision estimate: what fraction of flagged discrepancies are consequential? Run the prover on original gold FOL, then on "corrected" FOL (manually fixed for a sample), compare labels.

This is labor-intensive but would give us a solid number for a paper.

## Proposal 3: Cross-dataset audit tool

The round-trip approach is dataset-agnostic. Any NL↔FOL dataset could be audited:

- **FOLIO** (done): 487 stories, gold FOL annotations
- **LogicNLI**: NL inference with FOL
- **ProofWriter**: synthetic but has NL↔FOL pairs
- **ReClor**: reading comprehension with logical reasoning

Running claimcheck across multiple datasets would reveal whether the annotation quality issues are FOLIO-specific or systemic. If systemic, the tool has value as a standard quality check for FOL annotation projects.

## Proposal 4: Integration with claimcheck for Dafny

The original [claimcheck](../claimcheck) tool works on Dafny specs. The FOL version uses the same architecture (informalize → compare) but a different formal language. These could be unified:

- Shared comparator (the NL↔NL comparison is language-agnostic)
- Shared reporting format and categories
- Pluggable formalizer/informalizer backends (Dafny, FOL, potentially others: Lean, Coq, TLA+)

The value: one tool that audits specification faithfulness across formal languages.

## Proposal 5: Better informalization

The current informalizer reads FOL predicates literally (`TalentShows(x)` → "x is a talent show"). This is by design — literal reading is what reveals predicate compression losses. But it also means every compressed predicate name triggers a false positive.

Alternative: give the informalizer a predicate glossary extracted from the formalization context. "TalentShows(x) means x performs in school talent shows often." Then the informalizer can produce a more faithful English rendering, and any remaining discrepancies are structural, not naming.

Trade-off: this reduces noise but also reduces the tool's ability to catch predicate-naming bugs (where the name is actively misleading, not just abbreviated).

## What to do next

Ordered by effort/impact:

1. **Tighten the comparator prompt** (low effort, high impact): Tell it to ignore predicate-naming losses and focus on structural/logical differences. Re-run on FOLIO 50 to get a cleaner faithfulness number.

2. **Run full FOLIO** (medium effort, medium impact): 204 validation examples. Gets us a publishable number with statistical significance.

3. **Sample validation** (medium effort, high impact): Manually review 30-50 flagged discrepancies. Classify each as true-positive (real logic error) or false-positive (naming noise). This gives us precision.

4. **Cross-dataset** (high effort, high impact): Run on LogicNLI or ProofWriter. If we find similar rates, the story is "FOL annotation quality is systematically worse than assumed."

5. **Unify with Dafny claimcheck** (high effort, medium impact): Makes sense long-term but not urgent for validating the approach.
