"""Demo: run the refinement loop on a deliberately ambiguous example."""

from cotlog.refine import refine_loop


def main():
    # Ambiguities:
    # - "or" — inclusive or exclusive? (can a restaurant serve both?)
    # - "No restaurant that serves Chinese food" — on Main Street, or anywhere?
    # - "Some restaurants" — on Main Street specifically?
    premises = [
        "Every restaurant on Main Street serves Italian food or Chinese food.",
        "No restaurant that serves Chinese food has a Michelin star.",
        "Some restaurants on Main Street have a Michelin star.",
        "All Michelin-starred restaurants are expensive.",
    ]
    conclusion = "Some expensive restaurants on Main Street serve Italian food."

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
