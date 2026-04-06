"""Generate FOLIO_EVIDENCE.jsonl from the 12 error patterns in FOLIO_REPORT.md.

Pulls NL and FOL directly from the v1 and v2 datasets, matches examples
across versions, and outputs a machine-readable evidence file.

Usage:
    uv run python scripts/generate_evidence.py
"""

import json
from difflib import SequenceMatcher
from pathlib import Path

V1_PATH = Path("data/folio/data/v0.0/folio-validation.jsonl")
V2_PATH = Path("data/folio/data/v2/folio_v2_validation.jsonl")
OUTPUT = Path("results/FOLIO_EVIDENCE.jsonl")


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
    """Find the v2 example matching a v1 example by conclusion + first premise."""
    v1_conc = v1_ex["conclusion"].strip()
    best = None
    best_score = 0
    for e in v2_data:
        score = similarity(v1_conc, e["conclusion"].strip())
        if score > 0.8:
            v1_p0 = v1_ex["premises"][0].strip()[:100] if v1_ex["premises"] else ""
            v2_premises = to_list(e["premises"])
            v2_p0 = v2_premises[0].strip()[:100] if v2_premises else ""
            combined = score * 0.5 + similarity(v1_p0, v2_p0) * 0.5
            if combined > best_score:
                best_score = combined
                best = e
    return best if best_score > 0.6 else None


