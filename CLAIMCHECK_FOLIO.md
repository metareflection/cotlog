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

After deduplication (same FOL + original premise appearing in multiple FOLIO examples that share premise sets), there are **150 unique structural errors**. Manual audit of all 150 follows.

## Manual Audit of Structural Errors

### Classification scheme

Each unique structural error is classified as:
- **TRUE**: genuinely structural — a real logic error in the gold FOL
- **FALSE**: should have been surface — predicate-naming, expressivity loss, or comparator error
- **DEBATABLE**: reasonable people could disagree

### Audit results by error pattern

#### 1. XOR (⊕) used where biconditional (↔) or inclusive-or (∨) is meant

**Errors [2, 5, 6, 8, 9, 23, 31, 35, 48, 59, 60, 69, 80, 81, 107, 117, 120, 142]** — ~18 unique

The most systematic error in FOLIO. Two patterns:

**(a) "Either both A and B, or neither A nor B" → `A ⊕ B`**: The NL describes a biconditional (A ↔ B), meaning both-or-neither. FOLIO encodes this as `(A ∧ B) ⊕ (¬A ∧ ¬B)`, which is XOR between the two cases. Since both-and-neither are mutually exclusive, the XOR is actually *equivalent* to the disjunction `(A ∧ B) ∨ (¬A ∧ ¬B)` — i.e., they can't both be true simultaneously, so XOR and OR give the same result. **Verdict: FALSE** — the comparator flagged XOR vs biconditional but the FOL is logically correct. The "but not both" in the back-translation is technically accurate since (A∧B) and (¬A∧¬B) are mutually exclusive. Items [2, 82, 120] are this pattern.

