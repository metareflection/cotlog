# FOLIO Gold Annotation Errors

Errors in the FOLIO validation set gold FOL annotations, found via automated round-trip verification and confirmed by manual review. Each entry includes the full problem (all premises, conclusion, gold label) so errors can be assessed in context.

Example indices are 0-indexed positions in `folio-validation.jsonl`. Where the same premise set appears in multiple examples (different conclusions), one representative example is shown and affected indices are listed.

---

## 1. XOR used where biconditional is meant

**Affected examples: 3, 4, 5** (same premise set, different conclusions)

```
P1: All employees who schedule a meeting with their customers will appear
    in the company today.
    FOL: ∀x (Meeting(x) → AppearInCompany(x))
P2: Everyone who has lunch in the company schedules meetings with their
    customers.
    FOL: ∀x (LunchInCompany(x) → Meetings(x))
P3: Employees will either have lunch in the company or have lunch at home.
    FOL: ∀x (LunchInCompany(x) ∨ LunchAtHome(x))
P4: If an employee has lunch at home, then he/she is working remotely
    from home.
    FOL: ∀x (LunchAtHome(x) → WorkRemotelyFromHome(x))
P5: All employees who are in other countries work remotely from home.
    FOL: ∀x (InOtherCountries(x) → WorkRemotelyFromHome(x))
P6: No managers work remotely from home.
    FOL: ∀x (Manager(x) → ¬WorkRemotelyFromHome(x))
P7: James is either a manager and appears in the company today or neither
    a manager nor appears in the company today.
    FOL: Manager(james) ⊕ AppearInCompany(james)            ← ERROR
C:  James has lunch in the company. (label: Uncertain)
    FOL: LunchInCompany(james)
```

**P7 error:** The NL says "either (manager AND appears) or (neither manager NOR appears)" — i.e., `Manager(james) ↔ AppearInCompany(james)`. The gold FOL uses `Manager(james) ⊕ AppearInCompany(james)`, which means exactly one is true. These have opposite truth values: the biconditional is true when both are true or both are false; the XOR is true when exactly one is true.

The same XOR-for-biconditional error appears in conclusions of examples 5 and other premise sets that use the "either both A and B, or neither A nor B" pattern.

---

## 2. De Morgan error: ¬(A ∧ B) vs ¬A ∧ ¬B

**Affected examples: 27, 28, 29** (same premise set)

```
P1: All aliens are extraterrestrial.
    FOL: ∀x (Alien(x) → Extraterrestrial(x))
P2: If someone is from Mars, then they are aliens.
    FOL: ∀x (FromMars(x) → Alien(x))
P3: No extraterrestrial is human.
    FOL: ∀x (Extraterrestrial(x) → ¬Human(x))
P4: Everyone from Earth is a human.
    FOL: ∀x (FromEarth(x) → Human(x))
P5: Marvin cannot be from Earth and from Mars.
    FOL: ¬FromEarth(marvin) ∧ ¬FromMars(marvin)             ← ERROR
P6: If Marvin is not from Earth, then Marvin is an extraterrestrial.
    FOL: ¬FromEarth(marvin) → Extraterrestrial(marvin)
C:  Marvin is an alien. (label: False)
    FOL: Alien(marvin)
```

**P5 error:** "Cannot be from Earth *and* from Mars" means ¬(FromEarth ∧ FromMars) — he can't be from both. The gold FOL says ¬FromEarth ∧ ¬FromMars — he's from neither. The FOL is strictly stronger than what the NL states.

---

**Affected examples: 128, 129, 130, 131** (same premise set)

```
P1: All people who have a wedding are people who have at least one child.
    FOL: ∀x (Wedding(x) → Child(x))
P2: All people who travel to Paris for their honeymoon are people who
    have a wedding.
    FOL: ∀x (Paris(x) → Wedding(x))
P3: All weddings that occur in July belong to people who travel to Paris
    for their honeymoon.
    FOL: ∀x (July(x) → Paris(x))
P4: Some weddings in July are well-attended.
    FOL: ∃x (July(x) ∧ WellAttended(x))
P5: If John has at least one child, then John does not travel to Paris
    for his honeymoon and does not have a wedding.
    FOL: Child(john) → ¬(Paris(john) ∧ Wedding(john))       ← ERROR
P6: If John has a wedding that is well-attended, then John has a wedding
    in July or, if not, then John travels to Paris for their honeymoon.
    FOL: WellAttended(john) → July(john) ⊕ Paris(john)      ← ERROR
C:  John has a wedding that is well-attended. (label: False)
    FOL: WellAttended(john)
```

