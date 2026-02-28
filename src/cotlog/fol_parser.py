"""Parse FOLIO's Unicode FOL notation into an AST."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


# ── AST nodes ──────────────────────────────────────────────────────────────────

@dataclass
class Predicate:
    name: str
    args: list[Term]

@dataclass
class Var:
    name: str

@dataclass
class Const:
    name: str

Term = Var | Const

@dataclass
class ForAll:
    var: str
    body: Formula

@dataclass
class Exists:
    var: str
    body: Formula

@dataclass
class Not:
    body: Formula

@dataclass
class And:
    left: Formula
    right: Formula

@dataclass
class Or:
    left: Formula
    right: Formula

@dataclass
class Implies:
    left: Formula
    right: Formula

@dataclass
class Iff:
    left: Formula
    right: Formula

@dataclass
class Xor:
    left: Formula
    right: Formula

Formula = ForAll | Exists | Not | And | Or | Implies | Iff | Xor | Predicate


# ── Tokenizer ─────────────────────────────────────────────────────────────────

class TokType(Enum):
    FORALL = auto()
    EXISTS = auto()
    IMPLIES = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    XOR = auto()
    IFF = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    IDENT = auto()
    EOF = auto()

@dataclass
class Token:
    type: TokType
    value: str


_SYMBOL_MAP = {
    '∀': TokType.FORALL,
    '∃': TokType.EXISTS,
    '→': TokType.IMPLIES,
    '∧': TokType.AND,
    '∨': TokType.OR,
    '¬': TokType.NOT,
    '⊕': TokType.XOR,
    '↔': TokType.IFF,
    '⟷': TokType.IFF,  # long arrow variant
    '(': TokType.LPAREN,
    ')': TokType.RPAREN,
    ',': TokType.COMMA,
}


def tokenize(s: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch in _SYMBOL_MAP:
            tokens.append(Token(_SYMBOL_MAP[ch], ch))
            i += 1
            continue
        # Identifier: letters, digits, underscores, right single quote
        if ch.isalpha() or ch == '_':
            start = i
            while i < len(s) and (s[i].isalnum() or s[i] == '_' or s[i] == '\u2019'):
                i += 1
            tokens.append(Token(TokType.IDENT, s[start:i]))
            continue
        raise ValueError(f"Unexpected character {ch!r} (U+{ord(ch):04X}) at position {i} in: {s}")
    tokens.append(Token(TokType.EOF, ''))
    return tokens


# ── Parser ─────────────────────────────────────────────────────────────────────

class Parser:
    """Recursive descent parser for FOLIO FOL.

    Grammar (precedence low→high):
      formula     = iff_expr
      iff_expr    = implies_expr ((↔ | ⊕) implies_expr)*
      implies_expr = or_expr (→ or_expr)*       (right-assoc)
      or_expr     = and_expr (∨ and_expr)*
      and_expr    = unary (∧ unary)*
      unary       = ¬ unary | ∀var formula | ∃var formula | atom
      atom        = IDENT ( ( term_list ) )?  | ( formula )
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def consume(self, expected: TokType | None = None) -> Token:
        tok = self.tokens[self.pos]
        if expected is not None and tok.type != expected:
            raise ValueError(f"Expected {expected}, got {tok}")
        self.pos += 1
        return tok

    def parse(self) -> Formula:
        result = self.formula()
        if self.peek().type != TokType.EOF:
            raise ValueError(f"Unexpected token after formula: {self.peek()}")
        return result

    def formula(self) -> Formula:
        return self.iff_expr()

    def iff_expr(self) -> Formula:
        left = self.implies_expr()
        while self.peek().type in (TokType.IFF, TokType.XOR):
            op = self.consume()
            right = self.implies_expr()
            if op.type == TokType.IFF:
                left = Iff(left, right)
            else:
                left = Xor(left, right)
        return left

    def implies_expr(self) -> Formula:
        left = self.or_expr()
        if self.peek().type == TokType.IMPLIES:
            self.consume()
            right = self.implies_expr()  # right-associative
            return Implies(left, right)
        return left

    def or_expr(self) -> Formula:
        left = self.and_expr()
        while self.peek().type == TokType.OR:
            self.consume()
            right = self.and_expr()
            left = Or(left, right)
        return left

    def and_expr(self) -> Formula:
        left = self.unary()
        while self.peek().type == TokType.AND:
            self.consume()
            right = self.unary()
            left = And(left, right)
        return left

    def unary(self) -> Formula:
        tok = self.peek()
        if tok.type == TokType.NOT:
            self.consume()
            return Not(self.unary())
        if tok.type == TokType.FORALL:
            self.consume()
            var = self.consume(TokType.IDENT).value
            body = self.formula()
            return ForAll(var, body)
        if tok.type == TokType.EXISTS:
            self.consume()
            var = self.consume(TokType.IDENT).value
            body = self.formula()
            return Exists(var, body)
        return self.atom()

    def atom(self) -> Formula:
        tok = self.peek()
        if tok.type == TokType.LPAREN:
            self.consume()
            result = self.formula()
            self.consume(TokType.RPAREN)
            return result
        if tok.type == TokType.IDENT:
            name = self.consume().value
            if self.peek().type == TokType.LPAREN:
                self.consume()
                args = self.term_list()
                self.consume(TokType.RPAREN)
                return Predicate(name, args)
            # Bare identifier — 0-ary predicate
            return Predicate(name, [])
        raise ValueError(f"Unexpected token in atom: {tok}")

    def term_list(self) -> list[Term]:
        terms: list[Term] = []
        if self.peek().type == TokType.RPAREN:
            return terms
        terms.append(self.term())
        while self.peek().type == TokType.COMMA:
            self.consume()
            terms.append(self.term())
        return terms

    def term(self) -> Term:
        tok = self.consume(TokType.IDENT)
        return _classify_term(tok.value)


def _classify_term(name: str) -> Term:
    """Classify a term as Var or Const.

    FOLIO convention: quantifier-bound single lowercase letters are variables.
    We use a heuristic: single lowercase letter → Var, everything else → Const.
    """
    if len(name) == 1 and name.islower():
        return Var(name)
    return Const(name)


def parse_fol(s: str) -> Formula:
    """Parse a FOLIO FOL string into an AST."""
    tokens = tokenize(s)
    return Parser(tokens).parse()
