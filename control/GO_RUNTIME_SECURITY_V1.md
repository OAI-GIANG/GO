# GO Runtime Security V1

1. API token authentication is required unless anonymous mode is explicitly enabled for local tests.
2. Runtime state is stored under the GO runtime data directory.
3. Requests over 256 KiB are rejected.
4. Unsupported operations are rejected and never silently executed.
5. Idempotency is owned by the existing DurableExecution implementation; no second execution store is introduced.
6. Evidence verification must pass before execution is reported as successful.
7. A runtime identity mismatch between commit/tree and evidence is a deployment/test failure.
