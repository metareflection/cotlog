"""Refinement loop: formalize → reason → surface → refine → measure stability."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .fol_gen import build_prompt as build_fol_prompt, parse_fol_response
from .fol_parser import parse_fol
from .llm import generate
from .prover import prove_example
from .tptp import formula_to_tptp


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class ReasoningFindings:
    """Results from the REASON step."""
    provable_conclusions: list[str]      # conclusions proved True
    refuted_conclusions: list[str]       # conclusions proved False
    undetermined: list[str]              # could not prove either way
    contradictions: bool = False         # premises are contradictory
    raw_prover_output: str = ""


@dataclass
class StabilityResult:
    """Results from measuring formalization stability."""
    n_formalizations: int
    agreement_rate: float           # entailment-preservation: fraction agreeing on label
    structural_agreement: float     # structural: avg per-premise AST match rate across pairs
    labels: list[str]               # label from each independent formalization
    formalizations: list[list[str]] # raw FOL strings per run
    errors: list[str]               # parse/prover errors


@dataclass
class RefineIteration:
    """Record of a single refinement iteration."""
    k: int
    nl: list[str]                       # NL premises at this iteration
    fol_strings: list[str] | None = None
    findings: ReasoningFindings | None = None
    observations: str = ""
    stability: StabilityResult | None = None


@dataclass
class RefineResult:
    """Full result of the refinement loop."""
    original_premises: list[str]
    conclusion: str
    refined_premises: list[str]
    iterations: list[RefineIteration] = field(default_factory=list)
    initial_stability: StabilityResult | None = None
    final_stability: StabilityResult | None = None
    total_iterations: int = 0

    def to_record(self) -> dict:
        return {
            'original_premises': self.original_premises,
            'conclusion': self.conclusion,
            'refined_premises': self.refined_premises,
            'total_iterations': self.total_iterations,
            'initial_stability': _stability_to_dict(self.initial_stability),
            'final_stability': _stability_to_dict(self.final_stability),
            'iterations': [
                {
                    'k': it.k,
                    'nl': it.nl,
                    'fol_strings': it.fol_strings,
                    'observations': it.observations,
                    'stability': _stability_to_dict(it.stability),
                }
                for it in self.iterations
            ],
        }


def _stability_to_dict(s: StabilityResult | None) -> dict | None:
    if s is None:
        return None
    return {
        'n_formalizations': s.n_formalizations,
        'agreement_rate': s.agreement_rate,
        'structural_agreement': s.structural_agreement,
        'labels': s.labels,
        'formalizations': s.formalizations,
        'errors': s.errors,
    }


# ── Step 1: FORMALIZE ────────────────────────────────────────────────────────

_FOL_SYSTEM = "You are an expert in formal logic. Translate natural language to first-order logic precisely."


def formalize(
    premises: list[str],
    conclusion: str,
    *,
    model: str | None = None,
    temperature: float = 0.0,
) -> tuple[list[str], str, str]:
    """Formalize NL premises + conclusion into FOL strings.

    Returns:
        (premises_fol, conclusion_fol, raw_response)
    """
    prompt = build_fol_prompt(premises, conclusion)
    response = generate(prompt, system=_FOL_SYSTEM, model=model, temperature=temperature)
    premises_fol, conclusion_fol = parse_fol_response(response)
    return premises_fol, conclusion_fol, response


# ── Step 2: REASON ────────────────────────────────────────────────────────────

def reason(
    premises_fol: list[str],
    conclusion_fol: str,
    *,
    cpu_limit: int = 30,
) -> ReasoningFindings:
    """Run FOL through the prover and collect findings."""
    findings = ReasoningFindings(
        provable_conclusions=[],
        refuted_conclusions=[],
        undetermined=[],
    )

    try:
        premises_ast = [parse_fol(p) for p in premises_fol]
        conjecture_ast = parse_fol(conclusion_fol)
    except Exception as e:
        findings.undetermined.append(f"Parse error: {e}")
        return findings

    try:
        result = prove_example(
            premises_tptp=[],
            conjecture_tptp='',
            premises_ast=premises_ast,
            conjecture_ast=conjecture_ast,
            cpu_limit=cpu_limit,
        )
        findings.raw_prover_output = result.stdout

        if result.label == 'True':
            findings.provable_conclusions.append(conclusion_fol)
        elif result.label == 'False':
            findings.refuted_conclusions.append(conclusion_fol)
        else:
            findings.undetermined.append(conclusion_fol)

        # Check for contradictions: try proving False from premises alone
        from .fol_parser import Predicate
        false_const = Predicate("false_prop", [])
        from .prover import run_eprover
        from .tptp import problem_to_tptp
        contra_tptp = problem_to_tptp(premises_ast, false_const)
        contra_result = run_eprover(contra_tptp, cpu_limit=min(cpu_limit, 10))
        if contra_result.szs_status == 'Theorem':
            findings.contradictions = True

    except Exception as e:
        findings.undetermined.append(f"Prover error: {e}")

    return findings


# ── Step 3: SURFACE ───────────────────────────────────────────────────────────

_SURFACE_SYSTEM = (
    "You are a specification analyst. Your job is to identify ambiguities, "
    "implicit assumptions, and underspecification in natural language premises. "
    "Communicate findings clearly in plain English. Never ask the user to evaluate "
    "formal logic — keep everything in natural language."
)

_SURFACE_TEMPLATE = """\
I formalized the following natural language premises and ran them through a \
theorem prover. Here are the findings. Please identify any ambiguities, \
implicit assumptions, or surprising consequences.

