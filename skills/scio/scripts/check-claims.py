#!/usr/bin/env python3
"""Local pre-flight for a Scio proposal. Mirrors the gates and the constitution's mechanical rules so a
panel never sees what a script could have caught. Defense in depth only — the server gates are authoritative.

Two ways to run it:
  Claude Code PreToolUse hook: reads {"tool_input": {...}} on stdin, denies with a reason when problems exist.
  Any harness / by hand:       check-claims.py proposal.json   (the scio_propose_edit input) — prints problems,
                               exit 1 when any; exit 0 when clean.
"""
import json, re, sys

SENSITIVE = {"living_person", "health", "law", "politics"}
UNDATED = re.compile(r"\b(recently|currently|nowadays|at present|these days|now|today|this year|last year|latest)\b", re.I)
DATE = re.compile(r"\b(as of|in|since|until|on|between|from)\s+(\d{1,2}\s+)?(january|february|march|april|may|june|july|august|september|october|november|december|\d{4})\b|\b(19|20)\d{2}\b", re.I)
PUFFERY = re.compile(r"\b(groundbreaking|renowned|world-class|legendary|infamous|so-called|cutting-edge|revolutionary|iconic|prestigious|leading|best-known|widely (regarded|believed|considered|known)|it is (well )?known that|experts agree|many (people|experts) (say|believe))\b", re.I)
READER = re.compile(r"\b(note that|see below|as an ai|as a language model|you should|the reader)\b", re.I)
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
        missing = [f for f in ("ordinal", "text", "source_url", "quote", "accessed_at") if not c.get(f)]
        if missing:
            problems.append(f"claim {i}: missing {', '.join(missing)}")
        url = (c.get("source_url") or "").lower()
        if "wikipedia.org" in url or "wikimedia.org/wiki" in url:
            problems.append(f"claim {i}: Wikipedia is not a source (P7)")
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
        if isinstance(c.get("ordinal"), int):
            by_ordinal[c["ordinal"]] = c

    # --- prose ----------------------------------------------------------------
    markers = {int(n) for n in re.findall(r"\[\^c(\d+)\]", prose)}
    if markers - set(by_ordinal):
        problems.append(f"markers without a claim: {sorted(markers - set(by_ordinal))[:8]}")
    if set(by_ordinal) - markers and not inp.get("patch"):
        warnings.append(f"claims without a marker in the body: {sorted(set(by_ordinal) - markers)[:8]}")
    sentences = [s for s in re.split(r"(?<=[.!?\]])\s+", prose.strip()) if len(s) > 20 and not s.startswith("|")]
    unmarked = [s[:60] for s in sentences if not re.search(r"\[\^c\d+\]", s)]
    if unmarked:
        problems.append(f"{len(unmarked)} sentence(s) without a [^cN] marker, e.g. \"{unmarked[0]}…\"")
    if re.search(r"<[a-zA-Z/][^>]*>", prose):
        problems.append("raw HTML is rejected at gate 0; use the Markdown dialect")
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
