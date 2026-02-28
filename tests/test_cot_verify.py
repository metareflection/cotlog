"""Tests for CoT verification (Task B)."""

from unittest.mock import patch

from cotlog.cot_verify import (
    CotStep,
    build_prompt,
    parse_cot_response,
    verify_steps,
    verify_cot,
)


class TestBuildPrompt:
    def test_includes_premises_and_conclusion(self):
        prompt = build_prompt(
            ["All humans are mortal.", "Socrates is human."],
            "Socrates is mortal.",
        )
        assert "1. All humans are mortal." in prompt
        assert "2. Socrates is human." in prompt
        assert "Conclusion: Socrates is mortal." in prompt

    def test_includes_step_format_instructions(self):
        prompt = build_prompt(["P1"], "C1")
        assert "STEP N:" in prompt
        assert "FOL:" in prompt
        assert "ANSWER:" in prompt


class TestParseCotResponse:
    def test_simple_response(self):
        response = """\
STEP 1: From premise 1, all humans are mortal.
FOL: ∀x (Human(x) → Mortal(x))
STEP 2: Socrates is human, so Socrates is mortal.
FOL: Mortal(socrates)
ANSWER: True"""
        steps, answer = parse_cot_response(response)
        assert len(steps) == 2
        assert steps[0].step_num == 1
        assert steps[0].fol_str == "∀x (Human(x) → Mortal(x))"
        assert steps[1].step_num == 2
        assert steps[1].fol_str == "Mortal(socrates)"
        assert answer == "True"

    def test_no_answer(self):
        response = """\
STEP 1: Reasoning here.
FOL: A(x)"""
        steps, answer = parse_cot_response(response)
        assert len(steps) == 1
        assert answer is None

    def test_uncertain_answer(self):
        response = """\
STEP 1: Not enough info.
FOL: ∃x (A(x))
ANSWER: Uncertain"""
        steps, answer = parse_cot_response(response)
        assert answer == "Uncertain"

    def test_false_answer(self):
        response = """\
STEP 1: Contradicts premise.
FOL: ¬A(x)
ANSWER: False"""
        _, answer = parse_cot_response(response)
        assert answer == "False"

    def test_case_insensitive_answer(self):
        response = "STEP 1: Reasoning.\nFOL: A(x)\nANSWER: true"
        _, answer = parse_cot_response(response)
        assert answer == "True"

    def test_multiline_reasoning(self):
        response = """\
STEP 1: First, we note that all humans are mortal.
This follows from premise 1 directly.
FOL: ∀x (Human(x) → Mortal(x))
ANSWER: True"""
        steps, answer = parse_cot_response(response)
        assert len(steps) == 1
        assert "directly" in steps[0].reasoning


class TestVerifySteps:
    def test_valid_step_from_premises(self):
        """A step that restates a premise should verify."""
        steps = [
            CotStep(step_num=1, reasoning="From premise 1", fol_str="∀x (Human(x) → Mortal(x))"),
        ]
        result = verify_steps(
            steps,
            premises_fol=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.steps[0].verified is True

    def test_valid_derived_step(self):
        """A step that follows from premises should verify."""
        steps = [
            CotStep(step_num=1, reasoning="Socrates is mortal", fol_str="Mortal(socrates)"),
        ]
        result = verify_steps(
            steps,
            premises_fol=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.steps[0].verified is True

    def test_invalid_step(self):
        """A step with no logical support should not verify."""
        steps = [
            CotStep(step_num=1, reasoning="Just guessing", fol_str="Fly(socrates)"),
        ]
        result = verify_steps(
            steps,
            premises_fol=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.steps[0].verified is False

    def test_unparseable_fol_step(self):
        """A step with invalid FOL syntax should fail gracefully."""
        steps = [
            CotStep(step_num=1, reasoning="Bad syntax", fol_str="∀∀∀ broken"),
        ]
        result = verify_steps(
            steps,
            premises_fol=["Human(socrates)"],
            conclusion_fol="Human(socrates)",
        )
        assert result.steps[0].verified is False
        assert "Parse error" in result.steps[0].error

    def test_conclusion_verification(self):
        """The final conclusion should be verified against accumulated knowledge."""
        steps = [
            CotStep(step_num=1, reasoning="Mortal", fol_str="Mortal(socrates)"),
        ]
        result = verify_steps(
            steps,
            premises_fol=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.verified_label == "True"

    def test_all_steps_verified_flag(self):
        steps = [
            CotStep(step_num=1, reasoning="ok", fol_str="Human(socrates)"),
            CotStep(step_num=2, reasoning="ok", fol_str="Mortal(socrates)"),
        ]
        result = verify_steps(
            steps,
            premises_fol=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.all_steps_verified is True


class TestVerifyCot:
    @patch('cotlog.cot_verify.generate')
    def test_end_to_end_with_mock(self, mock_generate):
        mock_generate.return_value = """\
STEP 1: From premise 1, all humans are mortal.
FOL: ∀x (Human(x) → Mortal(x))
STEP 2: Socrates is human (premise 2), so by modus ponens, Socrates is mortal.
FOL: Mortal(socrates)
ANSWER: True"""

        result = verify_cot(
            premises=["All humans are mortal.", "Socrates is human."],
            conclusion="Socrates is mortal.",
            premises_fol=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.llm_answer == "True"
        assert len(result.steps) == 2
        assert result.verified_label == "True"
