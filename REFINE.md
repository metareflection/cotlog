# Formalization as Refinement: Improving Natural Language Through Disposable Formal Specifications

## Core Insight

Autoformalization is typically framed as: "given NL, produce a faithful FOL translation." This framing is stuck because verifying faithfulness requires either (a) comparing in the formal domain, where independently-produced formalizations are structurally incompatible, or (b) comparing in the NL domain, where informalization destroys the interpretive precision that formalization added.

We propose flipping the goal. The FOL is not the end product — the **improved NL** is. Formalization is a *diagnostic tool* that surfaces ambiguity, underspecification, and implicit assumptions in natural language. The formal representation is disposable; the NL refinements it produces accumulate.

The convergence criterion is not "does F match I" but rather: **does the NL become precise enough that independent formalizations agree?**

## The Loop

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   NL₀ (original, ambiguous)                         │
│     │                                               │
│     ▼                                               │
│   FORMALIZE: NL_k → FOL_k                           │
│     │         (picks one interpretation)            │
│     ▼                                               │
│   REASON: derive implications, edge cases,          │
│           surprising consequences from FOL_k        │
│     │                                               │
│     ▼                                               │
│   SURFACE: present findings as questions or         │
│            observations about the NL                │
│     │                                               │
│     ▼                                               │
│   REFINE: revise NL_k → NL_{k+1} to resolve         │
│           identified ambiguities                    │
│     │                                               │
│     ▼                                               │
│   MEASURE STABILITY: formalize NL_{k+1} n times     │
│           independently — do they agree?            │
│     │                                               │
│     ├── if unstable → loop again (k += 1)           │
│     └── if stable   → output NL_final               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Step 1: FORMALIZE

Given `NL_k` (a set of natural language premises), produce a first-order logic representation `FOL_k`.

- Use an LLM to translate each NL premise into FOL.
- The formalization will necessarily **choose interpretations** where the NL is ambiguous. This is expected and desirable — the choices become visible in subsequent steps.
- The FOL must be syntactically valid and parseable by an FOL inference engine (e.g., Prover9, Z3, or a TPTP-compatible prover).

### Step 2: REASON

Run the FOL through a theorem prover or inference engine.

- Derive all non-trivial consequences of the premises.
- Identify edge cases: what is true? What is false? What is unknown/undecidable from the premises?
- Check for unexpected consequences: does the formalization entail something that seems wrong or surprising given the NL?
- Check for vacuous truths, trivially satisfied conditions, or contradictions.

### Step 3: SURFACE

Translate the formal findings back into natural language observations and questions.

- "Your premises entail X — is that intended?"
- "The phrase 'all children are human' was interpreted as ∀x(Child(x) → Human(x)). This means adopted children count. Is that the intent?"
- "The premises are consistent with a world where no one is underage. Should that be possible?"
- "The following conclusion cannot be derived either way (Unknown). Is the NL missing a premise, or is this genuinely indeterminate?"

This step uses an LLM to produce human-readable diagnostics. The key: **never ask the user to evaluate FOL**. All communication happens in NL.

### Step 4: REFINE

Revise the NL to address the surfaced issues.

- Add precision where ambiguity was detected: "all children" → "every person who is a child"
- Add missing premises that were implicitly assumed
- Clarify scope, quantifier boundaries, edge cases
- Remove or rephrase wording that led to unintended formalizations

This step can be done by:
- A human (gold standard, most trustworthy)
- An LLM acting as a "specification writer" (automated, scalable)
- A hybrid where the LLM proposes and a human approves

### Step 5: MEASURE STABILITY

Formalize `NL_{k+1}` **n times independently** (different LLM calls, different temperatures, possibly different models).

- Parse each formalization into a canonical form.
- Measure agreement among the n formalizations.
- Stability metric: what fraction of premise-pairs produce logically equivalent formalizations across the n attempts?

If stability is above a threshold, stop. If not, loop.

## Termination Conditions