Original premises:
{premises_text}

Conclusion: {conclusion}

Formal logic chose these interpretations:
{fol_text}

Prover findings:
- Conclusion status: {conclusion_status}
{contradiction_note}\
{extra_findings}

For each issue you find, explain:
1. What specific phrase or premise is ambiguous or underspecified
2. What interpretation was chosen during formalization
3. What alternative interpretation might have been intended
4. What the natural language should say to remove the ambiguity

Be concise. Focus on substantive ambiguities, not trivial rephrasing."""


def surface(
    premises: list[str],
    conclusion: str,
    premises_fol: list[str],
    conclusion_fol: str,
    findings: ReasoningFindings,
    *,
    model: str | None = None,
) -> str:
    """Produce NL observations about ambiguities found during formalization."""
    premises_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(premises))
    fol_text = "\n".join(f"  P{i+1}: {f}" for i, f in enumerate(premises_fol))
    fol_text += f"\n  C: {conclusion_fol}"

    if findings.provable_conclusions:
        conclusion_status = "PROVABLE (the conclusion follows from the premises)"
    elif findings.refuted_conclusions:
        conclusion_status = "REFUTED (the negation of the conclusion follows from the premises)"
    else:
        conclusion_status = "UNDETERMINED (neither the conclusion nor its negation could be proved)"

    contradiction_note = ""
    if findings.contradictions:
        contradiction_note = "- WARNING: The premises are CONTRADICTORY (anything can be derived)\n"

    extra = ""
    if findings.undetermined:
        extra = "- Parse/prover issues: " + "; ".join(findings.undetermined) + "\n"

    prompt = _SURFACE_TEMPLATE.format(
        premises_text=premises_text,
        conclusion=conclusion,
        fol_text=fol_text,
        conclusion_status=conclusion_status,
        contradiction_note=contradiction_note,
        extra_findings=extra,
    )
    return generate(prompt, system=_SURFACE_SYSTEM, model=model)


# ── Step 4: REFINE ────────────────────────────────────────────────────────────

_REFINE_SYSTEM = (
    "You are a specification writer. Your job is to revise natural language "
    "premises to make them more precise, removing ambiguities while preserving "
    "the original intent. Output ONLY the revised premises, one per line, "
    "prefixed with the premise number."
)

_REFINE_TEMPLATE = """\
Revise the following premises to address the ambiguities identified below. \
Preserve the original meaning — only add precision where needed. \
Do not add new information that wasn't implied by the original premises. \
Keep the language natural and readable.

Original premises:
{premises_text}

Issues identified:
{observations}

Output the revised premises, one per line, in this exact format:
1. [revised premise 1]
2. [revised premise 2]
...

