#!/usr/bin/env python3
"""Regression test for the skill's defences: every fixture in assets/redteam must still be caught, every clean
fixture must still pass. Run after any change to scan-injection.py, check-claims.py, guard-*.py or the fixtures.
Exit 0 when all expectations hold, 1 otherwise. (P0 applied to ourselves: a defence is verified, not assumed.)"""
import glob, json, os, subprocess, sys

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

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