# The 12 error patterns from FOLIO_REPORT.md, with manual v2 verdicts.
# Each entry: pattern name, v1 example indices, premise index (or "conclusion"),
# error description, v2 verdict, and notes.
PATTERNS = [
    {
        "pattern_id": 1,
        "pattern": "xor_for_biconditional",
        "v1_indices": [3, 4, 5],
        "premise_idx": 6,
        "error": "XOR used where biconditional is meant. NL says 'either (manager AND appears) or (neither)' = A <-> B. FOL uses A XOR B, which has opposite truth values.",
        "v2_status": "fixed",
        "v2_notes": "P7 FOL now uses not(A XOR B) (= A <-> B). NL rewritten to explicit biconditional. v2 keeps only 1 of the 3 examples.",
    },
    {
        "pattern_id": 2,
        "pattern": "de_morgan_marvin",
        "v1_indices": [27, 28, 29],
        "premise_idx": 4,
        "error": "De Morgan error: 'cannot be from Earth and from Mars' means not(A AND B), but FOL has (not A) AND (not B) — from neither, which is strictly stronger.",
        "v2_status": "fixed",
        "v2_notes": "NL rewritten to 'either both or neither'. FOL uses not(A XOR B). Gold label changed from False to Uncertain.",
    },
    {
        "pattern_id": "2b",
        "pattern": "de_morgan_wedding_paris",
        "v1_indices": [128, 129, 130, 131],
        "premise_idx": 4,
        "error": "De Morgan error in P5: NL consequent is 'does not travel to Paris AND does not have a wedding' = (not A) AND (not B). Gold FOL has not(A AND B) = not both, which is weaker. Also P6 uses XOR where inclusive-or is meant.",
        "v2_status": "removed",
        "v2_notes": "Entire problem set deleted from v2.",
    },
    {
        "pattern_id": 3,
        "pattern": "de_morgan_conclusion_ko",
        "v1_indices": [73],
        "premise_idx": "conclusion",
        "error": "De Morgan error in conclusion: 'neither A nor B' = (not A) AND (not B), but FOL has (not A) OR (not B).",
        "v2_status": "fixed",
        "v2_notes": "Conclusion FOL now correctly uses (not A) AND (not B).",
    },
    {
        "pattern_id": "4a",
        "pattern": "misalignment_wild_turkeys",
        "v1_indices": [9, 10, 11],
        "premise_idx": [1, 2, 3, 4, 5],
        "error": "Statement misalignment: P1 NL was split across two lines in source data, so every subsequent FOL is shifted by one position. P6 ('Tom is a wild turkey') has no FOL at all.",
        "v2_status": "fixed",
        "v2_notes": "P1 no longer split across lines; 6 FOL formulas for 6 premises.",
    },
    {
        "pattern_id": "4b",
        "pattern": "misalignment_rental_cat",
        "v1_indices": [93],
        "premise_idx": [2, 3, 4, 5, 6, 7, 8],
        "error": "Statement misalignment: starting at P3, each FOL formula corresponds to a later premise. P4's FOL (Cat(fluffy)) is P5's intended formula, etc.",
        "v2_status": "fixed",
        "v2_notes": "Problem restructured with additional premises; all FOLs aligned.",
    },
    {
        "pattern_id": "4c",
        "pattern": "misalignment_gre_ets",
        "v1_indices": [105, 106, 107],
        "premise_idx": [1, 2, 3, 4],
        "error": "Statement misalignment: P2's FOL is for P1 (cost relationship), P3's is for P2 (hardship -> aid), P4's is for P3 (definition of hardship), P5's is for P4 (Tom's family).",
        "v2_status": "fixed",
        "v2_notes": "Problem restructured; all FOLs aligned.",
    },
    {
        "pattern_id": "4d",
        "pattern": "misalignment_salad_health",
        "v1_indices": [173, 174, 175],
        "premise_idx": [3, 4, 5],
        "error": "Statement misalignment: starting at P4, each FOL corresponds to a different/later premise. P4's FOL negates HealthyHabits (P5's meaning), P5's FOL is about gym (P6's meaning).",
        "v2_status": "fixed",
        "v2_notes": "Problem substantially rewritten; all FOLs aligned.",
    },
    {
        "pattern_id": 5,
        "pattern": "semantic_mismatch_mia_emma",
        "v1_indices": [46, 47, 48],
        "premise_idx": 3,
        "error": "Semantic mismatch: 'Mia's favorite season is not the same as Emma's' should compare seasons, but FOL has not(Love(mia, emma)) — 'Mia does not love Emma' — completely different relation.",
        "v2_status": "fixed",
        "v2_notes": "P4 FOL now uses forall x forall y (Season(x) AND Season(y) AND Favorite(mia,x) AND Favorite(emma,y) -> not(x=y)).",
    },
    {
        "pattern_id": 6,
        "pattern": "converse_implication_beethoven",
        "v1_indices": [36, 37, 38],
        "premise_idx": 1,
        "error": "Converse implication: 'Composers write music' means Composer(y) -> exists x (writes(y,x)). Gold FOL says: if x is written by y, then y is a composer — the converse.",
        "v2_status": "fixed",
        "v2_notes": "P2 FOL now forall x (MusicPiece(x) -> exists y (Composer(y) AND Write(y,x))). However, v2 P7 has a new precedence issue with exists y scoping.",
    },
    {
        "pattern_id": 7,
        "pattern": "wrong_arity_karen_share",
        "v1_indices": [21, 22, 23],
        "premise_idx": 5,
        "error": "Wrong arity: Share(x, lisa) is 2-ary, dropping Karen as the agent. Should be Share(karen, x, lisa). FOL says 'x is shared with Lisa' rather than 'Karen shares x with Lisa'.",
        "v2_status": "fixed",
        "v2_notes": "Share(x, lisa) -> ShareWith(karen, x, lisa) (3-ary).",
    },
    {
        "pattern_id": 8,
        "pattern": "wrong_arity_order_du_maurier",
        "v1_indices": [194, 195, 196],
        "premise_idx": [0, 1, 4],
        "error": "Wrong argument order: Winner(maurier, steinhauer) reads as 'the tournament won the player'. Participate(maurier, steinhauer) reads as 'the tournament participated with the player'. Arguments are reversed.",
        "v2_status": "partially_fixed",
        "v2_notes": "P1 fixed (WinnerOf(steinhauer, ...)), but P2 and P5 still have tournament as first argument.",
    },
    {
        "pattern_id": 9,
        "pattern": "wrong_quantifier_koala",
        "v1_indices": [96, 97, 98],
        "premise_idx": 5,
        "error": "Wrong quantifier: 'if a koala is very fluffy' and 'Koalas love to sleep' use universal quantification in NL, but FOL uses 'koala' as a constant (a specific individual named koala).",
        "v2_status": "removed",
        "v2_notes": "Entire problem set deleted from v2.",
    },
    {
        "pattern_id": 10,
        "pattern": "operator_precedence_picuris",
        "v1_indices": [112, 113, 114],
        "premise_idx": 0,
        "error": "Operator precedence: MountainRange(pm) AND In(pm, NM) OR In(pm, TX) — without parentheses, AND binds tighter, so MountainRange only applies to the NM branch. Should be MountainRange(pm) AND (In(pm, NM) OR In(pm, TX)).",
        "v2_status": "fixed",
        "v2_notes": "Parentheses added: MountainRange(pm) AND (In(pm, NM) XOR In(pm, TX)). Uses XOR, defensible for mutually exclusive locations.",
    },
    {
        "pattern_id": 11,
        "pattern": "negation_inversion_mary_jobs",
        "v1_indices": [76, 77, 78],
        "premise_idx": 5,
        "error": "Negation inversion: predicate NotPicky negated in formula gives double negation, making Mary picky instead of not-picky. NL consequent 'neither picky nor needs money' = not(Picky) AND not(Tuition), but not(NotPicky) = Picky.",
        "v2_status": "fixed",
        "v2_notes": "Predicate renamed from NotPicky to PickyEater, eliminating double-negation.",
    },
    {
        "pattern_id": 12,
        "pattern": "xor_for_inclusive_or_subway",
        "v1_indices": [84, 85, 86],
        "premise_idx": 4,
        "error": "XOR for clearly inclusive-or: 'has a rating greater than 9 or is popular among local residents' uses XOR, but both can obviously be true simultaneously. P4 says popular -> rating > 9, so if popular, both are true — XOR would make this false.",
        "v2_status": "not_fixed",
        "v2_notes": "Still uses XOR where inclusive-or is needed.",
    },
]