If a premise needs no changes, output it unchanged."""


_PREMISE_LINE_RE = re.compile(r'^\d+\.\s*(.+)$', re.MULTILINE)


def refine(
    premises: list[str],
    observations: str,
    *,
    model: str | None = None,
) -> list[str]:
    """Revise NL premises based on surfaced observations."""
    premises_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(premises))
    prompt = _REFINE_TEMPLATE.format(
        premises_text=premises_text,
        observations=observations,
    )
    response = generate(prompt, system=_REFINE_SYSTEM, model=model)

    refined = _PREMISE_LINE_RE.findall(response)
    if not refined:
        # Fallback: return originals if parsing fails
        return list(premises)

    # If LLM returned fewer premises than original, pad with originals
    if len(refined) < len(premises):
        refined.extend(premises[len(refined):])

    return refined[:len(premises)]  # Don't add extras


# ── Step 5: MEASURE STABILITY ────────────────────────────────────────────────

def _normalize_fol(fol_str: str) -> str:
    """Normalize a FOL string for structural comparison.

    Parses to AST, renders to TPTP (which normalizes variable case,
    predicate names, etc.), then returns the canonical string.
    Falls back to lowercased stripped string if parsing fails.
    """
    try:
        ast = parse_fol(fol_str)
        return formula_to_tptp(ast)
    except Exception:
        return fol_str.strip().lower()


def _structural_agreement(formalizations: list[list[str]]) -> float:
    """Compute pairwise structural agreement across formalizations.

    For each pair of runs, check what fraction of premises have identical
    normalized FOL. Return the average across all pairs.
    """
    if len(formalizations) < 2:
        return 1.0

    n_premises = min(len(f) for f in formalizations) if formalizations else 0
    if n_premises == 0:
        return 0.0

    # Normalize all formalizations
    normalized = [
        [_normalize_fol(f[i]) for i in range(n_premises)]
        for f in formalizations
    ]

    # Pairwise comparison
    pair_scores = []
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            matches = sum(
                1 for k in range(n_premises)
                if normalized[i][k] == normalized[j][k]
            )
            pair_scores.append(matches / n_premises)

    return sum(pair_scores) / len(pair_scores) if pair_scores else 1.0


def measure_stability(
    premises: list[str],
    conclusion: str,
    *,
    n: int = 5,
    model: str | None = None,
    cpu_limit: int = 30,
) -> StabilityResult:
    """Formalize n times independently and measure agreement.

    Reports two metrics:
    - entailment-preservation: do all formalizations yield the same label?
    - structural agreement: do per-premise FOL ASTs match across runs?
    """
    labels: list[str] = []
    all_formalizations: list[list[str]] = []
    errors: list[str] = []

    for i in range(n):
        # Use temperature > 0 for diversity (except first run)
        temp = 0.0 if i == 0 else 0.8
        try:
            p_fol, c_fol, _ = formalize(
                premises, conclusion, model=model, temperature=temp,
            )
            all_formalizations.append(p_fol + [c_fol])
            premises_ast = [parse_fol(p) for p in p_fol]
            conjecture_ast = parse_fol(c_fol)
            result = prove_example(
                premises_tptp=[],
                conjecture_tptp='',
                premises_ast=premises_ast,
                conjecture_ast=conjecture_ast,
                cpu_limit=cpu_limit,
            )
            labels.append(result.label)
        except Exception as e:
            errors.append(f"Run {i}: {e}")
            labels.append('Error')

    # Entailment agreement: fraction matching the majority label
    if labels:
        from collections import Counter
        counts = Counter(labels)
        majority_count = counts.most_common(1)[0][1]
        agreement_rate = majority_count / len(labels)
    else:
        agreement_rate = 0.0

    structural = _structural_agreement(all_formalizations)

    return StabilityResult(
        n_formalizations=n,
        agreement_rate=agreement_rate,
        structural_agreement=structural,
        labels=labels,
        formalizations=all_formalizations,
        errors=errors,
    )


# ── Loop orchestrator ─────────────────────────────────────────────────────────

def refine_loop(
    premises: list[str],
    conclusion: str,
    *,
    model: str | None = None,
    cpu_limit: int = 30,
    max_iterations: int = 3,
    stability_threshold: float = 0.9,
    stability_n: int = 5,
    verbose: bool = False,
) -> RefineResult:
    """Run the full refinement loop.

    Args:
        premises: Original NL premises.
        conclusion: NL conclusion.
        model: LLM model override.
        cpu_limit: E-prover timeout per problem.
        max_iterations: Max refinement iterations.
        stability_threshold: Stop when agreement >= this.
        stability_n: Number of independent formalizations for stability.
        verbose: Print progress.

    Returns:
        RefineResult with full trace.
    """
    result = RefineResult(
        original_premises=list(premises),
        conclusion=conclusion,
        refined_premises=list(premises),
    )

    current_premises = list(premises)

    # Measure initial stability
    if verbose:
        print("  Measuring initial stability...")
    result.initial_stability = measure_stability(
        current_premises, conclusion,
        n=stability_n, model=model, cpu_limit=cpu_limit,
    )
    if verbose:
        s = result.initial_stability
        print(f"  Initial stability: entailment={s.agreement_rate:.0%} structural={s.structural_agreement:.0%}")

    if result.initial_stability.structural_agreement >= stability_threshold:
        result.final_stability = result.initial_stability
        return result

    for k in range(max_iterations):
        if verbose:
            print(f"  Iteration {k+1}...")

        iteration = RefineIteration(k=k, nl=list(current_premises))

        # Step 1: FORMALIZE
        try:
            p_fol, c_fol, raw = formalize(
                current_premises, conclusion, model=model,
            )
            iteration.fol_strings = p_fol + [c_fol]
        except Exception as e:
            if verbose:
                print(f"    Formalization failed: {e}")
            result.iterations.append(iteration)
            continue

        # Step 2: REASON
        findings = reason(p_fol, c_fol, cpu_limit=cpu_limit)
        iteration.findings = findings

        # Step 3: SURFACE
        observations = surface(
            current_premises, conclusion,
            p_fol, c_fol, findings,
            model=model,
        )
        iteration.observations = observations
        if verbose:
            print(f"    Observations: {observations[:200]}...")

        # Step 4: REFINE
        current_premises = refine(
            current_premises, observations, model=model,
        )
        if verbose:
            for i, p in enumerate(current_premises):
                print(f"    P{i+1}: {p}")

        # Step 5: MEASURE STABILITY
        stability = measure_stability(
            current_premises, conclusion,
            n=stability_n, model=model, cpu_limit=cpu_limit,
        )
        iteration.stability = stability
        result.iterations.append(iteration)

        if verbose:
            print(f"    Stability: entailment={stability.agreement_rate:.0%} structural={stability.structural_agreement:.0%}")

        if stability.structural_agreement >= stability_threshold:
            break

    result.refined_premises = current_premises
    result.total_iterations = len(result.iterations)
    result.final_stability = (
        result.iterations[-1].stability if result.iterations else result.initial_stability
    )

    return result
