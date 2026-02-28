"""Task B: Chain-of-thought verification with per-step FOL proving."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .fol_parser import parse_fol
from .llm import chat
from .prover import prove_example

_SYSTEM = "You are an expert in first-order logic. Reason step by step, providing first-order logic for each step."

_PROMPT_TEMPLATE = """\
Given the premises below, determine whether the conclusion is True, False, or Uncertain.

First, formalize each premise into first-order logic.
Then, show your reasoning step by step.

For EACH premise, write exactly:
PREMISE N: [first-order logic formula]

Then formalize the conclusion:
CONCLUSION: [first-order logic formula]

For EACH reasoning step, write exactly:
STEP N: [natural language reasoning]
FOL: [a single first-order logic formula for this step]

After all steps, write your final answer as:
ANSWER: True/False/Uncertain

IMPORTANT:
- Each FOL line must contain exactly ONE formula, no prose or commentary.
- Use consistent predicate and constant names across all premises and steps.

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

_FEEDBACK_TEMPLATE = """\
Some of your reasoning steps could not be verified by the theorem prover. \
Please provide corrected FOL for the failed steps below.

For each corrected step, use exactly:
STEP N: [natural language reasoning]
FOL: [a single corrected first-order logic formula]

Failed steps:
{failures}

Remember: each FOL line must be a single formula with no extra text. \
Use the same predicate and constant names as your premises."""


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
    raw_response: str = ""
    premise_fols: list[str] = field(default_factory=list)
    conclusion_fol: str = ""
    rounds: int = 1

    def to_record(self) -> dict:
        """Convert to a JSON-serializable dict."""
        return {
            'llm_answer': self.llm_answer,
            'verified_label': self.verified_label,
            'all_steps_verified': self.all_steps_verified,
            'premise_fols': self.premise_fols,
            'conclusion_fol': self.conclusion_fol,
            'rounds': self.rounds,
            'raw_response': self.raw_response,
            'steps': [
                {
                    'step_num': s.step_num,
                    'reasoning': s.reasoning,
                    'fol_str': s.fol_str,
                    'verified': s.verified,
                    'error': s.error,
                }
                for s in self.steps
            ],
        }


def build_prompt(premises: list[str], conclusion: str) -> str:
    """Build the CoT verification prompt."""
    premises_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(premises))
    return _PROMPT_TEMPLATE.format(premises_text=premises_text, conclusion=conclusion)


_PREMISE_RE = re.compile(r'^PREMISE\s+\d+:\s*(.+)$', re.MULTILINE)
_CONCLUSION_RE = re.compile(r'^CONCLUSION:\s*(.+)$', re.MULTILINE)
_STEP_RE = re.compile(
    r'STEP\s+(\d+):\s*(.+?)\nFOL:\s*(.+?)(?=\nSTEP|\nANSWER|\Z)',
    re.DOTALL,
)
_ANSWER_RE = re.compile(r'ANSWER:\s*(True|False|Uncertain)', re.IGNORECASE)


def parse_cot_response(response: str) -> tuple[list[str], str | None, list[CotStep], str | None]:
    """Parse the LLM's CoT response into premise FOLs, conclusion FOL, steps, and answer.

    Returns:
        (premise_fols, conclusion_fol, steps, answer)
    """
    premise_fols = [m.strip() for m in _PREMISE_RE.findall(response)]

    conclusion_m = _CONCLUSION_RE.search(response)
    conclusion_fol = conclusion_m.group(1).strip() if conclusion_m else None

    steps = []
    for m in _STEP_RE.finditer(response):
        step_num = int(m.group(1))
        reasoning = m.group(2).strip()
        fol_str = m.group(3).strip()
        steps.append(CotStep(step_num=step_num, reasoning=reasoning, fol_str=fol_str))

    answer_m = _ANSWER_RE.search(response)
    answer = answer_m.group(1) if answer_m else None
    if answer:
        answer = answer.capitalize()

    return premise_fols, conclusion_fol, steps, answer


