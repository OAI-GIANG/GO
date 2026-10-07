from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "android/app/src/main/java/com/hg/phoneagent/MainActivity.java"
TERMUX = ROOT / "android/app/src/main/java/com/hg/phoneagent/TermuxRunner.java"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
DISPATCH = ROOT / "termux/dispatch.sh"

def test_wss_only_and_reconnect():
    s = JAVA.read_text(encoding="utf-8")
    assert "PHONE_AGENT_REQUIRES_WSS" in s
    assert "backoff=1000" in s
    assert "Math.min(backoff*2,30000)" in s
    assert "Thread.sleep(backoff)" in s

def test_termux_permission_and_fixed_path():
    m = MANIFEST.read_text(encoding="utf-8")
    t = TERMUX.read_text(encoding="utf-8")
    s = JAVA.read_text(encoding="utf-8")
    assert "com.termux.permission.RUN_COMMAND" in m
    assert "com.termux.app.RunCommandService" in t
    assert "/data/data/com.termux/files/home/hg-agent/dispatch.sh" in s
    assert "CAPABILITY_DENIED" in s

def test_no_arbitrary_command_path():
    s = JAVA.read_text(encoding="utf-8")
    assert 'c.optString("path")' in s
    assert "CAPABILITY_DENIED" in s
    assert "TermuxRunner.run(this,path,args)" in s

def test_dispatch_allowlist():
    s = DISPATCH.read_text(encoding="utf-8")
    assert 'case "$op" in' in s
    assert "health)" in s
    assert "runtime_status)" in s
    assert "CAPABILITY_DENIED" in s

def test_no_hg_core_mutation():
    # Implementation is isolated under phone_agent/.
    assert not any((ROOT / "../../runtime/go_runtime/core").glob("phone_bridge.py"))
