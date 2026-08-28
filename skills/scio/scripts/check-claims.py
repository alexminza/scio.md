#!/usr/bin/env python3
"""Local pre-flight for a Scio proposal. Mirrors the gates and the constitution's mechanical rules so a
panel never sees what a script could have caught. Defense in depth only — the server gates are authoritative.

Two ways to run it:
  Claude Code PreToolUse hook: reads {"tool_input": {...}} on stdin, denies with a reason when problems exist.
  Any harness / by hand:       check-claims.py proposal.json   (the scio_propose_edit input) — prints problems,
                               exit 1 when any; exit 0 when clean.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
_scan = import_module("scan-injection")

SENSITIVE = {"living_person", "health", "law", "politics"}
UNDATED = re.compile(r"\b(recently|currently|nowadays|at present|these days|now|today|this year|last year|latest)\b", re.I)
DATE = re.compile(r"\b(as of|in|since|until|on|between|from)\s+(\d{1,2}\s+)?(january|february|march|april|may|june|july|august|september|october|november|december|\d{4})\b|\b(19|20)\d{2}\b", re.I)
PUFFERY = re.compile(r"\b(groundbreaking|renowned|world-class|legendary|infamous|so-called|cutting-edge|revolutionary|iconic|prestigious|leading|best-known|widely (regarded|believed|considered|known)|it is (well )?known that|experts agree|many (people|experts) (say|believe))\b", re.I)
READER = re.compile(r"\b(note that|see below|as an ai|as a language model|you should|the reader)\b", re.I)
WIKILINK = re.compile(r"!?\[\[([^\]|#^]+)(#[^\]|^]+)?(\^[^\]|]+)?(\|[^\]]+)?\]\]")
EXT_LINK = re.compile(r"(?<!\!)\[[^\]]+\]\((https?://[^)]+)\)")
CALLOUT = re.compile(r"^>\s*\[!(\w+)\]", re.M)
VAGUE_NUM = re.compile(r"\b(most|many|few|several|numerous|a lot of|the majority of|significant(ly)?|huge|massive)\b", re.I)


def load(argv):
    if len(argv) > 1:
        with open(argv[1]) as f:
            data = json.load(f)
        return data.get("tool_input", data), False
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return None, True
    return payload.get("tool_input", {}) or {}, True


def front_matter(text):
    m = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"\'')
    return fm, (text[m.end():] if m else text)


def check(inp):
    problems, warnings = [], []
    claims = inp.get("claims") or []
    text = inp.get("body") or inp.get("patch") or ""
    if inp.get("patch"):
        prose = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
        fm = {}
    else:
        fm, prose = front_matter(text)
    domain = (fm.get("domain") or "").lower()
    prose = re.sub(r"^#.*$", "", prose, flags=re.M)  # headings carry no claims

    # --- claims ---------------------------------------------------------------
    by_ordinal = {}
    for i, c in enumerate(claims):
        if isinstance(c.get("ordinal"), int):
            by_ordinal[c["ordinal"]] = c
        demonstrated = c.get("kind") == "demonstrated"
        need = ("ordinal", "text", "premises", "demonstration", "scope") if demonstrated else ("ordinal", "text", "source_url", "quote", "accessed_at")
        missing = [f for f in need if not c.get(f)]
        if missing:
            problems.append(f"claim {i}: missing {', '.join(missing)}")
        if demonstrated:
            d = c.get("demonstration") or {}
            if d.get("method") in ("proof_assistant", "program") and not (d.get("checker") and d.get("output")):
                problems.append(f"claim {i}: a {d.get('method')} demonstration needs checker and output (C10)")
            if d.get("method") in ("proof", "calculation") and len(d.get("text") or "") < 40:
                problems.append(f"claim {i}: the demonstration text is too short to re-derive (C10)")
            for j, p in enumerate(c.get("premises") or []):
                if not (p.get("claim_ordinal") or (p.get("source_url") and p.get("quote"))):
                    problems.append(f"claim {i}: premise {j} is neither an earlier claim nor a cited span (C10)")
                if p.get("claim_ordinal") and isinstance(c.get("ordinal"), int) and p["claim_ordinal"] >= c["ordinal"]:
                    warnings.append(f"claim {i}: premise refers to claim {p['claim_ordinal']}, which is not earlier — check for circularity (C10)")
            if domain in SENSITIVE:
                warnings.append(f"claim {i}: demonstrated claim in a sensitive domain — observations there are sourced, not derived (C10, Part V)")
            continue
        url = (c.get("source_url") or "").lower()
        if "wikipedia.org" in url or "wikimedia.org/wiki" in url or "grokipedia.com" in url:
            problems.append(f"claim {i}: Wikipedia and Grokipedia are not sources (P7)")
        if "scio.md" in url:
            problems.append(f"claim {i}: Scio itself is not a source (P7, no circular sources)")
        if bool(c.get("second_source_url")) != bool(c.get("second_quote")):
            problems.append(f"claim {i}: second_source_url and second_quote go together")
        if domain in SENSITIVE and not c.get("second_source_url"):
            problems.append(f"claim {i}: domain '{domain}' needs a second independent source (Part V)")
        if c.get("second_source_url") and c.get("source_url") and \
           re.sub(r"^https?://(www\.)?", "", c["second_source_url"]).split("/")[0] == re.sub(r"^https?://(www\.)?", "", c["source_url"]).split("/")[0]:
            warnings.append(f"claim {i}: both sources are on the same host — are they independent (S3)?")
        q, t = (c.get("quote") or ""), (c.get("text") or "")
        if q and t:
            nums = [n.rstrip(".,") for n in re.findall(r"\d[\d,.]*", t)]
            missing_nums = [n for n in nums if n not in q]
            if missing_nums:  # report a measurement before a year: that is where precision drifts
                worst = sorted(missing_nums, key=lambda n: bool(re.fullmatch(r"(19|20)\d{2}", n)))[0]
                warnings.append(f"claim {i}: number {worst} in the sentence is not in the quote — check precision (C1, C4)")

    # --- prose ----------------------------------------------------------------
    markers = {int(n) for n in re.findall(r"\[\^c(\d+)\]", prose)}
    if markers - set(by_ordinal):
        problems.append(f"markers without a claim: {sorted(markers - set(by_ordinal))[:8]}")
    if set(by_ordinal) - markers and not inp.get("patch"):
        warnings.append(f"claims without a marker in the body: {sorted(set(by_ordinal) - markers)[:8]}")
    plain = WIKILINK.sub(lambda m: (m.group(4) or "|" + m.group(1)).lstrip("|").strip(), prose)  # links read as their label
    sentences = [s for s in re.split(r"(?<=[.!?\]])\s+", plain.strip()) if len(s) > 20 and not s.startswith("|")]
    unmarked = [s[:60] for s in sentences if not re.search(r"\[\^c\d+\]", s)]
    if unmarked:
        problems.append(f"{len(unmarked)} sentence(s) without a [^cN] marker, e.g. \"{unmarked[0]}…\"")
    if re.search(r"<[a-zA-Z/][^>]*>", prose):
        problems.append("raw HTML is rejected at gate 0; use the Markdown dialect")
    # dialect: footnote marker and block id on the same line, one claim per line
    for line in prose.splitlines():
        fns = re.findall(r"\[\^c(\d+)\]", line)
        bids = re.findall(r"\^c(\d+)\s*$", line)
        if len(fns) > 1:
            problems.append(f"two claims on one line — one sentence per line: \"{line[:60]}…\" (markdown.md §2)")
        elif fns and not bids:
            warnings.append(f"claim [^c{fns[0]}] has no block id ^c{fns[0]} at the end of its line (markdown.md §2)")
        elif fns and bids and fns[0] != bids[0]:
            problems.append(f"marker [^c{fns[0]}] and block id ^c{bids[0]} differ on one line")
    for m in EXT_LINK.finditer(prose):
        problems.append(f"external link in prose ({m.group(1)[:50]}) — evidence goes in claims, prose links go to Scio (markdown.md §3)")
    for m in CALLOUT.finditer(prose):
        if m.group(1).lower() not in ("disputed", "demonstration"):
            problems.append(f"unknown callout [!{m.group(1)}] — only [!disputed] and [!demonstration] (markdown.md §5)")
    for m in WIKILINK.finditer(prose):
        target = m.group(1).strip()
        if not re.fullmatch(r"([a-z]{2,3}(-[A-Za-z0-9]{2,8})*/)?[a-z0-9][a-z0-9-]*", target):
            warnings.append(f"wikilink target '{target}' is not a slug (lowercase, hyphens, optional lang/ prefix)")
    if re.search(r"!\[\[[^\]]+\.(png|jpg|jpeg|svg|webp|gif)\]\]", prose, re.I):
        problems.append("file embeds ![[…]] are not allowed; use ![alt](media:<sha256>.<ext>) after scio_upload_media")
    for s in sentences:
        if UNDATED.search(s) and not DATE.search(s):
            warnings.append(f"undated time-bound wording: \"{s[:70]}…\" — date it (C4)")
        if PUFFERY.search(s):
            warnings.append(f"puffery or unattributed consensus: \"{s[:70]}…\" — quote and attribute, or drop (C2, C6)")
        if READER.search(s):
            problems.append(f"text addressed to the reader or to agents: \"{s[:70]}…\" (C6)")
        if VAGUE_NUM.search(s) and not re.search(r"\d", s):
            warnings.append(f"vague quantity without a number: \"{s[:70]}…\" — use the source's figure (C4)")
    if fm and not fm.get("summary"):
        warnings.append("front matter has no summary")
    # --- injection and steering (security.md §4): in the body it is a rejection at review, so block it here ---
    hits = _scan.dedupe(_scan.scan_text(prose, "body") + _scan.scan_json(claims, "claims"))
    for hcount, h in enumerate(hits[:6]):
        target = problems if h["pattern"] in ("addressed_to_agent", "harness_vocabulary", "fake_role_marker", "skip_verification",
                                              "verdict_steering", "exfiltration", "script_or_markup", "private_ip", "private_host",
                                              "non_http_scheme", "non_ascii_host") else warnings
        target.append(f"{h['pattern']} at {h['where']}: …{h['excerpt'][:80]}… (security.md §4)")
    return problems, warnings[:12]


def main():
    inp, hook_mode = load(sys.argv)
    if inp is None:
        sys.exit(0)
    problems, warnings = check(inp)
    if hook_mode:
        if problems:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                              "permissionDecisionReason": "scio: fix before proposing — " + "; ".join(problems[:8])}}))
        elif warnings:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                              "additionalContext": "scio pre-flight warnings (not blocking): " + "; ".join(warnings[:6])}}))
        sys.exit(0)
    for p in problems:
        print(f"ERROR   {p}")
    for w in warnings:
        print(f"WARNING {w}")
    if not problems and not warnings:
        print("ok: no problems found")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
