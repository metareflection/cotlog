# FOLIO Gold Annotation Errors

Errors found in the FOLIO validation set gold FOL annotations via round-trip verification (NL → FOL → English → compare). Each entry shows the original natural language premise, the gold FOL, and the error.

Example indices refer to 0-indexed position in `folio-validation.jsonl`. Where the same premise set is shared across multiple examples (different conclusions), only one example index is listed.

---

## 1. XOR/biconditional confusion

The gold annotations use XOR (`⊕`) between individual properties where the NL describes a biconditional between conjunctions. `(A ∧ B) ⊕ (¬A ∧ ¬B)` is fine (the two cases are mutually exclusive, so XOR = OR), but `A ⊕ B` is not equivalent to "either both A and B, or neither A nor B."

**Example 3, P7:**
> James is either a manager and appears in the company today or neither a manager nor appears in the company today.

Gold FOL: `Manager(james) ⊕ AppearInCompany(james)`

Error: The NL says Manager(james) ↔ AppearInCompany(james) (both or neither). The FOL says exactly one is true (XOR). These have opposite truth values when both are true or both are false.

**Example 5, conclusion:**
> If James is either a manager or in other countries, then James either has lunch at home and works remotely from home, or neither has lunch at home nor works remotely from home.

Gold FOL: `(Manager(james) ⊕ InOtherCountries(james)) → (LunchAtHome(james) ⊕ WorkRemotelyFromHome(james))`

Error: Both the antecedent and consequent use XOR where biconditional or inclusive-or is meant. The antecedent should be `Manager(james) ∨ InOtherCountries(james)`. The consequent should be `LunchAtHome(james) ↔ WorkRemotelyFromHome(james)`.

---

## 2. Conjunction / disjunction errors

**Example 46, P1:**
> There are four seasons in a year: Spring, Summer, Fall, and Winter.

Gold FOL: `Season(spring) ∨ Season(summer) ∨ Season(fall) ∨ Season(winter)`

Error: Should be conjunction (∧). The original states all four ARE seasons. The disjunction only asserts at least one is a season.

**Example 138, P1:**
> Machine Learning algorithms can be categorized as supervised learning, unsupervised learning, and reinforcement learning.

Gold FOL: `MLAlgorithm(supervisedLearning) ∨ MLAlgorithm(unsupervisedLearning) ∨ MLAlgorithm(reinforcementLearning)`

Error: Same pattern — should be conjunction. All three ARE ML algorithm categories.

---

## 3. De Morgan errors (¬(A ∧ B) vs ¬A ∧ ¬B)

**Example 27, P5:**
> Marvin cannot be from Earth and from Mars.

Gold FOL: `¬FromEarth(marvin) ∧ ¬FromMars(marvin)`

Error: The NL means ¬(FromEarth(marvin) ∧ FromMars(marvin)) — Marvin can't be from *both*. The FOL says Marvin is from *neither*, which is strictly stronger.

**Example 128, P5:**
> If John has at least one child, then John does not travel to Paris for his honeymoon and does not have a wedding.

Gold FOL: `Child(john) → ¬(Paris(john) ∧ Wedding(john))`

Error: The NL consequent is ¬Paris(john) ∧ ¬Wedding(john) (neither travels nor has wedding). The FOL has ¬(Paris(john) ∧ Wedding(john)) (not both), which is weaker — allows one but not both.

**Example 73, conclusion:**
> If KO is a growth company's stock or if its price is volatile, then KO is neither a company's stock nor is its price volatile.

Gold FOL: `GrowthCompanies'Stocks(kO) ∨ PriceVolatile(kO) → ¬Companies'Stocks(kO) ∨ ¬PriceVolatile(kO)`

Error: "neither...nor" is ¬A ∧ ¬B, but the FOL has ¬A ∨ ¬B.

---

## 4. Converse implication

**Example 36, P2:**
> Composers write music pieces.

Gold FOL: `∀x ∀y ((MusicPiece(x) ∧ Writtenby(x, y)) → Composer(y))`

Error: The NL says composers write music (Composer(y) → writes). The FOL says: if something is a music piece written by y, then y is a composer. This is the converse — it defines composers as people who write music, rather than asserting composers write music.

---

## 5. Semantic mismatch (wrong property)

**Example 46, P4:**
> Mia's favorite season is not the same as Emma's.

Gold FOL: `¬Love(mia, emma)`

