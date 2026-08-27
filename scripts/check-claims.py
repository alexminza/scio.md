#!/usr/bin/env python3
"""PreToolUse guard for scio_propose_edit (Claude Code hook contract: tool input JSON on stdin).
Refuses proposals whose claims are incomplete, cite Wikipedia, or do not cover the body's sentences.
Defense in depth only — the server gates are authoritative and this check mirrors the platform contract."""
import json, re, sys

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
inp = payload.get("tool_input", {}) or {}
claims = inp.get("claims") or []
text = inp.get("body") or inp.get("patch") or ""
problems = []

REQUIRED = ("ordinal", "text", "source_url", "quote", "accessed_at")
for i, c in enumerate(claims):
    missing = [f for f in REQUIRED if not c.get(f)]
    if missing:
        problems.append(f"claim {i}: missing {', '.join(missing)}")
    if "wikipedia.org" in (c.get("source_url") or ""):
        problems.append(f"claim {i}: Wikipedia is not an acceptable source (P7)")
    if bool(c.get("second_source_url")) != bool(c.get("second_quote")):
        problems.append(f"claim {i}: second_source_url and second_quote go together")

# For a patch, look only at added lines; for a body, at everything after the front matter.
if inp.get("patch"):
    prose = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
else:
    prose = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
prose = re.sub(r"^#.*$", "", prose, flags=re.M)  # headings carry no claims
markers = {int(n) for n in re.findall(r"\[\^c(\d+)\]", prose)}
ordinals = {c.get("ordinal") for c in claims if isinstance(c.get("ordinal"), int)}
if markers - ordinals:
    problems.append(f"markers without a claim: {sorted(markers - ordinals)[:8]}")
sentences = [s for s in re.split(r"(?<=[.!?\]])\s+", prose.strip()) if len(s) > 20 and not s.startswith("|")]
unmarked = [s[:60] for s in sentences if not re.search(r"\[\^c\d+\]", s)]
if unmarked:
    problems.append(f"{len(unmarked)} sentence(s) without a [^cN] marker, e.g. \"{unmarked[0]}…\"")
if "<" in prose and re.search(r"<[a-zA-Z/][^>]*>", prose):
    problems.append("raw HTML is rejected at gate 0; use the Markdown dialect")

if problems:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "scio: fix before proposing — " + "; ".join(problems[:8]),
        }
    }))
sys.exit(0)
