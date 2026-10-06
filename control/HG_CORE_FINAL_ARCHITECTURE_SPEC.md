# HG CORE FINAL ARCHITECTURE SPEC

Status: IMPLEMENTED / TESTED
Scope: HG only; GO untouched.

## 1. Purpose

HG is a governed self-evolving intelligence core. Self-development means evidence-backed capability improvement, not unrestricted self-modifying code or self-authorization.

## 2. Canonical Evolution Loop

GOAL -> ASSESS -> EXPLORE -> HYPOTHESIZE -> EXPERIMENT_READY -> GOVERNANCE_REVIEW -> AUTHORIZED -> EXECUTING -> OBSERVING -> EVALUATING -> PROMOTION_REVIEW -> PROMOTED -> SELF_MODEL_UPDATE -> COMPLETED.

Alternative terminal/research paths are INCONCLUSIVE and REGRESSION_FAILED; neither may silently promote a capability.

## 3. Ownership

EvolutionPlan is orchestration semantics only.

- Goal: existing goal/task/intent semantics.
- SelfModel: cognition + memory as derived state.
- Hypothesis: cognition/research semantics.
- Experiment: existing WorkItem/Bounded Execution/DurableExecution path.
- Evidence: existing Evidence Authority.
- Replay: existing Replay owner.
- Learning: LearningArtifact V3 owner.
- Governance: existing AEGR/governance boundary.
- Capability: existing Capability Registry.
- Persistence: existing RuntimeStore.

Evolution code MUST NOT create a second authority, evidence authority, memory authority, replay owner, or durable execution owner.

## 4. Mandatory Contracts

GoalContract requires purpose, observable success criteria, scope and constraints.

SelfModelClaim requires evidence references, confidence, applicability and last validation.

HypothesisContract requires testable predictions and explicit state.

ExperimentContract requires baseline, prediction, method, preconditions, stop conditions and evaluation method.

LearningPromotion requires evidence and a regression result before promotion.

RegressionResult requires baseline/candidate identity, metrics, capability retention, reproducibility and safety.

CapabilityChange may only request promotion review; activation remains owned by the capability/governance boundary.

## 5. Promotion Rule

Observed learning is not truth. Mature learning is not authority. A capability is promoted only when evidence exists and the candidate demonstrates measurable improvement over the trusted baseline without unacceptable regression.

## 6. Continual Learning Protection

Trusted knowledge is never overwritten directly. New learning challenges prior knowledge through explicit evidence and regression. Promotion and revocation are separate lifecycle decisions.

## 7. Rollback / Replay / Recovery

Replay reconstructs evidence of what happened. Rollback returns a capability/state to a trusted baseline. Recovery requires correction followed by re-verification and regression. These concepts are not interchangeable.

Every governed evolution plan requires a rollback reference and a bounded iteration budget.

## 8. Creativity / Novelty

Creativity is a core behavior, not an authority. A creative candidate is novel plus potentially useful. A validated discovery additionally requires evidence and demonstrated value. Creativity cannot authorize execution.

## 9. Negative Boundaries

The following are forbidden:

- cognition/advice -> authorization
- evidence -> authorization
- learning -> authority
- self-model -> permission
- creativity -> execution permission
- observation -> truth
- hypothesis -> truth
- replay -> rollback authority
- recovery without re-verification -> success
- self-improvement -> automatic authority expansion
- capability promotion without baseline/regression evidence
- unbounded self-correction

## 10. Acceptance Matrix

A01 Goal continuity: PASS by GoalContract validation.
A02 Evidence-backed self-model: PASS by SelfModelClaim validation.
A03 Metacognition boundary: PASS by explicit self-model and bounded planning semantics.
A04 Exploration/hypothesis path: PASS by EvolutionPlan and hypothesis contracts.
A05 Hypothesis competition: PASS by deterministic evidence-ranked evaluation.
A06 Experiment: PASS by ExperimentContract validation.
A07 Evidence gate: PASS by promotion contract requiring evidence.
A08 Learning: PASS via LearningPromotion.
A09 Promotion: PASS via explicit PromotionDecision.
A10 Regression: PASS via RegressionResult.
A11 Capability preservation: PASS when capability_retained is false -> reject.
A12 Capability authority boundary: PASS; promotion request is distinct from activation.
A13 Creativity boundary: PASS; no creative authority exists.
A14 Recovery boundary: PASS; rollback reference and bounded iteration are mandatory.
A15 Replay boundary: PASS by separation from evolution orchestration.
A16 Governance boundary: PASS; AUTHORIZED requires explicit authority reference.
A17 Fail-closed: PASS; invalid state jumps, missing evidence and missing rollback fail.
A18 Provenance: delegated to existing evidence/memory owners; EvolutionPlan stores references only.

## 11. Test Evidence

Implementation: runtime/paradise/evolution.py
Tests: tests/test_hg_evolution.py

The focused suite covers 12 positive/negative cases, including full lifecycle, governance bypass, invalid transitions, evidence-backed self-model, promotion without regression, regression failure, wrong baseline, missing rollback and bounded iteration.

Full Python compilation and git diff whitespace checks were also run.

## 12. Boundary

This implementation is HG/PARADISE-local only. GO is historical/reference-only and is not modified, migrated, merged or versioned by this work.
