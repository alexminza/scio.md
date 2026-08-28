#!/usr/bin/env python3
"""Platform side: sign a rules document with the offline Ed25519 key. Not shipped in the skill.

  sign-rules.py rules.json [--key ~/.config/scio/rules-signing.key] [--key-id scio-rules-2026-08] > signed.json

rules.json: {"version": "...", "rules": {...}, "sources": [...], "effective_at": "..."}. Output adds
`canonical` (JCS-style canonical JSON of version+rules+sources+effective_at), `signature` (base64 Ed25519 over
canonical) and `signing_key_id`, matching the scio_get_rules contract. The private key never leaves the
machine that owns the rules (P1, P10); the public half is pinned in skills/scio/SKILL.md."""
import argparse, base64, json, os, sys
from cryptography.hazmat.primitives import serialization

ap = argparse.ArgumentParser()
ap.add_argument("rules")
ap.add_argument("--key", default=os.path.expanduser("~/.config/scio/rules-signing.key"))
ap.add_argument("--key-id", default="scio-rules-2026-08")
a = ap.parse_args()

doc = json.load(open(a.rules))
for f in ("version", "rules", "effective_at"):
    if f not in doc:
        sys.exit(f"rules.json needs {f}")
payload = {k: doc[k] for k in ("version", "rules", "sources", "effective_at") if k in doc}
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
key = serialization.load_pem_private_key(open(a.key, "rb").read(), password=None)
sig = key.sign(canonical.encode())
doc.update({"canonical": canonical, "signature": base64.b64encode(sig).decode(), "signing_key_id": a.key_id})
json.dump(doc, sys.stdout, indent=2, ensure_ascii=False); print()
