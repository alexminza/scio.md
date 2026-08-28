#!/usr/bin/env python3
"""Antigravity PreToolUse adapter: runs the skill's guards (guard-secrets, guard-fetch, check-claims, auto-approve)
on Antigravity's hook payload and answers in its contract.

Antigravity sends {"toolCall": {"name", "args"}, ...} on stdin and expects {"decision": "allow"|"deny"|"ask"} on
stdout; Claude Code sends {"tool_name", "tool_input"} and expects hookSpecificOutput.permissionDecision. This
script translates both ways so the same guard code protects both harnesses: any guard's deny → "deny";
auto-approve's allow → "allow"; otherwise no decision (Antigravity's own permission lists apply)."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
call = payload.get("toolCall") or {}
name = call.get("name") or ""
args = call.get("args") or {}
# map the tool to what the guards understand
if "scio_" in name:  # Antigravity names MCP tools by server and tool (e.g. scio/scio_whoami); keep the tool part
    tool = "mcp__scio__scio_" + name.rsplit("scio_", 1)[-1]
elif any(k in args for k in ("CommandLine", "command", "cmd")):
    tool = "Bash"
    args = {"command": args.get("CommandLine") or args.get("command") or args.get("cmd") or ""}
elif any(k in args for k in ("url", "Url", "URL")):
    tool = "WebFetch"
    args = {"url": args.get("url") or args.get("Url") or args.get("URL") or ""}
else:
    tool = name
claude_payload = json.dumps({"tool_name": tool, "tool_input": args})
env = dict(os.environ, CLAUDE_PLUGIN_ROOT=os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # …/skills/scio/scripts → repo root

def run(script):
    r = subprocess.run([sys.executable, os.path.join(HERE, script)], input=claude_payload, capture_output=True, text=True, env=env, timeout=10)
    try:
        return json.loads(r.stdout).get("hookSpecificOutput", {}) if r.stdout.strip() else {}
    except ValueError:
        return {}

decision, reason = None, None
for g in ("guard-secrets.py", "guard-fetch.py") + (("check-claims.py",) if tool == "mcp__scio__scio_propose_edit" else ()):
    out = run(g)
    if out.get("permissionDecision") == "deny":
        decision, reason = "deny", out.get("permissionDecisionReason"); break
if decision is None:
    out = run("auto-approve.py")
    if out.get("permissionDecision") == "allow":
        decision, reason = "allow", out.get("permissionDecisionReason")
if decision:
    print(json.dumps({"decision": decision, "reason": reason}))
sys.exit(0)
