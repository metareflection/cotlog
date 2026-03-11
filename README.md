# cotlog

FOL Chain-of-Thought Verification — a pipeline that verifies logical entailment by translating first-order logic into TPTP format and running an automated theorem prover. Supports gold FOL annotations, LLM-generated FOL, and chain-of-thought verification with per-step proving.

## Setup

```bash
uv sync
brew install eprover
```

Fetch the FOLIO dataset:

```bash
mkdir -p data
git clone https://github.com/Yale-LILY/FOLIO data/folio
```

For LLM modes (`llm`, `cot`), configure AWS credentials for Bedrock access (e.g. `aws sso login` or `~/.aws/credentials`).

## Usage

### Gold FOL evaluation (no LLM needed)

Run against gold FOL annotations from the FOLIO dataset:

```bash
uv run python -m cotlog.eval --mode gold
```

### LLM FOL generation

Have an LLM translate natural language to FOL, then verify via E-prover:

```bash
uv run python -m cotlog.eval --mode llm --limit 10 -v
```

### Chain-of-thought verification (eval)

Run CoT verification over FOLIO examples and report verification statistics (not accuracy — CoT checks internal reasoning consistency, not agreement with gold labels):

```bash
uv run python -m cotlog.eval --mode cot --limit 10 -v
```

### Standalone CoT verification

Verify any natural language argument, independent of the FOLIO dataset:

```bash
# From CLI flags
uv run python -m cotlog.cot \
  --premise "All humans are mortal." \
  --premise "Socrates is human." \
  --conclusion "Socrates is mortal."

# From a JSON file
uv run python -m cotlog.cot input.json

# Machine-readable output
uv run python -m cotlog.cot --json \
  --premise "All humans are mortal." \
  --premise "Socrates is human." \
  --conclusion "Socrates is mortal."
```

The JSON file format is `{"premises": ["..."], "conclusion": "..."}`. Use `--max-retries N` to control feedback loop iterations, `--model` to pick a model, and `-v` for verbose step reasoning.

### Refinement loop

Uses formalization as a diagnostic tool to surface ambiguities in natural language, then refines the premises to remove them. See [REFINE.md](REFINE.md) for the full proposal.

Run on the included examples:

```bash
uv run python -m cotlog --mode refine --data examples/refine-examples.jsonl -v
```

Or run the standalone demo:

```bash
uv run python examples/refine_demo.py
```

To add new examples, append to `examples/refine-examples.jsonl` — same format as FOLIO (the `premises-FOL` and `conclusion-FOL` fields can be empty since the loop generates its own):

```json
{"premises": ["...", "..."], "premises-FOL": [], "conclusion": "...", "conclusion-FOL": "", "label": "True"}
```

Refine-specific options:

```
--max-iterations N        Max refinement iterations (default: 3)
--stability-n N           Independent formalizations per stability check (default: 5)
--stability-threshold F   Structural agreement threshold to stop (default: 0.9)
```

### Options

```
--mode MODE        gold (default), llm, cot, or refine
--model NAME       LLM model: sonnet (default), haiku, opus, or a full model ARN
--limit N          Evaluate only the first N examples
--cpu-limit N      E-prover CPU time limit per problem (default: 30s)
--output-dir DIR   Directory for result files (default: results/)
-v, --verbose      Print per-example results
```

### Result caching

Each run writes two files to `results/` (or the directory specified by `--output-dir`):

```
results/{mode}_{YYYYMMDD_HHMMSS}.jsonl   — one JSON object per example
results/{mode}_{YYYYMMDD_HHMMSS}.txt     — human-readable summary report
```

The JSONL file contains per-example records with timing, error info, and mode-specific fields. Inspect with `jq`:

```bash
# Gold/LLM: find mismatches
cat results/llm_*.jsonl | jq 'select(.correct == false)'

# CoT: find examples with unverified steps
cat results/cot_*.jsonl | jq 'select(.all_steps_verified == false) | {index, conclusion, steps: [.steps[] | select(.verified == false) | {step_num, error, fol_str}]}'
```

## How it works

**FOL Parser** (`src/cotlog/fol_parser.py`) — tokenizes and parses FOLIO's Unicode FOL notation (`∀ ∃ → ∧ ∨ ¬ ⊕ ↔`) into an AST via recursive descent.

**TPTP Generator** (`src/cotlog/tptp.py`) — renders the AST to TPTP FOF syntax for E-prover (`∀`→`!`, `∃`→`?`, `→`→`=>`, etc.).

**Prover** (`src/cotlog/prover.py`) — runs E-prover and implements three-way entailment checking:
- **True**: conjecture as-is is a `Theorem`
- **False**: negated conjecture is a `Theorem`
- **Uncertain**: neither is provable

**LLM Client** (`src/cotlog/llm.py`) — Claude via Bedrock. Configured through `AWS_REGION` and `CLAUDE_MODEL` env vars.

**FOL Generation** (`src/cotlog/fol_gen.py`) — prompts the LLM with few-shot examples to translate NL premises/conclusion into FOL, then feeds the result through the standard prover pipeline.

**CoT Verification** (`src/cotlog/cot_verify.py`) — multi-turn pipeline: the LLM formalizes all premises and the conclusion into FOL using its own consistent vocabulary, then reasons step-by-step with a FOL formula per step. Each step is verified against the LLM's formalized premises plus previously verified steps, and the conclusion is verified against the full accumulated knowledge. When steps fail, prover errors are fed back to the LLM for revision (up to 2 retries by default). No gold FOL is needed.

## Tests

```bash
uv run python -m pytest tests/
```

## Results

Gold FOL on FOLIO validation (204 examples): **91.2% accuracy** (186/204 correct, 8 parse errors from malformed data).

## Known limitations

- **No equality support**: The FOL parser doesn't handle `=` or `≠`. LLM-generated steps using equality will fail to parse.
- **Uncertain conclusions can't be "proved"**: When the correct answer is Uncertain, the prover returns Uncertain by design (neither the conjecture nor its negation is provable). These aren't verification failures — they're correct, but they don't count as "fully verified" in the current reporting.
- **LLM may assume unstated facts**: Steps like `Employee(james)` that assert facts not in the premises are legitimately unverifiable by the prover.

See [DESIGN.md](DESIGN.md) for full architectural details.
