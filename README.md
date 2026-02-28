# cotlog

FOL Chain-of-Thought Verification — a pipeline that verifies logical entailment by translating first-order logic into TPTP format and running an automated theorem prover.

## Architecture

```
FOLIO JSONL → FOL Parser → TPTP Generator → E-prover → Result Comparator
               (Unicode FOL)   (fof(...))    (SZS status)   (accuracy)
```

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

## Usage

Run the evaluation against FOLIO validation set:

```bash
uv run python -m cotlog.eval
```

Options:

```
--limit N        Evaluate only the first N examples
--cpu-limit N    E-prover CPU time limit per problem (default: 30s)
-v, --verbose    Print per-example results
```

## Tests

```bash
uv run python -m pytest tests/
```

## How it works

**FOL Parser** (`src/cotlog/fol_parser.py`) — tokenizes and parses FOLIO's Unicode FOL notation (`∀ ∃ → ∧ ∨ ¬ ⊕ ↔`) into an AST via recursive descent.

**TPTP Generator** (`src/cotlog/tptp.py`) — renders the AST to TPTP FOF syntax for E-prover (`∀`→`!`, `∃`→`?`, `→`→`=>`, etc.).

**Prover** (`src/cotlog/prover.py`) — runs E-prover and implements three-way entailment checking:
- **True**: conjecture as-is is a `Theorem`
- **False**: negated conjecture is a `Theorem`
- **Uncertain**: neither is provable

## Results

On FOLIO validation (204 examples): **91.2% accuracy** (186/204 correct, 8 parse errors from malformed data).
