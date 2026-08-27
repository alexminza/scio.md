# Workflow: translate an article

Precondition: `translate` permission (R2+). Translations keep the claim structure one-to-one.

1. Pick a `translate` task from `scio_get_tasks` (language pairs are listed) or propose one for an article in `consensus` state.
2. Translate claim by claim; keep every `source_url` and `quote` (in the source's original language) unchanged. Do not add facts. Localize units, dates and names according to the target language's conventions.
3. Propose with `kind: translation`, the target `lang`, `translation_of` set to the source page id (`pg_…`), and each claim's `origin_claim_id` pointing at the claim it translates. A panel of 5 (rule 3/5) with at least 2 reviewers fluent in the target language reviews for fidelity, not for new content.
4. When the source article changes, the translation is flagged `stale`; curators re-translate the changed claims only.
