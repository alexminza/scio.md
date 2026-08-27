---
description: Research and propose a Scio article or edit on a topic, as a team (researcher → drafter → refuters → checker)
argument-hint: <topic or article slug>
---
Follow the scio skill, workflow "write", for: $ARGUMENTS. First run `scio_whoami` and stop with a plain explanation if `propose` is not permitted. Then `scripts/workdir.py write <slug>` and work only in that folder.

Run it as the team in the skill's team.md, using the Workflow tool (this command is the user's opt-in): phase Research → `scio-researcher` (stop and report if Part II fails); phase Draft → `scio-writer` producing draft.md and claims.json without proposing; phase Refute → `scio-refuter` in parallel with lenses precision and weight (add harm for sensitive domains); phase Fix → `scio-writer` addresses every unsupported label; repeat Refute/Fix until no unsupported claim, at most 3 rounds; phase Check → `scripts/check-claims.py proposal.json`. Only then verify every source with `scio_verify_source` and call `scio_propose_edit` yourself, once, with a fresh idempotency key. Report the proposal id, gate results, what the refuters changed, and expected panel time — not how many agents ran.
