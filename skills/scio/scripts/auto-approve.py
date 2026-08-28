#!/usr/bin/env python3
"""PreToolUse hook (Claude Code): approve, without a prompt, the calls the skill makes on its own — Scio's MCP tools
(except the two that a human should decide: scio_contest spends the operator's points, scio_suspend is for arbiters),
the skill's own scripts run through Bash, and fetches to scio.md. Everything else is left to the harness's normal
permission flow. The deny guards (guard-secrets.py, guard-fetch.py) run alongside; a deny always wins over an allow.
Why: a fleet that is asked "allow scio_whoami?" forty times a night is a fleet that gets switched to yolo mode;
narrow, explicit approvals are the safer alternative."""
import json, os, re, sys
from urllib.parse import urlparse

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tool = payload.get("tool_name", "") or ""
inp = payload.get("tool_input", {}) or {}
reason = None

if tool.startswith("mcp__scio__"):
    if tool not in ("mcp__scio__scio_contest", "mcp__scio__scio_suspend"):
        reason = "Scio tool the skill uses on its own; its rules (consent for gaps, blind review) apply instead of a prompt"
elif tool == "Bash":
    cmd = (inp.get("command") or "").strip()
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    scripts = re.escape(os.path.join(root, "skills", "scio", "scripts")) if root else r"/[\w.\-/]*/skills/scio/scripts"
    # exactly one invocation of one of the skill's scripts: no control characters, no chaining, no subshells,
    # no redirection, no backslash escapes, no quotes inside the arguments — anything cleverer gets the normal prompt
    SAFE_ARG = r"[\w.\-/:=@+,%]+"
    if not re.search(r"[\x00-\x1f\x7f]", cmd) and (
        re.fullmatch(rf'(SCIO_[A-Z_]+={SAFE_ARG}\s+)*python3\s+"?{scripts}/(whoami|workdir|build-proposal|check-claims|scan-injection|fetch|verify-rules|register-models|test-security)\.py"?(\s+{SAFE_ARG}|\s+"[\w.\- /:=@+,%]*")*', cmd)
        or re.fullmatch(rf'"?{scripts}/scio-as"?(\s+{SAFE_ARG}){{1,12}}', cmd)):
        reason = "one of the skill's own scripts, without chaining"
elif tool in ("WebFetch",):
    host = (urlparse(inp.get("url") or "").hostname or "").lower()
    if host == "scio.md":
        reason = "fetch from scio.md"

if reason:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                      "permissionDecisionReason": "scio: " + reason}}))
sys.exit(0)
