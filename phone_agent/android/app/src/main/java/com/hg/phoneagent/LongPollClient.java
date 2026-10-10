package com.hg.phoneagent;

import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;

/** Phone Agent v2 — client LONGPOLL_HTTPS_V2 (thay cho WSS của V1). Outbound-only, không mở listener.
 *  Bất biến: HTTPS bắt buộc · Bearer device-token · mỗi request 1 request_id · chỉ capability cho phép ·
 *  KHÔNG gửi lại kết quả nếu không xác định được đã thực thi (dispatcher tự chống replay bằng .hg_replay.jsonl). */
public final class LongPollClient {
    public interface Executor { JSONObject execute(String capability, JSONObject params) throws Exception; }
    private final String base; private final String token; private final Executor exec;
    private final AtomicBoolean running = new AtomicBoolean(false);

    public LongPollClient(String base, String token, Executor exec) {
        if (base == null || !base.startsWith("https://")) throw new IllegalArgumentException("HTTPS required");
        this.base = base.endsWith("/") ? base.substring(0, base.length() - 1) : base;
        this.token = token; this.exec = exec;
    }

    public static JSONObject register(String base, String pairingToken, String deviceId, String name) throws Exception {
        JSONObject b = new JSONObject().put("pairing_token", pairingToken)
                                       .put("device_id", deviceId).put("name", name);
        return post(base + "/api/phone/register", null, b);
    }

    public void stop() { running.set(false); }

    /** Vòng long-poll có backoff 1s→30s, xử lý idle/timeout/lỗi mạng. Chạy trên thread riêng. */
    public void runLoop() {
        running.set(true); long backoff = 1000L;
        while (running.get()) {
            try {
                JSONObject cmd = post(base + "/api/phone/poll", token, new JSONObject().put("wait_s", 25));
                backoff = 1000L;
                if (cmd.optBoolean("idle", false)) continue;
                String rid = cmd.getString("request_id");
                String cap = cmd.getString("capability");
                JSONObject params = cmd.optJSONObject("params"); if (params == null) params = new JSONObject();
                JSONObject payload = new JSONObject().put("request_id", rid);
                try {
                    JSONObject res = exec.execute(cap, params);          // chỉ capability allowlist
                    payload.put("ok", true).put("result", res);
                } catch (Exception ex) {
                    payload.put("ok", false).put("result", new JSONObject().put("error", String.valueOf(ex.getMessage())));
                }
                post(base + "/api/phone/result", token, payload);
            } catch (Exception netErr) {
                try { Thread.sleep(backoff); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); return; }
                backoff = Math.min(backoff * 2, 30000L);
            }
        }
    }

    private static JSONObject post(String url, String token, JSONObject body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setRequestMethod("POST"); c.setConnectTimeout(10000); c.setReadTimeout(40000);
            c.setDoOutput(true); c.setRequestProperty("Content-Type", "application/json");
            if (token != null) c.setRequestProperty("Authorization", "Bearer " + token);
            try (OutputStream os = c.getOutputStream()) { os.write(body.toString().getBytes(StandardCharsets.UTF_8)); }
            int code = c.getResponseCode();
            InputStream is = (code >= 200 && code < 300) ? c.getInputStream() : c.getErrorStream();
            StringBuilder sb = new StringBuilder();
            if (is != null) try (BufferedReader br = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                String l; while ((l = br.readLine()) != null) sb.append(l);
            }
            if (code < 200 || code >= 300) throw new IOException("HTTP " + code + ": " + sb);
            return new JSONObject(sb.toString());
        } finally { c.disconnect(); }
    }
}
