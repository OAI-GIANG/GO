# PROTOCOL v2 — LONG-POLL HTTPS (thay WSS)

**Thay đổi có ghi nhận:** V1 dùng outbound WSS `/v1/phone/ws`; server GO (stdlib) **không có WebSocket server** ⇒ v2 dùng **long-poll HTTPS**, thiết bị vẫn outbound-only.

| Bước | Endpoint | Body | Trả về |
|---|---|---|---|
| Đăng ký | `POST /api/phone/register` | `{pairing_token, device_id, name}` | `{device_token, protocol:"LONGPOLL_HTTPS_V2"}` |
| Nhận lệnh | `POST /api/phone/poll` (Bearer) | `{wait_s}` | `{request_id, capability, params}` hoặc `{idle:true}` |
| Trả kết quả | `POST /api/phone/result` (Bearer) | `{request_id, ok, result}` | `{state}` |
| (server) | `enqueue(device_id, capability, params)` | allowlist capability + chặn path thoát sandbox | `{request_id}` |

Bất biến: pairing token allowlist · device token HMAC có hạn · capability allowlist · tương quan request_id · **chặn replay kết quả** · audit hash-chain.
**Client Android phải sửa tương ứng** (MainActivity: bỏ WS, thay bằng vòng long-poll) — chưa thực hiện, ghi rõ là việc còn lại.
