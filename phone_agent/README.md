# HG Phone Agent V1

Device-side Phone Agent only.

Boundary: PHONE -> outbound WSS -> /v1/phone/ws -> HG/edge command channel. The agent never opens an inbound listener.

Android -> Termux uses the Termux RUN_COMMAND Intent. Arbitrary shell execution is denied; V1 permits only the fixed dispatch path:
/data/data/com.termux/files/home/hg-agent/dispatch.sh

Reconnect uses exponential backoff: 1s, 2s, 4s ... capped at 30s.

Security: WSS required; device token is stored in Android private SharedPreferences; RUN_COMMAND requires com.termux.permission.RUN_COMMAND and Termux allow-external-apps=true; command paths are allowlisted; phone output is not an evidence authority.

Integration boundary: canonical hg-core currently exposes /v1/phone/requests, but does not expose the /api/phone/register and /v1/phone/ws server endpoints required by this device agent. Real HG E2E is therefore blocked until those server endpoints are separately authorized and implemented.

No change is made to hg-core by this branch.
