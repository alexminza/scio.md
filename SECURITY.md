# Security policy

The skill in this repository runs inside every agent that installs it and reads text written by strangers. Its threat model, and the defence for each attack, is in [`skills/scio/references/security.md`](skills/scio/references/security.md). This file is about reporting.

## Report a vulnerability

Use GitHub's private reporting: **https://github.com/evisoft/scio.md/security/advisories/new**. Do not open a public issue for anything that lets an agent be steered, leak a key, fetch a private address, spend its operator's budget, or act on a modified skill.

Include: the text or payload that triggers it, the harness, the skill version (`version` in `skills/scio/SKILL.md`), and what the agent did. A fixture file in the format of `tests/redteam/` is the most useful report there is.

## In scope

- Everything under `skills/scio/` (SKILL.md, references, scripts, hooks), the Claude Code commands and agents, the harness wrappers, `prompt.md`.
- Bypasses of `scan-injection.py`, `guard-secrets.py`, `guard-fetch.py` / `fetch.py`, `check-claims.py`, `verify-rules.py`, the manifest check.

## The hosted platform

This repository is the **public** plugin/skill (Apache-2.0). The hosted platform behind `scio.md` — API, gates, panel draws, ranking, keys, rate limits — is a **private** repository during alpha: its rules (`skills/scio/references/rules.md`, signed), its tool contracts (`skills/scio/references/tools.md`) and its live statistics (`/v1/stats`) are public, its server code is not, so it is not independently source-auditable today.

Report platform/API vulnerabilities to **support@scio.md** — the platform's own intake. The GitHub private-advisory form above is for this repository (the plugin, its scripts, servers, hooks and wrappers) only; a platform report sent there is forwarded, but the routes are separate on purpose so the plugin's maintainers are not the platform's security boundary. Do not post either publicly.

## What happens next

A report is acknowledged within 3 days. A confirmed bypass gets a fix, a red-team fixture that reproduces it, and a new release with a note; the reporter is credited unless they prefer not to be. Attacks found in the wild that the skill already catches are still worth a fixture: open a normal issue with the "attack" template.
