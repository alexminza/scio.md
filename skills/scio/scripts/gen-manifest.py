#!/usr/bin/env python3
"""Write skills/scio/MANIFEST.sha256 — the SHA-256 of every file in the skill (except the manifest itself).
Run by the maintainer before a release; whoami.py verifies the installed skill against it at session start and
warns when a file differs. The skill is the agents' shared brain: a modified SKILL.md or workflow is the highest-value
attack there is, and a checksum is the cheapest thing that makes it visible. The manifest is committed with the
release and its own hash is published at https://scio.md/plugin so an installed copy can be checked end to end."""
import hashlib, os, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = []
for dirpath, dirs, files in os.walk(root):
    dirs[:] = sorted(d for d in dirs if d != "__pycache__")
    for f in sorted(files):
        if f == "MANIFEST.sha256" or f.endswith(".pyc"):
            continue
        p = os.path.join(dirpath, f)
        rel = os.path.relpath(p, root)
        lines.append(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {rel}")
out = os.path.join(root, "MANIFEST.sha256")
open(out, "w").write("\n".join(lines) + "\n")
print(f"wrote {out} ({len(lines)} files); manifest sha256 {hashlib.sha256(open(out,'rb').read()).hexdigest()}")
