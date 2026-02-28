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

### Chain-of-thought verification

LLM produces step-by-step reasoning with FOL for each step, each step verified incrementally:

```bash
uv run python -m cotlog.eval --mode cot --limit 10 -v
```

### Options

```
--mode MODE      gold (default), llm, or cot
--model NAME     LLM model: sonnet (default), haiku, opus, or a full model ARN
--limit N        Evaluate only the first N examples
--cpu-limit N    E-prover CPU time limit per problem (default: 30s)
-v, --verbose    Print per-example results
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

**CoT Verification** (`src/cotlog/cot_verify.py`) — prompts the LLM for step-by-step reasoning where each step includes a FOL formula. Each step is verified incrementally against the gold premises plus all previously verified steps, pinpointing exactly where reasoning chains break down.

## Tests

```bash
uv run python -m pytest tests/
```

## Results

Gold FOL on FOLIO validation (204 examples): **91.2% accuracy** (186/204 correct, 8 parse errors from malformed data).

See [DESIGN.md](DESIGN.md) for full architectural details.