**P5 error:** NL consequent is "does not travel to Paris AND does not have a wedding" = ¬Paris ∧ ¬Wedding. Gold FOL has ¬(Paris ∧ Wedding) = not both, which is weaker.

**P6 error:** "In July or, if not, then Paris" is inclusive-or / conditional fallback. Gold FOL uses XOR (⊕), which excludes both being true.

---

## 3. De Morgan error in conclusion

**Affected examples: 73**

```
P1: All growth companies' stocks are volatile.
    FOL: ∀x (GrowthCompanies'Stocks(x) → PriceVolatile(x))
P2: If the stock price is volatile, then it is not suitable for a
    retirement fund.
    FOL: ∀x (PriceVolatile(x) → ¬SuitableForRetirementRund(x))
P3: Some companies' stocks are growth companies' stocks.
    FOL: ∃x (Companies'Stocks(x) ∧ GrowthCompanies'Stocks(x))
P4: All mature companies' stocks are suitable for a retirement fund.
    FOL: ∀x (MatureCompanies'Stocks(x) → SuitableForRetirementRund(x))
P5: KO is a mature company's stock.
    FOL: MatureCompanies'Stocks(kO)
C:  If KO is a growth company's stock or if its price is volatile, then
    KO is neither a company's stock nor is its price volatile.
    (label: True)
    FOL: GrowthCompanies'Stocks(kO) ∨ PriceVolatile(kO) →
         ¬Companies'Stocks(kO) ∨ ¬PriceVolatile(kO)         ← ERROR
```

**Conclusion error:** "Neither A nor B" = ¬A ∧ ¬B, but the FOL has ¬A ∨ ¬B.

---

## 4. Statement misalignment (FOL shifted relative to NL premises)

### Wild turkeys — **Affected examples: 9, 10, 11**

```
P1: There are six types of wild turkeys: Eastern wild turkey, Osceola
    wild turkey, Gould's wild turkey, Merriam's wild
    FOL: ∀x (WildTurkey(x) → (Eastern(x) ∨ Osceola(x) ∨ Goulds(x)
         ∨ Merriams(x) ∨ Riogrande(x) ∨ Ocellated(x)))
P2: turkey, Rio Grande wild turkey, and Ocellated wild turkey.
    FOL: ¬(WildTurkey(tom) ∧ Eastern(tom))                  ← SHIFTED
P3: Tom is not an Eastern wild turkey.
    FOL: ¬(WildTurkey(tom) ∧ Osceola(tom))                  ← SHIFTED
P4: Tom is not an Osceola wild turkey.
    FOL: WildTurkey(tom) → ¬(Goulds(tom) ∨ Merriams(tom)
         ∨ Riogrande(tom))                                  ← SHIFTED
P5: Tom is also not a Gould's wild turkey, or a Merriam's wild turkey,
    or a Rio Grande wild turkey.
    FOL: WildTurkey(tom)                                     ← SHIFTED
C:  Tom is an Ocellated wild turkey. (label: True)
    FOL: Ocellated(tom)
```

**Error:** P1's NL was split across two lines in the source data ("Merriam's wild" / "turkey, Rio Grande..."). The FOL has one formula for the combined statement, so every subsequent FOL is shifted by one position. P2's FOL is actually P3's, P3's is P4's, etc. P6 ("Tom is a wild turkey") has no FOL at all.

### Rental/cat — **Affected examples: 93**

