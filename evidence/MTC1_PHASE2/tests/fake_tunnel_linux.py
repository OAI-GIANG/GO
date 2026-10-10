import os
import time

mode = os.environ.get("HG_FAKE_MODE", "healthy")
out = os.environ.get("HG_FAKE_OUT", "env.out")
with open(out, "a", encoding="utf-8") as f:
    f.write(mode + "\n")
if mode != "healthy":
    raise SystemExit(3)
time.sleep(3600)
