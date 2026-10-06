import unittest

from runtime.paradise.evolution import (
    CapabilityChange, CapabilityState, EvolutionController, EvolutionPlan,
    EvolutionState, ExperimentContract, GoalContract, HypothesisContract,
    HypothesisState, LearningPromotion, LearningState, PromotionDecision,
    RegressionResult, SelfModelClaim, evaluate_hypothesis_competition,
    validate_continual_learning, validate_negative_boundaries,
)


def make_plan() -> EvolutionPlan:
    goal = GoalContract(
        goal_id="G-1", purpose_ref="PURPOSE-1",
        objective="Improve bounded reasoning reliability",
        success_criteria=("candidate_success_rate_gt_baseline",),
        scope="reasoning-only", constraints=("no authority expansion",),
    )
    h1 = HypothesisContract(
        hypothesis_id="H-1", claim="strategy A improves reliability",
        rationale="observed failure pattern", predictions=("failure_rate_decreases",),
        alternatives=("H-2",), state=HypothesisState.TESTABLE, experiment_refs=("EXP-1",),
    )
    h2 = HypothesisContract(
        hypothesis_id="H-2", claim="strategy B improves reliability",
        rationale="alternative explanation", predictions=("failure_rate_decreases",),
        state=HypothesisState.TESTABLE, experiment_refs=("EXP-1",),
    )
    experiment = ExperimentContract(
        experiment_id="EXP-1", hypothesis_refs=("H-1", "H-2"), baseline="CAP-BASELINE",
        prediction="candidate beats baseline", method="bounded benchmark", scope="offline",
        preconditions=("baseline frozen",), stop_condition=("budget exhausted", "safety violation"),
        evaluation_method="paired comparison",
    )
    return EvolutionPlan(
        evolution_id="EV-1", goal=goal, hypotheses=(h1, h2), experiment=experiment,
        evaluation_criteria=("correctness", "robustness"),
        regression_criteria=("no capability regression",),
        promotion_criteria=("evidence-backed improvement",), rollback_ref="RB-1",
    )


class HGCoreEvolutionTests(unittest.TestCase):
    def test_goal_and_plan_require_observable_criteria(self):
        plan = make_plan(); plan.validate()
        self.assertEqual(plan.state, EvolutionState.PROPOSED)

    def test_full_evolution_lifecycle_requires_governance(self):
        controller = EvolutionController(make_plan())
        for state in (EvolutionState.ASSESSING, EvolutionState.EXPLORING,
                      EvolutionState.HYPOTHESIZING, EvolutionState.EXPERIMENT_READY,
                      EvolutionState.GOVERNANCE_REVIEW):
            controller.transition(state, "design")
        controller.authorize(authority_ref="AUTH-1")
        controller.transition(EvolutionState.EXECUTING, "authorized execution")
        controller.transition(EvolutionState.OBSERVING, "execution completed")
        controller.transition(EvolutionState.EVALUATING, "evidence collected")
        controller.transition(EvolutionState.IMPROVEMENT_SUPPORTED, "baseline comparison passed")
        controller.transition(EvolutionState.PROMOTION_REVIEW, "promotion evidence ready")
        controller.transition(EvolutionState.PROMOTED, "promotion accepted")
        controller.transition(EvolutionState.SELF_MODEL_UPDATE, "capability promoted")
        controller.transition(EvolutionState.COMPLETED, "self-model updated")
        self.assertEqual(controller.state, EvolutionState.COMPLETED)

    def test_execution_cannot_bypass_authorization(self):
        controller = EvolutionController(make_plan())
        for state in (EvolutionState.ASSESSING, EvolutionState.EXPLORING,
                      EvolutionState.HYPOTHESIZING, EvolutionState.EXPERIMENT_READY,
                      EvolutionState.GOVERNANCE_REVIEW):
            controller.transition(state, "design")
        with self.assertRaises(PermissionError):
            controller.transition(EvolutionState.AUTHORIZED, "no-governance-ref")

    def test_invalid_state_jump_is_rejected(self):
        with self.assertRaises(ValueError):
            EvolutionController(make_plan()).transition(EvolutionState.PROMOTED, "shortcut")

    def test_hypothesis_competition_is_deterministic_and_evidence_ranked(self):
        self.assertEqual(evaluate_hypothesis_competition(make_plan().hypotheses), ("H-1", "H-2"))

    def test_self_model_requires_evidence(self):
        with self.assertRaises(ValueError):
            SelfModelClaim("CAP-1", "I can do X", (), 0.9, "offline", "2026-10-06T00:00:00Z").validate()

    def test_learning_without_regression_does_not_promote(self):
        candidate = LearningPromotion("LA-1", LearningState.SUPPORTED, ("E-1",), None, "reasoning-only")
        self.assertEqual(candidate.decision(), PromotionDecision.HOLD)
        self.assertEqual(validate_continual_learning(candidate, "CAP-BASELINE"), PromotionDecision.HOLD)

    def test_regression_blocks_capability_promotion(self):
        regression = RegressionResult("CAP-BASELINE", "CAP-CANDIDATE",
            {"correctness": (0.9, 0.95), "robustness": (0.9, 0.8)}, True, True, True)
        change = CapabilityChange("CAP-CANDIDATE", "CAP-BASELINE", ("E-1",), regression, CapabilityState.PROMOTION_REVIEW)
        self.assertEqual(change.promotion_decision(), PromotionDecision.REJECT)

    def test_positive_improvement_promotes(self):
        regression = RegressionResult("CAP-BASELINE", "CAP-CANDIDATE",
            {"correctness": (0.9, 0.95), "robustness": (0.9, 0.92)}, True, True, True)
        candidate = LearningPromotion("LA-1", LearningState.SUPPORTED, ("E-1",), regression, "reasoning-only")
        self.assertEqual(validate_continual_learning(candidate, "CAP-BASELINE"), PromotionDecision.PROMOTE)

    def test_continual_learning_rejects_wrong_baseline(self):
        regression = RegressionResult("WRONG", "CAP-CANDIDATE", {"correctness": (0.9, 0.95)}, True, True, True)
        candidate = LearningPromotion("LA-2", LearningState.SUPPORTED, ("E-2",), regression)
        self.assertEqual(validate_continual_learning(candidate, "CAP-BASELINE"), PromotionDecision.REJECT)

    def test_negative_boundaries_include_missing_rollback(self):
        plan = make_plan()
        broken = EvolutionPlan(**{**plan.__dict__, "rollback_ref": ""})
        self.assertIn("rollback_ref_missing", validate_negative_boundaries(broken))

    def test_iteration_budget_is_bounded(self):
        controller = EvolutionController(make_plan())
        for _ in range(3): controller.mark_iteration()
        with self.assertRaises(RuntimeError): controller.mark_iteration()


if __name__ == "__main__":
    unittest.main(verbosity=2)
