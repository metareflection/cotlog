"""Tests for LLM-based FOL generation (Task A)."""

from unittest.mock import patch

from cotlog.fol_gen import build_prompt, parse_fol_response, generate_fol, FolGenResult


class TestBuildPrompt:
    def test_includes_premises_and_conclusion(self):
        prompt = build_prompt(
            ["All humans are mortal.", "Socrates is human."],
            "Socrates is mortal.",
        )
        assert "1. All humans are mortal." in prompt
        assert "2. Socrates is human." in prompt
        assert "Conclusion: Socrates is mortal." in prompt

    def test_includes_notation_instructions(self):
        prompt = build_prompt(["P1"], "C1")
        assert "∀" in prompt
        assert "∃" in prompt
        assert "CamelCase" in prompt

    def test_includes_few_shot_examples(self):
        prompt = build_prompt(["P1"], "C1")
        assert "Example 1:" in prompt
        assert "P: ∀x" in prompt
        assert "C:" in prompt


class TestParseFolResponse:
    def test_simple_response(self):
        response = """\
P: ∀x (Human(x) → Mortal(x))
P: Human(socrates)
C: Mortal(socrates)"""
        premises, conclusion = parse_fol_response(response)
        assert len(premises) == 2
        assert premises[0] == "∀x (Human(x) → Mortal(x))"
        assert premises[1] == "Human(socrates)"
        assert conclusion == "Mortal(socrates)"

    def test_extra_whitespace(self):
        response = "P:  ∀x (A(x))  \nC:  B(y)  "
        premises, conclusion = parse_fol_response(response)
        assert premises == ["∀x (A(x))"]
        assert conclusion == "B(y)"

    def test_multiple_conclusions_takes_last(self):
        response = "P: A(x)\nC: B(x)\nC: C(x)"
        premises, conclusion = parse_fol_response(response)
        assert conclusion == "C(x)"

    def test_no_premises_raises(self):
        try:
            parse_fol_response("C: A(x)")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "No premises" in str(e)

    def test_no_conclusion_raises(self):
        try:
            parse_fol_response("P: A(x)")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "No conclusion" in str(e)

    def test_complex_fol(self):
        response = """\
P: ∀x (Drinks(x) → Dependent(x))
P: ∀x (Drinks(x) ⊕ Jokes(x))
P: ∀x (Jokes(x) → ¬Unaware(x))
P: (Student(rina) ∧ Unaware(rina)) ⊕ ¬(Student(rina) ∨ Unaware(rina))
C: Jokes(rina) ∨ Unaware(rina)"""
        premises, conclusion = parse_fol_response(response)
        assert len(premises) == 4
        assert "⊕" in premises[1]
        assert conclusion == "Jokes(rina) ∨ Unaware(rina)"


class TestGenerateFol:
    @patch('cotlog.fol_gen.generate')
    def test_end_to_end_with_mock(self, mock_generate):
        mock_generate.return_value = """\
P: ∀x (Human(x) → Mortal(x))
P: Human(socrates)
C: Mortal(socrates)"""

        result = generate_fol(
            ["All humans are mortal.", "Socrates is a human."],
            "Socrates is mortal.",
        )
        assert isinstance(result, FolGenResult)
        assert len(result.premises_fol) == 2
        assert result.conclusion_fol == "Mortal(socrates)"
        assert result.raw_response == mock_generate.return_value

        # Verify prompt was constructed correctly
        call_args = mock_generate.call_args
        assert "All humans are mortal." in call_args[0][0]
        assert "Socrates is mortal." in call_args[0][0]

    @patch('cotlog.fol_gen.generate')
    def test_model_passthrough(self, mock_generate):
        mock_generate.return_value = "P: A(x)\nC: B(x)"
        result = generate_fol(["p"], "c", model="haiku")
        assert isinstance(result, FolGenResult)
        assert mock_generate.call_args[1].get('model') == 'haiku'
