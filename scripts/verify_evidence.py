"""Verify FOLIO_EVIDENCE.jsonl against the actual v1 and v2 datasets.

For each evidence record, checks that:
1. The v1 NL and FOL match what's in the v1 dataset at the claimed index
2. The v2 NL and FOL match (if a v2 match was found)
3. For "fixed" patterns: the v2 FOL actually differs from v1
4. For "removed" patterns: no matching example exists in v2
5. For "not_fixed": the v2 FOL is unchanged or still has the same issue

Prints a per-pattern verification report. Exits with code 1 if any
mechanical check fails (NL/FOL mismatch against dataset).

Does NOT judge whether an error is real — that's for human review.
The columns marked [HUMAN] require manual verification.

Usage:
    uv run python scripts/verify_evidence.py          # full report
    uv run python scripts/verify_evidence.py --human   # human review checklist only
"""

import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

V1_PATH = Path("data/folio/data/v0.0/folio-validation.jsonl")
V2_PATH = Path("data/folio/data/v2/folio_v2_validation.jsonl")
EVIDENCE_PATH = Path("results/FOLIO_EVIDENCE.jsonl")


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def to_list(val):
    if isinstance(val, list):
        return val
    return [s for s in val.split("\n") if s.strip()]


def similarity(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_v2_match(v1_ex, v2_data):
    v1_conc = v1_ex["conclusion"].strip()
    best = None
    best_score = 0
    for i, e in enumerate(v2_data):
        score = similarity(v1_conc, e["conclusion"].strip())
        if score > 0.8:
            v1_p0 = v1_ex["premises"][0].strip()[:100] if v1_ex["premises"] else ""
            v2_premises = to_list(e["premises"])
            v2_p0 = v2_premises[0].strip()[:100] if v2_premises else ""
            combined = score * 0.5 + similarity(v1_p0, v2_p0) * 0.5
            if combined > best_score:
                best_score = combined
                best = (i, e)
    return best if best_score > 0.6 else None


def print_human_checklist(evidence):
    """Print standalone human review checklist."""
    print("FOLIO ERROR PATTERNS — HUMAN REVIEW CHECKLIST")
    print("=" * 70)
    print()
    print("For each pattern below, verify:")
    print("  1. The FOL does not faithfully represent the NL (i.e., it's a real bug)")
    print("  2. The v2 status is correct (fixed / removed / not fixed)")
    print()
    print("Mark each with: [Y] confirmed  [N] not a real error  [?] uncertain")
    print()

    for rec in evidence:
        pid = rec["pattern_id"]
        pattern = rec["pattern"]
        v2_status = rec["v2_status"]

        print(f"{'─'*70}")
        print(f"Pattern {pid}: {pattern}")
        print(f"v2 status: {v2_status}")
        print(f"v1 examples: {rec['v1_example_indices']} (0-indexed in folio-validation.jsonl)")
        print()
        print(f"Claimed error: {rec['error']}")
        print()

        for stmt in rec["affected_statements"]:
            pos = stmt["position"]
            print(f"  {pos}:")
            print(f"    NL:      {stmt['v1_nl']}")
            print(f"    FOL:     {stmt['v1_fol']}")
            if stmt.get("v2_fol"):
                print(f"    v2 FOL:  {stmt['v2_fol']}")
                if stmt.get("v2_nl"):
                    print(f"    v2 NL:   {stmt['v2_nl']}")
            print()

        print(f"  [ ] Is this a real formalization error?")
        if v2_status == "not_fixed":
            print(f"  [ ] Does the same error persist in v2?")
        elif v2_status == "partially_fixed":
            print(f"  [ ] Which parts are fixed and which remain?")
        elif v2_status == "fixed":
            print(f"  [ ] Does the v2 FOL resolve the error?")
        elif v2_status == "removed":
            print(f"  [ ] (No v2 check needed — example was removed)")
        print()


def main():
    parser = argparse.ArgumentParser(description="Verify FOLIO evidence")
    parser.add_argument("--human", action="store_true",
                        help="Print human review checklist only (no mechanical checks)")
    args = parser.parse_args()

    evidence = load_jsonl(EVIDENCE_PATH)

    if args.human:
        print_human_checklist(evidence)
        return

    v1_data = load_jsonl(V1_PATH)
    v2_data = load_jsonl(V2_PATH)

    failures = 0
    total_checks = 0

    for rec in evidence:
        pid = rec["pattern_id"]
        pattern = rec["pattern"]
        v1_idx = rec["v1_representative_index"]
        v1_ex = v1_data[v1_idx]
        v1_premises = v1_ex["premises"] if isinstance(v1_ex["premises"], list) else v1_ex["premises"].split("\n")
        v1_fols = v1_ex["premises-FOL"] if isinstance(v1_ex["premises-FOL"], list) else v1_ex["premises-FOL"].split("\n")

        print(f"\n{'='*70}")
        print(f"Pattern {pid}: {pattern}")
        print(f"  v1 index: {v1_idx}, v2 status: {rec['v2_status']}")
        print(f"  Error: {rec['error'][:100]}")
        print(f"{'='*70}")

        # --- Check 1: v1 data matches evidence ---
        for stmt in rec["affected_statements"]:
            total_checks += 1
            pos = stmt["position"]

            if pos == "conclusion":
                actual_nl = v1_ex["conclusion"].strip()
                actual_fol = v1_ex["conclusion-FOL"].strip()
            else:
                pidx = int(pos[1:])
                actual_nl = v1_premises[pidx].strip() if pidx < len(v1_premises) else "[OUT OF RANGE]"
                actual_fol = v1_fols[pidx].strip() if pidx < len(v1_fols) else "[OUT OF RANGE]"

            claimed_nl = stmt["v1_nl"].strip()
            claimed_fol = stmt["v1_fol"].strip()

            nl_match = actual_nl == claimed_nl
            fol_match = actual_fol == claimed_fol

            if nl_match and fol_match:
                print(f"  [PASS] {pos}: v1 NL and FOL match dataset")
            else:
                failures += 1
                if not nl_match:
                    print(f"  [FAIL] {pos}: v1 NL mismatch")
                    print(f"         Evidence: {claimed_nl[:80]}")
                    print(f"         Dataset:  {actual_nl[:80]}")
                if not fol_match:
                    print(f"  [FAIL] {pos}: v1 FOL mismatch")
                    print(f"         Evidence: {claimed_fol[:80]}")
                    print(f"         Dataset:  {actual_fol[:80]}")

            # Show the error for human review
            print(f"  [HUMAN] {pos}: Is this a real error?")
            print(f"          NL:  {claimed_nl[:100]}")
            print(f"          FOL: {claimed_fol[:100]}")

        # --- Check 2: v2 status ---
        total_checks += 1
        v2_match = find_v2_match(v1_ex, v2_data)

        if rec["v2_status"] == "removed":
            if v2_match is None:
                print(f"  [PASS] v2 status 'removed': no matching example found in v2")
            else:
                v2_idx, _ = v2_match
                print(f"  [WARN] v2 status 'removed' but found potential match at v2 index {v2_idx}")
                print(f"         May be a false match — verify manually")
        elif v2_match is None:
            print(f"  [WARN] v2 match not found (NL rewritten too much for fuzzy matching)")
            print(f"         Manual verification needed for v2 status '{rec['v2_status']}'")
        else:
            v2_idx, v2_ex = v2_match
            v2_premises = to_list(v2_ex["premises"])
            v2_fols = to_list(v2_ex["premises-FOL"])

            print(f"  [INFO] v2 matched at index {v2_idx}")

            for stmt in rec["affected_statements"]:
                pos = stmt["position"]
                if stmt.get("v2_fol") is None:
                    print(f"  [SKIP] {pos}: no v2 data in evidence")
                    continue

                total_checks += 1
                claimed_v2_fol = stmt["v2_fol"].strip()

                if pos == "conclusion":
                    actual_v2_fol = v2_ex["conclusion-FOL"].strip()
                else:
                    # Use v2_premise_idx if available (NL-matched), fall back to positional
                    v2_pidx = stmt.get("v2_premise_idx")
                    if v2_pidx is None:
                        v2_pidx = int(pos[1:])
                    actual_v2_fol = v2_fols[v2_pidx].strip() if v2_pidx < len(v2_fols) else "[OUT OF RANGE]"

                v2_fol_match = actual_v2_fol == claimed_v2_fol
                if v2_fol_match:
                    print(f"  [PASS] {pos}: v2 FOL matches dataset")
                else:
                    # Check if it's close (whitespace differences)
                    if actual_v2_fol.replace(" ", "") == claimed_v2_fol.replace(" ", ""):
                        print(f"  [PASS] {pos}: v2 FOL matches (whitespace difference only)")
                    else:
                        failures += 1
                        print(f"  [FAIL] {pos}: v2 FOL mismatch")
                        print(f"         Evidence: {claimed_v2_fol[:80]}")
                        print(f"         Dataset:  {actual_v2_fol[:80]}")

                # Check v1 vs v2 FOL change
                v1_fol = stmt["v1_fol"].strip().replace(" ", "")
                v2_fol = actual_v2_fol.strip().replace(" ", "")
                fol_changed = v1_fol != v2_fol

                if rec["v2_status"] == "fixed":
                    if fol_changed:
                        print(f"  [PASS] {pos}: v2 FOL differs from v1 (consistent with 'fixed')")
                    else:
                        print(f"  [WARN] {pos}: v2 FOL identical to v1 but status is 'fixed'")
                        print(f"         NL may have been rewritten instead — check v2 NL")
                elif rec["v2_status"] == "not_fixed":
                    print(f"  [HUMAN] {pos}: v2 status 'not_fixed' — verify the error persists")
                    print(f"          v1 FOL: {stmt['v1_fol'][:80]}")
                    print(f"          v2 FOL: {actual_v2_fol[:80]}")
                elif rec["v2_status"] == "partially_fixed":
                    print(f"  [HUMAN] {pos}: v2 status 'partially_fixed' — verify what changed")
                    print(f"          v1 FOL: {stmt['v1_fol'][:80]}")
                    print(f"          v2 FOL: {actual_v2_fol[:80]}")

    # --- Summary ---
    print(f"\n{'='*70}")
    print(f"VERIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"Total mechanical checks: {total_checks}")
    print(f"Failures: {failures}")
    if failures == 0:
        print("All mechanical checks passed.")
        print("Review [HUMAN] items above to confirm errors are real.")
    else:
        print(f"{failures} mechanical check(s) failed — evidence file may be stale.")
        print("Re-run: uv run python scripts/generate_evidence.py")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
