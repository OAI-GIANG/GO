from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from engine import GovernanceLoadError, verify_policy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md"
BINDING = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"
GENERATED = ROOT / "runtime_v1" / "generated"


def main() -> int:
    try:
        verified = verify_policy(ROOT / "control")
    except GovernanceLoadError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 2
    GENERATED.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, GENERATED / SOURCE.name)
    shutil.copyfile(BINDING, GENERATED / BINDING.name)
    shutil.copyfile(ROOT / "runtime_v1" / "engine.py", GENERATED / "runtime.py")
    manifest = {
        "runtime_id": "HG-GENERATED-V1",
        "runtime_status": "GENERATED",
        "source_sha256": verified["source_sha256"],
        "source_file_sha256": hashlib.sha256((GENERATED / SOURCE.name).read_bytes()).hexdigest(),
        "entrypoint": "runtime.py",
        "generated_from": "control/MASTER_GOVERNANCE_RULESET_V1.md",
        "legacy_runtime_fallback": False,
        "source_internal_metadata_conflict": "DISCLOSED_IN_APPROVAL_BINDING",
    }
    (GENERATED / "runtime-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    check = subprocess.run(
        [sys.executable, str(GENERATED / "runtime.py"), "--self-test"],
        cwd=str(GENERATED),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    print(json.dumps({
        "status": "GENERATED" if check.returncode == 0 else "GENERATED_BUT_SELF_TEST_FAILED",
        "output_dir": str(GENERATED),
        "source_sha256": verified["source_sha256"],
        "runtime_self_test_exit": check.returncode,
        "runtime_stdout": check.stdout.strip(),
        "runtime_stderr": check.stderr.strip(),
    }, ensure_ascii=False, indent=2))
    return check.returncode


if __name__ == "__main__":
    raise SystemExit(main())
