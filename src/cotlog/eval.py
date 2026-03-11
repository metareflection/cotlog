"""Evaluation harness: run FOLIO examples through the prover pipeline."""

from __future__ import annotations

import io
import json
import sys
import time
from collections import Counter
from datetime import datetime
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
    records: list[dict] = []

    for i, ex in enumerate(examples):
        total += 1
        t0 = time.monotonic()
        error_msg: str | None = None
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
            error_msg = str(e)
            if verbose:
                print(f"  [{i}] ERROR: {e}", file=sys.stderr)

        elapsed = time.monotonic() - t0
        confusion[(ex.label, predicted)] += 1
        is_correct = predicted == ex.label
        if is_correct:
            correct += 1
        else:
            mismatches.append({
                'index': i,
                'gold': ex.label,
                'predicted': predicted,
                'conclusion': ex.conclusion,
                'conclusion_fol': ex.conclusion_fol,
            })

        records.append({
            'index': i,
            'gold_label': ex.label,
            'predicted_label': predicted,
            'correct': is_correct,
            'conclusion': ex.conclusion,
            'conclusion_fol': ex.conclusion_fol,
            'premises': ex.premises,
            'premises_fol': ex.premises_fol,
            'error': error_msg,
            'elapsed_s': round(elapsed, 3),
        })

        if verbose:
            status = 'OK' if is_correct else 'MISS'
            print(f"  [{i:3d}] {status}  gold={ex.label:<10s} pred={predicted:<10s}  {ex.conclusion_fol}")

    accuracy = correct / total if total > 0 else 0.0
    return {
        'total': total,
        'correct': correct,
        'errors': errors,
        'accuracy': accuracy,
        'confusion': dict(confusion),
        'mismatches': mismatches,
        'records': records,
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
    records: list[dict] = []

    for i, ex in enumerate(examples):
        total += 1
        t0 = time.monotonic()
        error_msg: str | None = None
        llm_response: str | None = None
        llm_premises_fol: list[str] | None = None
        llm_conclusion_fol: str | None = None
        szs_status: str | None = None
        try:
            gen_result = generate_fol(
                ex.premises, ex.conclusion, model=model,
            )
            llm_response = gen_result.raw_response
            llm_premises_fol = gen_result.premises_fol
            llm_conclusion_fol = gen_result.conclusion_fol
            if verbose:
                print(f"  [{i:3d}] LLM FOL premises: {gen_result.premises_fol}", file=sys.stderr)
                print(f"  [{i:3d}] LLM FOL conclusion: {gen_result.conclusion_fol}", file=sys.stderr)

            premises_ast = [parse_fol(p) for p in gen_result.premises_fol]
            conjecture_ast = parse_fol(gen_result.conclusion_fol)
            result = prove_example(
                premises_tptp=[],
                conjecture_tptp='',
                premises_ast=premises_ast,
                conjecture_ast=conjecture_ast,
                cpu_limit=cpu_limit,
            )
            predicted = result.label
            szs_status = result.szs_status
        except ValueError as e:
            parse_failures += 1
            errors += 1
            predicted = 'Error'
            error_msg = str(e)
            if verbose:
                print(f"  [{i}] PARSE ERROR: {e}", file=sys.stderr)
        except Exception as e:
            errors += 1
            predicted = 'Error'
            error_msg = str(e)
            if verbose:
                print(f"  [{i}] ERROR: {e}", file=sys.stderr)

        elapsed = time.monotonic() - t0
        confusion[(ex.label, predicted)] += 1
        is_correct = predicted == ex.label
        if is_correct:
            correct += 1
        else:
            mismatches.append({
                'index': i,
                'gold': ex.label,
                'predicted': predicted,
                'conclusion': ex.conclusion,
            })

        records.append({
            'index': i,
            'gold_label': ex.label,
            'predicted_label': predicted,
            'correct': is_correct,
            'conclusion': ex.conclusion,
            'conclusion_fol': ex.conclusion_fol,
            'premises': ex.premises,
            'premises_fol': ex.premises_fol,
            'error': error_msg,
            'elapsed_s': round(elapsed, 3),
            'llm_response': llm_response,
            'llm_premises_fol': llm_premises_fol,
            'llm_conclusion_fol': llm_conclusion_fol,
            'szs_status': szs_status,
        })

        if verbose:
            status = 'OK' if is_correct else 'MISS'
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
        'records': records,
    }


