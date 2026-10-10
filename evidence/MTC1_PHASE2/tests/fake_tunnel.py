import json
import os

out = os.environ.get("HG_FAKE_OUT") or "env_seen.json"
open(out, "w", encoding="utf-8").write(json.dumps({
    "url": os.environ.get("HG_EDGE_URL"),
    "dev": os.environ.get("HG_EDGE_DEVICE"),
    "tokf": os.environ.get("HG_EDGE_TOKEN_FILE"),
}))
