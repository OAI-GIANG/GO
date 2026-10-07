package com.hg.phoneagent;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

public final class TermuxResultReceiver extends BroadcastReceiver {
    public static final String ACTION_RESULT = "com.hg.phoneagent.TERMUX_RESULT";

    @Override public void onReceive(Context context, Intent intent) {
        // V1 keeps the callback boundary explicit. The Agent owns transport/result
        // correlation; this receiver only captures Termux completion metadata.
        // No arbitrary command output is trusted as governance/evidence.
        String requestId = intent.getStringExtra("request_id");
        Bundle result = intent.getBundleExtra("com.termux.RUN_COMMAND_RESULT_BUNDLE");
        if (result == null) result = intent.getBundleExtra("com.termux.service.EXTRA_PLUGIN_RESULT_BUNDLE");
        if (result == null) return;
        int exitCode = result.getInt("com.termux.service.EXTRA_PLUGIN_RESULT_BUNDLE_EXIT_CODE", -1);
        String stdout = result.getString("com.termux.service.EXTRA_PLUGIN_RESULT_BUNDLE_STDOUT", "");
        String stderr = result.getString("com.termux.service.EXTRA_PLUGIN_RESULT_BUNDLE_STDERR", "");
        TermuxResultCache.put(requestId, exitCode, stdout, stderr);
    }
}
