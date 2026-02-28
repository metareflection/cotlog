"""Unit tests for the FOL parser."""

from cotlog.fol_parser import (
    And, Const, Exists, ForAll, Iff, Implies, Not, Or, Predicate, Var, Xor,
    parse_fol, tokenize,
)


def test_simple_predicate():
    ast = parse_fol("Human(socrates)")
    assert ast == Predicate("Human", [Const("socrates")])


def test_predicate_with_variable():
    ast = parse_fol("Likes(x, y)")
    assert ast == Predicate("Likes", [Var("x"), Var("y")])


def test_forall():
    ast = parse_fol("∀x (Human(x) → Mortal(x))")
    assert ast == ForAll("x", Implies(
        Predicate("Human", [Var("x")]),
        Predicate("Mortal", [Var("x")]),
    ))


def test_exists():
    ast = parse_fol("∃x (Cat(x) ∧ Fluffy(x))")
    assert ast == Exists("x", And(
        Predicate("Cat", [Var("x")]),
        Predicate("Fluffy", [Var("x")]),
    ))


def test_negation():
    ast = parse_fol("¬Human(x)")
    assert ast == Not(Predicate("Human", [Var("x")]))


def test_xor():
    ast = parse_fol("A(x) ⊕ B(x)")
    assert ast == Xor(Predicate("A", [Var("x")]), Predicate("B", [Var("x")]))


def test_iff():
    ast = parse_fol("A(x) ↔ B(x)")
    assert ast == Iff(Predicate("A", [Var("x")]), Predicate("B", [Var("x")]))


def test_nested_quantifiers():
    ast = parse_fol("∀x ∀y (Likes(x, y) → Likes(y, x))")
    assert ast == ForAll("x", ForAll("y", Implies(
        Predicate("Likes", [Var("x"), Var("y")]),
        Predicate("Likes", [Var("y"), Var("x")]),
    )))


def test_complex_folio_formula():
    """Test a formula representative of FOLIO data."""
    s = "∀x (TalentShows(x) → Engaged(x))"
    ast = parse_fol(s)
    assert ast == ForAll("x", Implies(
        Predicate("TalentShows", [Var("x")]),
        Predicate("Engaged", [Var("x")]),
    ))


def test_constant_predicate():
    ast = parse_fol("Engaged(bonnie)")
    assert ast == Predicate("Engaged", [Const("bonnie")])


def test_xor_with_complex_operands():
    s = "(Engaged(bonnie) ∧ Students(bonnie)) ⊕ (¬Engaged(bonnie) ∧ ¬Students(bonnie))"
    ast = parse_fol(s)
    assert isinstance(ast, Xor)
    assert isinstance(ast.left, And)
    assert isinstance(ast.right, And)


def test_zero_arity_predicate():
    ast = parse_fol("Rain")
    assert ast == Predicate("Rain", [])


def test_disjunction():
    ast = parse_fol("∀x (TalentShows(x) ∨ Inactive(x))")
    assert ast == ForAll("x", Or(
        Predicate("TalentShows", [Var("x")]),
        Predicate("Inactive", [Var("x")]),
    ))


def test_right_single_quote_in_name():
    """FOLIO uses right single quote in some predicate names."""
    s = "∀x (GrowthCompanies\u2019Stocks(x) → PriceVolatile(x))"
    ast = parse_fol(s)
    assert isinstance(ast, ForAll)
    assert isinstance(ast.body, Implies)
    pred = ast.body.left
    assert isinstance(pred, Predicate)
    assert pred.name == "GrowthCompanies\u2019Stocks"


def test_multiple_premises_parse():
    """Ensure all premises from first FOLIO example parse."""
    premises = [
        "∀x (TalentShows(x) → Engaged(x))",
        "∀x (TalentShows(x) ∨ Inactive(x))",
        "∀x (Chaperone(x) → ¬Students(x))",
        "∀x (Inactive(x) → Chaperone(x))",
        "∀x (AcademicCareer(x) → Students(x))",
        "(Engaged(bonnie) ∧ Students(bonnie)) ⊕ (¬Engaged(bonnie) ∧ ¬Students(bonnie))",
    ]
    for p in premises:
        ast = parse_fol(p)
        assert ast is not None


def test_dot_in_identifier():
    """FOLIO uses dots in some constants like y42.3billion."""
    ast = parse_fol("ValuedAt(yalesendowment, y42.3billion)")
    assert isinstance(ast, Predicate)
    assert ast.args[1] == Const("y42.3billion")


def test_comma_as_conjunction():
    """FOLIO sometimes uses comma as conjunction between formulas."""
    s = "∀x ∀y (SuperheroMovie(x), NamedAfter(x, y) → GoodGuy(y))"
    ast = parse_fol(s)
    assert isinstance(ast, ForAll)
    inner = ast.body
    assert isinstance(inner, ForAll)
    impl = inner.body
    assert isinstance(impl, Implies)
    assert isinstance(impl.left, And)


def test_trailing_unmatched_paren():
    """FOLIO data sometimes has trailing unmatched close parens."""
    s = "Chaperone(bonnie) ⊕ TalentShows(bonnie) → AcademicCareer(bonnie) ∧ Inactive(bonnie))"
    ast = parse_fol(s)
    # Top-level is Xor (⊕ has lower precedence than →); key point: no parse error
    assert isinstance(ast, Xor)


def test_unbalanced_inner_paren():
    """Missing open paren but trailing close — e.g. FOLIO example 108."""
    s = "(Spill(peter) ∧ OnlyChild(peter)) ∨ ¬Spill(peter) ∧ ¬OnlyChild(peter))"
    ast = parse_fol(s)
    assert isinstance(ast, Or)