def build_feedback(failed_steps: list[CotStep]) -> str:
    """Build a feedback message listing failed steps and their errors."""
    lines = []
    for step in failed_steps:
        lines.append(f"- STEP {step.step_num}: {step.error}")
        lines.append(f"  Your FOL was: {step.fol_str}")
    return _FEEDBACK_TEMPLATE.format(failures="\n".join(lines))


def verify_steps(
    steps: list[CotStep],
    premise_fols: list[str],
    conclusion_fol: str | None,
    cpu_limit: int = 30,
) -> CotResult:
    """Verify each CoT step using the E-prover.

    Uses the LLM's own formalized premises as the axiom base.
    For step N, check that its FOL follows from:
    - The LLM's formalized premises
    - All previously verified steps' FOL

    Finally, check the LLM's conclusion FOL against all verified steps + premises.
    """
    # Parse LLM's premise FOL strings to AST
    premises_ast = []
    for p in premise_fols:
        try:
            premises_ast.append(parse_fol(p))
        except Exception:
            pass  # Skip unparseable premises

    verified_ast = list(premises_ast)  # Accumulate verified formulas
    result = CotResult(steps=steps, premise_fols=premise_fols)

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

    # Try to verify the LLM's conclusion from accumulated knowledge
    if conclusion_fol:
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
    else:
        result.verified_label = 'Uncertain'

    return result


def verify_cot(
    premises: list[str],
    conclusion: str,
    *,
    model: str | None = None,
    cpu_limit: int = 30,
    max_retries: int = 2,
) -> CotResult:
    """Full CoT verification pipeline with feedback loop.

    1. Prompt LLM for premise + conclusion formalization and step-by-step reasoning
    2. Parse the response
    3. Verify each step against LLM's own premises via E-prover
    4. If steps fail, send feedback and let LLM revise (up to max_retries)
    5. Verify LLM's conclusion against accumulated verified knowledge
    6. Return detailed results

    Args:
        premises: NL premises (for the LLM prompt).
        conclusion: NL conclusion (for the LLM prompt).
        model: Optional model override.
        cpu_limit: E-prover CPU limit per step.
        max_retries: Max feedback rounds (default 2).
    """
    prompt = build_prompt(premises, conclusion)
    messages: list[dict] = [{"role": "user", "content": prompt}]
    response = chat(messages, system=_SYSTEM, model=model)
    raw_responses = [response]

    premise_fols, conclusion_fol, steps, answer = parse_cot_response(response)

    result = verify_steps(steps, premise_fols, conclusion_fol, cpu_limit=cpu_limit)
    result.llm_answer = answer
    rounds = 1

    # Feedback loop
    failed = [s for s in result.steps if s.verified is False]
    retries = 0
    while failed and retries < max_retries:
        retries += 1
        rounds += 1

        feedback = build_feedback(failed)
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": feedback})
        response = chat(messages, system=_SYSTEM, model=model)
        raw_responses.append(response)

        # Parse only the corrected steps from the response
        _, _, corrected_steps, _ = parse_cot_response(response)

        # Build lookup of corrections by step number
        corrections = {s.step_num: s for s in corrected_steps}

        # Replace failed steps with corrections where available
        for i, step in enumerate(result.steps):
            if step.verified is False and step.step_num in corrections:
                corrected = corrections[step.step_num]
                result.steps[i] = corrected

        # Re-verify all steps from scratch with the updated step list
        result = verify_steps(result.steps, premise_fols, conclusion_fol, cpu_limit=cpu_limit)
        result.llm_answer = answer
        failed = [s for s in result.steps if s.verified is False]

    result.raw_response = "\n---\n".join(raw_responses)
    result.premise_fols = premise_fols
    result.conclusion_fol = conclusion_fol or ""
    result.rounds = rounds
    return result