```
P1: Pets are allowed in some managed buildings.
    FOL: ∃x (ManagedBuilding(x) ∧ AllowPet(x))
P2: A deposit is required to rent an apartment in a managed building.
    FOL: ∀x (ManagedBuilding(x) → RequireDeposit(x))
P3: The security deposit can be either equal to one month's rent or more.
    FOL: ∀x (Rent2000(x) ↔ ¬DepositNoMoreThan1500(x))      ← SHIFTED
P4: Fluffy is Tom's cat.
    FOL: ∀x (Rent2000(x) ↔ DepositNoLessThan2000(x))       ← SHIFTED
P5: Cats are pets.
    FOL: Cat(fluffy)                                         ← SHIFTED
P6: The Olive Garden is a managed building.
    FOL: ∀x (Cat(x) → Pet(x))                               ← SHIFTED
P7: The monthly rent at the Olive Garden is $2000.
    FOL: ManagedBuilding(oliveGarden)                        ← SHIFTED
P8: Tom will rent an apartment in a managed building if and only if he
    is allowed to move in with Fluffy, and the security deposit is no
    more than $1500.
    FOL: Rent2000(oliveGarden)                               ← SHIFTED
P9: 2000$ is more than $1500.
    FOL: ∀x (TomRent(x) ↔ (ManagedBuilding(x) ∧ AllowPet(x)
         ∧ DepositNoMoreThan1500(x)))                        ← SHIFTED
C:  Tom will rent an apartment in The Olive Garden. (label: False)
    FOL: TomRent(oliveGarden)
```

**Error:** Starting at P3, each FOL formula corresponds to a later premise. P4's FOL (`Cat(fluffy)`) is P5's intended formula. P5's FOL (`∀x (Cat(x) → Pet(x))`) is P6's. Etc.

### GRE/ETS — **Affected examples: 105, 106, 107**

```
P1: It costs US $205 to take the GRE test.
    FOL: Cost205(gre)
P2: ETS provides financial aid to those GRE applicants who prove
    economic hardship.
    FOL: ∀x (Cost205(x) → CostBelow300(x))                  ← SHIFTED
P3: Economic hardship refers to difficulty caused by having too little
    money or too few resources.
    FOL: ∀x (Hardship(x) → FinancialAid(x))                 ← SHIFTED
P4: Tom lives in a single-parent family.
    FOL: ∀x (SingleParent(x) ∨ FewResources(x) → Hardship(x)) ← SHIFTED
P5: His dad has been out of work for more than a year.
    FOL: SingleParent(tom)                                   ← SHIFTED
C:  Tom can apply for financial aid from ETS to take the GRE test.
    (label: True)
    FOL: FinancialAid(tom)
```

**Error:** P2's FOL is for P1 (cost relationship), P3's is for P2 (hardship → aid), P4's is for P3 (definition of hardship), P5's is for P4 (Tom's family situation).

### Salad/health — **Affected examples: 173, 174, 175**

```
P1: All people who eat salads regularly are very conscious about their
    health and eating habits.
    FOL: ∀x (Salad(x) → HealthyHabits(x))
P2: All people who grew up in health-conscious childhood homes eat
    salads regularly.
    FOL: ∀x (HealthyChildhood(x) → Salad(x))
P3: All people who fulfill their nutritional daily intakes grew up in
    health-conscious childhood homes.
    FOL: ∀x (Nutritional(x) → HealthyChildhood(x))
P4: If people have good relationships with their parents, then they
    fulfill their nutritional daily intakes.
    FOL: ∀x (GoodRelationship(x) → ¬HealthyHabits(x))      ← SHIFTED
P5: If people have good relationships with their parents, then they do
    not eat salads regularly.
    FOL: ∀x (Gym(x) → Nutritional(x))                       ← SHIFTED
P6: If people visit the gym at least once a day, then they always fulfill
    their daily nutritional intakes.
    FOL: (HealthyChildhood(taylor) ∧ GoodRelationship(taylor))
         ∨ ¬HealthyChildhood(taylor) ∧ ¬GoodRelationship(marcy) ← SHIFTED
C:  Taylor eats salads regularly. (label: Uncertain)
    FOL: Salad(taylor)
```

**Error:** Starting at P4, each FOL corresponds to a different/later premise. P4's FOL negates HealthyHabits (which is P5's meaning — not eating salads), P5's FOL is about gym → nutritional (P6's meaning), P6's FOL is a ground fact about Taylor (P7's meaning, but P7 doesn't exist in the NL).

---

## 5. Semantic mismatch (wrong property)

**Affected examples: 46, 47, 48** (same premise set)

