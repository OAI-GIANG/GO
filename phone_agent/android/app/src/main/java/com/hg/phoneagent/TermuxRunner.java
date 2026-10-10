package com.hg.phoneagent;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import java.util.UUID;

public final class TermuxRunner {
    public static final String ACTION_RUN_COMMAND = "com.termux.RUN_COMMAND";
    public static final String PERMISSION_RUN_COMMAND = "com.termux.permission.RUN_COMMAND";
    public static final String SERVICE = "com.termux.app.RunCommandService";
    public static final String EXTRA_COMMAND_PATH = "com.termux.RUN_COMMAND_PATH";
    public static final String EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS";
    public static final String EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND";
    public static final String EXTRA_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT";
    public static final String EXTRA_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR";

    private TermuxRunner() {}

    public static String run(Context context, String commandPath, String[] arguments) {
        if (commandPath == null || commandPath.isEmpty()) throw new IllegalArgumentException("commandPath");
        String requestId = UUID.randomUUID().toString();
        Intent callback = new Intent(context, TermuxResultReceiver.class);
        callback.setAction(TermuxResultReceiver.ACTION_RESULT);
        callback.putExtra("request_id", requestId);
        PendingIntent pending = PendingIntent.getBroadcast(
                context, requestId.hashCode(), callback,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Intent intent = new Intent(ACTION_RUN_COMMAND);
        intent.setClassName("com.termux", SERVICE);
        intent.putExtra(EXTRA_COMMAND_PATH, commandPath);
        intent.putExtra(EXTRA_ARGUMENTS, arguments == null ? new String[0] : arguments);
        intent.putExtra(EXTRA_BACKGROUND, true);
        intent.putExtra(EXTRA_WORKDIR, "/data/data/com.termux/files/home");
        intent.putExtra(EXTRA_PENDING_INTENT, pending);
        context.startService(intent);
        return requestId;
    }
}
