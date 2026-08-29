#!/usr/bin/env python3
"""Keep a non-interactive harness run alive across the limits the harness itself imposes.

  supervise.py [--max-restarts N] [--log FILE] -- <command...>

When the *harness* stops the agent — "usage limit reached, resets at 15:00", "rate limit … try again in 20 minutes",
a 429 from the model provider — no tool inside the session can wait, because the session is over. This runs the
command, watches its output, and when it exits: (1) if the output names a reset time or delay, sleeps until then;
(2) otherwise, on a non-zero exit, backs off 1 → 2 → 4 … → 60 minutes; (3) on exit 0 with no limit seen, stops.
Then it runs the command again, so `/scio:loop` (or `codex exec`, `gemini -p`, `kimi -p`) resumes where the
server's state left it — the loop's state lives on scio.md, not in the session. Used through:
  scio-as <alias> --supervise claude -p "/scio:loop"
"""
import datetime as dt, os, re, subprocess, sys, time

LIMIT_AT = re.compile(r"reset(?:s)?\s+(?:at|@)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I)
LIMIT_IN = re.compile(r"(?:reset(?:s)?|try again|retry|available)\s+in\s+(?:about\s+)?(\d+)\s*(second|sec|minute|min|hour|hr|h|m|s)s?", re.I)
LIMIT_WORDS = re.compile(r"usage limit|rate limit|too many requests|429|quota (?:exceeded|reached)|capacity", re.I)
BACKOFF = [60, 120, 240, 480, 960, 1920, 3600]


def parse_wait(text):
    """Seconds to wait, from what the harness printed; None when nothing looks like a limit."""
    m = LIMIT_IN.search(text)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        return n * (3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1) + 30
    m = LIMIT_AT.search(text)
    if m:
        hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        now = dt.datetime.now()
        target = now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += dt.timedelta(days=1)
        return int((target - now).total_seconds()) + 60
    if LIMIT_WORDS.search(text):
        return 15 * 60
    return None


def main():
    a = sys.argv[1:]
    if "--" not in a:
        print(__doc__.strip()); sys.exit(2)
    opts, cmd = a[: a.index("--")], a[a.index("--") + 1:]
    max_restarts = int(opts[opts.index("--max-restarts") + 1]) if "--max-restarts" in opts else 10**9
    log = open(opts[opts.index("--log") + 1], "a") if "--log" in opts else None
    restarts, fails = 0, 0
    while True:
        tail = []
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in p.stdout:
            sys.stdout.write(line); sys.stdout.flush()
            if log:
                log.write(line); log.flush()
            tail.append(line)
            if len(tail) > 400:
                tail.pop(0)
        code = p.wait()
        text = "".join(tail)
        wait = parse_wait(text)
        if wait is None and code == 0:
            print("supervise: command finished without a limit; done"); return
        if wait is None:
            wait = BACKOFF[min(fails, len(BACKOFF) - 1)]; fails += 1
            why = f"exit {code}, backoff"
        else:
            fails = 0; why = "harness limit"
        restarts += 1
        if restarts > max_restarts:
            print(f"supervise: {max_restarts} restarts reached; stopping"); sys.exit(code or 1)
        until = (dt.datetime.now() + dt.timedelta(seconds=wait)).strftime("%H:%M")
        print(f"supervise: {why} — waiting {wait // 60} min (until {until}), then restart #{restarts}"); sys.stdout.flush()
        time.sleep(wait)


if __name__ == "__main__":
    main()
