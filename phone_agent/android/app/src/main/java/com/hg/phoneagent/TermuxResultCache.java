package com.hg.phoneagent;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public final class TermuxResultCache {
    public static final class Result {
        public final int exitCode;
        public final String stdout;
        public final String stderr;
        Result(int exitCode, String stdout, String stderr) {
            this.exitCode = exitCode;
            this.stdout = stdout;
            this.stderr = stderr;
        }
    }
    private static final Map<String, Result> RESULTS = new ConcurrentHashMap<>();
    private TermuxResultCache() {}
    public static void put(String id, int exitCode, String stdout, String stderr) {
        if (id != null) RESULTS.put(id, new Result(exitCode, stdout, stderr));
    }
    public static Result take(String id) {
        return id == null ? null : RESULTS.remove(id);
    }
}