Error: "Mia does not love Emma" is a completely different claim from "Mia and Emma have different favorite seasons."

**Example 30, P8:**
> If Djokovic is famous and is an athlete, then Djokovic lives in well paid.

Gold FOL: `Famous(djokovic) ∧ Athlete(djokovic) → LivesInTaxHaven(djokovic)`

Error: The NL consequent is garbled ("lives in well paid") but is clearly not "lives in a tax haven." The predicate `LivesInTaxHaven` does not correspond to the original.

**Example 163, P5:**
> If people have good relationships with their parents, then they do not eat salads regularly.

Gold FOL: `∀x (Gym(x) → Nutritional(x))`

Error: FOL is for a different premise entirely ("visit the gym → fulfill nutritional intakes"). Statement misalignment.

**Example 163, P7:**
> It is either both true that Taylor grew up in a health-conscious childhood home and she has a good relationship with her parents, or neither is true.

Gold FOL: (empty/misaligned)

Back-translation: "Taylor is a salad."

Error: Statement misalignment — FOL for this premise corresponds to a different statement in the sequence.

---

## 6. Statement misalignment (FOL shifted relative to NL)

Multiple FOLIO stories have gold FOL statements that are shifted by one or more positions relative to the NL premises. The FOL for premise N corresponds to premise N+1 or later.

**Example 9 (wild turkeys):**

| Premise | NL | Gold FOL (should be for this premise) | Gold FOL (actually present) |
|---|---|---|---|
| P1 | "There are six types of wild turkeys..." | type enumeration | `∀x (WildTurkey(x) → (Eastern(x) ∨ ...))` ✓ |
| P2 | "turkey, Rio Grande wild turkey, and Ocellated wild turkey." | (continuation of P1) | `¬(WildTurkey(tom) ∧ Eastern(tom))` ← P3's FOL |
| P3 | "Tom is not an Eastern wild turkey." | `¬(WildTurkey(tom) ∧ Eastern(tom))` | `¬(WildTurkey(tom) ∧ Osceola(tom))` ← P4's FOL |
| P4 | "Tom is not an Osceola wild turkey." | `¬(WildTurkey(tom) ∧ Osceola(tom))` | `WildTurkey(tom) → ¬(Goulds(tom) ∨ ...)` ← P5's FOL |
| P5 | "Tom is also not a Gould's, Merriam's, or Rio Grande." | negation of three types | `WildTurkey(tom)` ← P6's FOL |
| P6 | "Tom is a wild turkey." | `WildTurkey(tom)` | (missing/empty) |

The root cause appears to be that the NL premise list was split across two lines ("There are six types..." / "turkey, Rio Grande...") but the FOL only has one formula for the combined statement, shifting everything after by one position.

**Example 93 (rental/cat):**

| Premise | NL | Gold FOL (actually present) |
|---|---|---|
| P3 | "The security deposit can be either equal to one month's rent or more." | `∀x (Rent2000(x) ↔ ¬DepositNoMoreThan1500(x))` ← wrong statement |
| P4 | "Fluffy is Tom's cat." | `∀x (Rent2000(x) ↔ DepositNoLessThan2000(x))` ← wrong statement |
| P5 | "Cats are pets." | `Cat(fluffy)` ← P4's FOL |
| P6 | "The Olive Garden is a managed building." | `∀x (Cat(x) → Pet(x))` ← P5's FOL |
| P7 | "The monthly rent at the Olive Garden is $2000." | `ManagedBuilding(oliveGarden)` ← P6's FOL |
| P8 | "Tom will rent an apartment..." | `Rent2000(oliveGarden)` ← P7's FOL |
| P9 | "$2000 is more than $1500." | `∀x (TomRent(x) ↔ ...)` ← P8's FOL |

**Example 105 (GRE/ETS):**

| Premise | NL | Gold FOL (actually present) |
|---|---|---|
| P2 | "ETS provides financial aid to those GRE applicants who prove economic hardship." | `∀x (Cost205(x) → CostBelow300(x))` ← wrong statement |
| P3 | "Economic hardship refers to difficulty caused by having too little money or too few resources." | `∀x (Hardship(x) → FinancialAid(x))` ← P2's meaning |
| P4 | "Tom lives in a single-parent family." | `∀x (SingleParent(x) ∨ FewResources(x) → Hardship(x))` ← P3's meaning |
| P5 | "His dad has been out of work for more than a year." | `SingleParent(tom)` ← P4's meaning |

---

