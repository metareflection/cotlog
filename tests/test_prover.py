"""Integration tests for E-prover runner."""

import shutil

import pytest

from cotlog.fol_parser import Const, ForAll, Implies, Predicate, Var, parse_fol
from cotlog.prover import prove_example, run_eprover
from cotlog.tptp import problem_to_tptp

pytestmark = pytest.mark.skipif(
    shutil.which("eprover") is None,
    reason="eprover not installed",
)


def test_socrates_theorem():
    """Classic: All humans are mortal. Socrates is human. ∴ Socrates is mortal."""
    premises = [
        ForAll("x", Implies(Predicate("Human", [Var("x")]), Predicate("Mortal", [Var("x")]))),
        Predicate("Human", [Const("socrates")]),
    ]
    conjecture = Predicate("Mortal", [Const("socrates")])
    tptp = problem_to_tptp(premises, conjecture)
    result = run_eprover(tptp, cpu_limit=10)
    assert result.szs_status == "Theorem"
    assert result.label == "True"


def test_counter_satisfiable():
    """A conjecture that does not follow from the premises."""
    premises = [Predicate("Human", [Const("socrates")])]
    conjecture = Predicate("Mortal", [Const("socrates")])
    tptp = problem_to_tptp(premises, conjecture)
    result = run_eprover(tptp, cpu_limit=10)
    assert result.szs_status == "CounterSatisfiable"
    assert result.label == "False"


def test_prove_example_true():
    """prove_example should return True for a valid entailment."""
    premises_ast = [
        ForAll("x", Implies(Predicate("Human", [Var("x")]), Predicate("Mortal", [Var("x")]))),
        Predicate("Human", [Const("socrates")]),
    ]
    conjecture_ast = Predicate("Mortal", [Const("socrates")])
    result = prove_example([], '', premises_ast, conjecture_ast, cpu_limit=10)
    assert result.label == "True"


def test_prove_example_false():
    """prove_example should return False when negation is provable."""
    premises_ast = [
        ForAll("x", Implies(Predicate("Human", [Var("x")]), Predicate("Mortal", [Var("x")]))),
        Predicate("Human", [Const("socrates")]),
    ]
    # Claim socrates is NOT mortal → this is false
    from cotlog.fol_parser import Not
    conjecture_ast = Not(Predicate("Mortal", [Const("socrates")]))
    result = prove_example([], '', premises_ast, conjecture_ast, cpu_limit=10)
    assert result.label == "False"


def test_prove_folio_first_example():
    """Test parsing and proving the first FOLIO validation example."""
    premises_fol = [
        "∀x (TalentShows(x) → Engaged(x))",
        "∀x (TalentShows(x) ∨ Inactive(x))",
        "∀x (Chaperone(x) → ¬Students(x))",
        "∀x (Inactive(x) → Chaperone(x))",
        "∀x (AcademicCareer(x) → Students(x))",
        "(Engaged(bonnie) ∧ Students(bonnie)) ⊕ (¬Engaged(bonnie) ∧ ¬Students(bonnie))",
    ]
    conclusion_fol = "Engaged(bonnie)"
    # Gold label: Uncertain

    premises_ast = [parse_fol(p) for p in premises_fol]
    conjecture_ast = parse_fol(conclusion_fol)
    result = prove_example([], '', premises_ast, conjecture_ast, cpu_limit=10)
    # Should be Uncertain since neither conclusion nor its negation follows
    assert result.label == "Uncertain"
