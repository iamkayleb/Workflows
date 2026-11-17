#!/usr/bin/env python3
"""Apply to supervisor.py: record why a round failed, not just that it did.

    python log-failures.patch.py supervisor.py

Two holes, both found the first night it ran unattended:

1. `tick()` logged work.py's stdout and ignored stderr. A round that died with
   its error on stderr — which is most of them — left a log saying only "no
   outcome printed (exit 1)". The one time the log mattered, it held nothing.

2. prerun's output was logged as its last line only. Recovery of an
   interrupted round prints its explanation on earlier lines, so a recovery
   looked identical to an ordinary idle tick.

Both are the same mistake: summarising output before knowing which part of it
would turn out to matter.
"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "supervisor.py")
s = p.read_text(encoding="utf-8")

# --- 1. prerun: log every line, not just the last -------------------------
OLD_PRE = '''    pre = run([str(ROUND), "prerun"], timeout=300)
    first = (pre.stdout or pre.stderr or "").strip().splitlines()
    if pre.returncode != 0:
        log(f"idle — {first[-1] if first else 'prerun refused'}")
        return
    log(f"claimed — {first[-1] if first else ''}")'''

NEW_PRE = '''    pre = run([str(ROUND), "prerun"], timeout=300)
    lines = [l.rstrip() for l in
             ((pre.stdout or "") + (pre.stderr or "")).splitlines() if l.strip()]
    # Every line, because recovery explains itself on the lines BEFORE the
    # verdict, and a recovered round must not look like an idle one.
    for extra in lines[:-1]:
        log(f"  {extra}")
    verdict = lines[-1] if lines else "(no output)"
    if pre.returncode != 0:
        log(f"idle — {verdict}")
        return
    log(f"claimed — {verdict}")'''

# --- 2. work: keep stderr, and say so when a round dies -------------------
OLD_WORK = '''    for line in (w.stdout or "").splitlines():
        if line.strip():
            log(f"  {line.rstrip()}")

    m = OUTCOME.search(out)
    outcome = m.group(1) if m else None
    if not outcome:
        # No outcome printed means work.py died in a way it did not handle. The
        # claim is left alone on purpose: the lease will expire and the next
        # prerun will recover it properly, which is the path already tested.
        log(f"{agent}: no outcome printed (exit {w.returncode}) — leaving the "
            f"claim for lease recovery")
        record(agent, None, ok=False)
        return'''

NEW_WORK = '''    for line in (w.stdout or "").splitlines():
        if line.strip():
            log(f"  {line.rstrip()}")

    m = OUTCOME.search(out)
    outcome = m.group(1) if m else None
    if not outcome:
        # No outcome printed means work.py died in a way it did not handle. The
        # claim is left alone on purpose: the lease will expire and the next
        # prerun will recover it properly, which is the path already tested.
        #
        # Record the error itself. A round that fails at 9pm with nobody
        # watching is only useful if the morning can tell you why, and most
        # failures arrive on stderr rather than stdout.
        err = [l.rstrip() for l in (w.stderr or "").splitlines() if l.strip()]
        if err:
            log(f"{agent}: stderr from the failed round —")
            for line in err[-25:]:
                log(f"  ! {line}")
        else:
            log(f"{agent}: the failed round wrote nothing to stderr either")
        log(f"{agent}: no outcome printed (exit {w.returncode}) — leaving the "
            f"claim for lease recovery")
        record(agent, None, ok=False)
        return'''

for old, new, what in ((OLD_PRE, NEW_PRE, "prerun logging"),
                       (OLD_WORK, NEW_WORK, "work failure logging")):
    if old not in s:
        sys.exit(f"could not find {what} — is this the current supervisor.py?")
    s = s.replace(old, new)

p.write_text(s, encoding="utf-8")
print(f"patched {p}")
