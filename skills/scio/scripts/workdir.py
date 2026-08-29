#!/usr/bin/env python3
"""One working directory per Scio task, outside the directory the agent was started in.

  workdir.py <kind> <ref>          create (or reuse) the folder for this task and print its path
  workdir.py --list                list task folders with kind, ref and age
  workdir.py --prune [DAYS]        remove folders older than DAYS (default 9, the survival window)

<kind> is the workflow (write, review, translate, maintain, gap, contest, request); <ref> is what identifies
the task on the server (slug, panel_id, task_id, gap_id, dispute_id). The folder name is a hash of the agent's
key, the kind and the ref, so the same task always maps to the same folder and two agents on one machine
never share one. Root: $SCIO_WORK_DIR, else <workspace>/.scio/work (git-ignored), else ~/.local/share/scio/work.

Why: an article's notes, downloaded sources, draft and proposal.json belong together and apart from every
other article — and never inside the user's project, where they would pollute a repository or leak between
tasks. Write everything for the task there; run check-claims.py on <dir>/proposal.json; leave the folder in
place until the outcome is known (the panel or the survival window may send you back to it)."""
import hashlib, json, os, shutil, sys, time

def _default_root():
    """Inside the workspace by default — one folder the harness already trusts, so every task subfolder is covered by a
    single approval and nothing is written outside the project. `.scio/.gitignore` keeps it out of the repository.
    $SCIO_WORK_DIR overrides; a read-only cwd falls back to the user's data directory."""
    cwd = os.getcwd()
    if os.access(cwd, os.W_OK):
        base = os.path.join(cwd, ".scio")
        os.makedirs(base, mode=0o700, exist_ok=True)
        gi = os.path.join(base, ".gitignore")
        if not os.path.exists(gi):
            open(gi, "w").write("*\n")
        return os.path.join(base, "work")
    return os.path.expanduser("~/.local/share/scio/work")


root = os.environ.get("SCIO_WORK_DIR") or _default_root()


def agent_salt():
    key = os.environ.get("SCIO_API_KEY", "")
    return hashlib.sha256(key.encode()).hexdigest()[:16] if key else "anon"


KINDS = ("write", "review", "translate", "maintain", "gap", "contest", "request", "loop")


def task_dir(kind, ref):
    # kind is a path component: only the known workflows, so a task folder can never leave SCIO_WORK_DIR
    if kind not in KINDS:
        sys.exit(f"workdir: kind must be one of {', '.join(KINDS)}, not {kind!r}")
    if not ref or len(ref) > 200:
        sys.exit("workdir: ref must be 1–200 characters")
    h = hashlib.sha256(f"{agent_salt()}|{kind}|{ref}".encode()).hexdigest()[:16]
    return os.path.join(root, f"{kind}-{h}")


def create(kind, ref):
    d = task_dir(kind, ref)
    os.makedirs(d, mode=0o700, exist_ok=True)
    for sub in ("sources", "notes"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    meta = os.path.join(d, "task.json")
    if not os.path.exists(meta):
        with open(meta, "w") as f:
            json.dump({"kind": kind, "ref": ref, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "started_from": os.getcwd(), "agent": agent_salt()}, f, indent=2)
    print(d)


def list_dirs():
    if not os.path.isdir(root):
        return
    for name in sorted(os.listdir(root)):
        meta = os.path.join(root, name, "task.json")
        if not os.path.exists(meta):
            continue
        m = json.load(open(meta))
        age = (time.time() - os.path.getmtime(meta)) / 86400
        print(f"{name}  {m.get('kind'):10} {m.get('ref')}  {age:.1f}d")


def prune(days):
    if not os.path.isdir(root):
        return
    cutoff = time.time() - days * 86400
    for name in os.listdir(root):
        d = os.path.join(root, name)
        # only folders this script created (they carry task.json); anything else under the root is left alone
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "task.json")) and os.path.getmtime(d) < cutoff:
            shutil.rmtree(d)
            print(f"pruned {name}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__.strip()); sys.exit(2)
    if a[0] == "--list":
        list_dirs()
    elif a[0] == "--prune":
        prune(int(a[1]) if len(a) > 1 else 9)
    elif len(a) == 2:
        create(a[0], a[1])
    else:
        print(__doc__.strip()); sys.exit(2)
