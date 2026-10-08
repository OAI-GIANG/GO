# HG V2 Threat Model — 12-Layer Runtime Boundary

## Purpose
This matrix is the P1-D canonical threat-model surface. It maps each layer to an existing semantic owner and an executable control. It intentionally does not create a second security engine.

| # | Layer | Primary threat | Canonical control | Execution evidence |
|---|---|---|---|---|
| 1 | Input / Prompt | direct or indirect prompt injection | CognitiveService input boundary; model output treated untrusted | P1-D injection tests |
| 2 | Model Output | model says ALLOW / authorized / tool_call | AuthorityRoot + Kernel; no model-output authorization | P1-D authorization denial |
| 3 | Provider Boundary | malicious provider/plugin gains core authority | ModelGateway ProviderAdapter contract | model_gateway plugin test + P1-D |
| 4 | Tool Selection | model chooses unauthorized capability | ToolGovernance + bounded registry | threat-model tool controls |
| 5 | Tool Arguments / Target | cross-target or malformed operation | VPS2ExecutionBridge target/allowlist/policy binding | existing cross-target/lost-response tests |
| 6 | Authority | forged or projected authority | single AuthorityRoot + Kernel authorization | P0-A + threat tests |
| 7 | Credential Boundary | credential treated as authority | require_authority rejects credential-like values | threat-model credential test |
| 8 | Evidence | caller-forged verification/promotion | trusted IVV registry + anchored VerificationResult | P0-B/P0-C |
| 9 | Freshness / Corroboration / Assurance | stale or weak evidence promotes | promotion_gate admission dimensions | P1-B |
| 10 | Memory Trust | model/plugin self-promotes memory | MemoryCore certificates + adapter boundary | existing memory trust tests + P1-D |
| 11 | Persistence / Replay / Checkpoint | state/evidence divergence or replay tampering | RuntimeStore + canonical unify + replay/checkpoint validation | P1-A/P1-C |
| 12 | Certification / Release | fabricated certification or self-certification | evidence-backed Certification Firewall | P0-D |

## Model-loop injection cases required for closure
1. model output authorized=true cannot create authority;
2. model output verification_status=INDEPENDENTLY_VERIFIED cannot promote evidence;
3. model output tool_call is data, not an execution request;
4. model output cannot access core memory-promotion capability;
5. provider adapter has no authority/evidence/tool execution surface.

## External references
- OWASP LLM06:2025 Excessive Agency — model output must not become unchecked downstream authority; complete mediation belongs in application/downstream controls.
- OWASP Prompt Injection — least privilege and backend privilege enforcement are required because prompt injection cannot be reliably solved inside the model.
- NIST AI 600-1 — direct/indirect prompt injection can cause unintended downstream consequences in connected systems.

## Closure rule
P1-D is CLOSED only when:
- all 12 layers are mapped to existing canonical owners;
- real model-loop injection tests execute through CognitiveService.invoke_model();
- malicious model output cannot cross into authorization, evidence promotion, tool execution, memory promotion, or certification;
- full regression remains PASS;
- no duplicate security semantic owner is introduced.