The loop terminates when any of:

1. **Stability threshold reached**: independent formalizations agree at rate ≥ τ (e.g., τ = 0.9)
2. **Max iterations**: k reaches a budget limit (e.g., k = 5)
3. **No new issues surfaced**: the REASON step produces no surprising consequences that weren't already addressed

## Evaluation on FOLIO

### Why FOLIO

FOLIO provides 487 stories (premise sets) with 1,430 conclusions, each annotated with:
- Natural language premises and conclusions
- Gold FOL translations of each premise/conclusion
- Entailment labels: True, False, or Unknown

This gives us a rich evaluation substrate without requiring us to match the gold FOL.

### Evaluation Axes

#### Axis 1: Formalization Stability (primary metric)

**Measures: did the loop reduce ambiguity in the NL?**

For each story:
1. Take `NL_0` (original FOLIO premises)
2. Formalize n times independently → measure agreement rate `S_0`
3. Run the loop for k iterations → produce `NL_k`
4. Formalize `NL_k` n times independently → measure agreement rate `S_k`
5. Report `ΔS = S_k - S_0`

Agreement is measured by:
- **Logical equivalence** (ideal): for each premise, are the n FOL translations logically equivalent? Check via ATP or SMT solver. This is expensive but precise.
- **Structural equivalence** (practical): after normalizing variable names and predicate ordering, do the ASTs match? Cheaper, but may undercount equivalent-but-different formulations.
- **Entailment preservation** (lightweight): do all n formalizations, when combined with the conclusion, yield the same True/False/Unknown label? This doesn't check per-premise agreement but checks whether disagreements are consequential.

We recommend reporting all three, with logical equivalence as the gold standard.

#### Axis 2: Faithfulness (safety check)

**Measures: did the loop distort the meaning?**

For each story and its associated conclusions:
1. Evaluate the entailment label (True/False/Unknown) using the **refined** NL
2. Compare to FOLIO's gold label
3. Report:
   - **Preservation rate**: fraction of conclusions where the label is unchanged
   - **Flip analysis**: for each label change, categorize as:
     - **Legitimate disambiguation**: the original NL was genuinely ambiguous about this conclusion, and the refinement resolved it one way. (Interesting finding, not a failure.)
     - **Error**: the refinement introduced a distortion. (Actual failure.)

Distinguishing legitimate disambiguation from error requires manual inspection on a sample. We propose inspecting all flipped cases (expected to be a small fraction).

#### Axis 3: Refinement Quality (qualitative)

**Measures: are the NL changes meaningful and natural?**

- Human evaluation on a sample of (NL_0, NL_final) pairs
- Rate on: (a) Does the refined NL read naturally? (b) Are the changes substantive (not just trivial rephrasing)? (c) Would a human agree the refined version is more precise?

### Baselines

1. **No refinement (NL_0 directly)**: formalization stability of the original FOLIO NL. This is the lower bound.
2. **Gold FOL informalized**: take FOLIO's gold FOL, informalize back to NL, measure that NL's stability. This gives an approximate upper bound — NL that was "designed" to be unambiguous (though informalization may re-introduce ambiguity).
3. **Single-pass clarification**: ask an LLM to "make this NL more precise" without any formalization step. This ablates the formalization — is the FOL reasoning actually helping, or is just asking an LLM to clarify sufficient?
4. **Multi-pass clarification without FOL**: run the loop but skip FORMALIZE and REASON — just repeatedly ask the LLM "what's ambiguous here? refine it." This ablates the formal reasoning specifically.

### Expected Results / Hypotheses

- **H1**: The loop increases formalization stability (ΔS > 0). Independent formalizations of refined NL agree more than those of original NL.
- **H2**: Faithfulness is high (>90% label preservation), with a small number of interesting cases where disambiguation flips a label.
- **H3**: The full loop (with formalization + reasoning) outperforms the ablations (baselines 3 and 4), demonstrating that formal reasoning contributes something beyond LLM-based clarification alone.
- **H4**: The loop converges quickly — most stability gains happen in the first 1–2 iterations.
- **H5**: Stories with lower initial stability (more ambiguous NL) show greater improvement.

