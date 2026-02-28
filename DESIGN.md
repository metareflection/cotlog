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
        └─── cot mode ───── LLM generates stepwise ───┤
                            reasoning + per-step FOL   │
                                                       ▼
                                              ┌─────────────────┐
                                              │   FOL Parser    │
                                              │  (Unicode AST)  │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  TPTP Renderer  │
                                              │  (AST → FOF)    │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │    E-prover     │
                                              │  (SZS status)   │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              True / False / Uncertain
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

**`llm.py`** — Thin Bedrock client. Single `generate()` function. Model resolved via short name (`sonnet` → `anthropic.claude-sonnet-4-6-20250514-v1:0`) or full ARN. Configured through environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `AWS_REGION` | `us-west-2` | Bedrock region |
| `CLAUDE_MODEL` | `sonnet` | Model short name or full ARN |

Auth uses the standard AWS credential chain (env vars, `~/.aws/`, instance profile, etc.) via `AnthropicBedrock`.

**`fol_gen.py`** — **Task A: LLM FOL generation.** Prompts the LLM to translate NL premises + conclusion into FOL using the same Unicode notation as FOLIO gold data. Includes 2 few-shot examples from the training set. Output format: `P:` prefixed premise lines, `C:` prefixed conclusion. Parsed via regex, then fed into the standard prover pipeline.

**`cot_verify.py`** — **Task B: Chain-of-thought verification.** Prompts the LLM to reason step-by-step, producing a FOL formula for each reasoning step. Each step is verified incrementally:
- Step 1: checked against gold FOL premises only
- Step N: checked against premises + all previously verified steps

This catches exactly where a reasoning chain breaks down. The final conclusion is verified against the full accumulated knowledge base (premises + all verified intermediate steps).

### Evaluation

**`eval.py`** — Harness with three modes:

| Mode | What it does | LLM needed |
|---|---|---|
| `--mode gold` | Uses gold FOL annotations from FOLIO | No |
| `--mode llm` | LLM generates FOL, prover verifies | Yes |
| `--mode cot` | LLM generates CoT + FOL, each step verified | Yes |

Reports accuracy, confusion matrix, and (for CoT) step-level verification rate and LLM self-reported answer accuracy.

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
FolioExample.premises (NL) ──build_prompt──▶ LLM ──parse_cot_response──▶ steps[]{fol_str}
FolioExample.conclusion (NL) ─────────────────┘                               │
                                                                               │
FolioExample.premises_fol ──parse_fol──▶ premises_ast                          │
                                              │                                │
                      ┌───────────────────────┘                                │
                      │                                                        │
                      ▼            for each step:                              │
              verified_ast ◀─────── parse_fol(step.fol_str)                    │
              (accumulates)         prove_example(verified_ast, step_ast)      │
                      │               ├── Theorem → verified, add to pool      │
                      │               └── else → not verified                  │
                      │                                                        │
                      ▼                                                        │
              prove_example(verified_ast, conclusion_fol) ──▶ verified_label
```

CoT mode uses gold FOL premises as the verification ground truth, while the LLM generates intermediate reasoning steps. This separates "can the LLM reason correctly" from "can the LLM formalize correctly" — the premises are trusted, only the reasoning is tested.

## Prompt design

Both prompts specify the exact Unicode notation, naming conventions (single lowercase letter = variable, CamelCase = predicate, lowercase multi-char = constant), and structured output format. Temperature is set to 0 for reproducibility.

The FOL generation prompt uses 2 few-shot examples drawn from FOLIO training data — one with quantifiers and XOR, one with constants and existential quantification. The CoT prompt uses a `STEP N:` / `FOL:` / `ANSWER:` format parsed by regex.

## Testing strategy

Tests are split by what they exercise:

- **`test_fol_parser.py`** (15 tests) — Parser correctness on FOLIO notation
- **`test_tptp.py`** (11 tests) — AST-to-TPTP rendering, roundtrips, name sanitization
- **`test_prover.py`** (5 tests) — E-prover integration, three-way strategy (requires `eprover` installed)
- **`test_fol_gen.py`** (11 tests) — Prompt construction, response parsing, mocked LLM end-to-end
- **`test_cot_verify.py`** (15 tests) — CoT parsing, step verification with real E-prover, mocked LLM end-to-end

The LLM tests mock `generate()` to avoid network calls while still exercising the full parse → prove pipeline with real E-prover.

## Usage

```bash
# Gold FOL baseline
uv run python -m cotlog.eval --mode gold

# LLM FOL generation (requires AWS credentials)
uv run python -m cotlog.eval --mode llm --limit 10 -v

# CoT verification
uv run python -m cotlog.eval --mode cot --limit 10 -v

# Override model
uv run python -m cotlog.eval --mode llm --model haiku
```
