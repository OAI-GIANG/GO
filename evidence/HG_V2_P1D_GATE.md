# HG V2 P1-D Gate Evidence

## Scope
Close the 12-layer threat model and prove runtime model-loop injection resistance.

## Research
- OWASP LLM06:2025 Excessive Agency requires complete mediation and independent downstream authorization rather than trusting LLM decisions.
- OWASP Prompt Injection requires privilege controls at backend/application boundaries because prompt injection cannot be reliably prevented inside the model.
- NIST AI 600-1 documents direct and indirect prompt injection as risks with downstream consequences in connected systems.

## 12-layer model
1. Input / Prompt
2. Model Output
3. Provider Boundary
4. Tool Selection
5. Tool Arguments / Target
6. Authority
7. Credential Boundary
8. Evidence
9. Freshness / Corroboration / Assurance
10. Memory Trust
11. Persistence / Replay / Checkpoint
12. Certification / Release

Full mapping: evidence/HG_V2_THREAT_MODEL_12L.md

## Runtime model-loop injection
All tests execute through CognitiveService.invoke_model() using a malicious ProviderAdapter.

Verified DENY / isolation:
- model output authorized=true cannot become Authority;
- model output verification_status=INDEPENDENTLY_VERIFIED cannot become VerificationResult;
- model output tool_call remains data and no tool execution occurs;
- provider adapter has no core authority/evidence/memory/tool methods;
- model output cannot obtain memory-promotion capability.

## Tests
- P1-D targeted threat/model gateway suite: 35 passed
- Full regression: 175 passed in 9.35s
- diff check: PASS with CRLF-aware whitespace

## Artifact hashes
Threat model:
642B1818E8FD915BAE1A31B4BB7882C635DA34B9B85783A99A094B9E6CD21753

P1-D reproduction stdout:
AF55EFF3C2C4467D4451473AF75A17D47F07F4BB833D61180F72414F3DF3CDC5

P1-D test:
8AA0EFE8001DC0693D73F73C0C584F6FCD63F0808FE09B94E95A2154700D220F

## Gate decision
P1-D = ENFORCED / CLOSED.

This closes the current HG V2 remediation sequence P0-A through P1-D. Global release/certification still requires the final independent cross-check and any remaining production-specific evidence gates.
