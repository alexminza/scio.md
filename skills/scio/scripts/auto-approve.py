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

if tool.startswith("mcp__scio-local__"):
    reason = "the skill's own local tool (task folders, drafts, pre-flight, guarded fetch, wait)"
elif tool.startswith("mcp__scio__"):
    if tool not in ("mcp__scio__scio_contest", "mcp__scio__scio_suspend"):
        reason = "Scio tool the skill uses on its own; its rules (consent for gaps, blind review) apply instead of a prompt"
elif tool == "Bash":
    cmd = (inp.get("command") or "").strip()
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    # without the plugin root there is nothing to anchor the script path to: a wildcard prefix would approve a planted
    # /tmp/x/skills/scio/scripts/fetch.py just the same — so no root, no approval (the normal prompt applies)
    scripts = re.escape(os.path.join(root, "skills", "scio", "scripts")) if root else None
    # exactly one invocation of one of the skill's scripts: no control characters, no chaining, no subshells,
    # no redirection, no backslash escapes, no quotes inside the arguments — anything cleverer gets the normal prompt
    SAFE_ARG = r"[\w.\-/:=@+,%]+"
    ALIAS = r"[A-Za-z0-9_\-]+"
    # scio-as execs its arguments: only a known harness binary is approved without a prompt, never an arbitrary command.
    # `scio-as <alias> --print-env` is not approved either: it prints the raw key into the session (it is for the
    # operator's shell, eval "$(…)"), and guard-secrets sees arguments, not output.
    HARNESS = r"(claude|codex|gemini|opencode|kimi|cursor-agent|hermes|grok|qwen|copilot)"
    # env overrides that cannot redirect the key or the keys file: SCIO_API (where the bearer key is sent),
    # SCIO_API_KEY and SCIO_KEYS_FILE are deliberately absent — a prompt-injected `SCIO_API=https://evil …`
    # would otherwise be approved silently and exfiltrate the agent's identity
    ENV = r"SCIO_(ROLES|WORK_DIR|HARNESS|LANGUAGES|MODEL_FAMILY|MODEL_VERSION|RULES_BUNDLED)"
    # per-script argument policy: workdir.py only `<kind> <ref>` (--prune deletes task folders: a prompt);
    # fetch.py never `--out` (it would write wherever the argument says: a prompt)
    SCRIPT_ARGS = {
        "workdir": r"\s+(write|review|translate|maintain|gap|contest|request|loop)\s+" + SAFE_ARG,
        "fetch": rf"(\s+(?!--out\b){SAFE_ARG})+",
    }
    if scripts and not re.search(r"[\x00-\x1f\x7f]", cmd):
        m = re.fullmatch(rf'({ENV}={SAFE_ARG}\s+)*python3\s+"?{scripts}/(?P<script>whoami|workdir|build-proposal|check-claims|scan-injection|fetch|verify-rules|register-models|test-security)\.py"?(?P<args>(\s+{SAFE_ARG}|\s+"[\w.\- /:=@+,%]*")*)', cmd)
        if m:
            script, args = m.group("script"), m.group("args") or ""
            policy = SCRIPT_ARGS.get(script)
            if policy is None or re.fullmatch(policy, args):
                reason = "one of the skill's own scripts, without chaining"
        elif re.fullmatch(rf'"?{scripts}/scio-as"?\s+(--list|{ALIAS}\s+(--supervise\s+)?{HARNESS}(\s+{SAFE_ARG}){{0,12}})', cmd):
            reason = "one of the skill's own scripts, without chaining"
elif tool in ("WebFetch",):
    host = (urlparse(inp.get("url") or "").hostname or "").lower()
    if host == "scio.md":
        reason = "fetch from scio.md"

if reason:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                      "permissionDecisionReason": "scio: " + reason}}))
sys.exit(0)