def evaluate_refine(
    examples: list[FolioExample],
    cpu_limit: int = 30,
    verbose: bool = False,
    model: str | None = None,
    max_iterations: int = 3,
    stability_n: int = 5,
    stability_threshold: float = 0.9,
) -> dict:
    """Run all examples through the refinement loop.

    Reports stability improvement and faithfulness.
    """
    from .refine import refine_loop

    total = 0
    errors = 0
    stability_improved = 0
    total_delta_s = 0.0
    records: list[dict] = []

    for i, ex in enumerate(examples):
        total += 1
        t0 = time.monotonic()
        error_msg: str | None = None
        try:
            result = refine_loop(
                ex.premises, ex.conclusion,
                model=model,
                cpu_limit=cpu_limit,
                max_iterations=max_iterations,
                stability_n=stability_n,
                stability_threshold=stability_threshold,
                verbose=verbose,
            )

            s0 = result.initial_stability.agreement_rate if result.initial_stability else 0.0
            sf = result.final_stability.agreement_rate if result.final_stability else 0.0
            delta_s = sf - s0
            total_delta_s += delta_s
            if delta_s > 0:
                stability_improved += 1

            if verbose:
                print(f"  [{i:3d}] S0={s0:.0%} Sf={sf:.0%} ΔS={delta_s:+.0%} "
                      f"iters={result.total_iterations}")

            record = {
                'index': i,
                'gold_label': ex.label,
                'conclusion': ex.conclusion,
                'premises': ex.premises,
                'error': None,
                'elapsed_s': round(time.monotonic() - t0, 3),
            }
            record.update(result.to_record())
            records.append(record)

        except Exception as e:
            errors += 1
            error_msg = str(e)
            if verbose:
                print(f"  [{i}] ERROR: {e}", file=sys.stderr)
            records.append({
                'index': i,
                'gold_label': ex.label,
                'conclusion': ex.conclusion,
                'premises': ex.premises,
                'error': error_msg,
                'elapsed_s': round(time.monotonic() - t0, 3),
            })

    avg_delta_s = total_delta_s / total if total > 0 else 0.0

    return {
        'total': total,
        'errors': errors,
        'stability_improved': stability_improved,
        'avg_delta_s': avg_delta_s,
        'records': records,
    }


def evaluate_cot(examples: list[FolioExample], cpu_limit: int = 30, verbose: bool = False, model: str | None = None) -> dict:
    """Run all examples using CoT verification.

    Reports verification statistics rather than accuracy — the CoT pipeline
    checks internal consistency of the LLM's reasoning, not agreement with
    gold labels.
    """
    from .cot_verify import verify_cot

    total = 0
    errors = 0
    total_steps = 0
    verified_steps = 0
    fully_verified = 0  # all steps + conclusion verified
    conclusion_verified = 0  # conclusion proved from accumulated knowledge
    total_rounds = 0
    records: list[dict] = []

    for i, ex in enumerate(examples):
        total += 1
        t0 = time.monotonic()
        error_msg: str | None = None
        result = None
        try:
            result = verify_cot(
                ex.premises, ex.conclusion,
                model=model, cpu_limit=cpu_limit,
            )

            total_rounds += result.rounds

            for step in result.steps:
                total_steps += 1
                if step.verified:
                    verified_steps += 1

            if result.all_steps_verified and result.verified_label in ('True', 'False'):
                fully_verified += 1

            if result.verified_label in ('True', 'False'):
                conclusion_verified += 1

            if verbose:
                n_verified = sum(1 for s in result.steps if s.verified)
                print(f"  [{i:3d}] Steps: {n_verified}/{len(result.steps)} verified, "
                      f"conclusion={result.verified_label}, "
                      f"llm_answer={result.llm_answer}, rounds={result.rounds}")
                for step in result.steps:
                    mark = 'V' if step.verified else 'X'
                    print(f"        [{mark}] Step {step.step_num}: {step.fol_str}")
                    if step.error:
                        print(f"             Error: {step.error}")

        except Exception as e:
            errors += 1
            error_msg = str(e)
            if verbose:
                print(f"  [{i}] ERROR: {e}", file=sys.stderr)

        elapsed = time.monotonic() - t0

        record = {
            'index': i,
            'gold_label': ex.label,
            'conclusion': ex.conclusion,
            'premises': ex.premises,
            'error': error_msg,
            'elapsed_s': round(elapsed, 3),
        }
        if result is not None:
            record.update(result.to_record())
        records.append(record)

    step_verification_rate = verified_steps / total_steps if total_steps > 0 else 0.0
    avg_rounds = total_rounds / total if total > 0 else 0.0

    return {
        'total': total,
        'errors': errors,
        'fully_verified': fully_verified,
        'conclusion_verified': conclusion_verified,
        'total_steps': total_steps,
        'verified_steps': verified_steps,
        'step_verification_rate': step_verification_rate,
        'avg_rounds': avg_rounds,
        'records': records,
    }


