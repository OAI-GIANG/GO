# HG Runtime API Contract V1

## Purpose
Connect the existing HG UI to the HG Core runtime without introducing a second semantic authority.

## Transport
- HTTP/JSON on the local runtime origin.
- Browser client uses `/api/*` relative URLs.
- Runtime binds to `127.0.0.1` by default.
- No credentials are stored in the repository.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Runtime health + core status |
| GET | `/api/bootstrap` | Initial memory/context/plugin/message state |
| POST | `/api/chat` | Append a chat message |
| POST | `/api/memory` | Create memory |
| DELETE | `/api/memory/{id}` | Delete memory |
| POST | `/api/context` | Create context |
| PATCH | `/api/context/{id}` | Toggle project membership |
| DELETE | `/api/context/{id}` | Delete context |
| POST | `/api/plugin/{id}/install` | Install plugin |
| POST | `/api/plugin/{id}/connect` | Connect/disconnect plugin |
| DELETE | `/api/plugin/{id}` | Uninstall plugin |
| POST | `/api/library` | Store library metadata + optional file |
| DELETE | `/api/library/{id}` | Delete library item |
| DELETE | `/api/library` | Delete all library items |
| GET | `/api/github/status` | GitHub adapter capability/auth status |
| GET | `/api/github/repos` | List authenticated-user repos when token exists; public fallback requires `owner` query |
| GET | `/api/github/repo/{owner}/{repo}` | Read repository metadata |

## Authority boundary
- HG Core remains the enforcement primitive.
- Runtime owns transport, persistence, and adapter orchestration.
- UI owns presentation and local cache.
- GitHub remains the external system of record for GitHub data.
- `GITHUB_TOKEN` is read only from the process environment; it is never written to project files.

## Error contract
```json
{"ok":false,"error":{"code":"...","message":"..."}}
```
Successful responses use `{"ok":true,...}`.

## GitHub security
Use a fine-grained token with the minimum repository permissions required. GitHub documents Bearer-token authentication and recommends fine-grained tokens where possible. The adapter never logs the token. Public repository reads can operate without a token; authenticated repository listing requires authentication.
