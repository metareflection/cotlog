"""Render FOL AST to TPTP FOF syntax."""

from __future__ import annotations

import re

from .fol_parser import (
    And, Const, Exists, ForAll, Formula, Iff, Implies, Not, Or, Predicate,
    Var, Xor,
)


def _sanitize_name(name: str) -> str:
    """Make a name TPTP-safe: replace non-ASCII, ensure valid identifier."""
    # Replace right single quote with underscore
    name = name.replace('\u2019', '_')
    # Replace any remaining non-alphanumeric/underscore
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return name


def _render_term(term: Var | Const) -> str:
    match term:
        case Var(name):
            return name.upper()  # TPTP: variables are uppercase
        case Const(name):
            s = _sanitize_name(name)
            # TPTP: constants must start lowercase
            return s[0].lower() + s[1:] if s else s


def _render(f: Formula) -> str:
    match f:
        case Predicate(name, args):
            sname = _sanitize_name(name)
            # TPTP: predicates/functions start lowercase
            sname = sname[0].lower() + sname[1:]
            if not args:
                return sname
            rendered_args = ', '.join(_render_term(a) for a in args)
            return f'{sname}({rendered_args})'
        case Not(body):
            return f'(~{_render(body)})'
        case And(left, right):
            return f'({_render(left)} & {_render(right)})'
        case Or(left, right):
            return f'({_render(left)} | {_render(right)})'
        case Implies(left, right):
            return f'({_render(left)} => {_render(right)})'
        case Iff(left, right):
            return f'({_render(left)} <=> {_render(right)})'
        case Xor(left, right):
            return f'({_render(left)} <~> {_render(right)})'
        case ForAll(var, body):
            return f'(![{var.upper()}]: {_render(body)})'
        case Exists(var, body):
            return f'(?[{var.upper()}]: {_render(body)})'
    raise TypeError(f"Unknown formula type: {type(f)}")


def formula_to_tptp(f: Formula) -> str:
    """Render a single formula to TPTP FOF syntax."""
    return _render(f)


def problem_to_tptp(
    premises: list[Formula],
    conjecture: Formula,
    negate_conjecture: bool = False,
) -> str:
    """Generate a complete TPTP problem file.

    Args:
        premises: List of axiom formulas.
        conjecture: The conclusion formula.
        negate_conjecture: If True, negate the conjecture (for testing False labels).
    """
    lines = []
    for i, p in enumerate(premises):
        lines.append(f"fof(premise_{i}, axiom, {_render(p)}).")
    conj = conjecture
    if negate_conjecture:
        conj = Not(conjecture)
    lines.append(f"fof(conclusion, conjecture, {_render(conj)}).")
    return '\n'.join(lines)
