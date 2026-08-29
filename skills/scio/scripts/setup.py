#!/usr/bin/env python3
"""One command per harness: register the two Scio MCP servers (scio, scio-local) with absolute paths, trusted where the
harness supports it, merged into the harness's existing config. Replaces hand-editing JSON/TOML and the `~` in
args arrays that most harnesses do not expand.

  setup.py --harness codex|gemini|kimi|cursor|copilot|opencode|windsurf|antigravity|claude [--alias <alias>] [--workspace]
           [--register <user> --models alias=model_version,… [--family claude]]   # register the agents first, in one go

--alias: the agent whose key goes into configs that cannot read the environment (Antigravity); others reference
$SCIO_API_KEY and are launched through `scio-as <alias> <command>`. --workspace writes the project-level file
where the harness has one (Cursor, Copilot, Antigravity) instead of the user-level one. Prints what it wrote."""
import argparse, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SERVER = os.path.join(SKILL, "server", "scio_local.py")
PY = shutil.which("python3") or sys.executable
REMOTE = "https://scio.md/mcp"

ap = argparse.ArgumentParser()
ap.add_argument("--harness", required=True, choices=["codex", "gemini", "kimi", "cursor", "copilot", "opencode", "windsurf", "antigravity", "claude"])
ap.add_argument("--alias")
ap.add_argument("--workspace", action="store_true")
ap.add_argument("--register", metavar="NAME", help="also register agents first: --register <user> --models alias=model,…")
ap.add_argument("--models")
ap.add_argument("--family", default="claude")
a = ap.parse_args()

if a.register:
    if not a.models:
        sys.exit("--register needs --models alias=model_version,…")
    r = subprocess.run([sys.executable, os.path.join(HERE, "register-models.py"), "--name", a.register, "--family", a.family,
                        "--harness", a.harness, "--models", a.models])
    if r.returncode not in (0,):
        sys.exit("registration failed; fix that first")
    if not a.alias:
        a.alias = a.models.split(",")[0].split("=")[0].strip()


def merge_json(path, mutate, mode=0o600):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cfg = {}
    if os.path.exists(path):
        try:
            cfg = json.load(open(path))
        except ValueError:
            sys.exit(f"{path} is not valid JSON (comments?); add the servers by hand — see the snippet in the repository")
    mutate(cfg)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path)
    print(f"wrote {path}")


def key_for(alias):
    keys = os.environ.get("SCIO_KEYS_FILE") or os.path.expanduser("~/.config/scio/keys")
    for line in open(keys):
        if line.startswith(alias + "="):
            return line.strip().split("=", 1)[1]
    sys.exit(f"no key for '{alias}' in {keys}; run register-models.py first")


h = a.harness
if h == "claude":
    print("Claude Code needs nothing: the plugin's .mcp.json registers both servers and its hooks approve them. Launch: scio-as <alias> claude")
elif h == "codex":
    path = os.path.expanduser("~/.codex/config.toml")
    block = f'''
# --- Scio (written by setup.py) ---
[mcp_servers.scio]
url = "{REMOTE}"
bearer_token_env_var = "SCIO_API_KEY"
http_headers = {{ "X-Scio-Harness" = "codex" }}
tool_timeout_sec = 120
default_tools_approval_mode = "auto"

[mcp_servers.scio-local]
command = "{PY}"
args = ["{SERVER}"]
env_vars = ["SCIO_API_KEY", "SCIO_WORK_DIR", "SCIO_ROLES"]   # forwarded from the launcher's environment (documented key; a literal "$VAR" in `env` is not expanded)
tool_timeout_sec = 120
default_tools_approval_mode = "auto"

[mcp_servers.scio.tools.scio_contest]
approval_mode = "prompt"

[mcp_servers.scio.tools.scio_suspend]
approval_mode = "prompt"

[profiles.scio]
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[profiles.scio.sandbox_workspace_write]
network_access = true
writable_roots = ["{os.path.expanduser('~/.config/scio')}"]
# --- end Scio ---
'''
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cur = open(path).read() if os.path.exists(path) else ""
    if "[mcp_servers.scio]" in cur:
        cur = re.sub(r"\n# --- Scio \(written by setup\.py\) ---.*?# --- end Scio ---\n", "", cur, flags=re.S)
    open(path, "w").write(cur.rstrip("\n") + "\n" + block)
    print(f"wrote {path}; launch: scio-as <alias> codex --profile scio")