## System Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│              │     │              │     │              │
│   LLM        │────▶│  FOL Parser  │────▶│  Prover /    │
│  (formalize) │     │  (validate)  │     │  Reasoner    │
│              │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
       ▲                                        │
       │                                        │
       │                                        ▼
┌──────────────┐                         ┌──────────────┐
│              │                         │              │
│   LLM        │◀────────────────────────│   LLM        │
│  (refine NL) │                         │  (surface    │
│              │                         │   findings)  │
└──────────────┘                         └──────────────┘
```

### Components

1. **Formalizer**: LLM prompted to translate NL premises → FOL. Must output syntactically valid FOL in a specified format (e.g., TPTP syntax, or a custom s-expression format parseable by the prover).

2. **Validator/Parser**: Checks syntactic validity of FOL output. Rejects and retries malformed output.

3. **Reasoner**: FOL inference engine. Options:
   - Prover9/Mace4 (classical first-order, well-suited to FOLIO's logic fragment)
   - Z3 (SMT solver, more powerful but may be overkill)
   - Vampire / E (high-performance ATP)
   
   The reasoner should:
   - Attempt to prove each conclusion
   - Enumerate non-trivial consequences of the premises
   - Check for contradictions
   - Find models/countermodels where relevant

4. **Surfacer**: LLM prompted with the FOL, the reasoning results, and the original NL. Produces natural language observations about discrepancies, edge cases, and implicit choices.

5. **Refiner**: LLM prompted with the original NL and the surfaced observations. Produces revised NL that addresses the identified issues while preserving the original intent.

6. **Stability Measurer**: Runs the Formalizer n times on the same NL input (varying temperature / random seed / model). Compares outputs for logical equivalence.

### Implementation Notes

- Prefer Node.js for orchestration (CLI tool or library).
- FOL inference can shell out to Prover9 or call Z3 via its JS bindings.
- Each LLM call should be independent (no shared context between formalizer instances in the stability measurement step).
- Log everything: each iteration's NL, FOL, reasoning results, surfaced observations, and refined NL. The trace is valuable data.

## What This Is Not

- **Not a new autoformalization method.** We don't claim to formalize better than anyone else. The formalization is a means, not an end.
- **Not a verification tool.** We're not proving code correct. We're improving specifications.
- **Not dependent on formalization quality.** Even a *bad* formalization is useful if it reveals an ambiguity. A formalization that "gets it wrong" is often surfacing a genuine interpretive choice.

## What This Is

A demonstration that **formal reasoning is useful as a specification refinement tool**, even when the formalization itself is imperfect and disposable. The formal domain serves as a "clean room" where ambiguities become visible — not because the FOL is right, but because it is *precise*, and precision makes disagreement detectable.

The conceptual contribution: **the theory of autoformalization has been asking the wrong question.** The question is not "how do we guarantee F matches I." The question is "how do we use F to make I better." The guarantee is not about the formalization — it's about the *convergence* of the natural language toward unambiguity, as witnessed by formalization stability.

## Lessons from Implementation

We implemented the loop in Python (see `src/cotlog/refine.py`) using Claude via Bedrock for LLM steps and E-prover for reasoning, then ran it on 10 custom examples (`examples/refine-examples.jsonl`) and a subset of FOLIO. Key findings:

### Structural agreement is the right convergence metric

The document proposes three stability metrics: logical equivalence, structural equivalence, and entailment preservation. In practice, **entailment preservation is nearly useless** — it reads 100% on almost everything because structurally different formalizations tend to produce the same prover label (often "Uncertain" when the prover times out, or the same True/False when the conclusion is straightforward). It never triggered the refinement loop.

Structural agreement (normalizing each premise's FOL to a canonical AST and comparing pairwise across independent formalizations) is the metric that actually discriminates. On our custom examples, initial structural agreement ranged from 54% to 100%, while entailment agreement was 80-100%. The loop should converge on structural agreement, with entailment preservation as a sanity check.

### The loop works on naturally ambiguous text

On 10 custom examples with everyday ambiguities, 4 had low initial structural stability. All 4 reached 100% after 1-2 iterations. The surfacer found substantive issues:

- **Inclusive vs. exclusive "or"**: "serves Italian food or Chinese food" → "serves at least one of Italian food or Chinese food (and possibly both)"
- **Necessary vs. sufficient conditions**: "To get a driver's license, you must pass both tests" was formalized inconsistently as necessary-condition vs. sufficient-condition across runs. Refinement produced separate premises for each direction.
- **Implicit category membership**: "Tom owns a cat named Whiskers" does not entail Whiskers is a *pet* — the surfacer caught this and refinement added "keeps a cat as his pet."
- **Normative vs. factual claims**: "must show a valid ID" was refined to "has a valid ID" to distinguish policy from state.

Convergence is fast — most gains happen in iteration 1 (confirming H4).

### FOLIO is the wrong evaluation substrate

FOLIO premises are logic puzzles designed to be precise-but-tricky. The refinement loop either found nothing to do (already stable) or actively made things worse. On one FOLIO story (the Bonnie/talent-show premises), structural stability went from 71% to 31% — the refined NL was harder to formalize consistently than the original.

The problem: when forced to "find ambiguities" in already-precise text, the surfacer invents issues that aren't there and "fixes" them in ways that change meaning. FOLIO tests logical reasoning, not specification quality. Better evaluation substrates would be software requirements, legal clauses, or API specifications — domains where ambiguity is a bug, not a feature.

### Refinement is not monotonic

The loop can make things worse. A rewrite that resolves one ambiguity may introduce new phrasing that the LLM formalizes less consistently. This suggests the loop needs a **no-regression guard**: if an iteration decreases structural stability, revert to the previous NL and stop.

### Partial answers to open questions

- **Can the loop be fully automated?** (Q2) Yes, for surfacing and proposing refinements. But the refiner LLM does introduce bias — it tends to "disambiguate" toward the most common reading rather than the intended one. The Bonnie example showed this: the LLM simplified a precise biconditional into a simpler conditional, losing information. For high-stakes use, human approval of refinements is warranted.
- **Does stability imply correctness?** (Q3) No. On our "every student passed a test" demo, the refined premises reached 100% structural stability but changed the entailment label from True to False. The original True was vacuous (from contradictory premises), so the label flip was actually an improvement — but this shows stability and correctness are independent.
- **Transfer across domains** (Q5) The custom examples (everyday reasoning about restaurants, drivers' licenses, committees) worked well. FOLIO (logic puzzles) did not. This suggests the approach is better suited to specification-like text than to pre-formalized domains.

## Open Questions

1. **What fragment of FOL is sufficient?** Full FOL may be overkill for many NL statements. Could a restricted fragment (e.g., effectively propositional, or monadic FOL) capture enough to be useful while being easier to reason about?

2. **Can the loop be fully automated?** If the refiner is an LLM, does it introduce its own biases — always "disambiguating" toward the most common interpretation rather than the intended one? Is human-in-the-loop necessary for high-stakes applications?

3. **Does stability imply correctness?** Convergence of formalizations means the NL is unambiguous, but it could be unambiguously *wrong* — precise but not what was intended. Stability is necessary but not sufficient. What additional check, if any, is needed?

4. **What is the theoretical limit?** Is there a class of NL statements for which no finite number of refinement iterations can achieve stability? What characterizes such statements?

5. **Transfer across domains.** FOLIO is logic puzzles. Does the approach work for software requirements? Legal text? Mathematical theorems? The loop is domain-agnostic in principle, but the effectiveness of each step may vary.
