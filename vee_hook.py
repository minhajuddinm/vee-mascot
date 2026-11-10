"""Helper Claude Code hooks call: python vee_hook.py work|need|done|idle
Forwards the hook's JSON (prompt, tool name, notification text) to Vee.
Never fails, so a closed mascot never blocks Claude Code."""
import json
import sys
import urllib.request

try:
    state = sys.argv[1] if len(sys.argv) > 1 else "idle"
    data = {}
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                data = json.loads(raw)
    except Exception:
        data = {}
    body = json.dumps({"state": state, "data": data}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:7777/event", data=body,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=1)
except Exception:
    pass
sys.exit(0)