def print_report(results: dict, mode: str = 'gold') -> None:
    """Print a human-readable evaluation report."""
    print(f"\n{'='*60}")
    print(f"FOLIO Evaluation Report (mode={mode})")
    print(f"{'='*60}")
    print(f"Total:    {results['total']}")
    print(f"Errors:   {results['errors']}")

    if mode == 'cot':
        _print_cot_report(results)
        return
    if mode == 'refine':
        _print_refine_report(results)
        return

    print(f"Correct:  {results['correct']}")
    print(f"Accuracy: {results['accuracy']:.1%}")

    if mode == 'llm':
        print(f"Parse failures: {results.get('parse_failures', 0)}")

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


def _print_refine_report(results: dict) -> None:
    """Print refinement loop statistics."""
    total = results['total']
    print(f"\nRefinement Summary:")
    print(f"  Stability improved:  {results['stability_improved']}/{total}"
          f"  ({results['stability_improved']/total:.0%})" if total else "")
    print(f"  Avg ΔS:              {results['avg_delta_s']:+.1%}")

    # Per-example breakdown
    for rec in results['records']:
        if rec.get('error'):
            continue
        init = rec.get('initial_stability')
        final = rec.get('final_stability')
        if init and final:
            s0 = init['agreement_rate']
            sf = final['agreement_rate']
            print(f"  [{rec['index']:3d}] S0={s0:.0%} → Sf={sf:.0%} "
                  f"(ΔS={sf-s0:+.0%}, iters={rec.get('total_iterations', 0)})")


def _print_cot_report(results: dict) -> None:
    """Print CoT verification statistics."""
    total = results['total']
    print(f"\nVerification Summary:")
    print(f"  Fully verified:      {results['fully_verified']}/{total}"
          f"  ({results['fully_verified']/total:.0%})" if total else "")
    print(f"  Conclusion verified: {results['conclusion_verified']}/{total}"
          f"  ({results['conclusion_verified']/total:.0%})" if total else "")
    print(f"\nStep-Level Stats:")
    print(f"  Total steps:         {results['total_steps']}")
    print(f"  Verified steps:      {results['verified_steps']}")
    print(f"  Step verify rate:    {results['step_verification_rate']:.1%}")
    print(f"  Avg rounds/example:  {results['avg_rounds']:.1f}")


def write_results(results: dict, mode: str, output_dir: Path) -> None:
    """Write JSONL and TXT result files for a completed evaluation run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    basename = f"{mode}_{timestamp}"

    jsonl_path = output_dir / f"{basename}.jsonl"
    txt_path = output_dir / f"{basename}.txt"

    # Write JSONL
    with open(jsonl_path, 'w') as f:
        for record in results['records']:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    # Capture print_report output to string and also print to stdout
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    print_report(results, mode=mode)
    sys.stdout = old_stdout
    report_text = buf.getvalue()

    # Print to stdout
    sys.stdout.write(report_text)

    # Write TXT
    with open(txt_path, 'w') as f:
        f.write(report_text)

    print(f"Results written to:")
    print(f"  {jsonl_path}")
    print(f"  {txt_path}")


# Keep backward compat
evaluate = evaluate_gold


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Run FOLIO evaluation')
    parser.add_argument('--mode', choices=['gold', 'llm', 'cot', 'refine'], default='gold',
                        help='Evaluation mode: gold (gold FOL), llm (LLM FOL gen), cot (CoT verification), refine (refinement loop)')
    parser.add_argument('--model', type=str, default=None,
                        help='LLM model name (for llm/cot modes)')
    parser.add_argument('--data', type=Path, default=None, help='Path to FOLIO JSONL')
    parser.add_argument('--limit', type=int, default=None, help='Max examples to evaluate')
    parser.add_argument('--cpu-limit', type=int, default=30, help='E-prover CPU limit per problem')
    parser.add_argument('--max-iterations', type=int, default=3, help='Max refinement iterations (refine mode)')
    parser.add_argument('--stability-n', type=int, default=5, help='Number of independent formalizations for stability (refine mode)')
    parser.add_argument('--stability-threshold', type=float, default=0.9, help='Stability threshold to stop (refine mode)')
    parser.add_argument('--output-dir', type=Path, default=Path('results'),
                        help='Directory for result files (default: results/)')
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
    elif args.mode == 'refine':
        results = evaluate_refine(
            examples, cpu_limit=args.cpu_limit, verbose=args.verbose, model=args.model,
            max_iterations=args.max_iterations, stability_n=args.stability_n,
            stability_threshold=args.stability_threshold,
        )
    else:
        raise ValueError(f"Unknown mode: {args.mode}")

    write_results(results, mode=args.mode, output_dir=args.output_dir)


if __name__ == '__main__':
    main()
