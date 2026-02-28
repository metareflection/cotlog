"""Evaluation harness: run FOLIO examples through the prover pipeline."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from .folio import FolioExample, load_folio
from .fol_parser import parse_fol
from .prover import prove_example


def evaluate(examples: list[FolioExample], cpu_limit: int = 30, verbose: bool = False) -> dict:
    """Run all examples and return evaluation results."""
    correct = 0
    total = 0
    errors = 0
    confusion: Counter[tuple[str, str]] = Counter()  # (gold, predicted)
    mismatches: list[dict] = []

    for i, ex in enumerate(examples):
        total += 1
        try:
            premises_ast = [parse_fol(p) for p in ex.premises_fol]
            conjecture_ast = parse_fol(ex.conclusion_fol)
            result = prove_example(
                premises_tptp=[],
                conjecture_tptp='',
                premises_ast=premises_ast,
                conjecture_ast=conjecture_ast,
                cpu_limit=cpu_limit,
            )
            predicted = result.label
        except Exception as e:
            errors += 1
            predicted = 'Error'
            if verbose:
                print(f"  [{i}] ERROR: {e}", file=sys.stderr)

        confusion[(ex.label, predicted)] += 1
        if predicted == ex.label:
            correct += 1
        else:
            mismatches.append({
                'index': i,
                'gold': ex.label,
                'predicted': predicted,
                'conclusion': ex.conclusion,
                'conclusion_fol': ex.conclusion_fol,
            })

        if verbose:
            status = 'OK' if predicted == ex.label else 'MISS'
            print(f"  [{i:3d}] {status}  gold={ex.label:<10s} pred={predicted:<10s}  {ex.conclusion_fol}")

    accuracy = correct / total if total > 0 else 0.0
    return {
        'total': total,
        'correct': correct,
        'errors': errors,
        'accuracy': accuracy,
        'confusion': dict(confusion),
        'mismatches': mismatches,
    }


def print_report(results: dict) -> None:
    """Print a human-readable evaluation report."""
    print(f"\n{'='*60}")
    print(f"FOLIO Evaluation Report")
    print(f"{'='*60}")
    print(f"Total:    {results['total']}")
    print(f"Correct:  {results['correct']}")
    print(f"Errors:   {results['errors']}")
    print(f"Accuracy: {results['accuracy']:.1%}")
    print()

    # Confusion matrix
    labels = ['True', 'False', 'Uncertain', 'Error']
    print("Confusion Matrix (rows=gold, cols=predicted):")
    print(f"{'':>12s}", end='')
    for pl in labels:
        print(f"{pl:>12s}", end='')
    print()
    for gl in labels[:3]:  # gold labels only
        print(f"{gl:>12s}", end='')
        for pl in labels:
            count = results['confusion'].get((gl, pl), 0)
            print(f"{count:>12d}", end='')
        print()

    # Mismatches
    if results['mismatches']:
        print(f"\nMismatches ({len(results['mismatches'])}):")
        for m in results['mismatches'][:20]:
            print(f"  [{m['index']:3d}] gold={m['gold']:<10s} pred={m['predicted']:<10s} {m['conclusion_fol']}")
        if len(results['mismatches']) > 20:
            print(f"  ... and {len(results['mismatches']) - 20} more")


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Run FOLIO evaluation')
    parser.add_argument('--data', type=Path, default=None, help='Path to FOLIO JSONL')
    parser.add_argument('--limit', type=int, default=None, help='Max examples to evaluate')
    parser.add_argument('--cpu-limit', type=int, default=30, help='E-prover CPU limit per problem')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args(argv)

    kwargs = {}
    if args.data:
        kwargs['path'] = args.data
    examples = load_folio(**kwargs)
    if args.limit:
        examples = examples[:args.limit]

    print(f"Evaluating {len(examples)} FOLIO examples...")
    results = evaluate(examples, cpu_limit=args.cpu_limit, verbose=args.verbose)
    print_report(results)


if __name__ == '__main__':
    main()
