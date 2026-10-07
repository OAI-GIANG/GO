package com.hg.phoneagent;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class TermuxResultReceiver extends BroadcastReceiver {
    public static final String ACTION_RESULT = "com.hg.phoneagent.TERMUX_RESULT";

    @Override public void onReceive(Context context, Intent intent) {
        // V1 keeps the callback boundary explicit. The Agent owns transport/result
        // correlation; this receiver only captures Termux completion metadata.
        // No arbitrary command output is trusted as governance/evidence.
        String requestId = intent.getStringExtra("request_id");
        int exitCode = intent.getIntExtra("com.termux.RUN_COMMAND_EXIT_STATUS", -1);
        String stdout = intent.getStringExtra("com.termux.RUN_COMMAND_STDOUT");
        String stderr = intent.getStringExtra("com.termux.RUN_COMMAND_STDERR");
        TermuxResultCache.put(requestId, exitCode, stdout, stderr);
    }
}
