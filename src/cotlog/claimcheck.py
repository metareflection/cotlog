"""Claimcheck for FOL: round-trip verification of NL ↔ FOL faithfulness.

Formalizes NL premises to FOL, informalizes the FOL back to English
(without seeing the original), then compares to find discrepancies.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .fol_gen import generate_fol
from .llm import generate


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class PremiseResult:
    """Round-trip result for a single premise."""
    index: int
    original: str
    fol: str
    back_translation: str
    match: bool
    discrepancy: str  # empty if match
    category: str     # none, weakened, strengthened, scope-change, missing-aspect, wrong-property


@dataclass
class ClaimcheckResult:
    """Full result for one example (all premises + conclusion)."""
    premises: list[str]
    conclusion: str
    premise_results: list[PremiseResult] = field(default_factory=list)
    conclusion_fol: str = ""
    conclusion_back_translation: str = ""
    conclusion_match: bool = True
    conclusion_discrepancy: str = ""
    raw_fol_response: str = ""
    raw_informalize_response: str = ""
    raw_compare_response: str = ""

    def to_record(self) -> dict:
        return {
            'premises': self.premises,
            'conclusion': self.conclusion,
            'conclusion_fol': self.conclusion_fol,
            'conclusion_back_translation': self.conclusion_back_translation,
            'conclusion_match': self.conclusion_match,
            'conclusion_discrepancy': self.conclusion_discrepancy,
            'premise_results': [
                {
                    'index': r.index,
                    'original': r.original,
                    'fol': r.fol,
                    'back_translation': r.back_translation,
                    'match': r.match,
                    'discrepancy': r.discrepancy,
                    'category': r.category,
                }
                for r in self.premise_results
            ],
        }


# ── Pass 1: INFORMALIZE ──────────────────────────────────────────────────────

_INFORMALIZE_SYSTEM = (
    "You are a logician translating first-order logic formulas to plain English. "
    "Be LITERAL — describe what the formula actually says, not what you think "
    "the author intended. You have NOT seen the original natural language."
)

_INFORMALIZE_TEMPLATE = """\
Translate each of the following first-order logic formulas to plain English.

Use this notation reference:
  ∀ (for all), ∃ (there exists), → (implies), ∧ (and), ∨ (or),
  ¬ (not), ⊕ (exclusive or), ↔ (if and only if)
  CamelCase names are predicates, single lowercase letters are variables,
  multi-char lowercase names are constants.

Formulas:
{fol_list}

For each formula, produce a faithful English sentence describing what it says.
Be precise about quantifier scope, logical connectives, and whether conditions
are necessary, sufficient, or both.

Respond in this exact format, one line per formula:
1. [English translation]
2. [English translation]
..."""


def _informalize(fol_strings: list[str], *, model: str | None = None) -> tuple[list[str], str]:
    """Informalize FOL formulas back to English without seeing the originals.

    Returns:
        (back_translations, raw_response)
    """
    fol_list = "\n".join(f"{i+1}. {f}" for i, f in enumerate(fol_strings))
    prompt = _INFORMALIZE_TEMPLATE.format(fol_list=fol_list)
    response = generate(prompt, system=_INFORMALIZE_SYSTEM, model=model)

    import re
    lines = re.findall(r'^\d+\.\s*(.+)$', response, re.MULTILINE)

    # Pad if needed
    while len(lines) < len(fol_strings):
        lines.append("[translation failed]")

    return lines[:len(fol_strings)], response


# ── Pass 2: COMPARE ──────────────────────────────────────────────────────────

_COMPARE_SYSTEM = (
    "You are a specification auditor. You compare original natural language "
    "statements against back-translations produced from formal logic. "
    "Be STRICT — flag any meaning change, not just phrasing differences."
)

_COMPARE_TEMPLATE = """\
Compare each original natural language statement against its back-translation \
(produced by a different model that did NOT see the originals). \
The back-translation was generated from a first-order logic formalization of \
the original.