def main():
    v1_data = load_jsonl(V1_PATH)
    v2_data = load_jsonl(V2_PATH)

    # Cache v2 matches per v1 index
    v2_cache = {}

    records = []
    for pat in PATTERNS:
        v1_idx = pat["v1_indices"][0]  # representative example
        v1_ex = v1_data[v1_idx]
        premises = v1_ex["premises"] if isinstance(v1_ex["premises"], list) else v1_ex["premises"].split("\n")
        premises_fol = v1_ex["premises-FOL"] if isinstance(v1_ex["premises-FOL"], list) else v1_ex["premises-FOL"].split("\n")

        # Collect affected premises
        pidxs = pat["premise_idx"]
        if pidxs == "conclusion":
            pidxs = ["conclusion"]
        elif isinstance(pidxs, int):
            pidxs = [pidxs]

        affected = []
        for pidx in pidxs:
            if pidx == "conclusion":
                affected.append({
                    "position": "conclusion",
                    "v1_nl": v1_ex["conclusion"],
                    "v1_fol": v1_ex["conclusion-FOL"],
                })
            elif pidx < len(premises) and pidx < len(premises_fol):
                affected.append({
                    "position": f"P{pidx}",
                    "v1_nl": premises[pidx].strip(),
                    "v1_fol": premises_fol[pidx].strip(),
                })

        # Find v2 match
        if v1_idx not in v2_cache:
            v2_cache[v1_idx] = find_v2_match(v1_ex, v2_data)
        v2_match = v2_cache[v1_idx]

        # Add v2 data to affected premises — match by NL text, not index
        for a in affected:
            a["v2_fol"] = None
            a["v2_nl"] = None
            a["v2_premise_idx"] = None
            if v2_match is None:
                continue
            v2_premises = to_list(v2_match["premises"])
            v2_fols = to_list(v2_match["premises-FOL"])
            if a["position"] == "conclusion":
                a["v2_nl"] = v2_match["conclusion"]
                a["v2_fol"] = v2_match["conclusion-FOL"]
            else:
                # Find the v2 premise that best matches the v1 NL text
                v1_nl = a["v1_nl"].strip()
                best_idx = None
                best_score = 0
                for j, v2_p in enumerate(v2_premises):
                    s = similarity(v1_nl, v2_p.strip())
                    if s > best_score:
                        best_score = s
                        best_idx = j
                if best_idx is not None and best_score > 0.5:
                    a["v2_premise_idx"] = best_idx
                    a["v2_nl"] = v2_premises[best_idx].strip()
                    if best_idx < len(v2_fols):
                        a["v2_fol"] = v2_fols[best_idx].strip()

        record = {
            "pattern_id": pat["pattern_id"],
            "pattern": pat["pattern"],
            "error": pat["error"],
            "v1_example_indices": pat["v1_indices"],
            "v1_representative_index": v1_idx,
            "affected_statements": affected,
            "v2_status": pat["v2_status"],
            "v2_notes": pat["v2_notes"],
            "v2_matched": v2_match is not None,
        }
        records.append(record)

    with open(OUTPUT, "w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Print summary
    print(f"Generated {len(records)} evidence records -> {OUTPUT}")
    for rec in records:
        n_affected = len(rec["affected_statements"])
        v2 = rec["v2_status"]
        matched = "matched" if rec["v2_matched"] else "NOT MATCHED"
        print(f"  [{rec['pattern_id']:>3}] {rec['pattern']:<35s} {n_affected} stmt(s), v2={v2:<16s} ({matched})")


if __name__ == "__main__":
    main()
