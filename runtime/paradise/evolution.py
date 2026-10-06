"""Canonical HG Evolution Loop semantics.

This module is orchestration semantics only. It does not own memory, evidence,
replay, durable execution, governance authority, or capability registry state.
It produces bounded proposals and state transitions that must be admitted by
existing owners before any external mutation occurs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class EvolutionState(str, Enum):
    PROPOSED = "PROPOSED"
    ASSESSING = "ASSESSING"
    EXPLORING = "EXPLORING"
    HYPOTHESIZING = "HYPOTHESIZING"
    EXPERIMENT_READY = "EXPERIMENT_READY"
    GOVERNANCE_REVIEW = "GOVERNANCE_REVIEW"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    EVALUATING = "EVALUATING"
    INCONCLUSIVE = "INCONCLUSIVE"
    REGRESSION_FAILED = "REGRESSION_FAILED"
    IMPROVEMENT_SUPPORTED = "IMPROVEMENT_SUPPORTED"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    REJECTED = "REJECTED"
    PROMOTED = "PROMOTED"
    SELF_MODEL_UPDATE = "SELF_MODEL_UPDATE"
    COMPLETED = "COMPLETED"


class HypothesisState(str, Enum):
    CANDIDATE = "CANDIDATE"
    TESTABLE = "TESTABLE"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    WEAKENED = "WEAKENED"
    REJECTED = "REJECTED"


class LearningState(str, Enum):
    OBSERVED = "OBSERVED"
    CANDIDATE = "CANDIDATE"
    TESTED = "TESTED"
    SUPPORTED = "SUPPORTED"
    MATURE = "MATURE"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    DEPRECATED = "DEPRECATED"


class CapabilityState(str, Enum):
    PROPOSED = "PROPOSED"
    EVALUATED = "EVALUATED"
    SUPPORTED = "SUPPORTED"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    ACTIVE = "ACTIVE"
    CHALLENGED = "CHALLENGED"
    REVOKED = "REVOKED"
    DEPRECATED = "DEPRECATED"


class PromotionDecision(str, Enum):
    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    HOLD = "HOLD"


@dataclass(frozen=True)
class GoalContract:
    goal_id: str
    purpose_ref: str
    objective: str
    success_criteria: tuple[str, ...]
    scope: str
    constraints: tuple[str, ...] = ()
    priority: int = 0
    horizon: str = "bounded"
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.goal_id.strip() or not self.objective.strip():
            raise ValueError("goal_id and objective are required")
        if not self.purpose_ref.strip():
            raise ValueError("purpose_ref is required")
        if not self.success_criteria:
            raise ValueError("observable success criteria are required")
        if not self.scope.strip():
            raise ValueError("scope is required")
        if self.priority < 0:
            raise ValueError("priority cannot be negative")


@dataclass(frozen=True)
class SelfModelClaim:
    capability_id: str
    claim: str
    evidence_refs: tuple[str, ...]
    confidence: float
    applicability: str
    last_validated: str
    regression_status: str = "UNKNOWN"

    def validate(self) -> None:
        if not self.capability_id.strip() or not self.claim.strip():
            raise ValueError("self-model capability and claim are required")
        if not self.evidence_refs:
            raise ValueError("self-model claims require evidence references")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("self-model confidence must be between 0 and 1")
        if not self.applicability.strip() or not self.last_validated.strip():
            raise ValueError("self-model applicability and validation time are required")


@dataclass(frozen=True)
class HypothesisContract:
    hypothesis_id: str
    claim: str
    rationale: str
    predictions: tuple[str, ...]
    alternatives: tuple[str, ...] = ()
    uncertainty: float = 1.0
    evidence_for: tuple[str, ...] = ()
    evidence_against: tuple[str, ...] = ()
    experiment_refs: tuple[str, ...] = ()
    state: HypothesisState = HypothesisState.CANDIDATE

    def validate(self) -> None:
        if not self.hypothesis_id.strip() or not self.claim.strip():
            raise ValueError("hypothesis identity and claim are required")
        if not self.predictions:
            raise ValueError("hypothesis requires testable predictions")
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValueError("hypothesis uncertainty must be between 0 and 1")
        if self.state in {HypothesisState.TESTABLE, HypothesisState.TESTING} and not self.experiment_refs:
            raise ValueError("testable hypothesis requires experiment references")


@dataclass(frozen=True)
class ExperimentContract:
    experiment_id: str
    hypothesis_refs: tuple[str, ...]
    baseline: str
    prediction: str
    method: str
    scope: str
    preconditions: tuple[str, ...]
    stop_condition: tuple[str, ...]
    evaluation_method: str
    execution_ref: str | None = None
    observation_refs: tuple[str, ...] = ()
    evidence_ref: str | None = None

    def validate(self) -> None:
        required = {
            "experiment_id": self.experiment_id,
            "baseline": self.baseline,
            "prediction": self.prediction,
            "method": self.method,
            "scope": self.scope,
            "evaluation_method": self.evaluation_method,
        }
        if any(not str(value).strip() for value in required.values()):
            raise ValueError("experiment requires identity, baseline, prediction, method, scope and evaluation")
        if not self.hypothesis_refs or not self.preconditions or not self.stop_condition:
            raise ValueError("experiment requires hypothesis, preconditions and stop conditions")


@dataclass(frozen=True)
class RegressionResult:
    baseline_id: str
    candidate_id: str
    metrics: Mapping[str, tuple[float, float]]
    capability_retained: bool
    reproducible: bool
    safety_ok: bool

    @property
    def improved(self) -> bool:
        if not self.capability_retained or not self.reproducible or not self.safety_ok:
            return False
        if not self.metrics:
            return False
        return all(candidate >= baseline for baseline, candidate in self.metrics.values()) and any(
            candidate > baseline for baseline, candidate in self.metrics.values()
        )


@dataclass(frozen=True)
class LearningPromotion:
    artifact_id: str
    state: LearningState
    evidence_refs: tuple[str, ...]
    regression: RegressionResult | None = None
    applicability: str = ""

    def decision(self) -> PromotionDecision:
        if not self.evidence_refs:
            return PromotionDecision.REJECT
        if self.state not in {LearningState.SUPPORTED, LearningState.MATURE}:
            return PromotionDecision.HOLD
        if self.regression is None:
            return PromotionDecision.HOLD
        return PromotionDecision.PROMOTE if self.regression.improved else PromotionDecision.REJECT


@dataclass(frozen=True)
class CapabilityChange:
    capability_id: str
    baseline_capability_id: str | None
    evidence_refs: tuple[str, ...]
    regression: RegressionResult | None
    requested_state: CapabilityState

    def promotion_decision(self) -> PromotionDecision:
        if self.requested_state is not CapabilityState.PROMOTION_REVIEW:
            return PromotionDecision.HOLD
        if not self.evidence_refs or self.regression is None:
            return PromotionDecision.REJECT
        return PromotionDecision.PROMOTE if self.regression.improved else PromotionDecision.REJECT


@dataclass(frozen=True)
class EvolutionPlan:
    evolution_id: str
    goal: GoalContract
    hypotheses: tuple[HypothesisContract, ...]
    experiment: ExperimentContract
    evaluation_criteria: tuple[str, ...]
    regression_criteria: tuple[str, ...]
    promotion_criteria: tuple[str, ...]
    rollback_ref: str
    state: EvolutionState = EvolutionState.PROPOSED
    max_iterations: int = 3
    current_iteration: int = 0

    def validate(self) -> None:
        if not self.evolution_id.strip():
            raise ValueError("evolution_id is required")
        self.goal.validate()
        if not self.hypotheses:
            raise ValueError("EvolutionPlan requires at least one hypothesis")
        for hypothesis in self.hypotheses:
            hypothesis.validate()
        self.experiment.validate()
        if not self.evaluation_criteria or not self.regression_criteria or not self.promotion_criteria:
            raise ValueError("evaluation, regression and promotion criteria are mandatory")
        if not self.rollback_ref.strip():
            raise ValueError("rollback reference is mandatory")
        if self.max_iterations <= 0 or self.current_iteration < 0 or self.current_iteration > self.max_iterations:
            raise ValueError("invalid bounded evolution iteration")


_ALLOWED_TRANSITIONS: dict[EvolutionState, frozenset[EvolutionState]] = {
    EvolutionState.PROPOSED: frozenset({EvolutionState.ASSESSING, EvolutionState.REJECTED}),
    EvolutionState.ASSESSING: frozenset({EvolutionState.EXPLORING, EvolutionState.REJECTED}),
    EvolutionState.EXPLORING: frozenset({EvolutionState.HYPOTHESIZING, EvolutionState.REJECTED}),
    EvolutionState.HYPOTHESIZING: frozenset({EvolutionState.EXPERIMENT_READY, EvolutionState.REJECTED}),
    EvolutionState.EXPERIMENT_READY: frozenset({EvolutionState.GOVERNANCE_REVIEW, EvolutionState.REJECTED}),
    EvolutionState.GOVERNANCE_REVIEW: frozenset({EvolutionState.AUTHORIZED, EvolutionState.REJECTED}),
    EvolutionState.AUTHORIZED: frozenset({EvolutionState.EXECUTING, EvolutionState.REJECTED}),
    EvolutionState.EXECUTING: frozenset({EvolutionState.OBSERVING, EvolutionState.REJECTED}),
    EvolutionState.OBSERVING: frozenset({EvolutionState.EVALUATING, EvolutionState.REJECTED}),
    EvolutionState.EVALUATING: frozenset({EvolutionState.IMPROVEMENT_SUPPORTED, EvolutionState.INCONCLUSIVE, EvolutionState.REGRESSION_FAILED}),
    EvolutionState.INCONCLUSIVE: frozenset({EvolutionState.HYPOTHESIZING, EvolutionState.REJECTED}),
    EvolutionState.REGRESSION_FAILED: frozenset({EvolutionState.REJECTED, EvolutionState.HYPOTHESIZING}),
    EvolutionState.IMPROVEMENT_SUPPORTED: frozenset({EvolutionState.PROMOTION_REVIEW}),
    EvolutionState.PROMOTION_REVIEW: frozenset({EvolutionState.PROMOTED, EvolutionState.REJECTED}),
    EvolutionState.PROMOTED: frozenset({EvolutionState.SELF_MODEL_UPDATE}),
    EvolutionState.SELF_MODEL_UPDATE: frozenset({EvolutionState.COMPLETED}),
    EvolutionState.REJECTED: frozenset(),
    EvolutionState.COMPLETED: frozenset(),
}


@dataclass(frozen=True)
class EvolutionTransition:
    evolution_id: str
    from_state: EvolutionState
    to_state: EvolutionState
    reason: str


@dataclass
class EvolutionController:
    """Bounded state machine; all external owners remain authoritative."""
    plan: EvolutionPlan
    transitions: list[EvolutionTransition] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.plan.validate()

    @property
    def state(self) -> EvolutionState:
        return self.plan.state

    def transition(self, target: EvolutionState, reason: str) -> EvolutionTransition:
        if target not in _ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"invalid evolution transition {self.state.value}->{target.value}")
        if not reason.strip():
            raise ValueError("transition reason is required")
        if target is EvolutionState.AUTHORIZED:
            if self.state is not EvolutionState.GOVERNANCE_REVIEW or not reason.startswith("governance:"):
                raise PermissionError("authorization requires explicit governance boundary")
        elif target is EvolutionState.EXECUTING and not self._has_governance_boundary():
            raise PermissionError("execution transition requires governance boundary")
        if target is EvolutionState.PROMOTION_REVIEW and not self.plan.promotion_criteria:
            raise ValueError("promotion criteria missing")
        if target is EvolutionState.SELF_MODEL_UPDATE and self.state is not EvolutionState.PROMOTED:
            raise ValueError("self-model update requires promoted capability")
        event = EvolutionTransition(self.plan.evolution_id, self.state, target, reason)
        self.plan = EvolutionPlan(**{**self.plan.__dict__, "state": target})
        self.transitions.append(event)
        return event

    def authorize(self, *, authority_ref: str) -> EvolutionTransition:
        if not authority_ref.strip():
            raise PermissionError("explicit governance authority reference required")
        if self.state is not EvolutionState.GOVERNANCE_REVIEW:
            raise ValueError("authorization is only valid at GOVERNANCE_REVIEW")
        return self.transition(EvolutionState.AUTHORIZED, f"governance:{authority_ref}")

    def mark_iteration(self) -> None:
        if self.plan.current_iteration >= self.plan.max_iterations:
            raise RuntimeError("evolution_iteration_budget_exhausted")
        self.plan = EvolutionPlan(**{**self.plan.__dict__, "current_iteration": self.plan.current_iteration + 1})

    def _has_governance_boundary(self) -> bool:
        return any(event.to_state is EvolutionState.AUTHORIZED for event in self.transitions)


def evaluate_hypothesis_competition(hypotheses: Iterable[HypothesisContract]) -> tuple[str, ...]:
    rows = tuple(hypotheses)
    if not rows:
        raise ValueError("at least one hypothesis is required")
    for hypothesis in rows:
        hypothesis.validate()
    # Ranking is deliberately evidence-based: more supporting refs, fewer
    # contradictory refs, then lower uncertainty. No ranking creates authority.
    ranked = sorted(
        rows,
        key=lambda h: (-len(h.evidence_for), len(h.evidence_against), h.uncertainty, h.hypothesis_id),
    )
    return tuple(h.hypothesis_id for h in ranked)


def validate_continual_learning(candidate: LearningPromotion, trusted_capability_id: str) -> PromotionDecision:
    if not trusted_capability_id.strip():
        raise ValueError("trusted capability baseline is required")
    if candidate.regression is None:
        return PromotionDecision.HOLD
    if candidate.regression.baseline_id != trusted_capability_id:
        return PromotionDecision.REJECT
    return candidate.decision()


def validate_negative_boundaries(plan: EvolutionPlan) -> tuple[str, ...]:
    """Return explicit semantic violations; empty tuple means no violation."""
    violations: list[str] = []
    if plan.state is EvolutionState.AUTHORIZED:
        violations.append("plan state cannot be initialized directly as AUTHORIZED")
    if not plan.rollback_ref.strip():
        violations.append("rollback_ref_missing")
    for hypothesis in plan.hypotheses:
        if hypothesis.state in {HypothesisState.SUPPORTED, HypothesisState.TESTING} and not hypothesis.experiment_refs:
            violations.append(f"hypothesis_without_experiment:{hypothesis.hypothesis_id}")
    return tuple(violations)
