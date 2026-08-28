#!/usr/bin/env python3
"""Write a harness's MCP config with the agent's key, for harnesses whose config files cannot read environment
variables (Antigravity's mcp_config.json).  write-mcp-config.py <alias> antigravity [--global|--workspace]
Reads the key for <alias> from the keys file (register-models.py), writes the file with mode 600 and merges into
an existing one. The key still travels only to scio.md; the file is the harness's own secret store."""
import json, os, sys

a = sys.argv[1:]
if len(a) < 2:
    print(__doc__.strip()); sys.exit(2)
alias, harness = a[0], a[1]
keys = os.environ.get("SCIO_KEYS_FILE") or os.path.expanduser("~/.config/scio/keys")
key = None
for line in open(keys):
    if line.startswith(alias + "="):
        key = line.strip().split("=", 1)[1]
if not key:
    sys.exit(f"no key for '{alias}' in {keys}")
if harness == "antigravity":
    path = os.path.join(".agents", "mcp_config.json") if "--workspace" in a else os.path.expanduser("~/.gemini/config/mcp_config.json")
    entry = {"serverUrl": "https://scio.md/mcp", "headers": {"Authorization": f"Bearer {key}", "X-Scio-Harness": "antigravity"}}
else:
    sys.exit(f"unknown harness {harness}; supported: antigravity")
os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
cfg = {}
if os.path.exists(path):
    try:
        cfg = json.load(open(path))
    except ValueError:
        cfg = {}
cfg.setdefault("mcpServers", {})["scio"] = entry
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(cfg, f, indent=2)
os.chmod(path, 0o600)
print(f"wrote {path} (mode 600) with the scio server for agent '{alias}'")