```
P1: There are four seasons in a year: Spring, Summer, Fall, and Winter.
    FOL: Season(spring) ∨ Season(summer) ∨ Season(fall) ∨ Season(winter)
P2: All students who want to have a long vacation love summer the most.
    FOL: ∀x (WantlongVacation(x) → Love(x, summer))
P3: Emma's favorite season is summer.
    FOL: Love(emma, summer)
P4: Mia's favorite season is not the same as Emma's.
    FOL: ¬Love(mia, emma)                                   ← ERROR
P5: James wants to have a long vacation.
    FOL: WantlongVacation(james)
C:  James's favorite season is summer. (label: True)
    FOL: Love(james, summer)
```

**P4 error:** "Mia's favorite season is not the same as Emma's" should compare their favorite seasons — e.g., `¬(Love(mia, X) ↔ Love(emma, X))` or `¬Love(mia, summer)` given that Emma's favorite is summer. The gold FOL says `¬Love(mia, emma)` — "Mia does not love Emma" — which is a completely different relation with wrong arguments.

---

## 6. Converse implication

**Affected examples: 36, 37, 38** (same premise set)

```
P1: Symphony No. 9 is a music piece.
    FOL: MusicPiece(symphony9)
P2: Composers write music pieces.
    FOL: ∀x ∀y ((MusicPiece(x) ∧ Writtenby(x, y)) → Composer(y)) ← ERROR
P3: Beethoven wrote Symphony No. 9.
    FOL: Writtenby(symphony9, beethoven)
P4: Vienna Music Society premiered Symphony No. 9.
    FOL: Premiered(viennamusicsociety, symphony9)
P5: Vienna Music Society is an orchestra.
    FOL: Orchestra(viennamusicsociety)
P6: Beethoven leads the Vienna Music Society.
    FOL: Lead(beethoven, viennamusicsociety)
P7: Orchestras are led by conductors.
    FOL: ∀x ∀y ((Orchestra(x) ∧ Lead(y, x)) → Conductor(y))
C:  Beethoven is a composer. (label: True)
    FOL: Composer(beethoven)
```

**P2 error:** "Composers write music pieces" means Composer(y) → ∃x (MusicPiece(x) ∧ Writes(y, x)). The gold FOL says: if x is a music piece written by y, then y is a composer — which is the converse. It defines "anyone who writes music is a composer" rather than "composers write music."

