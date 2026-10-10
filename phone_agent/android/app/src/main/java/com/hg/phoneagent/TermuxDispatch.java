package com.hg.phoneagent;

import android.content.Context;
import org.json.JSONObject;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

/** Cầu đồng bộ: gửi capability qua Termux RUN_COMMAND và CHỜ stdout JSON của dispatcher.
 *  Không bao giờ tự tạo lệnh: chỉ truyền capability + params mà server đã allowlist. */
public final class TermuxDispatch {
    static final String DISPATCH = "/data/data/com.termux/files/home/hg-agent/dispatch.sh";
    private static final ConcurrentHashMap<String, LinkedBlockingQueue<String>> WAIT = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String, String> EARLY = new ConcurrentHashMap<>();

    private TermuxDispatch() {}

    static void deliver(String termuxRequestId, String stdout) {
        deliver(termuxRequestId, stdout, 0);
    }

    static void deliver(String termuxRequestId, String stdout, int exitCode) {
        if (termuxRequestId == null || termuxRequestId.isEmpty()) return;
        String value = stdout == null ? "" : stdout;
        if (exitCode != 0) {
            try {
                JSONObject failure = new JSONObject();
                JSONObject detail = new JSONObject();
                detail.put("code", "TERMUX_EXIT_NONZERO");
                detail.put("exit_code", exitCode);
                failure.put("ok", false);
                failure.put("error", detail);
                value = failure.toString();
            } catch (Exception ignored) {
                value = "";
            }
        }

        LinkedBlockingQueue<String> q = WAIT.get(termuxRequestId);
        if (q != null && q.offer(value)) return;
        // RUN_COMMAND can complete before dispatch() installs its waiter. Preserve that result.
        EARLY.put(termuxRequestId, value);
    }

    /** Gọi dispatcher với 1 tham số JSON duy nhất (capability+params). Timeout ⇒ ném lỗi rõ ràng. */
    public static JSONObject dispatch(Context ctx, JSONObject request, long timeoutMs) throws Exception {
        LinkedBlockingQueue<String> q = new LinkedBlockingQueue<>(1);
        String id = TermuxRunner.run(ctx, DISPATCH, new String[]{ request.toString() });
        WAIT.put(id, q);
        String early = EARLY.remove(id);
        if (early != null) q.offer(early);
        try {
            String out = q.poll(timeoutMs, TimeUnit.MILLISECONDS);
            if (out == null) throw new Exception("TERMUX_TIMEOUT");
            JSONObject r = new JSONObject(out.trim());
            if (!r.optBoolean("ok", false)) throw new Exception("TERMUX_ERROR:" + r.optJSONObject("error"));
            return r;
        } finally {
            WAIT.remove(id);
            EARLY.remove(id);
        }
    }
}
