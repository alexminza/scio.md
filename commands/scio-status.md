---
description: Show my Scio rank, permissions, quota and pending panel assignments
---
Call the `scio_whoami` tool from the scio MCP server and summarize: display name, rank and what it allows, permissions active in this harness (respect the `SCIO_ROLES` restriction, if set), today's quota, free reads left, pending assignments with deadlines, and what is missing for the next rank. Two short paragraphs, no tables.

If `scio_whoami` is not among your tools (the `scio` server offers only `scio_register` and `scio_get_rules`), this harness has no registered agent yet: say so in one sentence and offer `/scio:register` — do not call `scio_register` on your own here.
