#!/usr/bin/env python3
"""PreToolUse guard for scio_propose_edit: refuses proposals whose sentences lack claims or whose claims lack quotes.
Defense in depth only — the server gates are authoritative. Reads the tool input JSON from stdin (Claude Code hook contract)."""
import json, sys, re
try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
inp = payload.get("tool_input", {})
claims = inp.get("claims") or []
text = inp.get("new_text") or inp.get("patch") or ""
problems = []
for i, c in enumerate(claims):
    for f in ("text", "source_url", "quote", "source_class", "accessed_at"):
        if not c.get(f):
            problems.append(f"claim {i}: missing {f}")
    if "wikipedia.org" in (c.get("source_url") or ""):
        problems.append(f"claim {i}: Wikipedia is not an acceptable source (P7)")
sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if len(s) > 20]
if sentences and len(claims) < max(1, len(sentences) // 2):
    problems.append(f"only {len(claims)} claims for ~{len(sentences)} sentences; every sentence needs a claim")
if problems:
    print(json.dumps({"decision": "block", "reason": "scio: fix before proposing — " + "; ".join(problems[:8])}))
    sys.exit(0)
sys.exit(0)
