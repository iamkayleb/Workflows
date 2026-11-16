# The local automation layer — archive

**3–15 November 2026 · retired 15 November 2026**

For two weeks `iamkayleb/bukay` was built by a local supervisor on a Windows
laptop instead of by the GitHub Actions belt in this repository. This directory
is what that attempt produced. It is kept because the failures are the useful
part: every entry in `FINDINGS.md` is a defect found by running something, with
an issue or pull request number attached so it can be checked rather than taken
on trust.

The harness itself is retired. Nothing here runs, and nothing here should be
revived. It is evidence, not a component.

## Why it was retired

It worked, and it was too slow. One agent, one issue at a time, inside an
off-hours window, on a machine that sleeps. Six of fourteen nights were lost to
a harness defect rather than to anything the agents did. The throughput ceiling
was roughly one merged pull request a day, against a project that needs tens.

The replacement is the belt in this repository, re-synced from upstream and
extended — browser-run acceptance checks and an enforced design system, so the
verification the local layer did by hand happens in CI instead.

## What is here

| Path | What it is |
|---|---|
| `FINDINGS.md` | The operational log. 7 product defects, 21 harness defects, and the four patterns they fall into. The primary document. |
| `harness/` | The supervisor, the worker, and the diagnostic tool, as they stood when the layer was retired. |
| `harness/patches/` | The incremental fixes applied while it ran. Section H of the findings is about these: the tooling written to diagnose the problem had the same defect as the problem. |
| `round-specs/` | The issue specifications actually fed to agents, in the format the harness consumed. |
| `bukay-context/` | The instruction surface the agents read — `AGENTS.md`, `CLAUDE.md`, the verification contract, and four generated prompts. |

## What did not survive

`round.py` (the sentinel state machine) and `guard.py` (the opener/closer lane
decision) were lost when the working directory holding them was cleared. Their
behaviour is described in `FINDINGS.md` sections B and E; the code is gone.

This loss is the reason this directory exists in version control rather than in
a working directory.

## The four patterns

Stated here because they outlive the harness and apply directly to the belt:

1. **A check that cannot fail for the reason it exists.** A test mock that
   accepts a database column which is not there. A probe that searches the
   output for a token its own prompt spelled out.
2. **A question asked because it is easy, in place of the one that matters.**
   How old is this lock file, rather than is that process alive. Does this file
   exist, rather than does the application build.
3. **Silence as the default failure mode.** A round that failed and recorded
   nothing. A recovery indistinguishable from an idle tick.
4. **Work that passes every test and cannot be used.** 413 passing tests, 93%
   declared-file conformance, and an application that did not compile, could
   not create a service, and did not read its own login.

The last one is why browser-run acceptance checks are being added to the belt.
Every measure the previous pipeline had was satisfied by work a person could
not use, because no measure ever asked a person to use it.
