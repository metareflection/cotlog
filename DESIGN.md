# cotlog Design

Formal verification of natural language reasoning via first-order logic (FOL) and automated theorem proving, evaluated on the [FOLIO](https://github.com/Yale-LILY/FOLIO) benchmark.

## Architecture

```
NL premises + conclusion
        │
        ├─── gold mode ──── Gold FOL annotations ─────┐
        │                                              │
        ├─── llm mode ───── LLM generates FOL ────────┤
        │                                              │
        │                                              ▼
        │                                     ┌─────────────────┐
        │                                     │   FOL Parser    │
        │                                     │  (Unicode AST)  │
        │                                     └────────┬────────┘
        │                                              ▼
        │                                     ┌─────────────────┐
        │                                     │  TPTP Renderer  │
        │                                     └────────┬────────┘
        │                                              ▼
        │                                     ┌─────────────────┐
        │                                     │    E-prover     │
        │                                     └────────┬────────┘
        │                                              ▼
        │                                     True / False / Uncertain
        │
        └─── cot mode ───── LLM formalizes premises + conclusion,
                            reasons step-by-step with FOL
                                       │
                              verify each step via prover
                                       │
                              feedback loop on failures
                                       │
                              verify conclusion via prover
                                       ▼
                            verification report (not accuracy)
```

## Modules

### Core pipeline (no external deps besides E-prover)

**`fol_parser.py`** — Recursive-descent parser for FOLIO's Unicode FOL notation (`∀ ∃ → ∧ ∨ ¬ ⊕ ↔`) into a typed AST. Handles FOLIO data quirks like unbalanced parentheses. Operator precedence: iff/xor < implies (right-assoc) < or < and < not/quantifiers < atom.

**`tptp.py`** — Renders FOL AST to TPTP FOF syntax for E-prover. Sanitizes names (Unicode → ASCII, case conventions). Generates problem files with axioms + conjecture.

**`prover.py`** — Subprocess wrapper for E-prover. Three-way entailment strategy:
1. Try conjecture → if `Theorem`, label = **True**
2. Try negated conjecture → if `Theorem`, label = **False**
3. Otherwise → **Uncertain**

**`folio.py`** — Loads FOLIO JSONL dataset into `FolioExample` dataclasses (NL premises, FOL premises, NL conclusion, FOL conclusion, gold label).

### LLM layer (requires `anthropic[bedrock]`)

**`llm.py`** — Thin Bedrock client. `generate()` for single-shot prompts, `chat()` for multi-turn conversations. Model resolved via short name (`sonnet` → `anthropic.claude-sonnet-4-6-20250514-v1:0`) or full ARN. Configured through environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `AWS_REGION` | `us-west-2` | Bedrock region |
| `CLAUDE_MODEL` | `sonnet` | Model short name or full ARN |

Auth uses the standard AWS credential chain (env vars, `~/.aws/`, instance profile, etc.) via `AnthropicBedrock`.

**`fol_gen.py`** — **Task A: LLM FOL generation.** Prompts the LLM to translate NL premises + conclusion into FOL using the same Unicode notation as FOLIO gold data. Includes 2 few-shot examples from the training set. Output format: `P:` prefixed premise lines, `C:` prefixed conclusion. Parsed via regex, then fed into the standard prover pipeline. Returns `FolGenResult` with parsed FOL and raw LLM response.

**`cot_verify.py`** — **Task B: Chain-of-thought verification with feedback loop.** Multi-turn pipeline:
1. Prompt the LLM to formalize all premises (`PREMISE N:`) and the conclusion (`CONCLUSION:`) into FOL, then reason step-by-step (`STEP N:` / `FOL:`), using its own consistent predicate vocabulary.
2. Verify each step incrementally against the LLM's own formalized premises + previously verified steps.
3. If steps fail verification, send prover errors back to the LLM and ask it to revise (up to `max_retries` rounds, default 2).
4. Verify the LLM's formalized conclusion against accumulated verified knowledge.

The entire pipeline uses the LLM's own vocabulary — no gold FOL is needed. This avoids the naming mismatch problem and lets the prover verify full internal consistency end-to-end.

### Evaluation

**`eval.py`** — Harness with three modes:

| Mode | What it does | LLM needed |
|---|---|---|
| `--mode gold` | Uses gold FOL annotations from FOLIO | No |
| `--mode llm` | LLM generates FOL, prover verifies | Yes |
| `--mode cot` | LLM generates CoT + FOL, each step verified | Yes |

Gold and LLM modes report accuracy and confusion matrix. CoT mode reports verification statistics (fully verified rate, step verification rate, avg feedback rounds) — it measures reasoning soundness, not agreement with gold labels. Each run writes per-example JSONL and a summary TXT file to `results/` (configurable via `--output-dir`).

**`cot.py`** — Standalone CoT verification CLI. Takes arbitrary NL premises + conclusion (via flags or JSON file), runs the full CoT pipeline, prints human-readable or JSON output. Independent of any dataset.

### Claimcheck

**`claimcheck.py`** — Round-trip faithfulness verification of NL ↔ FOL. See [CLAIMCHECK.md](CLAIMCHECK.md) for the full design, discrepancy categories, and results.

## Data flow by mode

### Gold mode

```
FolioExample.premises_fol ──parse_fol──▶ AST ──problem_to_tptp──▶ TPTP ──eprover──▶ label
FolioExample.conclusion_fol ─────────────┘
```

Baseline. No LLM involved. Measures how well the gold FOL + prover pipeline recovers the gold labels.

### LLM mode

```
FolioExample.premises (NL) ──build_prompt──▶ LLM ──parse_fol_response──▶ FOL strings
FolioExample.conclusion (NL) ─────────────────┘                              │
                                                                   parse_fol │
                                                                             ▼
                                                          AST ──prover──▶ label
```

Measures LLM FOL translation quality end-to-end. Failures can occur at two points: the LLM may produce unparseable FOL (caught as `ValueError`), or the FOL may be syntactically valid but semantically wrong (wrong prover label).

### CoT mode

```
FolioExample.premises (NL) ──build_prompt──▶ LLM ──parse_cot_response──▶ premise_fols[]
FolioExample.conclusion (NL) ─────────────────┘                          steps[]{fol_str}
                                                                               │
                                    LLM's own premise FOLs ──parse_fol──▶ premises_ast
                                                                               │
                                              ┌────────────────────────────────┘
                                              │
                                              ▼            for each step:
                                      verified_ast ◀─────── parse_fol(step.fol_str)
                                      (accumulates)         prove_example(verified_ast, step_ast)
                                              │               ├── Theorem → verified, add to pool
                                              │               └── else → not verified
                                              │
                              ┌────── any failures? ──yes──▶ build_feedback ──▶ LLM (retry)
                              │                                                     │
                              no                                          parse corrections
                              │                                           re-verify failed steps
                              ▼                                           (up to max_retries)
                      prove_example(verified_ast, llm_conclusion_fol) ──▶ verified_label
```

The entire pipeline uses the LLM's own consistent vocabulary — premises, steps, and conclusion are all formalized by the LLM. The prover verifies internal consistency: each step must follow from the LLM's premises + prior verified steps, and the conclusion must follow from the accumulated knowledge. When steps fail, prover errors are fed back to the LLM for revision.

## Prompt design

Both prompts specify the exact Unicode notation, naming conventions (single lowercase letter = variable, CamelCase = predicate, lowercase multi-char = constant), and structured output format. Temperature is set to 0 for reproducibility.

The FOL generation prompt uses 2 few-shot examples drawn from FOLIO training data — one with quantifiers and XOR, one with constants and existential quantification. The CoT prompt uses a `PREMISE N:` / `CONCLUSION:` / `STEP N:` / `FOL:` / `ANSWER:` format parsed by regex, and emphasizes that each FOL line must contain exactly one formula with no prose.

## Testing strategy

Tests are split by what they exercise:

- **`test_fol_parser.py`** (15 tests) — Parser correctness on FOLIO notation
- **`test_tptp.py`** (11 tests) — AST-to-TPTP rendering, roundtrips, name sanitization
- **`test_prover.py`** (5 tests) — E-prover integration, three-way strategy (requires `eprover` installed)
- **`test_fol_gen.py`** (11 tests) — Prompt construction, response parsing, mocked LLM end-to-end
- **`test_cot_verify.py`** (18 tests) — CoT parsing, feedback construction, step verification with real E-prover, feedback loop with mocked LLM

The LLM tests mock `generate()`/`chat()` to avoid network calls while still exercising the full parse → prove pipeline with real E-prover.

## Usage

```bash
# Gold FOL baseline
uv run python -m cotlog.eval --mode gold

# LLM FOL generation (requires AWS credentials)
uv run python -m cotlog.eval --mode llm --limit 10 -v

# CoT verification statistics over FOLIO
uv run python -m cotlog.eval --mode cot --limit 10 -v

# Standalone CoT on arbitrary input
uv run python -m cotlog.cot \
  --premise "All humans are mortal." \
  --premise "Socrates is human." \
  --conclusion "Socrates is mortal."

# Override model
uv run python -m cotlog.eval --mode llm --model haiku
```
