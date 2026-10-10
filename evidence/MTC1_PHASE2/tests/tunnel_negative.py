import os, subprocess, sys, tempfile, pathlib

TUN = r"C:\Users\dang quang vinh\AppData\Local\Temp\opencode\b2_audit\health-tunnel.deployed.py"
results = []

def run(home, extra_env=None):
    env = {"PATH": os.environ.get("PATH",""), "HOME": home, "USERPROFILE": home, "PYTHONIOENCODING":"utf-8"}
    if extra_env: env.update(extra_env)
    p = subprocess.run([sys.executable, TUN], capture_output=True, text=True, env=env, timeout=30)
    return p.returncode, (p.stdout or "") + (p.stderr or "")

# N1: no config, no env -> fail-closed device unset
h1 = tempfile.mkdtemp()
rc, out = run(h1)
ok1 = "BLOCKED_DEVICE_ID_UNSET" in out and rc != 0
results.append(("N1_missing_device_failclosed", ok1, out.splitlines()[0] if out else ""))

# N2: config with URL+DEVICE but NO token file -> fail-closed edge/token absent
h2 = tempfile.mkdtemp()
os.makedirs(os.path.join(h2, ".config", "hg"), exist_ok=True)
pathlib.Path(h2, ".config", "hg", "edge.conf").write_text("HG_EDGE_URL=https://160.191.242.198\nHG_EDGE_DEVICE=phone-primary-u0_a460\n")
rc, out = run(h2)
ok2 = "BLOCKED_EDGE_OR_TOKEN_ABSENT" in out and rc != 0
results.append(("N2_missing_token_failclosed", ok2, out.splitlines()[0] if out else ""))

# N3: config present but token file empty -> fail-closed
h3 = tempfile.mkdtemp()
os.makedirs(os.path.join(h3, ".config", "hg"), exist_ok=True)
pathlib.Path(h3, ".config", "hg", "edge.conf").write_text("HG_EDGE_URL=https://160.191.242.198\nHG_EDGE_DEVICE=phone-primary-u0_a460\n")
pathlib.Path(h3, ".config", "hg", "edge_token").write_text("")
rc, out = run(h3)
ok3 = "BLOCKED_EDGE_OR_TOKEN_ABSENT" in out and rc != 0
results.append(("N3_empty_token_failclosed", ok3, out.splitlines()[0] if out else ""))

# N4: --dry-run must not start polling (exit inline, code 0)
h4 = tempfile.mkdtemp()
os.makedirs(os.path.join(h4, ".config", "hg"), exist_ok=True)
pathlib.Path(h4, ".config", "hg", "edge.conf").write_text("HG_EDGE_URL=https://160.191.242.198\nHG_EDGE_DEVICE=dev\n")
pathlib.Path(h4, ".config", "hg", "edge_token").write_text("dummy")
env = {"PATH": os.environ.get("PATH",""), "HOME": h4, "USERPROFILE": h4, "PYTHONIOENCODING":"utf-8"}
p = subprocess.run([sys.executable, TUN, "--dry-run"], capture_output=True, text=True, env=env, timeout=30)
ok4 = "DRY_RUN_OK" in (p.stdout+p.stderr)
results.append(("N4_dry_run_no_poll", ok4, (p.stdout+p.stderr).splitlines()[0] if (p.stdout+p.stderr) else ""))

for name, ok, info in results:
    print(("PASS " if ok else "FAIL ") + name + (" | " + info if info else ""))
allok = all(r[1] for r in results)
print("B2_TUNNEL_NEGATIVE:", "PASS" if allok else "FAIL")
