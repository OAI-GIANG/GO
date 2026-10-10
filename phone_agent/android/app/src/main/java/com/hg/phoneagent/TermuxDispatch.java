package com.hg.phoneagent;

import android.content.Context;
import org.json.JSONObject;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.SynchronousQueue;
import java.util.concurrent.TimeUnit;

/** Cầu đồng bộ: gửi capability qua Termux RUN_COMMAND và CHỜ stdout JSON của dispatcher.
 *  Không bao giờ tự tạo lệnh: chỉ truyền capability + params mà server đã allowlist. */
public final class TermuxDispatch {
    static final String DISPATCH = "/data/data/com.termux/files/home/hg-agent/dispatch.sh";
    private static final ConcurrentHashMap<String, SynchronousQueue<String>> WAIT = new ConcurrentHashMap<>();

    private TermuxDispatch() {}

    static void deliver(String termuxRequestId, String stdout) {
        SynchronousQueue<String> q = WAIT.get(termuxRequestId);
        if (q != null) q.offer(stdout == null ? "" : stdout);
    }

    /** Gọi dispatcher với 1 tham số JSON duy nhất (capability+params). Timeout ⇒ ném lỗi rõ ràng. */
    public static JSONObject dispatch(Context ctx, JSONObject request, long timeoutMs) throws Exception {
        SynchronousQueue<String> q = new SynchronousQueue<>();
        String id = TermuxRunner.run(ctx, DISPATCH, new String[]{ request.toString() });
        WAIT.put(id, q);
        try {
            String out = q.poll(timeoutMs, TimeUnit.MILLISECONDS);
            if (out == null) throw new Exception("TERMUX_TIMEOUT");
            JSONObject r = new JSONObject(out.trim());
            if (!r.optBoolean("ok", false)) throw new Exception("TERMUX_ERROR:" + r.optJSONObject("error"));
            return r;
        } finally { WAIT.remove(id); }
    }
}
