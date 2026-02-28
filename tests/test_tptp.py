"""Unit tests for TPTP generation."""

from cotlog.fol_parser import (
    And, Const, Exists, ForAll, Iff, Implies, Not, Or, Predicate, Var, Xor,
    parse_fol,
)
from cotlog.tptp import formula_to_tptp, problem_to_tptp


def test_simple_predicate():
    f = Predicate("Human", [Const("socrates")])
    assert formula_to_tptp(f) == "human(socrates)"


def test_forall_implies():
    f = ForAll("x", Implies(
        Predicate("Human", [Var("x")]),
        Predicate("Mortal", [Var("x")]),
    ))
    assert formula_to_tptp(f) == "(![X]: (human(X) => mortal(X)))"


def test_exists():
    f = Exists("x", And(
        Predicate("Cat", [Var("x")]),
        Predicate("Fluffy", [Var("x")]),
    ))
    assert formula_to_tptp(f) == "(?[X]: (cat(X) & fluffy(X)))"


def test_not():
    f = Not(Predicate("Happy", [Var("x")]))
    assert formula_to_tptp(f) == "(~happy(X))"


def test_or():
    f = Or(Predicate("A", []), Predicate("B", []))
    assert formula_to_tptp(f) == "(a | b)"


def test_iff():
    f = Iff(Predicate("A", []), Predicate("B", []))
    assert formula_to_tptp(f) == "(a <=> b)"


def test_xor():
    f = Xor(Predicate("A", []), Predicate("B", []))
    assert formula_to_tptp(f) == "(a <~> b)"


def test_problem_generation():
    premises = [
        ForAll("x", Implies(Predicate("Human", [Var("x")]), Predicate("Mortal", [Var("x")]))),
        Predicate("Human", [Const("socrates")]),
    ]
    conjecture = Predicate("Mortal", [Const("socrates")])
    tptp = problem_to_tptp(premises, conjecture)
    assert "fof(premise_0, axiom," in tptp
    assert "fof(premise_1, axiom," in tptp
    assert "fof(conclusion, conjecture," in tptp
    assert "human(socrates)" in tptp
    assert "mortal(socrates)" in tptp


def test_problem_negate_conjecture():
    conjecture = Predicate("Happy", [Const("bob")])
    tptp = problem_to_tptp([], conjecture, negate_conjecture=True)
    assert "(~happy(bob))" in tptp


def test_roundtrip_folio_formula():
    s = "∀x (TalentShows(x) → Engaged(x))"
    ast = parse_fol(s)
    tptp = formula_to_tptp(ast)
    assert tptp == "(![X]: (talentShows(X) => engaged(X)))"


def test_sanitize_right_quote():
    """Right single quote in names should become underscore."""
    s = "GrowthCompanies\u2019Stocks(x)"
    ast = parse_fol(s)
    tptp = formula_to_tptp(ast)
    assert "growthCompanies_Stocks" in tptp


def test_constant_lowercased():
    f = Predicate("P", [Const("Bonnie")])
    tptp = formula_to_tptp(f)
    assert tptp == "p(bonnie)"
