#!/usr/bin/env python3
"""Phase 3: the work phase. Replaces `round.py work`.

The sequence is now:

    python round.py prerun
    python work.py                 <- this file, instead of `round.py work`
    python round.py postrun <outcome>

`work.py` prints the outcome to pass to postrun, so you never have to guess it.

What it does, in order: read the claim, ask the guard what to do, cut a
worktree, run the agent CLI, then check whether anything actually landed on
disk before opening a pull request.

That last step is the point. In the evaluation the pipeline marked tasks
complete in thirteen seconds with no implementing commit, three times, on two
lanes. An agent's account of what it did is not evidence. `git log` is. If the
agent produces no commit, this returns `no_op` and opens nothing — a round that
did nothing should look like a round that did nothing.

    python work.py doctor          probe the agent CLIs, spend nothing
    python work.py --dry-run       everything except running the agent
    python work.py                 a real round
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SENTINEL = HERE / "sentinel.json"
GUARD = HERE / "guard.py"

REPO = os.environ.get("BUKAY_REPO", "iamkayleb/bukay")
BASE_BRANCH = os.environ.get("BUKAY_BASE", "main")

# Short path on purpose. Windows still trips over 260 characters, and a git
# worktree plus node_modules plus a nested route directory gets there fast.
WORKTREE_ROOT = Path(os.environ.get(
    "BUKAY_WORKTREE_ROOT",
    r"C:\bw" if platform.system() == "Windows" else "/tmp/bw"))

# The clone the worktrees are cut from.
REPO_DIR = Path(os.environ.get("BUKAY_REPO_DIR", HERE.parent / "bukay"))

# Shorter than the 45-minute lease in round.py, so a hung agent is killed by
# this timeout and closed out cleanly, rather than being left for the lease to
# expire and recovery to mop up.
AGENT_TIMEOUT_SECONDS = int(os.environ.get("BUKAY_AGENT_TIMEOUT", "2100"))  # 35 min

# Opener pull requests open as drafts, matching the upstream design: the opener
# creates work in progress and the closer finishes it. The guard treats a draft
# with no push for 24 hours as a stall, which is what stops "draft" quietly
# becoming the silent failure mode it was last time.
OPEN_AS_DRAFT = os.environ.get("BUKAY_DRAFT", "1") != "0"


# ---------------------------------------------------------------------------
# Agent adapters
#
# Each agent is a command template, not a code path. Routing belongs in config
# so a new agent is a dict entry rather than a new branch in the logic.
#
# The argv lines below are a starting point, NOT verified on your machine.
# These CLIs change their flags often. Run `python work.py doctor` first: it
# finds the binary, prints its help, and tells you what to correct here. Fixing
# a wrong flag costs a minute; discovering it during a real round costs a round.
# ---------------------------------------------------------------------------

ADAPTERS: dict[str, dict] = {
    "cursor": {
        # The Windows installer names the binary `agent`, not `cursor-agent`.
        # `agent` is a generic name other products also use, so doctor prints
        # the version string and asks you to confirm it really is Cursor.
        "bins": ["cursor-agent", "cursor-agent.exe", "agent", "agent.exe", "cursor"],
        "version_hint": "cursor",
        # Non-interactive, print-and-exit, auto-approving file edits.
        # `-p` is the headless print-once-and-exit switch; `--force` auto-
        # approves tool use. Unverified against Cursor's own docs — this
        # session cannot reach cursor.com — so `work.py probe` exists to check
        # it on your machine for a few hundred tokens instead of a whole round.
        "argv": lambda b, prompt: [b, "-p", "--force", prompt],
        "help_argv": lambda b: [b, "--help"],
        "auth_env": "CURSOR_API_KEY",
        # Not on PATH on Windows for everyone. Extra places to look:
        "extra_paths": [
            r"%LOCALAPPDATA%\\cursor-agent\\agent.exe",
            r"%LOCALAPPDATA%\\cursor-agent\\cursor-agent.exe",
            r"%LOCALAPPDATA%\\cursor-agent\\bin\\agent.exe",
            r"%LOCALAPPDATA%\\Programs\\cursor-agent\\agent.exe",
            r"%USERPROFILE%\\.local\\bin\\agent.exe",
            r"%LOCALAPPDATA%\\Programs\\cursor-agent\\cursor-agent.exe",
            r"%USERPROFILE%\\.local\\bin\\cursor-agent.exe",
            r"%USERPROFILE%\\.cursor\\bin\\cursor-agent.exe",
            r"%APPDATA%\\npm\\cursor-agent.cmd",
        ],
    },
    "claude": {
        "bins": ["claude", "claude.exe"],
        "argv": lambda b, prompt: [b, "-p", prompt,
                                   "--permission-mode", "acceptEdits"],
        "help_argv": lambda b: [b, "--help"],
        "auth_env": "CLAUDE_CODE_OAUTH_TOKEN",
    },
    "codex": {
        "bins": ["codex", "codex.exe"],
        # Confirmed from `codex exec --help`: `exec` is the non-interactive
        # entry point and `--sandbox workspace-write` lets it edit the worktree
        # without reaching the rest of the machine. `--dangerously-bypass-
        # approvals-and-sandbox` would remove the sandbox entirely; we do not
        # need that, because the harness prepares the worktree before handing
        # it over, so the agent needs no network of its own.
        # The model is pinned by the harness, not inherited from whatever
        # ~/.codex/config.toml happens to hold. A ChatGPT-account login only
        # serves the Codex-tuned models, and a config naming one it cannot
        # serve fails as a 400 at request time rather than at startup.
        #   export BUKAY_CODEX_MODEL="gpt-5.5-codex"
        # Unset means "use whatever the local config says".
        # `-` means "read the instructions from stdin", per `codex exec --help`.
        "stdin_prompt": True,
        "argv": lambda b, prompt: [
            b, "exec", "--sandbox", "workspace-write", "--skip-git-repo-check",
            # `--model`, matching what the CI verifier used successfully for
            # months, rather than the `-c model="..."` config-override form.
            *(["--model", os.environ["BUKAY_CODEX_MODEL"]]
              if os.environ.get("BUKAY_CODEX_MODEL") else []),
            "-"],
        "help_argv": lambda b: [b, "exec", "--help"],
    },
}


def launch(argv: list[str]) -> list[str]:
    """Make an argv runnable.

    Cursor's Windows installer ships `agent.ps1`. A PowerShell script is not an
    executable — subprocess cannot run it the way it runs Codex's `.CMD` — so
    it has to be handed to PowerShell explicitly. Everything else is returned
    untouched.
    """
    exe = argv[0].lower()
    if exe.endswith(".ps1"):
        ps = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", *argv]
    return argv


def die(msg: str, code: int = 2):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def run(argv: list[str], cwd: Path | None = None, timeout: int = 120,
        check: bool = True) -> subprocess.CompletedProcess:
    try:
        cp = subprocess.run(argv, cwd=str(cwd) if cwd else None,
                            capture_output=True, text=True, timeout=timeout,
                            encoding="utf-8", errors="replace")
    except FileNotFoundError:
        die(f"command not found: {argv[0]}")
    except subprocess.TimeoutExpired:
        die(f"timed out after {timeout}s: {' '.join(argv[:3])}")
    if check and cp.returncode != 0:
        die(f"{' '.join(argv[:3])} failed ({cp.returncode}):\n"
            f"{(cp.stderr or cp.stdout or '').strip()[:500]}")
    return cp


def find_bin(agent: str) -> str | None:
    # An explicit path always wins. Installers put binaries in places PATH does
    # not know about, particularly on Windows, and guessing more locations is a
    # worse answer than letting you name it:
    #     export BUKAY_CURSOR_BIN="/c/Users/user/AppData/Local/.../agent.ps1"
    override = os.environ.get(f"BUKAY_{agent.upper()}_BIN")
    if override:
        p = Path(os.path.expandvars(override)).expanduser()
        if p.exists():
            return str(p)
        print(f"warning: BUKAY_{agent.upper()}_BIN points at {p}, which does "
              f"not exist — falling back to PATH", file=sys.stderr)
    for b in ADAPTERS[agent]["bins"]:
        p = shutil.which(b)
        if p:
            return p
    # Not every installer puts its binary on PATH, particularly on Windows.
    for raw in ADAPTERS[agent].get("extra_paths", []):
        p = Path(os.path.expandvars(raw))
        if p.exists():
            return str(p)
    return None


# ---------------------------------------------------------------------------
# doctor — spend nothing, learn everything
# ---------------------------------------------------------------------------

def cmd_doctor(_args) -> int:
    print("Probing the environment. This runs no agent and costs nothing.\n")

    ok = True
    for tool in ("git", "gh"):
        p = shutil.which(tool)
        print(f"  {tool:14} {p or 'NOT FOUND'}")
        ok &= bool(p)
    if shutil.which("gh"):
        cp = run(["gh", "auth", "status"], check=False, timeout=30)
        line = (cp.stdout or cp.stderr or "").strip().splitlines()
        print(f"  {'gh auth':14} {line[0][:70] if line else 'unknown'}")

    have_clone = (REPO_DIR / ".git").exists()
    have_guard = GUARD.exists()
    print(f"\n  {'repo clone':14} {REPO_DIR}  "
          f"{'exists' if have_clone else '** MISSING — set BUKAY_REPO_DIR'}")
    print(f"  {'worktree root':14} {WORKTREE_ROOT}")
    print(f"  {'guard.py':14} {GUARD}  "
          f"{'found' if have_guard else '** MISSING — put it beside work.py'}")
    ok &= have_clone and have_guard

    print("\nAgent CLIs:")
    found_any = False
    for name in ADAPTERS:
        b = find_bin(name)
        print(f"\n  {name}: {b or 'NOT FOUND'}")
        if not b:
            # More useful than another guess: show what is actually on disk in
            # the places this binary normally lives.
            seen_dirs = set()
            for raw in ADAPTERS[name].get("extra_paths", []):
                expanded = os.path.expandvars(raw)
                if "%" in expanded:        # the variable does not exist here
                    continue
                d = Path(expanded).parent
                if d in seen_dirs or not d.exists():
                    continue
                seen_dirs.add(d)
                entries = sorted(x.name for x in d.iterdir())[:12]
                print(f"    {d} contains: {', '.join(entries) or '(empty)'}")
            print(f"    tried on PATH: {', '.join(ADAPTERS[name]['bins'])}")
            continue
        found_any = True
        env_name = ADAPTERS[name].get("auth_env")
        if env_name:
            state = ("set" if os.environ.get(env_name)
                     else "not set (fine if you are logged in interactively)")
            print(f"    {env_name}: {state}")
        ver = run(launch([b, "--version"]), check=False, timeout=30)
        vtext = (ver.stdout or ver.stderr or "").strip()
        print(f"    version: {vtext[:80]}")
        hint = ADAPTERS[name].get("version_hint")
        if hint and hint not in vtext.lower():
            print(f"    ** this does not mention '{hint}' — `{Path(b).name}` is a "
                  f"generic name; confirm it is really {name} before trusting it")
        help_argv = ADAPTERS[name]["help_argv"](b)
        helps = run(launch(help_argv), check=False, timeout=30)
        text = (helps.stdout or helps.stderr or "")
        sample = ADAPTERS[name]["argv"](b, "<prompt>")
        print(f"    configured invocation: {' '.join(sample[1:])}")
        missing = [f for f in sample[1:] if f.startswith("-") and f not in text]
        # The prompt placeholder and any subcommand are not flags; ignore them.
        if missing:
            print(f"    ** these flags do not appear in --help: {missing}")
            print(f"    ** correct ADAPTERS['{name}']['argv'] in this file "
                  f"before running a real round")
            ok = False
        else:
            print("    flags look present in --help")
        # Show the lines that decide the invocation, not the first 14 of
        # whatever the CLI prints. Approval and sandbox flags are what we need
        # and they are usually far down an Options section.
        KEYS = ("approv", "sandbox", "auto", "yolo", "permission", "danger",
                "non-interactive", "--print", "--cd", "skip-git")
        hits = [ln for ln in text.splitlines()
                if any(k in ln.lower() for k in KEYS) and ln.strip()]
        print(f"    --- `{' '.join([Path(help_argv[0]).name, *help_argv[1:]])}` "
              f"— lines that look relevant ---")
        if hits:
            for ln in hits[:22]:
                print(f"      {ln.strip()[:100]}")
        else:
            for ln in text.splitlines()[:16]:
                print(f"      {ln[:100]}")
        print(f"    (full help: run `{' '.join([Path(help_argv[0]).name, *help_argv[1:]])}` yourself)")

    if not found_any:
        print("\n  ** no agent CLI found on PATH at all")
    ok &= found_any

    print("\n" + ("All checks passed — safe to run a real round." if ok else
                  "Fix the items marked ** above before running a real round."))
    return 0 if ok else 1


# The token to look for must NOT appear literally in the prompt. Codex echoes
# the prompt back in its transcript, so a probe that asked for "PROBE_OK" and
# then searched the output for "PROBE_OK" found its own question and declared a
# dead agent healthy. Describing the token instead of spelling it means a match
# can only have come from the model.
PROBE_TOKEN = "PROBE" + "_OK"
PROBE_PROMPT = ("Reply with the word PROBE followed immediately by an "
                "underscore and the letters OK, with no space between them, "
                "and nothing else at all. "
                "Do not create, modify or delete any file.")


def cmd_probe(args) -> int:
    """Run each agent once on a trivial prompt, under a short timeout.

    Three answers for a few hundred tokens: the binary runs, the flags are
    accepted, and it exits without a terminal. Finding any of those out during
    a real round means blocking for the full agent timeout instead.
    """
    names = [args.agent] if args.agent else list(ADAPTERS)
    worst = 0
    for name in names:
        b = find_bin(name)
        print(f"\n  {name}: {b or 'NOT FOUND — skipping'}")
        if not b:
            continue
        try:
            worst = max(worst, _probe_one(name, b, args))
        except Exception as exc:                       # noqa: BLE001
            # One agent's mess must not abort the others. Windows in
            # particular refuses to delete a temp directory while a child
            # process still holds a handle on it.
            print(f"    ** probe raised {type(exc).__name__}: {exc}")
            worst = max(worst, 2)
    return worst


def _probe_one(name: str, b: str, args) -> int:
    import tempfile, time
    argv = launch(ADAPTERS[name]["argv"](b, PROBE_PROMPT))
    shown = [Path(argv[0]).name] + ["<prompt>" if a is PROBE_PROMPT else a
                                    for a in argv[1:]]
    print(f"    running: {' '.join(shown)}")
    # ignore_cleanup_errors: the directory is temporary and the OS reclaims it.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        subprocess.run(["git", "init", "-q"], cwd=td,
                       capture_output=True, timeout=60)
        t0 = time.time()
        try:
            use_stdin = ADAPTERS[name].get("stdin_prompt")
            cp = subprocess.run(
                argv, cwd=td, capture_output=True, text=True,
                timeout=args.timeout, encoding="utf-8", errors="replace",
                **({"input": PROBE_PROMPT} if use_stdin
                   else {"stdin": subprocess.DEVNULL}))
        except subprocess.TimeoutExpired:
            print(f"    ** HUNG — no exit within {args.timeout}s. This CLI "
                  f"likely wants a real terminal; keep it out of the rotation.")
            return 2
        dt = time.time() - t0
        out = (cp.stdout or "") + (cp.stderr or "")
        said_ok = PROBE_TOKEN in out

    print(f"    exited {cp.returncode} in {dt:.1f}s"
          f"{'  (' + PROBE_TOKEN + ' in output)' if said_ok else ''}")
    if said_ok and cp.returncode == 0:
        print("    invocation works")
        return 0
    if said_ok:
        # Answered, but the process still failed. `work.py` judges a round by
        # commits rather than exit code, so this is usable — but it means the
        # exit code carries no signal about whether a round really failed.
        print(f"    ** answered correctly but exited {cp.returncode}. Usable, "
              f"but the exit code carries no signal. Output:")
        for ln in out.strip().splitlines()[-12:]:
            print(f"       {ln[:96]}")
        return 1
    low = out.lower()
    if any(k in low for k in ("authenticat", "api key", "login", "401",
                              "unauthor", "expired")):
        print("    ** NOT AUTHENTICATED — this is a credential problem, not a "
              "wiring problem. The invocation itself reached the CLI.")
    else:
        print(f"    ** did not return {PROBE_TOKEN}. Output:")
    for ln in out.strip().splitlines()[:12]:
        print(f"       {ln[:96]}")
    return 2


# ---------------------------------------------------------------------------
# A real round
# ---------------------------------------------------------------------------

def load_claim() -> dict:
    if not SENTINEL.exists():
        die(f"no sentinel at {SENTINEL}; run `python round.py prerun` first")
    s = json.loads(SENTINEL.read_text(encoding="utf-8"))
    if s.get("phase") != "work":
        die(f"no claimed round (phase is '{s.get('phase')}'). "
            f"Run `python round.py prerun` first.")
    lease = s.get("lease_expires_at")
    if lease and datetime.fromisoformat(lease) < datetime.now():
        die("the lease on this round has expired; run `python round.py prerun` "
            "again so it can be recovered properly")
    return s


def ask_guard() -> dict:
    cp = subprocess.run([sys.executable, str(GUARD), "status"],
                        capture_output=True, text=True, timeout=120)
    if not cp.stdout.strip():
        die(f"guard produced no output: {(cp.stderr or '').strip()[:300]}")
    return json.loads(cp.stdout)


def issue(number: int) -> dict:
    cp = run(["gh", "api", f"repos/{REPO}/issues/{number}"], timeout=60)
    return json.loads(cp.stdout)


# Dedented at module level, then formatted. Doing it the other way round leaves
# the template indented and the interpolated issue body flush left, because the
# body's own newlines destroy the common prefix dedent looks for — and the
# result reads to an agent like a code block.
PROMPT_TEMPLATE = textwrap.dedent("""\
    You are implementing one GitHub issue in this repository, unattended.

    Issue #{number}: {title}

    ---
    {body}
    ---

    Rules for this run:

    - You are on branch `{branch}`, cut from `{base}`. Stay on it.
    - Dependencies are installed and the Prisma client is generated already.
      You do not need `pnpm install`, and you have no network access.
    - Read AGENTS.md and CLAUDE.md in the repository root first. They are the
      house rules and they take precedence over your habits.
    - Do not modify anything under `.github/`. That directory is operated
      separately and changes there are reverted.
    - Leave your changes in the working tree. Do NOT commit, push, open a pull
      request or merge — the harness does all of that. Your sandbox cannot
      write git's index, so `git add` will fail with a permission error. That
      is expected and is not a problem for you to solve or work around.
    - Satisfy every acceptance criterion in the issue, including the ones
      needing a real database rather than a mocked Prisma client. If one
      cannot be met, say so plainly in your final message and leave the rest
      done rather than faking it.
    - If there is genuinely nothing to change, leave the tree clean and say so.
      An empty round is a legitimate outcome; a fabricated one is not.
    - End with a short summary of what you changed and why.
    """)



def build_prompt(iss: dict, branch: str) -> str:
    return PROMPT_TEMPLATE.format(number=iss['number'], title=iss['title'],
                                  body=iss['body'], branch=branch, base=BASE_BRANCH)


def git(args: list[str], cwd: Path, check: bool = True) -> str:
    return run(["git", *args], cwd=cwd, check=check, timeout=300).stdout.strip()


def cmd_round(args) -> int:
    claim = load_claim()
    agent = claim["agent"]
    if agent not in ADAPTERS:
        die(f"no adapter for agent '{agent}'")
    if not (REPO_DIR / ".git").exists():
        die(f"no clone at {REPO_DIR}; set BUKAY_REPO_DIR or clone bukay there")

    binary = find_bin(agent)
    if not binary and not args.dry_run:
        die(f"{agent} CLI not on PATH. Run `python work.py doctor`.")

    plan = ask_guard()
    print(f"guard: {plan['lane']} — {plan['reason']}")
    if plan["lane"] != "opener":
        print(f"\nPhase 3 implements the opener lane only. "
              f"The guard chose '{plan['lane']}'.")
        print("outcome to record: no_op")
        return 1
    if not plan["actionable_issues"]:
        print("\nnothing approved for work.")
        print("outcome to record: no_op")
        return 1

    number = plan["actionable_issues"][0]
    iss = issue(number)
    branch = f"{agent}/issue-{number}"
    wt = WORKTREE_ROOT / claim["round_id"]

    print(f"issue:    #{number} {iss['title'][:60]}")
    print(f"branch:   {branch}")
    print(f"worktree: {wt}")

    # --- worktree -----------------------------------------------------------
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
    git(["fetch", "origin", BASE_BRANCH], REPO_DIR)
    git(["worktree", "add", "-B", branch, str(wt), f"origin/{BASE_BRANCH}"],
        REPO_DIR)
    base_sha = git(["rev-parse", "HEAD"], wt)
    print(f"base:     {base_sha[:10]}")

    try:
        # Deterministic setup belongs to the harness, not to the agent. A fresh
        # worktree has no node_modules, so without this the agent's first act
        # would be `pnpm install` — slow, network-dependent inside a sandbox,
        # and an opportunity to fail in a way that looks like a bad round.
        if not args.no_prepare:
            print("preparing worktree (pnpm install, prisma generate)...")
            pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
            if not pnpm:
                die("pnpm not found on PATH; install it or pass --no-prepare")
            run([pnpm, "install", "--frozen-lockfile"], cwd=wt, timeout=900,
                check=False)
            npx = shutil.which("npx") or shutil.which("npx.cmd")
            if npx:
                run([npx, "prisma", "generate"], cwd=wt, timeout=600, check=False)
            print("prepared.")

        prompt = build_prompt(iss, branch)
        if args.dry_run:
            print("\n--- dry run: the agent would receive ---")
            print(prompt)
            print("outcome to record: no_op")
            return 0

        # --- run the agent --------------------------------------------------
        argv = launch(ADAPTERS[agent]["argv"](binary, prompt))
        print(f"\nrunning {agent} (timeout {AGENT_TIMEOUT_SECONDS}s)...\n")
        use_stdin = ADAPTERS[agent].get("stdin_prompt")
        cp = subprocess.run(argv, cwd=str(wt), text=True,
                            timeout=AGENT_TIMEOUT_SECONDS,
                            encoding="utf-8", errors="replace",
                            input=prompt if use_stdin else None)
        print(f"\n{agent} exited {cp.returncode}")

        # --- commit whatever the agent left ---------------------------------
        # The agent cannot do this itself: a git worktree keeps its index under
        # the MAIN repository's .git/worktrees/<id>/, which is outside the
        # sandbox's writable roots, so `git add` fails with permission denied.
        # Committing is bookkeeping rather than judgement, so it belongs here.
        dirty = git(["status", "--porcelain"], wt, check=False)
        if dirty and not args.no_prepare:
            # Run the formatter before staging. `prettier --check` is a CI gate
            # here, and an agent that forgets it fails the build for a reason
            # that has nothing to do with whether its change is correct.
            # Deterministic, so it belongs to the harness, not the prompt.
            pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
            if pnpm:
                print("formatting...")
                run([pnpm, "format"], cwd=wt, timeout=600, check=False)
                dirty = git(["status", "--porcelain"], wt, check=False)
        if dirty:
            print(f"staging {len(dirty.splitlines())} change(s) left by {agent}")
            git(["add", "-A"], wt)
            git(["-c", "user.name=bukay-ops",
                 "-c", "user.email=ops@localhost",
                 "commit", "-m",
                 f"{iss['title'][:60]}\n\nCloses #{number}. "
                 f"Round {claim['round_id']}, agent {agent}."], wt)

        # --- ground truth ---------------------------------------------------
        # Not "did it say it was done" — did anything land on disk.
        commits = git(["rev-list", "--count", f"{base_sha}..HEAD"], wt)
        n = int(commits or "0")
        print(f"commits:  {n}")

        if n == 0:
            print("\nno commit was produced, so nothing is opened.")
            print("outcome to record: no_op")
            return 1

        files = git(["diff", "--name-only", f"{base_sha}..HEAD"], wt)
        print("files changed:")
        for f in files.splitlines()[:20]:
            print(f"  {f}")

        # --- publish --------------------------------------------------------
        git(["push", "-u", "origin", branch], wt)
        body = (f"Closes #{number}\n\n"
                f"Opened by the local {agent} opener lane, round "
                f"`{claim['round_id']}`.\n"
                f"{n} commit(s) on top of `{BASE_BRANCH}` at {base_sha[:10]}.")
        pr = run(["gh", "api", "-X", "POST", f"repos/{REPO}/pulls",
                  "-f", f"title={iss['title']}",
                  "-f", f"head={branch}",
                  "-f", f"base={BASE_BRANCH}",
                  "-f", f"body={body}",
                  "-F", f"draft={'true' if OPEN_AS_DRAFT else 'false'}"],
                 timeout=120)
        url = json.loads(pr.stdout)["html_url"]
        print(f"\npull request: {url}")
        print("outcome to record: new_issue")
        return 0

    finally:
        # Only reclaim the worktree when there is nothing left to lose. A round
        # that produced no commit may still hold hours of edits the agent could
        # not stage, and deleting those is the one unrecoverable mistake here.
        leftover = git(["status", "--porcelain"], wt, check=False) if wt.exists() else ""
        if leftover:
            print(f"keeping {wt} — it still has uncommitted changes")
        elif not args.keep_worktree:
            git(["worktree", "remove", "--force", str(wt)], REPO_DIR, check=False)
            print(f"cleaned up {wt}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="probe the CLIs and the environment; spends nothing")
    pp = sub.add_parser("probe", help="run each agent once on a trivial prompt (cheap, real)")
    pp.add_argument("--agent", help="just this one")
    pp.add_argument("--timeout", type=int, default=90, help="seconds before calling it hung")
    ap.add_argument("--dry-run", action="store_true",
                    help="do everything except run the agent")
    ap.add_argument("--no-prepare", action="store_true",
                    help="skip pnpm install / prisma generate in the worktree")
    ap.add_argument("--keep-worktree", action="store_true",
                    help="leave the worktree in place for inspection")
    args = ap.parse_args()
    if args.cmd == "doctor":
        return cmd_doctor(args)
    if args.cmd == "probe":
        return cmd_probe(args)
    return cmd_round(args)


if __name__ == "__main__":
    sys.exit(main())
