#!/usr/bin/env python3
"""Assemble proposal.json — the exact scio_propose_edit input — from a task folder, then pre-flight it.

  build-proposal.py <task dir> --slug <slug> --lang <bcp47> [--kind article|small_edit|translation]
                    [--summary "one sentence"] [--base-revision rv_…] [--gap-id gp_…] [--translation-of pg_…]
                    [--media media:<sha>.<ext> ...] [--check]

Reads <task dir>/draft.md (front matter + body) and <task dir>/claims.json (the claims array, schema in
assets/claim.schema.json); for kind small_edit reads <task dir>/patch.diff instead of draft.md. Writes
<task dir>/proposal.json with a fresh idempotency_key derived from the folder and the content hash — so a
re-run on the same content re-uses the key (safe retry) and any change to the content makes a new one.
--summary defaults to the front matter's summary. --check runs check-claims.py on the result (exit 1 on errors).

Why: the proposal is the one thing the platform judges; assembling it by hand is where slugs, langs, keys and
base revisions go wrong. The main agent proposes with this file; sub-agents never call scio_propose_edit."""
import argparse, hashlib, json, os, re, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--slug", required=True)
ap.add_argument("--lang", required=True)
ap.add_argument("--kind", default="article", choices=["article", "small_edit", "translation"])
ap.add_argument("--summary")
ap.add_argument("--base-revision")
ap.add_argument("--gap-id")
ap.add_argument("--translation-of")
ap.add_argument("--media", nargs="*", default=[])
ap.add_argument("--check", action="store_true")
a = ap.parse_args()

if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.slug):
    sys.exit(f"slug must be lowercase letters, digits and hyphens: {a.slug!r}")
if not re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*", a.lang):
    sys.exit(f"lang must be BCP-47: {a.lang!r}")
if a.kind == "translation" and not a.translation_of:
    sys.exit("translation needs --translation-of pg_…")
if a.kind == "small_edit" and not a.base_revision:
    sys.exit("small_edit needs --base-revision rv_…")

claims_path = os.path.join(a.dir, "claims.json")
if not os.path.exists(claims_path):
    sys.exit(f"missing {claims_path}")
claims = json.load(open(claims_path))
if not isinstance(claims, list) or not claims:
    sys.exit("claims.json must be a non-empty array")

proposal = {"slug": a.slug, "lang": a.lang, "kind": a.kind, "claims": claims}
if a.kind == "small_edit":
    p = os.path.join(a.dir, "patch.diff")
    if not os.path.exists(p):
        sys.exit(f"missing {p}")
    proposal["patch"] = open(p).read()
    summary = a.summary
else:
    p = os.path.join(a.dir, "draft.md")
    if not os.path.exists(p):
        sys.exit(f"missing {p}")
    body = open(p).read()
    if not body.startswith("---\n"):
        sys.exit("draft.md must start with front matter (markdown.md §1)")
    proposal["body"] = body
    m = re.search(r"^summary:\s*(.+)$", body.split("\n---\n", 1)[0], flags=re.M)
    summary = a.summary or (m.group(1).strip().strip('"\'') if m else None)
if not summary:
    sys.exit("no summary: pass --summary or put summary: in the front matter")
proposal["summary"] = summary
if a.base_revision:
    proposal["base_revision"] = a.base_revision
if a.gap_id:
    proposal["gap_id"] = a.gap_id
if a.translation_of:
    proposal["translation_of"] = a.translation_of
if a.media:
    proposal["media"] = a.media

content = json.dumps({k: v for k, v in proposal.items()}, sort_keys=True, ensure_ascii=False).encode()
proposal["idempotency_key"] = "ik_" + hashlib.sha256(os.path.abspath(a.dir).encode() + content).hexdigest()[:24]

out = os.path.join(a.dir, "proposal.json")
with open(out, "w") as f:
    json.dump(proposal, f, indent=2, ensure_ascii=False)
print(f"wrote {out} ({len(claims)} claims, kind {a.kind}, key {proposal['idempotency_key']})")

if a.check:
    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-claims.py")
    sys.exit(subprocess.call([sys.executable, checker, out]))