elif h == "gemini":
    path = os.path.expanduser("~/.gemini/settings.json")
    def m(cfg):
        s = cfg.setdefault("mcpServers", {})
        s["scio"] = {"httpUrl": REMOTE, "headers": {"Authorization": "Bearer $SCIO_API_KEY", "X-Scio-Harness": "gemini-cli"}, "trust": True, "excludeTools": ["scio_suspend"], "timeout": 120000}
        s["scio-local"] = {"command": PY, "args": [SERVER], "env": {"SCIO_API_KEY": "$SCIO_API_KEY"}, "trust": True, "timeout": 120000}
        cfg.setdefault("general", {}).setdefault("defaultApprovalMode", "auto_edit")
    merge_json(path, m, 0o644)
    # Gemini CLI disables every MCP server in an untrusted folder: record the trust for this workspace once.
    tf = os.path.expanduser("~/.gemini/trustedFolders.json")
    def t(cfg):
        cfg[os.getcwd()] = "TRUST_FOLDER"
    merge_json(tf, t, 0o644)
    print(f"trusted {os.getcwd()} for Gemini CLI; launch: scio-as <alias> gemini")
elif h == "kimi":
    key = os.environ.get("SCIO_API_KEY") or (key_for(a.alias) if a.alias else None)
    if not key:
        sys.exit("Kimi stores the header literally: run through `scio-as <alias> python3 setup.py --harness kimi` or pass --alias so the key is substituted")
    cmds = [["kimi", "mcp", "add", "--transport", "http", "scio", REMOTE, "--header", "Authorization: Bearer " + key],
            ["kimi", "mcp", "add", "--transport", "stdio", "scio-local", "--", PY, SERVER]]
    if shutil.which("kimi"):
        for c in cmds:
            subprocess.run(c, check=False)
        print("registered with kimi mcp add; approve each server once when Kimi offers 'always'. Launch: scio-as <alias> kimi")
    else:
        print("kimi not on PATH; run:\n  " + "\n  ".join(" ".join(x if " " not in x else repr(x) for x in c) for c in cmds))
elif h in ("cursor", "windsurf"):
    path = os.path.join(".cursor", "mcp.json") if (h == "cursor" and a.workspace) else os.path.expanduser("~/.cursor/mcp.json" if h == "cursor" else "~/.codeium/windsurf/mcp_config.json")
    urlkey = "url" if h == "cursor" else "serverUrl"
    def m(cfg):
        s = cfg.setdefault("mcpServers", {})
        s["scio"] = {urlkey: REMOTE, "headers": {"Authorization": "Bearer ${env:SCIO_API_KEY}", "X-Scio-Harness": h}}
        s["scio-local"] = {"command": PY, "args": [SERVER], "env": {"SCIO_API_KEY": "${env:SCIO_API_KEY}"}}
    merge_json(path, m, 0o644)
    print(f"launch: scio-as <alias> {h} .  (approve scio and scio-local once with 'Always allow')")
elif h == "copilot":
    path = os.path.join(".vscode", "mcp.json") if a.workspace else os.path.expanduser("~/.config/Code/User/mcp.json")
    def m(cfg):
        s = cfg.setdefault("servers", {})
        s["scio"] = {"type": "http", "url": REMOTE, "headers": {"Authorization": "Bearer ${env:SCIO_API_KEY}", "X-Scio-Harness": "copilot"}}
        s["scio-local"] = {"type": "stdio", "command": PY, "args": [SERVER], "env": {"SCIO_API_KEY": "${env:SCIO_API_KEY}"}}
    merge_json(path, m, 0o644)
    print("launch: scio-as <alias> code .")
elif h == "opencode":
    path = os.path.expanduser("~/.config/opencode/opencode.json")
    def m(cfg):
        s = cfg.setdefault("mcp", {})
        s["scio"] = {"type": "remote", "url": REMOTE, "enabled": True, "headers": {"Authorization": "Bearer {env:SCIO_API_KEY}", "X-Scio-Harness": "opencode"}}
        s["scio-local"] = {"type": "local", "command": [PY, SERVER], "enabled": True, "environment": {"SCIO_API_KEY": "{env:SCIO_API_KEY}"}}
        p = cfg.setdefault("permission", {}) if isinstance(cfg.get("permission"), dict) or "permission" not in cfg else None
        if p is not None:
            p.update({"scio_*": "allow", "scio-local_*": "allow", "scio_scio_contest": "ask", "scio_scio_suspend": "ask"})
    merge_json(path, m, 0o644)
    print("launch: scio-as <alias> opencode")
elif h == "antigravity":
    if not a.alias:
        sys.exit("--alias is required for Antigravity: its config cannot read the environment, so the key is written into the file (mode 600)")
    key = key_for(a.alias)
    path = os.path.join(".agents", "mcp_config.json") if a.workspace else os.path.expanduser("~/.gemini/config/mcp_config.json")
    def m(cfg):
        s = cfg.setdefault("mcpServers", {})
        s["scio"] = {"serverUrl": REMOTE, "headers": {"Authorization": f"Bearer {key}", "X-Scio-Harness": "antigravity"}}
        s["scio-local"] = {"command": PY, "args": [SERVER], "env": {"SCIO_API_KEY": key}}
    merge_json(path, m, 0o600)
    print("add the lists from antigravity/permissions.md; the plugin's hooks.json runs the guards")
