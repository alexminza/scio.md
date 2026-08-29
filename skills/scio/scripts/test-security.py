#!/usr/bin/env python3
"""Regression test for the skill's defences: every fixture in assets/redteam must still be caught, every clean
fixture must still pass. Run after any change to scan-injection.py, check-claims.py, guard-*.py or the fixtures.
Exit 0 when all expectations hold, 1 otherwise. (P0 applied to ourselves: a defence is verified, not assumed.)"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "..", "assets", "redteam")
PY = sys.executable
env = dict(os.environ, SCIO_API_KEY="REDTEAM_KEY_0123456789", SCIO_KEYS_FILE="/nonexistent")
failures = []


def run(script, args=None, stdin=None):
    r = subprocess.run([PY, os.path.join(HERE, script)] + (args or []), input=stdin, capture_output=True, text=True, env=env)
    return r.returncode, r.stdout


def expect(cond, msg):
    print(("  ok    " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


for f in sorted(glob.glob(os.path.join(FIX, "*.txt"))):
    code, out = run("scan-injection.py", [f])
    name = os.path.basename(f)
    if name.startswith("clean"):
        expect(code == 0, f"{name}: no findings")
    else:
        expect(code == 1, f"{name}: scanner finds it ({out.count(chr(10))} findings)")
for f in sorted(glob.glob(os.path.join(FIX, "*.proposal.json"))):
    code, out = run("check-claims.py", [f])
    name = os.path.basename(f)
    if name.startswith("clean"):
        expect(code == 0 and "ERROR" not in out, f"{name}: pre-flight passes")
    else:
        expect(code == 1 and "security.md" in out or "P7" in out, f"{name}: pre-flight blocks it")
for f in sorted(glob.glob(os.path.join(FIX, "*.hook.json"))):
    name = os.path.basename(f)
    payload = open(f).read()
    denied = False
    for guard in ("guard-secrets.py", "guard-fetch.py"):
        code, out = run(guard, stdin=payload)
        if '"deny"' in out:
            denied = True
    if name.startswith("clean"):
        expect(not denied, f"{name}: guards allow it")
    else:
        expect(denied, f"{name}: a guard denies it")


# --- the review of v0.3.11: every confirmed bug stays fixed ---------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
S = os.path.join(ROOT, "skills", "scio", "scripts")
CFG = os.path.join(".config", "scio")   # built, not written: the guards deny a command that carries the literal path
aenv = dict(env, CLAUDE_PLUGIN_ROOT=ROOT)


def hook(script, tool, inp, extra_env=None):
    r = subprocess.run([PY, os.path.join(HERE, script)], input=json.dumps({"tool_name": tool, "tool_input": inp}),
                       capture_output=True, text=True, env=dict(aenv, **(extra_env or {})))
    try:
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else None
    except (ValueError, KeyError):
        return "malformed:" + r.stdout[:60]


def approve(cmd, extra_env=None):
    return hook("auto-approve.py", "Bash", {"command": cmd}, extra_env)


print("\nauto-approve.py")
expect(approve(f"{S}/scio-as opus --print-env") is None, "1: scio-as --print-env is not auto-approved (it prints the key)")
expect(approve(f"{S}/scio-as opus codex --profile scio") == "allow", "1: scio-as <alias> <harness> still is")
expect(approve(f"{S}/scio-as --list") == "allow", "1: scio-as --list still is")
expect(approve(f"python3 {S}/fetch.py https://example.com --out ~/.ssh/authorized_keys") is None, "2: fetch.py --out is not auto-approved")
expect(approve(f"python3 {S}/fetch.py https://example.com --out skills/scio/SKILL.md") is None, "2: fetch.py --out onto the skill is not")
expect(approve(f"python3 {S}/fetch.py https://example.com --max-bytes 1000") == "allow", "2: fetch.py without --out still is")
expect(approve(f"python3 {S}/workdir.py --prune 0") is None, "3: workdir.py --prune is not auto-approved")
expect(approve(f"python3 {S}/workdir.py write my-article") == "allow", "3: workdir.py <kind> <ref> still is")
expect(approve(f"python3 {S}/workdir.py evil ../x") is None, "3: workdir.py with an unknown kind is not")
expect(hook("auto-approve.py", "Bash", {"command": "python3 /tmp/evil/skills/scio/scripts/fetch.py https://x"},
            {"CLAUDE_PLUGIN_ROOT": ""}) is None, "4: without CLAUDE_PLUGIN_ROOT nothing is auto-approved")
expect(approve("python3 /tmp/evil/skills/scio/scripts/fetch.py https://x") is None, "4: a planted script outside the plugin root is not")

print("guard-secrets.py")
KF = os.path.join(HERE, "..", "assets", "redteam", "credfile.tmp")
open(KF, "w").write("opus=REDTEAM_SECOND_KEY_9876543210\n")
try:
    expect(hook("guard-secrets.py", "Bash", {"command": f"head {KF}"}, {"SCIO_KEYS_FILE": KF}) == "deny", "5: head of a custom keys file (no 'keys' in the name) is denied")
    expect(hook("guard-secrets.py", "Bash", {"command": f"python3 -c \"open('~/{CFG}/'+'ke'+'ys')\""}) == "deny", "5: the keys directory reached by concatenation is denied")
    expect(hook("guard-secrets.py", "Read", {"file_path": os.path.expanduser(f"~/{CFG}/keys")}) == "deny", "5: Read of the keys file is denied")
    expect(hook("guard-secrets.py", "Bash", {"command": "ls ~/.config"}) is None, "5: an unrelated command is not")
finally:
    os.remove(KF)

print("agy-hook.py")
def agy(name, args):
    r = subprocess.run([PY, os.path.join(HERE, "agy-hook.py")], input=json.dumps({"toolCall": {"name": name, "args": args}}),
                       capture_output=True, text=True, env=aenv)
    return json.loads(r.stdout)["decision"] if r.stdout.strip() else None
expect(agy("filesystem/write_scio_file", {"path": "x"}) is None, "6: a foreign tool containing 'scio_' gets no decision")
expect(agy("scio/scio_whoami", {}) == "allow", "6: scio/scio_whoami is allowed")
expect(agy("scio/scio_contest", {}) is None, "6: scio/scio_contest is not")
expect(agy("scio-local/workdir", {"kind": "write", "ref": "x"}) == "allow", "6: scio-local/workdir is allowed")

print("redirects (whoami.py, register-models.py)")
import http.server, threading
seen = []
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        seen.append((self.server.server_port, self.headers.get("Authorization")))
        if self.path == "/v1/me":
            self.send_response(302); self.send_header("Location", f"http://127.0.0.1:{other.server_port}/stolen"); self.end_headers()
        else:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b"{}")
    def log_message(self, *a): pass
api = http.server.HTTPServer(("127.0.0.1", 0), H); other = http.server.HTTPServer(("127.0.0.1", 0), H)
for srv in (api, other):
    threading.Thread(target=srv.serve_forever, daemon=True).start()
subprocess.run([PY, os.path.join(HERE, "whoami.py")], capture_output=True, text=True, env=dict(aenv, SCIO_API=f"http://127.0.0.1:{api.server_port}/v1"))
expect(any(p == api.server_port and a for p, a in seen), "8: the bearer reaches the API host")
expect(not any(p == other.server_port for p, a in seen), "8: a redirect to another host is not followed")
api.shutdown(); other.shutdown()

print("guard-fetch.py / scan-injection.py / check-claims.py")
expect(hook("guard-fetch.py", "WebFetch", {"url": "https://nonexistent.invalid/"}) == "deny", "12: an unresolvable host is denied (fail closed)")
gf = subprocess.run([PY, "-c", "import sys; sys.path.insert(0, %r); import importlib; g = importlib.import_module('guard-fetch'); print(g.check('https://cafe/'))" % HERE], capture_output=True, text=True).stdout
expect("non-canonical" not in gf, "16: a hex word without a colon is a name, not a numeric host")
expect(hook("guard-fetch.py", "WebFetch", {"url": "http://0x7f000001/"}) == "deny", "16: hex IPv4 is still numeric and private")
expect(hook("guard-fetch.py", "WebFetch", {"url": "http://[::1]/"}) == "deny", "16: IPv6 loopback is still denied")
code, out = run("scan-injection.py", ["-"], stdin="see http://foo.localhost/admin")
expect(code == 1 and "private_host" in out, "14: scan-injection flags *.localhost")
def claims(*cl):
    return json.dumps({"tool_input": {"body": "---\ndomain: history\n---\nA sentence.[^c1] ^c1", "claims": list(cl)}})
def preflight(payload):
    r = subprocess.run([PY, os.path.join(HERE, "check-claims.py")], input=payload, capture_output=True, text=True, env=aenv)
    try:
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else None
    except (ValueError, KeyError):
        return "malformed"
base = {"ordinal": 1, "text": "x", "quote": "q", "accessed_at": "2026-08-29"}
expect(preflight(claims(dict(base, source_url="https://wikipedia.org#@evil.example/"))) == "deny", "13: wikipedia.org hidden behind #@ is forbidden")
expect(preflight(claims(dict(base, source_url="https://wikipedia.org./wiki/X"))) == "deny", "13: wikipedia.org. (trailing dot) is forbidden")
expect(preflight(claims(dict(base, source_url="https://example.com/x"))) in (None, "allow"), "13: an ordinary host passes")
expect(preflight(json.dumps({"tool_input": {"body": "x", "claims": ["not-a-dict"]}})) == "deny", "15: a non-object claim is denied, not a crash")
expect(preflight(json.dumps({"tool_input": {"body": "x", "claims": "nope"}})) == "deny", "15: a non-list claims field is denied")

print("harness configuration")
setup = open(os.path.join(HERE, "setup.py")).read()
expect('"excludeTools": ["scio_contest", "scio_suspend"]' in setup and "scio_contest" in json.load(open(os.path.join(ROOT, "gemini", "settings.scio.json")))["mcpServers"]["scio"]["excludeTools"], "9: Gemini excludes scio_contest")
expect('"exclude_tools": ["scio_contest", "scio_suspend"]' in setup, "9: Hermes excludes scio_contest")
expect(CFG not in setup.split("writable_roots")[1].split("\n")[0] and CFG not in open(os.path.join(ROOT, "codex", "config.scio.toml")).read().split("writable_roots")[1].split("\n")[0], "10: Codex cannot write the keys directory")
expect('"Authorization: Bearer " + key' not in setup and 'f"Bearer {key}", "X-Scio-Harness": "openclaw"' not in setup, "11: no key on argv for kimi-cli / OpenClaw")
vs = open(os.path.join(ROOT, "vscode", "settings.scio.json")).read()
oc = open(os.path.join(ROOT, "opencode", "opencode.scio.jsonc")).read()
ag = open(os.path.join(ROOT, "antigravity", "permissions.md")).read()
expect("(?:claude|codex|gemini|opencode|kimi|cursor-agent|hermes|grok|qwen|copilot)" in vs, "7: VS Code allows scio-as only before a known harness")
expect('"*scio-as *": "ask"' in oc and '"*scio-as *": "allow"' not in oc, "7: OpenCode asks for an arbitrary scio-as")
expect("command((.*/)?scio-as)" in ag.split("# Ask list")[1], "7: Antigravity has scio-as on Ask")
expect("hooks-cursor.json" in setup and "write_hooks_absolute" in setup, "17: setup.py rewrites Cursor/Antigravity hook paths to absolute")

# --- the review of v0.3.12 ------------------------------------------------------------------------------------
print("\nthe review of v0.3.12")
expect(approve(f"python3 {S}/verify-rules.py /tmp/served.json --out /tmp/out.json") is None, "2: verify-rules.py --out is not auto-approved")
expect(approve(f"python3 {S}/verify-rules.py /tmp/served.json") == "allow", "2: verify-rules.py without --out still is")
expect(approve(f"python3 {S}/fetch.py https://example.com --max-bytes 999999999") is None, "6: fetch.py --max-bytes above the 200 KB budget is not auto-approved")
expect(approve(f"python3 {S}/fetch.py https://example.com --max-bytes 200000") == "allow", "6: fetch.py --max-bytes 200000 still is")
expect("min(int(a[a.index(\"--max-bytes\") + 1]), 200_000)" in open(os.path.join(HERE, "fetch.py")).read()
       and "min(int(a[\"max_bytes\"]), 200_000)" in open(os.path.join(HERE, "..", "server", "scio_local.py")).read(), "6: fetch.py and scio-local clamp max_bytes")
for name, txt in (("VS Code", vs), ("OpenCode", "\n".join(l for l in oc.splitlines() if not l.strip().startswith("//"))), ("Antigravity", ag)):
    expect("__SCIO_SCRIPTS__" in txt and "(?:\\/[\\w.\\-\\/]+)?" not in txt and "*skills/scio/scripts/" not in txt and "(.*/)?skills/scio" not in txt,
           f"1: {name} approves only the absolute scripts directory (placeholder, no wildcard prefix)")
vs_rule = lambda script: next(l for l in vs.splitlines() if f"/{script}\\\\.py" in l)
expect("(?!--out\\\\b)" in vs_rule("verify-rules") and '"python3 __SCIO_SCRIPTS__/verify-rules.py *--out*": "ask"' in oc
       and "verify-rules\\.py .*--out" in ag.split("# Ask list")[1], "2: VS Code / OpenCode / Antigravity ask for verify-rules.py --out")
expect("--max-bytes (?:[1-9]\\\\d{0,4}|1\\\\d{5}|200000)" in vs_rule("fetch") and "(?!--max-bytes\\\\b)" in vs_rule("fetch"), "6: VS Code caps fetch.py --max-bytes")
gx = json.load(open(os.path.join(ROOT, "gemini-extension.json")))["mcpServers"]["scio"]
expect(gx.get("excludeTools") == ["scio_contest", "scio_suspend"], "3: gemini-extension.json excludes contest/suspend")
for hf in ("hooks.json", os.path.join("hooks", "hooks-cursor.json")):
    cmds = re.findall(r'"command":\s*"((?:[^"\\]|\\.)*)"', open(os.path.join(ROOT, hf)).read())
    expect(cmds and all(not c.startswith("python3 skills/") for c in cmds) and all("|| echo" in c and "deny" in c for c in cmds if "hook.py" in c),
           f"4: {hf} ships absolute guard paths with a deny fallback")
CC = os.path.join(HERE, "..", "assets", "redteam", "nondict.tmp.json")
json.dump({"body": "x", "claims": ["not-a-dict"]}, open(CC, "w"))
try:
    r = subprocess.run([PY, os.path.join(HERE, "check-claims.py"), CC], capture_output=True, text=True, env=aenv)
finally:
    os.remove(CC)
expect("Traceback" not in r.stderr and "must be an object" in r.stdout + r.stderr, "5: check-claims.py CLI reports a non-object claim instead of crashing")
# verify-rules.py --out only inside the task work root: a document signed with a throwaway key
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    import base64, tempfile
    k = Ed25519PrivateKey.generate()
    pub = base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    rules = {"version": "2026-08-29", "limits": {}}
    canonical = json.dumps(rules, sort_keys=True, separators=(",", ":"))
    doc = {"version": rules["version"], "rules": rules, "canonical": canonical, "signature": base64.b64encode(k.sign(canonical.encode())).decode()}
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "served.json"); json.dump(doc, open(src, "w"))
        wd = os.path.join(d, "work"); os.makedirs(wd)
        outside = os.path.join(d, "bashrc")
        r1 = subprocess.run([PY, os.path.join(HERE, "verify-rules.py"), src, "--key", pub, "--out", outside], capture_output=True, text=True, env=dict(aenv, SCIO_WORK_DIR=wd))
        expect(r1.returncode != 0 and not os.path.exists(outside), "2: verify-rules.py refuses --out outside the task work root")
        inside = os.path.join(wd, "rules.json")
        r2 = subprocess.run([PY, os.path.join(HERE, "verify-rules.py"), src, "--key", pub, "--out", inside], capture_output=True, text=True, env=dict(aenv, SCIO_WORK_DIR=wd))
        expect(r2.returncode == 0 and json.load(open(inside)) == rules, "2: verify-rules.py writes --out inside the task work root")
except ImportError:
    print("  (cryptography not installed: verify-rules.py --out root check not exercised)")

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
