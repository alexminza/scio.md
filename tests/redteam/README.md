# Red-team fixtures

Attack payloads the skill must recognise, one file per attack class of `references/security.md`. `tests/test-security.py` runs every fixture through the scanner, the proposal pre-flight and the hook guards and fails when a defence stops catching what it caught before. Add a fixture whenever a new attack is found in the wild — the fixture is the regression test.

`*.txt` — text scanned by `scan-injection.py` (expected: findings). `*.proposal.json` — `scio_propose_edit` inputs for `check-claims.py` (expected: blocked). `*.hook.json` — hook payloads for `guard-secrets.py` / `guard-fetch.py` (expected: denied). `clean.*` — benign counterparts (expected: pass).