**(b) "Either A or B" → `A ⊕ B`**: NL uses "either...or" which in English is typically inclusive-or. FOLIO encodes as XOR. Whether this is an error depends on context — "a man is either kind or evil" might genuinely mean exclusive-or (can't be both). **Verdict: DEBATABLE** for most, TRUE for a few where inclusive-or is clearly intended (e.g., [60] "rating > 9 or popular" — both can obviously be true). Items [31, 48, 69, 81, 117, 142] are this pattern.

**(c) Biconditional consequents rendered as XOR**: e.g., [8] "James is either a manager and appears... or neither" → `Manager(james) ⊕ AppearInCompany(james)`. This XOR between the two individual properties is NOT equivalent to the biconditional between conjunctions. The NL says manager↔appears, XOR says exactly-one. **Verdict: TRUE**. Items [8, 9] are this pattern.

#### 2. Predicate-naming / subject conflation → flagged as wrong-property

**Errors [0, 1, 3, 7, 53, 54, 55, 56, 57, 66, 83, 91, 92, 103, 104, 105, 108, 118, 119, 121, 122, 123, 131, 132, 137]** — ~25 unique

The largest group of **misclassifications**. These are predicate-naming issues that should be surface:

- `TalentShows(x)` back-translated as "x is a talent show" instead of "x performs in talent shows" [0, 1]
- `Meeting(x)` for "x schedules a meeting" → "x is a meeting" [7]
- `Wedding(x)` for "x has a wedding" → "x is a wedding" [103, 104, 105]
- `Desktop(x)` for "x owns a desktop" → "x is a desktop" [118, 119]
- `Database(x)` for "x takes the database course" → "x is a database" [121, 122, 123]
- `Salad(x)` for "x eats salads" → "x is a salad" [131, 132]
- `Knowledge(x)` for "x contains knowledge" → "x is knowledge" [66]
- `Vehicleregistrationplate(joe, istanbul)` for "Joe's plate is from Istanbul" → "Joe is a plate" [53, 54]

The FOL predicates are opaque symbols. `Wedding(x)` *means* "x has a wedding" — the back-translation reads the name literally, which is a tool artifact. **Verdict: FALSE (should be surface)**.

#### 3. Statement misalignment / shifted FOL

**Errors [16, 17, 18, 19, 20, 70-76, 84-90, 134-136]** — ~20 unique

FOLIO gold FOL statements are shifted relative to NL premises. The FOL for premise N corresponds to premise N+1 (or further). This happens in:
- Turkey types (Examples 9-11): FOL shifted by 1-2 positions
- GRE/ETS financial aid (Examples 105-107): FOL for "ETS provides aid" maps to "if cost is 205 then cost < 300"
- Rental/cat (Example 93): "Fluffy is Tom's cat" maps to a rent biconditional
- Salad/health (Examples 163-165): "visit the gym" maps to a childhood/relationship formula

**Verdict: TRUE** — these are genuine dataset bugs, not expressivity issues.

#### 4. ¬(A ∧ B) vs ¬A ∧ ¬B (De Morgan confusion)

**Errors [30, 106, 52]** — ~3 unique

- [30] "Marvin cannot be from Earth and from Mars" → `¬FromEarth(marvin) ∧ ¬FromMars(marvin)`. The NL means ¬(FromEarth ∧ FromMars) (can't be both), but FOL says ¬FromEarth ∧ ¬FromMars (is neither). **Verdict: TRUE**.
- [106] "John does not travel to Paris AND does not have a wedding" → `Child(john) → ¬(Paris(john) ∧ Wedding(john))`. The NL consequent is ¬A ∧ ¬B but FOL has ¬(A ∧ B). **Verdict: TRUE**.
- [52] "neither a company's stock nor is its price volatile" → `¬A ∨ ¬B`. NL says ¬A ∧ ¬B, FOL has ¬A ∨ ¬B. **Verdict: TRUE**.

#### 5. ∃ used for definitional/universal claims

**Errors [10, 11, 12, 28]** — ~4 unique

- "Monkeypox is a disease caused by..." → `∃x (OccurMonkeypoxVirus(x) ∧ GetMonkeypox(x))`. Definitional claim formalized as existential.
- "Many of Beijing's 91 universities..." → `∃x (BeijingUniversity(x) ∧ ...)`. "Many" weakened to "at least one."

**Verdict: TRUE** for [10, 12] (wrong quantifier for definitional claims), **DEBATABLE** for [11, 28] (∃ is arguably appropriate for "can occur" and "many" is inexpressible in basic FOL).

#### 6. Conjunction/disjunction errors

**Errors [39, 111, 96]** — ~3 unique

- [39] "Spring, Summer, Fall, and Winter" → `Season(spring) ∨ Season(summer) ∨ ...`. Should be conjunction (all four ARE seasons). **Verdict: TRUE**.
- [111] "categorized as A, B, and C" → `ML(A) ∨ ML(B) ∨ ML(C)`. Should be conjunction. **Verdict: TRUE**.
- [96] "in New Mexico or Texas" → `MountainRange(pm) ∧ In(pm, NM) ∨ In(pm, TX)`. Operator precedence error — ∧ binds tighter than ∨, so MountainRange only applies to NM branch. **Verdict: TRUE**.

#### 7. Semantic mismatch (truly wrong property)

**Errors [40, 32, 65, 100, 102, 133, 139, 145]** — ~8 unique

- [40] "favorite season not the same as Emma's" → `¬Love(mia, emma)` — completely wrong. **TRUE**.
- [32] "lives in well paid" → `LivesInTaxHaven(djokovic)` — NL is garbled but predicate is wrong. **TRUE**.
- [65] "if named after a character, character appears" → back-translation says "appears → good guy" — misaligned FOL. **TRUE**.
- [102] "neither a fly nor a bird" → `¬Fly(rock)` interpreted as "does not fly" instead of "is not a fly" — ambiguous predicate name. **DEBATABLE** (arguably predicate-naming).
- [133] "good relationships → fulfill nutritional intakes" → `GoodRelationship(x) → ¬HealthyHabits(x)` — negation is wrong. **TRUE**.

#### 8. Converse implications

**Errors [33]** — 1 unique

"Composers write music" → `MusicPiece(x) ∧ WrittenBy(x,y) → Composer(y)`. This is the converse: "if written by y, then y is a composer" rather than "if composer, then writes music." **Verdict: TRUE**.

#### 9. Wrong arity / argument order

**Errors [25, 26, 27, 93, 143, 144, 146]** — ~5 unique

- `Share(x, lisa)` drops Karen as agent — 2-ary instead of 3-ary. **TRUE**.
- `Winner(maurier, steinhauer)` — argument order wrong. **TRUE**.

#### 10. Quantifier scope (∀ used for definite/specific claims)

**Errors [13, 34, 36, 77, 101, 112-114, 127, 128, 141]** — ~10 unique

- [77] "if a koala..." → `VeryFluffy(koala)` where `koala` is a constant, not a variable. **TRUE** (gold FOL uses a constant where universal is meant).
- [34, 36] "Either Zaha Hadid's style or Kelly Wearstler's" → `∀x (ZahaHadid(x) ∨ KellyWearstler(x))`. NL is about specific designs, FOL universalizes. **DEBATABLE** (context-dependent).
- [101] "An animal is either a monkey or a bird" → `∀x (Monkey(x) ∨ Bird(x))` — missing `Animal(x)` guard. **DEBATABLE** (wrong-quantifier or missing-guard?).

#### 11. Conclusion-only errors flagged by the comparator

**Errors [3, 5, 6, 9, 14, 22, 26, 27, 29, 37, 38, 41-44, 46, 47, 51, 55, 56, 59, 61-63, 67, 68, 78-80, 88-90, 94, 95, 97-99, 109, 110, 115, 116, 124-126, 130, 138, 147-149]** — ~45 unique

Many of these are predicate-naming issues on conclusions (same problem as #2 above) or consequences of premise errors (shifted FOL). A few are genuinely structural:
- [38] ¬(A ∨ B) rendered as ¬A ∨ ¬B — De Morgan. **TRUE**.
- [52] "neither...nor" rendered as "not...or not." **TRUE**.
- [95] "(foodie ∧ high-income) ∨ (foodie ∧ ¬high-income)" rendered as "(foodie ∧ high-income) ∨ (¬foodie ∧ ¬high-income)" — biconditional vs always-foodie. **TRUE**.
- [109] "John has a child" → `Child(john)` → "John is a child." **FALSE** (predicate-naming).
- [37] "has lost" vs "lost" — tense. **FALSE** (should be surface/tense-loss).
- [29] "second largest by urban population" → "second largest" — dropped qualifier. **FALSE** (should be surface/missing-aspect).
- [44] "is a star" → "is a soccer star" — added qualifier. **FALSE** (should be surface).
- [68] "smarter than before" → "is smarter" — dropped temporal comparison. **FALSE** (should be surface/tense-loss).

### Summary counts

| Classification | Unique errors | With repeats (×204 examples) |
|---|---|---|
| **TRUE** (genuinely structural) | ~55 | ~130 |
| **FALSE** (should be surface) | ~60 | ~100 |
| **DEBATABLE** | ~35 | ~49 |

### Corrected numbers

If we reclassify the FALSE items as surface:

```
Structural errors (corrected): ~130 of 1292 → ~10% error rate
Surface noise (corrected): ~187 of 1292 → ~14%
Faithfulness rate (structural only, corrected): ~90%
```

The headline number moves from 78% to ~90%. The remaining 10% structural errors are:
- Statement misalignment bugs (~20 unique, very high repeat rate)
- XOR/biconditional confusion where it genuinely matters (~5 unique)
- De Morgan / connective errors (~6 unique)
- Semantic mismatches (~8 unique)
- Converse implications (1 unique)
- Wrong arity (5 unique)
- Conjunction/disjunction confusion (3 unique)
- Quantifier errors (7 unique)

### Key finding: the comparator still has a predicate-naming blind spot

About 40% of items classified as "structural" are actually predicate-naming issues that the two-tier prompt failed to catch. The problem: when `Wedding(x)` back-translates to "x is a wedding" and the original says "x has a wedding", the comparator sees a subject change (person → wedding) and calls it `wrong-property` rather than `predicate-naming`. The logical *structure* (∀x, →) is preserved — only the predicate's English gloss is wrong.

This suggests the comparator prompt needs a stronger rule: **if the FOL formula's logical skeleton (quantifiers, connectives, variable bindings) matches, and the only difference is how predicate names are interpreted, classify as surface.** The current prompt says predicates are opaque symbols, but the comparator doesn't apply this consistently when the back-translation produces a dramatically different-sounding English sentence.

## Method

- Mode: gold (uses FOLIO's gold FOL annotations, no LLM formalization)
- Model: default (sonnet)
- Dataset: FOLIO validation set, 204 examples, 1292 total statements
- Comparator: two-tier (structural vs surface), see `claimcheck.py`