## 7. Wrong arity / dropped arguments

**Example 21, P6:**
> If Karen binge-watches a Netflix show, she will share it to Lisa.

Gold FOL: `∀x ((NetflixShow(x) ∧ BingeWatch(karen, x)) → Share(x, lisa))`

Error: `Share(x, lisa)` is 2-ary, dropping Karen as the agent. Should be `Share(karen, x, lisa)` — Karen shares x with Lisa.

**Example 199, P1 and P5:**
> The winner of the 1992 du Maurier Classic was Steinhauer.

Gold FOL: `Winner(maurier, steinhauer)`

Error: Argument order implies "maurier won steinhauer" rather than "steinhauer won the maurier." Same issue with `Participate(maurier, steinhauer)` — implies the tournament participates with the player.

---

## 8. Wrong quantifier (constant used where variable is needed)

**Example 96, P6:**
> If a koala is very fluffy, then the koala is not a quokka.

Gold FOL: `VeryFluffy(koala) → ¬Quokka(koala)`

Error: `koala` is used as a constant (a specific individual named "koala"), but the NL quantifies universally over all koalas ("if *a* koala is very fluffy"). Should be `∀x (Koala(x) ∧ VeryFluffy(x) → ¬Quokka(x))`.

---

## 9. Operator precedence error

**Example 112, P1:**
> The Picuris Mountains are a mountain range in New Mexico or Texas.

Gold FOL: `MountainRange(picurismountains) ∧ In(picurismountains, newmexico) ∨ In(picurismountains, texas)`

Error: Without parentheses, this parses as `(MountainRange(pm) ∧ In(pm, NM)) ∨ In(pm, TX)`, which only asserts the mountain range property for the New Mexico branch. Should be `MountainRange(pm) ∧ (In(pm, NM) ∨ In(pm, TX))`.

---

## 10. Negation inversion

**Example 76, P6:**
> If Mary works in student jobs on campus and needs to earn money to help pay for her college tuition, then Mary is neither picky nor needs to earn money to help pay for her college tuition.

Gold FOL: `StudentJobs(mary) ∧ Tuition(mary) → ¬(NotPicky(mary) ∨ Tuition(mary))`

Error: The predicate is `NotPicky` (already negated), so `¬(NotPicky(mary) ∨ ...)` becomes `¬¬Picky(mary) ∧ ...` = `Picky(mary) ∧ ...`. But the NL says "neither picky nor needs to earn money" — Mary should NOT be picky. The predicate name bakes in a negation that then gets double-negated.

---

## 11. Inclusive-or vs exclusive-or (contextually wrong)

These cases use XOR (`⊕`) where the NL "either...or" is clearly inclusive:

**Example 84, P5:**
> Subway has a rating greater than 9 or is popular among local residents.

Gold FOL: `RatingGreaterThan9(subway) ⊕ PopularAmongLocalResidents(subway)`

Error: A restaurant can obviously have both a high rating AND be popular. XOR incorrectly excludes this case.

**Example 128, P6:**
> If John has a wedding that is well-attended, then John has a wedding in July or, if not, then John travels to Paris for their honeymoon.

Gold FOL: `WellAttended(john) → July(john) ⊕ Paris(john)`

Error: "or, if not" suggests a fallback, not mutual exclusion. Inclusive-or is appropriate.

---

## Summary

| Error type | Unique instances | Affected examples |
|---|---|---|
| Statement misalignment | ~20 | 9-11, 93, 105-107, 163-165 |
| XOR/biconditional confusion | ~5 | 3-5, 128-131 |
| Conjunction/disjunction | ~3 | 46-48, 138-139 |
| De Morgan errors | ~3 | 27-29, 73, 128-131 |
| Semantic mismatch | ~4 | 30-32, 46-48, 163-165 |
| Wrong arity / argument order | ~5 | 21-23, 199 |
| Converse implication | 1 | 36-38 |
| Wrong quantifier (constant for variable) | 1 | 96-98 |
| Operator precedence | 1 | 112-114 |
| Negation inversion | 1 | 76-78 |
| Inclusive/exclusive-or | ~3 | 84-86, 128-131 |
| **Total unique errors** | **~47** | |

These errors were detected automatically via round-trip verification (FOL → English → compare against original NL) and confirmed by manual review. An additional ~60 flagged discrepancies were false positives due to predicate-naming conventions (e.g., `Wedding(x)` back-translated literally as "x is a wedding") and were excluded from this report.