{pairs}

For each pair, determine:
1. Do they express the same meaning? (yes/no)
2. If no, what specifically changed? Categorize as one of:
   - weakened: the FOL says less than the original
   - strengthened: the FOL says more than the original
   - scope-change: quantifier scope or domain differs
   - missing-aspect: the original has a nuance the FOL dropped
   - wrong-property: the FOL captures a different property entirely

Focus on MEANING, not phrasing. "All cats are mammals" and "Every cat is a \
mammal" match. But "All cats are mammals" and "Some cats are mammals" do not.

Respond in this exact JSON format:
```json
[
  {{"index": 0, "match": true, "discrepancy": "", "category": "none"}},
  {{"index": 1, "match": false, "discrepancy": "Original says X but back-translation says Y", "category": "weakened"}}
]
```"""


def _compare(
    originals: list[str],
    back_translations: list[str],
    *,
    model: str | None = None,
) -> tuple[list[dict], str]:
    """Compare originals against back-translations.

    Returns:
        (comparisons, raw_response) where each comparison is
        {index, match, discrepancy, category}
    """
    pairs = "\n\n".join(
        f"### Statement {i}\n"
        f"**Original:** {orig}\n"
        f"**Back-translation:** {bt}"
        for i, (orig, bt) in enumerate(zip(originals, back_translations))
    )
    prompt = _COMPARE_TEMPLATE.format(pairs=pairs)
    response = generate(prompt, system=_COMPARE_SYSTEM, model=model)

    # Extract JSON from response
    import re
    json_match = re.search(r'\[.*\]', response, re.DOTALL)
    if json_match:
        try:
            comparisons = json.loads(json_match.group())
            return comparisons, response
        except json.JSONDecodeError:
            pass

    # Fallback: assume all match
    return [
        {"index": i, "match": True, "discrepancy": "", "category": "none"}
        for i in range(len(originals))
    ], response


# ── Main entry point ─────────────────────────────────────────────────────────

def claimcheck(
    premises: list[str],
    conclusion: str,
    *,
    model: str | None = None,
    verbose: bool = False,
) -> ClaimcheckResult:
    """Run claimcheck round-trip on NL premises and conclusion.

    1. Formalize all premises + conclusion to FOL
    2. Informalize the FOL back to English (without seeing originals)
    3. Compare originals vs back-translations
    """
    result = ClaimcheckResult(premises=list(premises), conclusion=conclusion)

    # Step 1: Formalize
    if verbose:
        print("  Formalizing...")
    gen = generate_fol(premises, conclusion, model=model)
    result.raw_fol_response = gen.raw_response
    result.conclusion_fol = gen.conclusion_fol

    all_fol = gen.premises_fol + [gen.conclusion_fol]
    all_originals = list(premises) + [conclusion]

    if verbose:
        for i, (orig, fol) in enumerate(zip(all_originals, all_fol)):
            label = f"P{i+1}" if i < len(premises) else "C"
            print(f"    {label}: {orig}")
            print(f"        → {fol}")

    # Step 2: Informalize (without seeing originals)
    if verbose:
        print("  Informalizing...")
    back_translations, raw_inf = _informalize(all_fol, model=model)
    result.raw_informalize_response = raw_inf

    if verbose:
        for i, bt in enumerate(back_translations):
            label = f"P{i+1}" if i < len(premises) else "C"
            print(f"    {label} back: {bt}")

    # Step 3: Compare
    if verbose:
        print("  Comparing...")
    comparisons, raw_cmp = _compare(all_originals, back_translations, model=model)
    result.raw_compare_response = raw_cmp

    # Build results
    comp_by_index = {c["index"]: c for c in comparisons}

    for i, premise in enumerate(premises):
        comp = comp_by_index.get(i, {"match": True, "discrepancy": "", "category": "none"})
        result.premise_results.append(PremiseResult(
            index=i,
            original=premise,
            fol=gen.premises_fol[i] if i < len(gen.premises_fol) else "",
            back_translation=back_translations[i] if i < len(back_translations) else "",
            match=comp.get("match", True),
            discrepancy=comp.get("discrepancy", ""),
            category=comp.get("category", "none"),
        ))

    # Conclusion
    conc_idx = len(premises)
    conc_comp = comp_by_index.get(conc_idx, {"match": True, "discrepancy": "", "category": "none"})
    result.conclusion_back_translation = back_translations[conc_idx] if conc_idx < len(back_translations) else ""
    result.conclusion_match = conc_comp.get("match", True)
    result.conclusion_discrepancy = conc_comp.get("discrepancy", "")

    return result


def claimcheck_gold(
    premises: list[str],
    conclusion: str,
    premises_fol: list[str],
    conclusion_fol: str,
    *,
    model: str | None = None,
    verbose: bool = False,
) -> ClaimcheckResult:
    """Run claimcheck round-trip using pre-existing (gold) FOL annotations.

    Skips the formalize step — goes straight to informalize + compare.
    """
    result = ClaimcheckResult(premises=list(premises), conclusion=conclusion)
    result.conclusion_fol = conclusion_fol

    all_fol = list(premises_fol) + [conclusion_fol]
    all_originals = list(premises) + [conclusion]

    if verbose:
        for i, (orig, fol) in enumerate(zip(all_originals, all_fol)):
            label = f"P{i+1}" if i < len(premises) else "C"
            print(f"    {label}: {orig}")
            print(f"        → {fol}")

    # Step 1: Informalize (without seeing originals)
    if verbose:
        print("  Informalizing...")
    back_translations, raw_inf = _informalize(all_fol, model=model)
    result.raw_informalize_response = raw_inf

    if verbose:
        for i, bt in enumerate(back_translations):
            label = f"P{i+1}" if i < len(premises) else "C"
            print(f"    {label} back: {bt}")

    # Step 2: Compare
    if verbose:
        print("  Comparing...")
    comparisons, raw_cmp = _compare(all_originals, back_translations, model=model)
    result.raw_compare_response = raw_cmp

    # Build results
    comp_by_index = {c["index"]: c for c in comparisons}

    for i, premise in enumerate(premises):
        comp = comp_by_index.get(i, {"match": True, "discrepancy": "", "category": "none"})
        result.premise_results.append(PremiseResult(
            index=i,
            original=premise,
            fol=premises_fol[i] if i < len(premises_fol) else "",
            back_translation=back_translations[i] if i < len(back_translations) else "",
            match=comp.get("match", True),
            discrepancy=comp.get("discrepancy", ""),
            category=comp.get("category", "none"),
        ))

    # Conclusion
    conc_idx = len(premises)
    conc_comp = comp_by_index.get(conc_idx, {"match": True, "discrepancy": "", "category": "none"})
    result.conclusion_back_translation = back_translations[conc_idx] if conc_idx < len(back_translations) else ""
    result.conclusion_match = conc_comp.get("match", True)
    result.conclusion_discrepancy = conc_comp.get("discrepancy", "")

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def print_report(results: list[ClaimcheckResult]) -> None:
    """Print a human-readable claimcheck report."""
    total_premises = 0
    mismatches = 0

    for i, r in enumerate(results):
        print(f"\n{'─'*60}")
        print(f"Example {i}")
        print(f"{'─'*60}")

        for pr in r.premise_results:
            total_premises += 1
            status = "✓" if pr.match else "✗"
            if not pr.match:
                mismatches += 1
            print(f"  {status} P{pr.index+1}: {pr.original}")
            if not pr.match:
                print(f"       FOL: {pr.fol}")
                print(f"       Back: {pr.back_translation}")
                print(f"       Issue: {pr.discrepancy} [{pr.category}]")

        status = "✓" if r.conclusion_match else "✗"
        if not r.conclusion_match:
            mismatches += 1
        print(f"  {status} C:  {r.conclusion}")
        if not r.conclusion_match:
            print(f"       FOL: {r.conclusion_fol}")
            print(f"       Back: {r.conclusion_back_translation}")
            print(f"       Issue: {r.conclusion_discrepancy}")

    total = total_premises + len(results)  # premises + conclusions
    print(f"\n{'='*60}")
    print(f"Total statements: {total}")
    print(f"Faithful: {total - mismatches}")
    print(f"Discrepancies: {mismatches}")
    if total:
        print(f"Faithfulness rate: {(total - mismatches) / total:.0%}")


def print_summary(results: list[ClaimcheckResult], mode: str) -> dict:
    """Print summary stats and return them."""
    total = 0
    mismatches = 0
    categories: dict[str, int] = {}

    for r in results:
        for pr in r.premise_results:
            total += 1
            if not pr.match:
                mismatches += 1
                cat = pr.category or "unknown"
                categories[cat] = categories.get(cat, 0) + 1
        total += 1  # conclusion
        if not r.conclusion_match:
            mismatches += 1

    print(f"\n{'='*60}")
    print(f"Claimcheck Summary (mode={mode})")
    print(f"{'='*60}")
    print(f"Total statements: {total}")
    print(f"Faithful: {total - mismatches}")
    print(f"Discrepancies: {mismatches}")
    if total:
        print(f"Faithfulness rate: {(total - mismatches) / total:.0%}")
    if categories:
        print(f"\nDiscrepancy categories:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

    return {'total': total, 'faithful': total - mismatches, 'discrepancies': mismatches, 'categories': categories}


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Claimcheck: NL ↔ FOL round-trip verification')
    parser.add_argument('--mode', choices=['llm', 'gold'], default='llm',
                        help='llm: formalize then round-trip; gold: use gold FOL annotations')
    parser.add_argument('--data', type=Path, default=None,
                        help='JSONL file (default: FOLIO validation set)')
    parser.add_argument('--model', type=str, default=None, help='LLM model name')
    parser.add_argument('--limit', type=int, default=None, help='Max examples')
    parser.add_argument('--output-dir', type=Path, default=Path('results'), help='Output directory')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args(argv)

    from .folio import load_folio
    kwargs = {}
    if args.data:
        kwargs['path'] = args.data
    examples = load_folio(**kwargs)
    if args.limit:
        examples = examples[:args.limit]

    print(f"Running claimcheck ({args.mode}) on {len(examples)} examples...")

    results = []
    records = []
    errors = 0
    for i, ex in enumerate(examples):
        t0 = time.monotonic()
        try:
            if args.mode == 'gold':
                if not ex.premises_fol or not ex.conclusion_fol:
                    raise ValueError("No gold FOL annotations available")
                r = claimcheck_gold(
                    ex.premises, ex.conclusion,
                    ex.premises_fol, ex.conclusion_fol,
                    model=args.model, verbose=args.verbose,
                )
            else:
                r = claimcheck(
                    ex.premises, ex.conclusion,
                    model=args.model, verbose=args.verbose,
                )
            results.append(r)
            rec = r.to_record()
            rec['index'] = i
            rec['gold_label'] = ex.label
            rec['elapsed_s'] = round(time.monotonic() - t0, 3)
            records.append(rec)
        except Exception as e:
            errors += 1
            print(f"  [{i}] ERROR: {e}", file=sys.stderr)
            records.append({'index': i, 'error': str(e), 'elapsed_s': round(time.monotonic() - t0, 3)})

    print_report(results)
    summary = print_summary(results, args.mode)
    if errors:
        print(f"Errors: {errors}")

    # Write results
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    jsonl_path = args.output_dir / f"claimcheck_{args.mode}_{ts}.jsonl"
    with open(jsonl_path, 'w') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(f"\nResults written to: {jsonl_path}")


if __name__ == '__main__':
    main()
