"""Task B: Chain-of-thought verification with per-step FOL proving."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .fol_parser import parse_fol
from .llm import generate
from .prover import prove_example
from .tptp import problem_to_tptp

_SYSTEM = "You are an expert in formal logic. Reason step by step, providing first-order logic for each step."

_PROMPT_TEMPLATE = """\
Given the premises below, determine whether the conclusion is True, False, or Uncertain.
Show your reasoning step by step.

For EACH step, write exactly this format:
STEP N: [natural language reasoning]
FOL: [first-order logic formula for this step]

After all steps, write your final answer as:
ANSWER: True/False/Uncertain

Use this notation for FOL:
  ∀ (forall), ∃ (exists), → (implies), ∧ (and), ∨ (or),
  ¬ (not), ⊕ (xor), ↔ (iff)

Naming conventions:
  Constants: lowercase multi-char (e.g., socrates, bonnie)
  Variables: single lowercase letters (e.g., x, y)
  Predicates: CamelCase (e.g., Human, TalentShows)

Premises:
{premises_text}

Conclusion: {conclusion}"""


@dataclass
class CotStep:
    step_num: int
    reasoning: str
    fol_str: str
    verified: bool | None = None  # None = not yet checked
    error: str | None = None


@dataclass
class CotResult:
    steps: list[CotStep] = field(default_factory=list)
    llm_answer: str | None = None  # The LLM's stated answer
    verified_label: str | None = None  # Label from step-level verification
    all_steps_verified: bool = False


def build_prompt(premises: list[str], conclusion: str) -> str:
    """Build the CoT verification prompt."""
    premises_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(premises))
    return _PROMPT_TEMPLATE.format(premises_text=premises_text, conclusion=conclusion)


_STEP_RE = re.compile(
    r'STEP\s+(\d+):\s*(.+?)\nFOL:\s*(.+?)(?=\nSTEP|\nANSWER|\Z)',
    re.DOTALL,
)
_ANSWER_RE = re.compile(r'ANSWER:\s*(True|False|Uncertain)', re.IGNORECASE)


def parse_cot_response(response: str) -> tuple[list[CotStep], str | None]:
    """Parse the LLM's CoT response into steps and a final answer.

    Returns:
        (steps, answer) where answer may be None if not found.
    """
    steps = []
    for m in _STEP_RE.finditer(response):
        step_num = int(m.group(1))
        reasoning = m.group(2).strip()
        fol_str = m.group(3).strip()
        steps.append(CotStep(step_num=step_num, reasoning=reasoning, fol_str=fol_str))

    answer_m = _ANSWER_RE.search(response)
    answer = answer_m.group(1) if answer_m else None
    if answer:
        answer = answer.capitalize()  # Normalize to "True"/"False"/"Uncertain"

    return steps, answer


def verify_steps(
    steps: list[CotStep],
    premises_fol: list[str],
    conclusion_fol: str,
    cpu_limit: int = 30,
) -> CotResult:
    """Verify each CoT step using the E-prover.

    For step N, check that its FOL follows from:
    - The original premises (as FOL)
    - All previously verified steps' FOL

    Finally, check the conclusion against all verified steps + premises.
    """
    # Parse premise FOL strings to AST
    premises_ast = []
    for p in premises_fol:
        try:
            premises_ast.append(parse_fol(p))
        except Exception:
            pass  # Skip unparseable premises

    verified_ast = list(premises_ast)  # Accumulate verified formulas
    result = CotResult(steps=steps)

    for step in steps:
        try:
            step_ast = parse_fol(step.fol_str)
        except Exception as e:
            step.verified = False
            step.error = f"Parse error: {e}"
            continue

        try:
            prover_result = prove_example(
                premises_tptp=[],
                conjecture_tptp='',
                premises_ast=verified_ast,
                conjecture_ast=step_ast,
                cpu_limit=cpu_limit,
            )
            if prover_result.label == 'True':
                step.verified = True
                verified_ast.append(step_ast)
            else:
                step.verified = False
                step.error = f"Prover: {prover_result.szs_status}"
        except Exception as e:
            step.verified = False
            step.error = f"Prover error: {e}"

    result.all_steps_verified = all(s.verified for s in steps)

    # Try to verify the final conclusion from accumulated knowledge
    try:
        conj_ast = parse_fol(conclusion_fol)
        final_result = prove_example(
            premises_tptp=[],
            conjecture_tptp='',
            premises_ast=verified_ast,
            conjecture_ast=conj_ast,
            cpu_limit=cpu_limit,
        )
        result.verified_label = final_result.label
    except Exception:
        result.verified_label = 'Uncertain'

    return result


def verify_cot(
    premises: list[str],
    conclusion: str,
    premises_fol: list[str],
    conclusion_fol: str,
    *,
    model: str | None = None,
    cpu_limit: int = 30,
) -> CotResult:
    """Full CoT verification pipeline.

    1. Prompt LLM for step-by-step reasoning with FOL
    2. Parse the response
    3. Verify each step via E-prover
    4. Return detailed results

    Args:
        premises: NL premises (for the LLM prompt).
        conclusion: NL conclusion (for the LLM prompt).
        premises_fol: Gold FOL premises (for prover verification).
        conclusion_fol: Gold FOL conclusion (for prover verification).
        model: Optional model override.
        cpu_limit: E-prover CPU limit per step.
    """
    prompt = build_prompt(premises, conclusion)
    response = generate(prompt, system=_SYSTEM, model=model)
    steps, answer = parse_cot_response(response)

    result = verify_steps(steps, premises_fol, conclusion_fol, cpu_limit=cpu_limit)
    result.llm_answer = answer
    return result
