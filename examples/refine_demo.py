"""Demo: run the refinement loop on a deliberately ambiguous example."""

from cotlog.refine import refine_loop


def main():
    # Quantifier scope ambiguity + implicit assumptions:
    # - "every student passed a test" — same test or different tests?
    # - "the teacher praised everyone who passed" — passed what?
    # - "not all students were praised" — contradicts if "passed" = "passed a test"
    premises = [
        "Every student in the class passed a test.",
        "The teacher praised everyone who passed.",
        "Not all students in the class were praised by the teacher.",
    ]
    conclusion = "Some students passed a test but were not praised."

    result = refine_loop(
        premises, conclusion,
        max_iterations=3,
        stability_n=5,
        verbose=True,
    )

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    s0 = result.initial_stability
    sf = result.final_stability
    print(f"Initial: entailment={s0.agreement_rate:.0%}  structural={s0.structural_agreement:.0%}  labels={s0.labels}")
    print(f"Final:   entailment={sf.agreement_rate:.0%}  structural={sf.structural_agreement:.0%}  labels={sf.labels}")
    print(f"Iterations: {result.total_iterations}")

    print()
    print("Original premises:")
    for i, p in enumerate(result.original_premises):
        print(f"  {i+1}. {p}")

    print()
    print("Refined premises:")
    for i, p in enumerate(result.refined_premises):
        print(f"  {i+1}. {p}")

    for it in result.iterations:
        print()
        print(f"--- Iteration {it.k + 1} ---")
        print("Observations:")
        print(it.observations)


if __name__ == "__main__":
    main()
