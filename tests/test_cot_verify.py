"""Tests for CoT verification (Task B)."""

from unittest.mock import patch

from cotlog.cot_verify import (
    CotStep,
    build_prompt,
    parse_cot_response,
    build_feedback,
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

    def test_includes_premise_format_instructions(self):
        prompt = build_prompt(["P1"], "C1")
        assert "PREMISE N:" in prompt

    def test_includes_conclusion_format_instructions(self):
        prompt = build_prompt(["P1"], "C1")
        assert "CONCLUSION:" in prompt


class TestParseCotResponse:
    def test_simple_response(self):
        response = """\
PREMISE 1: ∀x (Human(x) → Mortal(x))
PREMISE 2: Human(socrates)
CONCLUSION: Mortal(socrates)
STEP 1: From premise 1, all humans are mortal.
FOL: ∀x (Human(x) → Mortal(x))
STEP 2: Socrates is human, so Socrates is mortal.
FOL: Mortal(socrates)
ANSWER: True"""
        premise_fols, conclusion_fol, steps, answer = parse_cot_response(response)
        assert len(premise_fols) == 2
        assert premise_fols[0] == "∀x (Human(x) → Mortal(x))"
        assert premise_fols[1] == "Human(socrates)"
        assert conclusion_fol == "Mortal(socrates)"
        assert len(steps) == 2
        assert steps[0].step_num == 1
        assert steps[0].fol_str == "∀x (Human(x) → Mortal(x))"
        assert steps[1].step_num == 2
        assert steps[1].fol_str == "Mortal(socrates)"
        assert answer == "True"

    def test_no_answer(self):
        response = """\
PREMISE 1: A(x)
CONCLUSION: B(x)
STEP 1: Reasoning here.
FOL: A(x)"""
        premise_fols, conclusion_fol, steps, answer = parse_cot_response(response)
        assert len(premise_fols) == 1
        assert conclusion_fol == "B(x)"
        assert len(steps) == 1
        assert answer is None

    def test_uncertain_answer(self):
        response = """\
PREMISE 1: A(x)
CONCLUSION: B(x)
STEP 1: Not enough info.
FOL: ∃x (A(x))
ANSWER: Uncertain"""
        _, _, _, answer = parse_cot_response(response)
        assert answer == "Uncertain"

    def test_false_answer(self):
        response = """\
PREMISE 1: A(x)
CONCLUSION: ¬A(x)
STEP 1: Contradicts premise.
FOL: ¬A(x)
ANSWER: False"""
        _, conclusion_fol, _, answer = parse_cot_response(response)
        assert answer == "False"
        assert conclusion_fol == "¬A(x)"

    def test_case_insensitive_answer(self):
        response = "PREMISE 1: A(x)\nCONCLUSION: A(x)\nSTEP 1: Reasoning.\nFOL: A(x)\nANSWER: true"
        _, _, _, answer = parse_cot_response(response)
        assert answer == "True"

    def test_multiline_reasoning(self):
        response = """\
PREMISE 1: ∀x (Human(x) → Mortal(x))
CONCLUSION: Mortal(socrates)
STEP 1: First, we note that all humans are mortal.
This follows from premise 1 directly.
FOL: ∀x (Human(x) → Mortal(x))
ANSWER: True"""
        _, _, steps, answer = parse_cot_response(response)
        assert len(steps) == 1
        assert "directly" in steps[0].reasoning

    def test_no_premises(self):
        response = """\
STEP 1: Reasoning.
FOL: A(x)
ANSWER: True"""
        premise_fols, conclusion_fol, steps, _ = parse_cot_response(response)
        assert len(premise_fols) == 0
        assert conclusion_fol is None
        assert len(steps) == 1

    def test_no_conclusion(self):
        response = """\
PREMISE 1: A(x)
STEP 1: Reasoning.
FOL: A(x)
ANSWER: True"""
        premise_fols, conclusion_fol, _, _ = parse_cot_response(response)
        assert len(premise_fols) == 1
        assert conclusion_fol is None


class TestBuildFeedback:
    def test_includes_failed_steps(self):
        failed = [
            CotStep(step_num=1, reasoning="r", fol_str="bad(", verified=False, error="Parse error: unexpected"),
            CotStep(step_num=3, reasoning="r", fol_str="A(x)", verified=False, error="Prover: CounterSatisfiable"),
        ]
        feedback = build_feedback(failed)
        assert "STEP 1" in feedback
        assert "STEP 3" in feedback
        assert "Parse error" in feedback
        assert "CounterSatisfiable" in feedback
        assert "bad(" in feedback


class TestVerifySteps:
    def test_valid_step_from_premises(self):
        """A step that restates a premise should verify."""
        steps = [
            CotStep(step_num=1, reasoning="From premise 1", fol_str="∀x (Human(x) → Mortal(x))"),
        ]
        result = verify_steps(
            steps,
            premise_fols=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
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
            premise_fols=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
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
            premise_fols=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
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
            premise_fols=["Human(socrates)"],
            conclusion_fol="Human(socrates)",
        )
        assert result.steps[0].verified is False
        assert "Parse error" in result.steps[0].error

    def test_conclusion_verification(self):
        """The conclusion should be verified against accumulated knowledge."""
        steps = [
            CotStep(step_num=1, reasoning="Mortal", fol_str="Mortal(socrates)"),
        ]
        result = verify_steps(
            steps,
            premise_fols=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.verified_label == "True"

    def test_no_conclusion_fol(self):
        """When conclusion_fol is None, verified_label should be Uncertain."""
        steps = [
            CotStep(step_num=1, reasoning="ok", fol_str="Human(socrates)"),
        ]
        result = verify_steps(
            steps,
            premise_fols=["Human(socrates)"],
            conclusion_fol=None,
        )
        assert result.verified_label == "Uncertain"

    def test_all_steps_verified_flag(self):
        steps = [
            CotStep(step_num=1, reasoning="ok", fol_str="Human(socrates)"),
            CotStep(step_num=2, reasoning="ok", fol_str="Mortal(socrates)"),
        ]
        result = verify_steps(
            steps,
            premise_fols=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.all_steps_verified is True

    def test_premise_fols_stored(self):
        steps = [
            CotStep(step_num=1, reasoning="ok", fol_str="Human(socrates)"),
        ]
        result = verify_steps(
            steps,
            premise_fols=["∀x (Human(x) → Mortal(x))", "Human(socrates)"],
            conclusion_fol="Mortal(socrates)",
        )
        assert result.premise_fols == ["∀x (Human(x) → Mortal(x))", "Human(socrates)"]


class TestVerifyCot:
    @patch('cotlog.cot_verify.chat')
    def test_end_to_end_with_mock(self, mock_chat):
        mock_chat.return_value = """\
PREMISE 1: ∀x (Human(x) → Mortal(x))
PREMISE 2: Human(socrates)
CONCLUSION: Mortal(socrates)
STEP 1: From premise 1, all humans are mortal.
FOL: ∀x (Human(x) → Mortal(x))
STEP 2: Socrates is human (premise 2), so by modus ponens, Socrates is mortal.
FOL: Mortal(socrates)
ANSWER: True"""

        result = verify_cot(
            premises=["All humans are mortal.", "Socrates is human."],
            conclusion="Socrates is mortal.",
        )
        assert result.llm_answer == "True"
        assert len(result.steps) == 2
        assert result.verified_label == "True"
        assert len(result.premise_fols) == 2
        assert result.conclusion_fol == "Mortal(socrates)"
        assert result.rounds == 1
        # No retries needed since all steps verified
        assert mock_chat.call_count == 1

    @patch('cotlog.cot_verify.chat')
    def test_feedback_loop_fixes_step(self, mock_chat):
        """Test that the feedback loop retries failed steps."""
        # First call: step 2 has bad FOL
        # Second call: step 2 is corrected
        mock_chat.side_effect = [
            """\
PREMISE 1: ∀x (Human(x) → Mortal(x))
PREMISE 2: Human(socrates)
CONCLUSION: Mortal(socrates)
STEP 1: All humans are mortal.
FOL: ∀x (Human(x) → Mortal(x))
STEP 2: Socrates flies.
FOL: Fly(socrates)
ANSWER: True""",
            """\
STEP 2: Socrates is mortal by modus ponens.
FOL: Mortal(socrates)""",
        ]

        result = verify_cot(
            premises=["All humans are mortal.", "Socrates is human."],
            conclusion="Socrates is mortal.",
        )
        assert result.rounds == 2
        assert mock_chat.call_count == 2
        # After correction, step 2 should be verified
        assert result.steps[1].verified is True
        assert result.steps[1].fol_str == "Mortal(socrates)"

    @patch('cotlog.cot_verify.chat')
    def test_max_retries_respected(self, mock_chat):
        """Test that retries stop after max_retries."""
        # All calls return an unverifiable step
        mock_chat.return_value = """\
PREMISE 1: Human(socrates)
CONCLUSION: Mortal(socrates)
STEP 1: Socrates flies.
FOL: Fly(socrates)
ANSWER: True"""

        result = verify_cot(
            premises=["Socrates is human."],
            conclusion="Socrates is mortal.",
            max_retries=2,
        )
        # 1 initial + 2 retries = 3 calls
        assert mock_chat.call_count == 3
        assert result.rounds == 3
