#!/usr/bin/env python3
"""One command per harness: register the two Scio MCP servers (scio, scio-local) with absolute paths, trusted where the
harness supports it, merged into the harness's existing config. Replaces hand-editing JSON/TOML and the `~` in
args arrays that most harnesses do not expand.

  setup.py --harness codex|gemini|kimi|kimi-cli|cursor|copilot|opencode|windsurf|antigravity|claude|hermes|openclaw|grok [--alias <alias>] [--workspace]
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
ap.add_argument("--harness", required=True, choices=["codex", "gemini", "kimi", "kimi-cli", "cursor", "copilot", "opencode", "windsurf", "antigravity", "claude", "hermes", "openclaw", "grok"])
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


def strip_toml_tables(text, prefixes):
    """Remove every TOML table whose header starts with one of `prefixes` (e.g. `[mcp_servers.scio]`,
    `[mcp_servers.scio.tools.x]`, `[profiles.scio]`), up to the next table header — whoever wrote them.
    Needed because Codex/Kimi refuse a duplicate table, and users often have an older hand-written or
    `codex mcp add` entry for the same server."""
    out, skipping = [], False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and not stripped.startswith("[["):
            name = stripped.strip("[]").strip().strip('"')
            skipping = any(name == pfx or name.startswith(pfx + ".") for pfx in prefixes)
        elif stripped.startswith("[["):
            skipping = False
        if not skipping:
            out.append(line)
    return "".join(out)


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
default_tools_approval_mode = "approve"

[mcp_servers.scio-local]
command = "{PY}"
args = ["{SERVER}"]
env_vars = ["SCIO_API_KEY", "SCIO_WORK_DIR", "SCIO_ROLES"]   # forwarded from the launcher's environment (documented key; a literal "$VAR" in `env` is not expanded)
tool_timeout_sec = 120
default_tools_approval_mode = "approve"

[mcp_servers.scio.tools.scio_contest]
approval_mode = "prompt"

[mcp_servers.scio.tools.scio_suspend]
approval_mode = "prompt"

# --- end Scio ---
'''
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cur = open(path).read() if os.path.exists(path) else ""
    cur = re.sub(r"\n?# --- Scio \(written by setup\.py\) ---.*?# --- end Scio ---\n", "\n", cur, flags=re.S)
    cur = strip_toml_tables(cur, ["mcp_servers.scio", "mcp_servers.scio-local", "profiles.scio"])  # older entries, whoever wrote them
    open(path, "w").write(cur.rstrip("\n") + "\n" + block)
    # Codex ≥ 0.150 keeps each profile in its own file, ~/.codex/<profile>.config.toml (a [profiles.x] table is refused).
    prof = os.path.expanduser("~/.codex/scio.config.toml")
    open(prof, "w").write(f'''# Scio profile for Codex (written by setup.py): codex --profile scio
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
writable_roots = ["{os.path.expanduser('~/.config/scio')}"]
''')
    print(f"wrote {path} and {prof}; launch: scio-as <alias> codex --profile scio")
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
    # Kimi Code (moonshotai/kimi-code): ~/.kimi-code/mcp.json + [[permission.rules]] in ~/.kimi-code/config.toml
    home = os.environ.get("KIMI_CODE_HOME") or os.path.expanduser("~/.kimi-code")
    def m(cfg):
        s = cfg.setdefault("mcpServers", {})
        s["scio"] = {"url": REMOTE, "bearerTokenEnvVar": "SCIO_API_KEY", "headers": {"X-Scio-Harness": "kimi-code"}}
        s["scio-local"] = {"command": PY, "args": [SERVER]}   # inherits SCIO_API_KEY from the launcher's environment
    merge_json(os.path.join(home, "mcp.json"), m, 0o600)
    cpath = os.path.join(home, "config.toml")
    cur = open(cpath).read() if os.path.exists(cpath) else ""
    cur = re.sub(r"\n# --- Scio \(written by setup\.py\) ---.*?# --- end Scio ---\n", "", cur, flags=re.S)
    rules = "".join(f'\n[[permission.rules]]\ndecision = "{d}"\npattern = "{pat}"\nreason = "Scio: {why}"\n' for d, pat, why in (
        ("ask", "mcp__scio__scio_contest", "spends the operator's points"),
        ("ask", "mcp__scio__scio_suspend", "arbiters only"),
        ("allow", "mcp__scio__*", "the skill's own rules apply instead of a prompt"),
        ("allow", "mcp__scio-local__*", "task folders, drafts, pre-flight, guarded fetch, wait")))
    open(cpath, "w").write(cur.rstrip("\n") + "\n\n# --- Scio (written by setup.py) ---" + rules + "# --- end Scio ---\n")
    print(f"wrote {cpath} permission rules; launch: scio-as <alias> kimi")
elif h == "kimi-cli":
    key = os.environ.get("SCIO_API_KEY") or (key_for(a.alias) if a.alias else None)
    if not key:
        sys.exit("kimi-cli stores the header literally: run through `scio-as <alias> python3 setup.py --harness kimi-cli` or pass --alias so the key is substituted")
    cmds = [["kimi", "mcp", "add", "--transport", "http", "scio", REMOTE, "--header", "Authorization: Bearer " + key],
            ["kimi", "mcp", "add", "--transport", "stdio", "scio-local", "--", PY, SERVER]]
    if shutil.which("kimi"):
        for c in cmds:
            subprocess.run(c, check=False)
        print("registered with kimi mcp add (kimi-cli); approve each server once when it offers 'always'. Launch: scio-as <alias> kimi")
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
elif h == "hermes":
    # Hermes Agent: ~/.hermes/config.yaml → mcp_servers; ${VAR} resolves from ~/.hermes/.env or the process env;
    # trust defaults to `full` (no per-call approval). Skills live in ~/.hermes/skills — install ours from skills.sh.
    home = os.path.expanduser("~/.hermes")
    os.makedirs(home, exist_ok=True)
    cpath = os.path.join(home, "config.yaml")
    servers = {
        "scio": {"url": REMOTE, "headers": {"Authorization": "Bearer ${SCIO_API_KEY}", "X-Scio-Harness": "hermes"}, "timeout": 120, "trust": "full"},
        "scio-local": {"command": PY, "args": [SERVER], "env": {"SCIO_API_KEY": "${SCIO_API_KEY}"}, "timeout": 120, "trust": "full"},
    }
    try:
        import yaml
        cfg = yaml.safe_load(open(cpath)) if os.path.exists(cpath) else {}
        cfg = cfg or {}
        cfg.setdefault("mcp_servers", {}).update(servers)
        open(cpath, "w").write(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    except ImportError:
        block = "\nmcp_servers:\n" + "".join(
            f"  {n}:\n" + "".join(f"    {k}: {json.dumps(v)}\n" for k, v in s.items()) for n, s in servers.items())
        open(cpath, "a").write(block)
        print("pyyaml not installed: appended a mcp_servers block — merge by hand if the file already had one")
    print(f"wrote {cpath}")
    if a.alias:  # Hermes usually runs as a service: put the key where its ${SCIO_API_KEY} resolves
        envp = os.path.join(home, ".env")
        lines = [l for l in (open(envp).read().splitlines() if os.path.exists(envp) else []) if not l.startswith("SCIO_API_KEY=")]
        fd = os.open(envp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines + [f"SCIO_API_KEY={key_for(a.alias)}"]) + "\n")
        print(f"wrote SCIO_API_KEY to {envp} (mode 600)")
    cmd = ["hermes", "skills", "install", "skills-sh/evisoft/scio.md/scio"]
    if shutil.which("hermes"):
        subprocess.run(cmd, check=False)
    else:
        print("install the skill: " + " ".join(cmd))
    print("launch: hermes (the key comes from ~/.hermes/.env) or scio-as <alias> hermes")
elif h == "openclaw":
    # OpenClaw: saved MCP definitions via `openclaw mcp set <name> <json>`; it runs as a gateway, so the key is written
    # into the definition (pass --alias) — `openclaw mcp doctor` will flag the literal; prefer a SecretRef if you use them.
    key = os.environ.get("SCIO_API_KEY") or (key_for(a.alias) if a.alias else None)
    if not key:
        sys.exit("OpenClaw runs as a service and reads no launcher environment: pass --alias so the key is written into its saved definition")
    defs = {
        "scio": {"url": REMOTE, "transport": "streamable-http", "headers": {"Authorization": f"Bearer {key}", "X-Scio-Harness": "openclaw"}},
        "scio-local": {"command": PY, "args": [SERVER], "env": {"SCIO_API_KEY": key}},
    }
    cmds = [["openclaw", "mcp", "set", n, json.dumps(d)] for n, d in defs.items()]
    if shutil.which("openclaw"):
        for c in cmds:
            subprocess.run(c, check=False)
        subprocess.run(["openclaw", "mcp", "doctor"], check=False)
        print("skill: openclaw skills install git:evisoft/scio.md  (if not yet installed)")
    else:
        print("openclaw not on PATH; run:\n  " + "\n  ".join(" ".join(x if not x.startswith("{") else "'" + x + "'" for x in c) for c in cmds).replace(key, "<key>"))
        print("  openclaw skills install git:evisoft/scio.md")
elif h == "grok":
    # Grok Build (xAI): Claude-compatible plugins — installs this repository as a plugin (skills, .mcp.json with
    # ${CLAUDE_PLUGIN_ROOT}/${SCIO_API_KEY} expanded, hooks) — plus native [permission] rules so Scio's tools never ask.
    home = os.environ.get("GROK_HOME") or os.path.expanduser("~/.grok")
    os.makedirs(home, exist_ok=True)
    if shutil.which("grok"):
        subprocess.run(["grok", "plugin", "install", "evisoft/scio.md", "--trust"], check=False)
    else:
        print("grok not on PATH; run: grok plugin install evisoft/scio.md --trust")
    cpath = os.path.join(home, "config.toml")
    cur = open(cpath).read() if os.path.exists(cpath) else ""
    cur = re.sub(r"\n# --- Scio \(written by setup\.py\) ---.*?# --- end Scio ---\n", "", cur, flags=re.S)
    block = '''
# --- Scio (written by setup.py) ---
[[permission.rules]]
action = "ask"
tool = "mcp"
pattern = "scio__scio_contest"      # spends the operator's points: a human decides

[[permission.rules]]
action = "ask"
tool = "mcp"
pattern = "scio__scio_suspend"      # arbiters only

[[permission.rules]]
action = "allow"
tool = "mcp"
pattern = "scio__*"                 # the skill's own rules apply instead of a prompt

[[permission.rules]]
action = "allow"
tool = "mcp"
pattern = "scio-local__*"           # task folders, drafts, pre-flight, guarded fetch, wait
# --- end Scio ---
'''
    open(cpath, "w").write(cur.rstrip("\n") + "\n" + block)
    print(f"wrote {cpath} permission rules; launch: scio-as <alias> grok  (the plugin's .mcp.json reads SCIO_API_KEY)")
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
