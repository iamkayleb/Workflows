#!/usr/bin/env python3
"""Apply to supervisor.py: make the lock prove liveness instead of guessing.

    python lock-liveness.patch.py supervisor.py

The old lock treated any file under six hours old as a running supervisor.
A hard restart kills the process without running its cleanup, so the lock
survives with a recent timestamp and a dead process behind it — and the
supervisor started at the next logon refuses to run for up to six hours.

That is the same shape as every other failure in this project: a check that
asks an easy question (how old is this file) in place of the real one (is
that process alive). Ask the real one.
"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "supervisor.py")
s = p.read_text(encoding="utf-8")

OLD = '''def acquire_lock() -> bool:
    """One supervisor at a time.

    Task Scheduler can start a second copy after a restart while the first is
    still finishing a round, and two loops sharing one sentinel would each
    think the other's claim was stale.
    """
    try:
        if LOCK.exists():
            pid = LOCK.read_text(encoding="utf-8").strip()
            # A stale lock from a hard kill should not block forever.
            if LOCK.stat().st_mtime > time.time() - 6 * 3600:
                log(f"another supervisor appears to be running (pid {pid}); "
                    f"delete {LOCK.name} if that is wrong")
                return False
            log("found a stale lock, taking over")
        LOCK.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError as exc:                                   # noqa: BLE001
        log(f"could not take the lock: {exc}")
        return False'''

NEW = '''def pid_alive(pid: int) -> bool:
    """Is a process with this id running right now?

    Deliberately not a timestamp heuristic. A supervisor killed by a restart
    leaves a lock whose mtime says "seconds ago" and whose process is gone;
    anything that infers liveness from the file's age gets that backwards and
    blocks the next logon from starting.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace").stdout
        except (OSError, subprocess.SubprocessError):
            return True        # cannot tell — assume alive and stay out of the way
        return str(pid) in out
    try:
        os.kill(pid, 0)        # signal 0 only checks; it does not terminate
    except ProcessLookupError:
        return False
    except PermissionError:
        return True            # exists, owned by someone else
    return True


def acquire_lock() -> bool:
    """One supervisor at a time.

    Task Scheduler can start a second copy while the first is still finishing a
    round, and two loops sharing one sentinel would each treat the other's
    claim as stale. The lock records a pid; whether that pid is running is the
    only question worth asking about it.
    """
    try:
        if LOCK.exists():
            raw = LOCK.read_text(encoding="utf-8").strip()
            try:
                pid = int(raw)
            except ValueError:
                pid = -1
            if pid == os.getpid():
                return True                      # our own lock, re-entered
            if pid_alive(pid):
                log(f"another supervisor is running (pid {pid}); "
                    f"delete {LOCK.name} if that is wrong")
                return False
            log(f"found a lock from pid {raw}, which is no longer running — "
                f"taking over")
        LOCK.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError as exc:                                   # noqa: BLE001
        log(f"could not take the lock: {exc}")
        return False'''

if OLD not in s:
    sys.exit("could not find the old acquire_lock — is this the current supervisor.py?")

p.write_text(s.replace(OLD, NEW), encoding="utf-8")
print(f"patched {p}")
