# GO Runtime Deployment V1

## Target
- Runtime root: `/opt/go`
- Entrypoint: `python -m runtime.go_runtime.core.server`
- Bind: `127.0.0.1:8877`
- Health: `GET /healthz`
- Authenticated status: `GET /v1/status`
- Execution: `POST /v1/tasks`
- Task lookup: `GET /v1/tasks/<task_id>`

## Environment
- `GO_HOST`
- `GO_PORT`
- `GO_API_TOKEN`
- `GO_ALLOW_ANONYMOUS`
- `GO_DATA`
- `GO_COMMIT`
- `GO_TREE_SHA`
- `GO_ENV`

Anonymous mode is disabled in production.

## Service
Systemd unit: `go-runtime.service`.
The unit owns the GO process. No legacy runtime service may execute the same workload.

## Evidence
Deployment evidence must record commit, tree, worktree, runtime identity, process, endpoint, health result, authenticated status result, execution result and evidence identifiers.
