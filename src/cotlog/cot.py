"""Standalone chain-of-thought verification.

Usage:
    python -m cotlog.cot --premise "All humans are mortal." --premise "Socrates is human." --conclusion "Socrates is mortal."
    python -m cotlog.cot input.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cot_verify import verify_cot


def print_result(result, premises: list[str], conclusion: str, verbose: bool = False) -> None:
    """Print a human-readable CoT verification result."""
    print("Premises:")
    for i, p in enumerate(premises, 1):
        print(f"  {i}. {p}")
    print(f"Conclusion: {conclusion}")

    if result.premise_fols:
        print("\nFormalized premises:")
        for i, p in enumerate(result.premise_fols, 1):
            print(f"  {i}. {p}")
    if result.conclusion_fol:
        print(f"Formalized conclusion: {result.conclusion_fol}")

    print("\nReasoning steps:")
    for step in result.steps:
        mark = 'V' if step.verified else 'X' if step.verified is False else '?'
        print(f"  [{mark}] Step {step.step_num}: {step.fol_str}")
        if verbose and step.reasoning:
            print(f"        {step.reasoning}")
        if step.error:
            print(f"        Error: {step.error}")

    verified = result.verified_label == result.llm_answer
    status = "verified" if verified else f"prover says {result.verified_label}"
    print(f"\nAnswer: {result.llm_answer} ({status})")
    if result.rounds > 1:
        print(f"Rounds: {result.rounds}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description='Run chain-of-thought verification on arbitrary premises and conclusion.',
    )
    parser.add_argument('input_file', nargs='?', type=Path, default=None,
                        help='JSON file with {"premises": [...], "conclusion": "..."}')
    parser.add_argument('--premise', action='append', dest='premises', default=[],
                        help='Natural language premise (repeat for multiple)')
    parser.add_argument('--conclusion', type=str, default=None,
                        help='Natural language conclusion')
    parser.add_argument('--model', type=str, default=None,
                        help='LLM model name (default: sonnet)')
    parser.add_argument('--cpu-limit', type=int, default=30,
                        help='E-prover CPU limit per step (default: 30)')
    parser.add_argument('--max-retries', type=int, default=2,
                        help='Max feedback loop retries (default: 2)')
    parser.add_argument('--json', action='store_true', dest='json_output',
                        help='Output raw JSON instead of human-readable')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args(argv)

    # Resolve input
    if args.input_file:
        with open(args.input_file) as f:
            data = json.load(f)
        premises = data['premises']
        conclusion = data['conclusion']
    elif args.premises and args.conclusion:
        premises = args.premises
        conclusion = args.conclusion
    else:
        parser.error('Provide either a JSON file or --premise/--conclusion flags.')

    result = verify_cot(
        premises, conclusion,
        model=args.model,
        cpu_limit=args.cpu_limit,
        max_retries=args.max_retries,
    )

    if args.json_output:
        out = result.to_record()
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print_result(result, premises, conclusion, verbose=args.verbose)


if __name__ == '__main__':
    main()
