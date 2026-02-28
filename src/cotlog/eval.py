"""Evaluation harness: run FOLIO examples through the prover pipeline."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from .folio import FolioExample, load_folio
from .fol_parser import parse_fol
from .prover import prove_example


def evaluate_gold(examples: list[FolioExample], cpu_limit: int = 30, verbose: bool = False) -> dict:
    """Run all examples using gold FOL annotations and return evaluation results."""
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


def evaluate_llm(examples: list[FolioExample], cpu_limit: int = 30, verbose: bool = False, model: str | None = None) -> dict:
    """Run all examples using LLM-generated FOL, then verify via prover."""
    from .fol_gen import generate_fol

    correct = 0
    total = 0
    errors = 0
    parse_failures = 0
    confusion: Counter[tuple[str, str]] = Counter()
    mismatches: list[dict] = []

    for i, ex in enumerate(examples):
        total += 1
        try:
            premises_fol, conclusion_fol = generate_fol(
                ex.premises, ex.conclusion, model=model,
            )
            if verbose:
                print(f"  [{i:3d}] LLM FOL premises: {premises_fol}", file=sys.stderr)
                print(f"  [{i:3d}] LLM FOL conclusion: {conclusion_fol}", file=sys.stderr)

            premises_ast = [parse_fol(p) for p in premises_fol]
            conjecture_ast = parse_fol(conclusion_fol)
            result = prove_example(
                premises_tptp=[],
                conjecture_tptp='',
                premises_ast=premises_ast,
                conjecture_ast=conjecture_ast,
                cpu_limit=cpu_limit,
            )
            predicted = result.label
        except ValueError as e:
            parse_failures += 1
            errors += 1
            predicted = 'Error'
            if verbose:
                print(f"  [{i}] PARSE ERROR: {e}", file=sys.stderr)
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
            })

        if verbose:
            status = 'OK' if predicted == ex.label else 'MISS'
            print(f"  [{i:3d}] {status}  gold={ex.label:<10s} pred={predicted:<10s}  {ex.conclusion}")

    accuracy = correct / total if total > 0 else 0.0
    return {
        'total': total,
        'correct': correct,
        'errors': errors,
        'parse_failures': parse_failures,
        'accuracy': accuracy,
        'confusion': dict(confusion),
        'mismatches': mismatches,
    }


def evaluate_cot(examples: list[FolioExample], cpu_limit: int = 30, verbose: bool = False, model: str | None = None) -> dict:
    """Run all examples using CoT verification."""
    from .cot_verify import verify_cot

    correct = 0
    total = 0
    errors = 0
    total_steps = 0
    verified_steps = 0
    llm_answer_correct = 0
    confusion: Counter[tuple[str, str]] = Counter()
    mismatches: list[dict] = []

    for i, ex in enumerate(examples):
        total += 1
        try:
            result = verify_cot(
                ex.premises, ex.conclusion,
                ex.premises_fol, ex.conclusion_fol,
                model=model, cpu_limit=cpu_limit,
            )

            # Count step-level stats
            for step in result.steps:
                total_steps += 1
                if step.verified:
                    verified_steps += 1

            # LLM's own answer accuracy
            if result.llm_answer == ex.label:
                llm_answer_correct += 1

            predicted = result.verified_label or 'Uncertain'

            if verbose:
                print(f"  [{i:3d}] Steps: {len(result.steps)}, "
                      f"verified: {sum(1 for s in result.steps if s.verified)}/{len(result.steps)}, "
                      f"llm_answer={result.llm_answer}, prover_label={predicted}")
                for step in result.steps:
                    mark = 'V' if step.verified else 'X'
                    print(f"        [{mark}] Step {step.step_num}: {step.fol_str}")
                    if step.error:
                        print(f"             Error: {step.error}")

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
            })

    accuracy = correct / total if total > 0 else 0.0
    step_verification_rate = verified_steps / total_steps if total_steps > 0 else 0.0
    llm_answer_accuracy = llm_answer_correct / total if total > 0 else 0.0

    return {
        'total': total,
        'correct': correct,
        'errors': errors,
        'accuracy': accuracy,
        'total_steps': total_steps,
        'verified_steps': verified_steps,
        'step_verification_rate': step_verification_rate,
        'llm_answer_correct': llm_answer_correct,
        'llm_answer_accuracy': llm_answer_accuracy,
        'confusion': dict(confusion),
        'mismatches': mismatches,
    }


def print_report(results: dict, mode: str = 'gold') -> None:
    """Print a human-readable evaluation report."""
    print(f"\n{'='*60}")
    print(f"FOLIO Evaluation Report (mode={mode})")
    print(f"{'='*60}")
    print(f"Total:    {results['total']}")
    print(f"Correct:  {results['correct']}")
    print(f"Errors:   {results['errors']}")
    print(f"Accuracy: {results['accuracy']:.1%}")

    if mode == 'llm':
        print(f"Parse failures: {results.get('parse_failures', 0)}")

    if mode == 'cot':
        print(f"\nCoT Step-Level Stats:")
        print(f"  Total steps:    {results['total_steps']}")
        print(f"  Verified steps: {results['verified_steps']}")
        print(f"  Step verify rate: {results['step_verification_rate']:.1%}")
        print(f"  LLM answer accuracy: {results['llm_answer_accuracy']:.1%}")

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
            detail = m.get('conclusion_fol', m.get('conclusion', ''))
            print(f"  [{m['index']:3d}] gold={m['gold']:<10s} pred={m['predicted']:<10s} {detail}")
        if len(results['mismatches']) > 20:
            print(f"  ... and {len(results['mismatches']) - 20} more")


# Keep backward compat
evaluate = evaluate_gold


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Run FOLIO evaluation')
    parser.add_argument('--mode', choices=['gold', 'llm', 'cot'], default='gold',
                        help='Evaluation mode: gold (gold FOL), llm (LLM FOL gen), cot (CoT verification)')
    parser.add_argument('--model', type=str, default=None,
                        help='LLM model name (for llm/cot modes)')
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

    print(f"Evaluating {len(examples)} FOLIO examples (mode={args.mode})...")

    if args.mode == 'gold':
        results = evaluate_gold(examples, cpu_limit=args.cpu_limit, verbose=args.verbose)
    elif args.mode == 'llm':
        results = evaluate_llm(examples, cpu_limit=args.cpu_limit, verbose=args.verbose, model=args.model)
    elif args.mode == 'cot':
        results = evaluate_cot(examples, cpu_limit=args.cpu_limit, verbose=args.verbose, model=args.model)
    else:
        raise ValueError(f"Unknown mode: {args.mode}")

    print_report(results, mode=args.mode)


if __name__ == '__main__':
    main()
