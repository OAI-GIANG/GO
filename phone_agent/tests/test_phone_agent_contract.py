from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA_ROOT = ROOT / "android/app/src/main/java/com/hg/phoneagent"
MAIN = JAVA_ROOT / "MainActivity.java"
LONGPOLL = JAVA_ROOT / "LongPollClient.java"
DISPATCH_BRIDGE = JAVA_ROOT / "TermuxDispatch.java"
RECEIVER = JAVA_ROOT / "TermuxResultReceiver.java"
RUNNER = JAVA_ROOT / "TermuxRunner.java"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
DISPATCH_V2 = ROOT / "termux/dispatch_v2.sh"
INSTALLER = ROOT / "termux/install_dispatch.sh"


def test_https_longpoll_and_request_correlation():
    main = MAIN.read_text(encoding="utf-8")
    client = LONGPOLL.read_text(encoding="utf-8")
    assert "PHONE_AGENT_REQUIRES_HTTPS" in main
    assert 'startsWith("https://")' in client
    assert "/api/phone/register" in main
    assert "/api/phone/poll" in client
    assert "/api/phone/result" in client
    assert "Math.min(backoff * 2, 30000L)" in client
    assert "exec.execute(rid, cap, params)" in client
    assert "execute(String requestId, String capability, JSONObject params)" in client
    assert "startLongPoll" in main


def test_termux_permission_and_fixed_dispatch_path():
    manifest = MANIFEST.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")
    bridge = DISPATCH_BRIDGE.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    assert "com.termux.permission.RUN_COMMAND" in manifest
    assert "com.termux.app.RunCommandService" in runner
    assert "/data/data/com.termux/files/home/hg-agent/dispatch.sh" in bridge
    assert "HG_PHONE_AGENT_V2_DISPATCH_WRAPPER_V1" in installer
    assert "TARGET_EXISTS_NOT_OWNED_BY_INSTALLER" in installer
    assert "feature/phone-agent-v2-fileops" in installer
    assert "https://github.com/OAI-GIANG/GO.git" in installer


def test_no_arbitrary_command_path():
    main = MAIN.read_text(encoding="utf-8")
    assert 'c.optString("path")' in main
    assert "CAPABILITY_DENIED" in main
    assert '"/data/data/com.termux/files/home/hg-agent/dispatch.sh".equals(path)' in main


def test_dispatch_is_bounded_to_fileops_capabilities():
    dispatch = DISPATCH_V2.read_text(encoding="utf-8")
    fileops = (ROOT.parent / "runtime/go_runtime/core/phone_fileops.py").read_text(encoding="utf-8")
    assert "from phone_fileops import PhoneFileOps" in dispatch
    assert "ops.handle(req)" in dispatch
    for capability in ("LIST_FILES", "READ_FILE", "WRITE_FILE", "APPLY_PATCH", "GET_DIFF", "RUN_TEST"):
        assert capability in fileops
    assert "ALLOWED_TESTS" in fileops
    assert "CORE_IMPORT_FAILED" in dispatch


def test_termux_result_delivery_is_race_safe_and_uses_bundle_stdout():
    receiver = RECEIVER.read_text(encoding="utf-8")
    bridge = DISPATCH_BRIDGE.read_text(encoding="utf-8")
    assert "EXTRA_PLUGIN_RESULT_BUNDLE_STDOUT" in receiver
    assert "TermuxDispatch.deliver(requestId, stdout, exitCode)" in receiver
    assert "LinkedBlockingQueue" in bridge
    assert "EARLY.put(termuxRequestId, value)" in bridge
    assert "TERMUX_EXIT_NONZERO" in bridge
    assert "SynchronousQueue" not in bridge


def test_phone_agent_dispatch_isolated_from_phone_bridge_owner():
    # The canonical Phone Bridge may exist; this dispatcher must not import or mutate it directly.
    dispatch = DISPATCH_V2.read_text(encoding="utf-8")
    assert "from phone_bridge import" not in dispatch
    assert "phone_bridge.py" not in dispatch
