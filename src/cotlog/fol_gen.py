"""Task A: LLM-based FOL generation from natural language."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .llm import generate

_SYSTEM = "You are an expert in formal logic. Translate natural language to first-order logic precisely."

_PROMPT_TEMPLATE = """\
Translate the following natural language premises and conclusion into first-order logic.

Use this notation:
  ∀ (forall), ∃ (exists), → (implies), ∧ (and), ∨ (or),
  ¬ (not), ⊕ (xor), ↔ (iff)

Naming conventions:
  Constants: lowercase multi-char (e.g., socrates, bonnie, rina)
  Variables: single lowercase letters (e.g., x, y, z)
  Predicates: CamelCase (e.g., Human, TalentShows, Love)

Here are some examples:

Example 1:
Premises:
1. All people who regularly drink coffee are dependent on caffeine.
2. People either regularly drink coffee or joke about being addicted to caffeine.
3. No one who jokes about being addicted to caffeine is unaware that caffeine is a drug.

Conclusion: If someone jokes about being addicted to caffeine, they are not unaware that caffeine is a drug.

P: ∀x (Drinks(x) → Dependent(x))
P: ∀x (Drinks(x) ⊕ Jokes(x))
P: ∀x (Jokes(x) → ¬Unaware(x))
C: ∀x (Jokes(x) → ¬Unaware(x))

Example 2:
Premises:
1. Miroslav Venhoda was a Czech choral conductor who specialized in the performance of Renaissance and Baroque music.
2. Any choral conductor is a musician.
3. Some musicians love music.
4. Miroslav Venhoda published a book in 1946 called Method of Studying Gregorian Chant.

Conclusion: Miroslav Venhoda loved music.

P: Czech(miroslav) ∧ ChoralConductor(miroslav) ∧ Specialize(miroslav, renaissance) ∧ Specialize(miroslav, baroque)
P: ∀x (ChoralConductor(x) → Musician(x))
P: ∃x (Musician(x) → Love(x, music))
P: Book(methodOfStudyingGregorianChant) ∧ Author(miroslav, methodOfStudyingGregorianChant) ∧ Publish(methodOfStudyingGregorianChant, year1946)
C: Love(miroslav, music)

Now translate:

Premises:
{premises_text}

Conclusion: {conclusion}

Output each premise FOL on its own line prefixed with "P: ",
and the conclusion FOL on a line prefixed with "C: ".
Do not include any other text."""


def build_prompt(premises: list[str], conclusion: str) -> str:
    """Build the FOL generation prompt from NL premises and conclusion."""
    premises_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(premises))
    return _PROMPT_TEMPLATE.format(premises_text=premises_text, conclusion=conclusion)


_P_RE = re.compile(r'^P:\s*(.+)$', re.MULTILINE)
_C_RE = re.compile(r'^C:\s*(.+)$', re.MULTILINE)


def parse_fol_response(response: str) -> tuple[list[str], str]:
    """Parse the LLM response into FOL premise strings and a conclusion string.

    Returns:
        (premises_fol, conclusion_fol)

    Raises:
        ValueError if parsing fails.
    """
    premises = _P_RE.findall(response)
    conclusions = _C_RE.findall(response)
    if not premises:
        raise ValueError(f"No premises found in LLM response:\n{response}")
    if not conclusions:
        raise ValueError(f"No conclusion found in LLM response:\n{response}")
    return [p.strip() for p in premises], conclusions[-1].strip()


@dataclass
class FolGenResult:
    """Result of FOL generation from natural language."""
    premises_fol: list[str]
    conclusion_fol: str
    raw_response: str


def generate_fol(
    premises: list[str],
    conclusion: str,
    *,
    model: str | None = None,
) -> FolGenResult:
    """Generate FOL from natural language using an LLM.

    Args:
        premises: Natural language premise strings.
        conclusion: Natural language conclusion string.
        model: Optional model override.

    Returns:
        FolGenResult with premises_fol, conclusion_fol, and raw_response.
    """
    prompt = build_prompt(premises, conclusion)
    response = generate(prompt, system=_SYSTEM, model=model)
    premises_fol, conclusion_fol = parse_fol_response(response)
    return FolGenResult(
        premises_fol=premises_fol,
        conclusion_fol=conclusion_fol,
        raw_response=response,
    )