Note: in this problem the converse actually *helps* prove the conclusion (Beethoven wrote Symphony No. 9, so by the converse, he's a composer). The original direction wouldn't prove the conclusion. So the gold FOL "works" for the entailment task, but it doesn't faithfully represent what P2 says.

---

## 7. Wrong arity / dropped agent

**Affected examples: 21, 22, 23** (same premise set)

```
P1: "Stranger Things" is a popular Netflix show.
    FOL: NetflixShow(strangerThings) ∧ Popular(strangerThings)
P2: If a Netflix show is popular, Karen will binge-watch it.
    FOL: ∀x ((NetflixShow(x) ∧ Popular(x)) → BingeWatch(karen, x))
P3: If and only if Karen binge-watches a Netflix show, she will
    download it.
    FOL: ∀x ((NetflixShow(x) ∧ BingeWatch(karen, x)) ↔ Download(karen, x))
P4: Karen does not download "Black Mirror".
    FOL: ¬Download(karen, blackMirror)
P5: "Black Mirror" is a Netflix show.
    FOL: NetflixShow(blackMirror)
P6: If Karen binge-watches a Netflix show, she will share it to Lisa.
    FOL: ∀x ((NetflixShow(x) ∧ BingeWatch(karen, x)) → Share(x, lisa))  ← ERROR
C:  Karen will share "Stranger Things" to Lisa. (label: True)
    FOL: Share(strangerThings, lisa)                         ← ERROR
```

**P6 and conclusion error:** `Share(x, lisa)` is 2-ary, dropping Karen as the agent. Should be `Share(karen, x, lisa)`. The FOL says "x is shared with Lisa" rather than "Karen shares x with Lisa."

---

## 8. Wrong arity / argument order

**Affected examples: 194, 195, 196**

```
P1: The winner of the 1992 du Maurier Classic was Steinhauer.
    FOL: Winner(maurier, steinhauer)                         ← ERROR
P2: Steinhauer participated in the 1992 du Maurier Classic.
    FOL: Participate(maurier, steinhauer)                    ← ERROR
P3: There was one six-way tie on the leaderboard and one person in the
    six-way tie was from Belgium.
    FOL: ∃x (LeaderBoard(maurier, x) ∧ SixWayTie(x) ∧ Belgium(x))
P4: Descampe is from Belgium and is on the leaderboard of the 1992 du
    Maurier Classic.
    FOL: Belgium(descampe) ∧ LeaderBoard(maurier, descampe)
P5: All people on the leaderboard of the 1992 du Maurier Classic
    participated in the 1992 du Maurier Classic.
    FOL: ∀x (LeaderBoard(maurier, x) → Participate(maurier, x))  ← ERROR
C:  Steinhauer was not the winner of the 1992 du Maurier Classic.
    (label: False)
    FOL: ¬Winner(maurier, steinhauer)
```

**P1, P2, P5 error:** `Winner(maurier, steinhauer)` reads as "the tournament won the player." `Participate(maurier, steinhauer)` reads as "the tournament participated with the player." The arguments are reversed — should be `Winner(steinhauer, maurier)` and `Participate(steinhauer, maurier)`.

Note: since the argument order is consistently reversed across all premises and the conclusion, the entailment label is unaffected. The error is in faithfulness, not consequentiality.

---

## 9. Wrong quantifier (constant used where variable is needed)

**Affected examples: 96, 97, 98** (same premise set)

```
P1: If animals are loved by tourists, then they are Max's favorite animals.
    FOL: ∀x (AnimalsLovedByTourists(x) → MaxFavoriteAnimals(x))
P2: All animals from Australia are loved by tourists.
    FOL: ∀x (AnimalsFromAustralia(x) → AnimalsLovedByTourists(x))
P3: All quokka are animals from Australia.
    FOL: ∀x (Quokka(x) → AnimalsFromAustralia(x))
P4: All of Max's favorite animals are very fluffy.
    FOL: ∀x (MaxFavoriteAnimals(x) → VeryFluffy(x))
P5: All of Max's favorite animals love to sleep.
    FOL: ∀x (MaxFavoriteAnimals(x) → LoveToSleep(x))
P6: If a koala is very fluffy, then the koala is not a quokka.
    FOL: VeryFluffy(koala) → ¬Quokka(koala)                 ← ERROR
C:  Koalas love to sleep. (label: Uncertain)
    FOL: LoveToSleep(koala)                                  ← ERROR
```

**P6 and conclusion error:** `koala` is used as a constant (a specific individual named "koala"), but the NL quantifies universally: "if *a* koala is very fluffy" and "Koalas love to sleep." Should use a variable: `∀x (Koala(x) ∧ VeryFluffy(x) → ¬Quokka(x))`.

---

## 10. Operator precedence error

**Affected examples: 112, 113, 114** (same premise set)

```
P1: The Picuris Mountains are a mountain range in New Mexico or Texas.
    FOL: MountainRange(picurismountains) ∧ In(picurismountains, newmexico)
         ∨ In(picurismountains, texas)                       ← ERROR
P2: Juan de Onate visited the Picuris Mountains.
    FOL: Visited(juandeonate, picurismountains)
P3: The Harding Pegmatite Mine, located in the Picuris Mountains, was
    donated.
    FOL: In(hardingpegmatitemine, picurismountains) ∧
         Mine(hardingpegmatitemine) ∧ Donated(hardingpegmatitemine)
P4: There are no mountain ranges in Texas that have mines which have
    been donated.
    FOL: ∀x ∀y (Mine(x) ∧ Donated(x) ∧ In(x, y) ∧ MountainRange(y)
         → ¬In(y, texas))
C:  Juan de Onate visited a mountain range in New Mexico. (label: True)
    FOL: ∃x (Visited(juandeonate, x) ∧ MountainRange(x) ∧ In(x, newmexico))
```

**P1 error:** Without parentheses, standard precedence gives `(MountainRange(pm) ∧ In(pm, NM)) ∨ In(pm, TX)`. This only asserts the Picuris Mountains are a mountain range in the New Mexico branch. Should be `MountainRange(pm) ∧ (In(pm, NM) ∨ In(pm, TX))`.

---

## 11. Negation inversion (double negation via predicate name)

**Affected examples: 76, 77, 78** (same premise set)

```
P1: If people work in student jobs on campus, then they need to earn
    money to help pay for their college tuition.
    FOL: ∀x (StudentJobs(x) → Tuition(x))
P2: If people order takeout frequently in college, then they work in
    student jobs on campus.
    FOL: ∀x (Takeout(x) → StudentJobs(x))
P3: People either order takeout frequently in college or enjoy the
    dining hall meals and recipes.
    FOL: ∀x (Takeout(x) ∨ DiningHall(x))
P4: If people enjoy the dining hall meals and recipes, then they are not
    picky eaters.
    FOL: ∀x (DiningHall(x) → NotPicky(x))
P5: If people enjoy the dining hall meals and recipes, then they spend a
    lot of their time eating and catching up with friends in the campus
    dining halls.
    FOL: ∀x (DiningHall(x) → Eating(x))
P6: If Mary works in student jobs on campus and needs to earn money to
    help pay for her college tuition, then Mary is neither picky nor
    needs to earn money to help pay for her college tuition.
    FOL: StudentJobs(mary) ∧ Tuition(mary) →
         ¬(NotPicky(mary) ∨ Tuition(mary))                  ← ERROR
C:  Mary needs to earn money to help pay for her college tuition.
    (label: Uncertain)
    FOL: Tuition(mary)
```

**P6 error:** The predicate is named `NotPicky` (P4 defines it: dining hall → NotPicky). The NL consequent says "neither picky nor needs money" = ¬Picky ∧ ¬Tuition. But `¬(NotPicky(mary) ∨ Tuition(mary))` = `¬NotPicky(mary) ∧ ¬Tuition(mary)` = `Picky(mary) ∧ ¬Tuition(mary)`. The negation of `NotPicky` becomes a double negation, making Mary picky instead of not-picky.

---

## 12. XOR for clearly inclusive-or

**Affected examples: 84, 85, 86** (same premise set)

```
P1: If the restaurant is listed in Yelp's recommendations, then the
    restaurant does not receive many negative reviews.
    FOL: ∀x (YelpRecommendation(x) → ¬NegativeReview(x))
P2: All restaurants with a rating greater than 9 are listed in Yelp's
    recommendations.
    FOL: ∀x (RatingGreaterThan9(x) → YelpRecommendation(x))
P3: Some restaurants that do not provide take-out service receive many
    negative reviews.
    FOL: ∃x (NoTakeOutService(x) ∧ NegativeReview(x))
P4: All restaurants that are popular among local residents have ratings
    greater than 9.
    FOL: ∀x (PopularAmongLocalResidents(x) → RatingGreaterThan9(x))
P5: Subway has a rating greater than 9 or is popular among local
    residents.
    FOL: RatingGreaterThan9(subway) ⊕
         PopularAmongLocalResidents(subway)                  ← ERROR
C:  If Subway provides take-out service and receives many negative
    reviews, then its rating is greater than 9 and it does not provide
    take-out service. (label: Uncertain)
    FOL: NoTakeOutService(subway)
```

**P5 error:** A restaurant can obviously have both a rating > 9 AND be popular among local residents. In fact, P4 says popular → rating > 9, so if Subway is popular, it necessarily also has rating > 9 — both are true simultaneously. XOR would make this premise false in that case. Should be inclusive-or (∨).

---

## Summary

| Error type | Unique instances | Affected examples |
|---|---|---|
| Statement misalignment | ~20 premises | 9-11, 93, 105-107, 173-175 |
| XOR for biconditional | ~5 | 3-5, 128-131 |
| De Morgan (¬(A∧B) vs ¬A∧¬B) | ~3 | 27-29, 73, 128-131 |
| Semantic mismatch | ~2 | 46-48 |
| Wrong arity / argument order | ~7 | 21-23, 194-196 |
| Converse implication | 1 | 36-38 |
| Wrong quantifier | 1 | 96-98 |
| Operator precedence | 1 | 112-114 |
| Negation inversion | 1 | 76-78 |
| XOR for inclusive-or | ~3 | 84-86, 128-131 |

Errors were detected automatically via round-trip verification (FOL → English → compare against original NL) using `cotlog.claimcheck` and confirmed by manual review. An additional ~60 flagged discrepancies were false positives due to predicate-naming conventions and were excluded from this report.

---

## FOLIO v2 comparison (2026-03-11)

The Yale NLP group released a revised dataset (`folio_v2_validation.jsonl`, 203 examples) on [HuggingFace](https://huggingface.co/datasets/yale-nlp/FOLIO). We checked every error above against v2 by matching examples on premise text (indices shifted due to removals).

### Status of each error in v2

| # | Error | v1 indices | v2 status | Notes |
|---|---|---|---|---|
| 1 | XOR for biconditional | 3–5 | **Fixed** | P7 FOL now uses `¬(A ⊕ B)` (= A ↔ B). NL rewritten to explicit biconditional. v2 keeps only 1 of the 3 examples. |
| 2 | De Morgan (Marvin) | 27–29 | **Fixed** | NL rewritten ("either both or neither"). FOL uses `¬(A ⊕ B)`. Gold label for "Marvin is an alien" changed from False to Uncertain. |
| 2b | De Morgan (wedding/Paris) | 128–131 | **Removed** | Entire problem set deleted from v2. |
| 3 | De Morgan in conclusion (KO) | 73 | **Fixed** | Conclusion FOL now correctly uses `¬A ∧ ¬B` for "neither A nor B." |
| 4a | Misalignment (wild turkeys) | 9–11 | **Fixed** | P1 no longer split across lines; 6 FOL formulas for 6 premises. |
| 4b | Misalignment (rental/cat) | 93 | **Fixed** | Problem restructured with additional premises; all FOLs aligned. |
| 4c | Misalignment (GRE/ETS) | 105–107 | **Fixed** | Problem restructured; all FOLs aligned. |
| 4d | Misalignment (salad/health) | 173–175 | **Fixed** | Problem substantially rewritten; all FOLs aligned. |
| 5 | Semantic mismatch (Mia/Emma) | 46–48 | **Fixed** | P4 FOL now uses `∀x ∀y (Season(x) ∧ Season(y) ∧ Favorite(mia,x) ∧ Favorite(emma,y) → ¬(x=y))`. |
| 6 | Converse implication (Beethoven) | 36–38 | **Fixed** | P2 FOL now `∀x (MusicPiece(x) → ∃y (Composer(y) ∧ Write(y,x)))`. However, v2 P7 has a new precedence issue with `∃y` scoping. |
| 7 | Wrong arity (Karen/Share) | 21–23 | **Fixed** | `Share(x, lisa)` → `ShareWith(karen, x, lisa)` (3-ary). |
| 8 | Wrong arity/order (du Maurier) | 194–196 | **Partially fixed** | P1 fixed (`WinnerOf(steinhauer, ...)`), but P2 and P5 still have tournament as first argument. |
| 9 | Wrong quantifier (koala) | 96–98 | **Removed** | Entire problem set deleted from v2. |
| 10 | Operator precedence (Picuris) | 112–114 | **Fixed** | Parentheses added: `MountainRange(pm) ∧ (In(pm, NM) ⊕ In(pm, TX))`. Uses XOR, defensible for mutually exclusive locations. |
| 11 | Negation inversion (Mary/jobs) | 76–78 | **Fixed** | Predicate renamed from `NotPicky` to `PickyEater`, eliminating the double-negation bug. |
| 12 | XOR for inclusive-or (Subway) | 84–86 | **Not fixed** | Still uses ⊕ where ∨ is needed. P4 (popular → rating > threshold) makes both disjuncts simultaneously satisfiable. |

### New issues introduced in v2

- **Beethoven P7 (v2 index 38):** `∀x (Orchestra(x) → (∃y Conductor(y) ∧ Lead(y, x)))` — likely missing parentheses around the existential body, leaving `Lead(y, x)` with `y` potentially unbound depending on parser precedence.
- **Subway P5 (v2 index 85):** The universal quantifier `∀x` scopes over the rating variable but not the popularity predicate, creating a structural mismatch.

### Overall

| Outcome | Count |
|---|---|
| Fixed | 9 |
| Removed | 2 |
| Partially fixed | 1 |
| Not fixed | 1 |

Most fixes were achieved by rewriting the NL premises rather than only correcting the FOL — v2 is substantially revised, not just patched. The dataset shrank from 204 to 203 validation examples.
