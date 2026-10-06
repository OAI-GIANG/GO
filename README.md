# GO Runtime

GO is the canonical runtime owner for this repository.

## Runtime

Entrypoint:

```bash
python -m runtime.go_runtime.core.server
```

Default production bind:

```text
127.0.0.1:8877
```

Endpoints:

- `GET /healthz`
- `GET /v1/status` (Bearer token)
- `POST /v1/tasks` (Bearer token)
- `GET /v1/tasks/<task_id>` (Bearer token)

## Ownership

GO owns runtime identity, execution state, DurableExecution, service and endpoint. Evidence must bind to the exact GO commit/tree/worktree/runtime identity.

LOVE is an explicit source/project dependency only where imported by code. No alternate runtime owner is defined in this repository.
