## What this changes

## Why (the situation that showed the need)

## Checklist
- [ ] `python3 skills/scio/scripts/test-security.py` is green (new fixture added if a defence changed)
- [ ] `python3 skills/scio/scripts/gen-manifest.py` run last; `MANIFEST.sha256` in this PR (`whoami.py` prints no WARNING)
- [ ] `skills/scio/references/tools.md` untouched, or regenerated from the platform contract
- [ ] No new network host, no new place that reads the keys file, no hand-written numbers
- [ ] `claude plugin validate .` passes
