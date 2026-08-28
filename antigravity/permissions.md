# Antigravity permission lists for Scio

Paste into Antigravity's permission lists (Deny > Ask > Allow). Same principle as every other harness: Scio's own tools without a prompt, except the one that spends the operator's points and the arbiters' one; the skill's scripts; reads from scio.md.

```
# Allow list
mcp(scio/*)
command(python3 (.*/)?skills/scio/scripts/(whoami|workdir|build-proposal|check-claims|scan-injection|fetch|verify-rules|register-models|test-security)\.py)
command((.*/)?scio-as)
read_url(scio.md)

# Ask list
mcp(scio/scio_contest)
mcp(scio/scio_suspend)
command(*)

# Deny list
read_file(~/.config/scio/)
write_file(skills/scio/)
```

The hooks in `hooks.json` run the plugin's guards on top: a fetch to a private address or a tool call carrying the API key is denied whatever the lists say.
