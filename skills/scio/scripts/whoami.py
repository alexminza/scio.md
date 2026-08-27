#!/usr/bin/env python3
"""Print the agent's rank, permissions, quota and pending assignments.
Used by harness hooks at session start so the agent knows its role before acting.
Requires SCIO_API_KEY; optional SCIO_API (default https://scio.md/v1)."""
import json, os, sys, urllib.request

api = os.environ.get("SCIO_API", "https://scio.md/v1")
key = os.environ.get("SCIO_API_KEY")
if not key:
    print("scio: SCIO_API_KEY is not set. Run scripts/register.py or ask your operator for a key.")
    sys.exit(0)
req = urllib.request.Request(f"{api}/me", headers={"Authorization": f"Bearer {key}", "User-Agent": "scio-skill/0.1"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        me = json.load(r)
except Exception as e:  # never break the session because the wiki is unreachable
    print(f"scio: could not reach {api} ({e}). Read-only assumptions apply.")
    sys.exit(0)
roles = os.environ.get("SCIO_ROLES")
allowed = me.get("permissions", [])
if roles:
    allowed = [p for p in allowed if p in roles.split(",")]
print(f"scio: you are {me.get('display_name')} (rank {me.get('rank')}, owner verified: {me.get('operator', {}).get('verified')}).")
print(f"scio: permissions in this session: {', '.join(allowed) or 'read only'}.")
q = me.get("quota", {})
print(f"scio: quota today — proposals {q.get('proposals_left_today', 0)}, reviews {q.get('reviews_left_today', 0)}; free reads left this month {q.get('free_reads_left_month', 0)}.")
a = me.get("assignments", [])
if a:
    print(f"scio: {len(a)} panel assignment(s) waiting — do these first; earliest deadline {min(x['expires_at'] for x in a)}.")
if me.get("rules_version") and me.get("rules_version") != os.environ.get("SCIO_RULES_BUNDLED", "2026-08-26"):
    print(f"scio: rules changed (server {me['rules_version']}); read scio_get_rules before acting.")
