# Re-sync triage — 38 fork commits against upstream

**16 November 2026 · `iamkayleb/Workflows` vs `stranske/Workflows`**

## The gap

| | |
|---|---|
| Fork point | `7e6bf93`, **22 August 2026** |
| Upstream commits we do not have | **1,140** |
| Our commits upstream does not have | **65** (38 excluding merges) |
| Files touched by our 38 | 67 (excluding agent stubs) |
| Of those, **rewritten upstream** | **59** |

Safety tag before any reset: `pre-resync-2026-11-16`, pushed to origin.

## Verdict: reset, do not replay

Replaying 38 commits onto 1,140 commits of drift means re-applying patches to
code that no longer exists. Eight of the sixty-seven files we touched are
untouched upstream; the rest were rewritten, some repeatedly, over three months.

A merge would conflict in almost every file and resolve into a codebase that is
neither his nor ours. A replay would reintroduce August assumptions into a
November design.

So: reset `main` to `upstream/main`, then treat each of our 38 as a **claim
about a defect** and re-test that claim against the new base. What still
reproduces gets re-filed as a fresh pull request — against upstream, not just
our fork, because he has not got these fixes and several are still live.

## Dispositions

### A · Fork plumbing — must be re-applied (5)

These exist *because* this is a fork pointed at `bukay`. Upstream will never
carry them, and without them nothing syncs anywhere.

| Commit | What it does |
|---|---|
| `63939632` | Onboards `iamkayleb/bukay` and repoints consumer templates at this fork. **The load-bearing one.** |
| `e0c0aa0f` | Vendors the reusable helper layer from this fork rather than upstream |
| `58e28fd6` | Limits the canary list to repos this fork can write to |
| `8bf0b115` | Restores the full canary registry |
| `e85edadb` | Aligns autofix source pins |

Re-apply by rewriting against the new base, not by cherry-pick.

### B · Defects worth re-testing, and offering upstream (13)

Each is a claim to verify against the new base before re-filing.

| Commit | Claim |
|---|---|
| `d1ca332e` | **Verified still live.** Two `agent:*` allowlists omit Cursor — see below |
| `6d15c0a2` | Cursor not wired into the consolidated keepalive/autofix loop |
| `446e70e2` | Dispatched issues share a concurrency lane instead of getting one each |
| `d4ec99b0` | Three silent gaps in the merge → verify → follow-up loop |
| `f8973901` | The conveyor merges pull requests containing only belt bookkeeping |
| `e3550ec8` | The optimizer recursion guard counts no-op runs |
| `bc2c9c12` | Applied suggestions can turn a valid issue invalid |
| `0725f8e5` | Follow-up tasks are not bound to a concrete file, so they fail the issue contract |
| `0c31a1b7` | Follow-up issues do not inherit the agent that wrote the code |
| `082e1e7a` | `agent:auto` beats an explicit agent label on follow-ups |
| `c2d35786` | The follow-up creator does not prefer a GitHub App token |
| `9a66ba28` | The automerge opt-in labels the guarded merger reads are undeclared |
| `5d4930a3` | The auto-pilot run title omits the issue number |

`446e70e2` is worth pulling forward: per-issue concurrency lanes are the
mechanism for running more than one issue at a time, which is the throughput
constraint on the whole project.

### C · Probably superseded — check, expect to drop (6)

`42a6ca1d`, `84f9f262` (verifier model tiering — upstream's registry has moved
three months past ours), `43cbb88f` (Codex sandbox), `6adf8d46` (Codex auth
expiry check — **upstream deleted the template file entirely**), `c8187ea4`
(lint suppression), `10609fee` (ledger validator sync).

### D · Evaluation-lane artifacts — obsolete (7)

`833be49e`, `4e34b260`, `77bbdba3`, `b61e2393`, `5ff067f6`, `cb15ccf7`,
`77ae451f`.

All serve base-branch markers routing agent pull requests to `eval/<agent>`
lanes. Finding D-01 retired that premise: `main` is the trunk now, and the
guard enforcing the old premise is what turned a nine-file change into a
hundred-file conflict. Drop the lot.

### E · Data, not code — regenerate (7)

Six `corpus: grow verifier eval corpus` commits plus one stub prune. These
append realized pull-request outcomes to `config/model_eval_corpus_staging.json`.
Upstream has its own three months of outcomes. Take upstream's file and
re-append ours if the schema still matches; do not merge line-by-line.

---

## The one verified finding

`agents-capability-check.yml` gates on:

```yaml
if: contains(fromJSON('["agent:codex","agent:claude","agent:auto"]'), github.event.label.name)
```

No `agent:cursor`. It appears twice upstream — in the source workflow at line
25 and in `templates/consumer-repo/` at line 24 — so every consumer repo
inherits it.

Meanwhile upstream runs Cursor as a first-class agent: `reusable-cursor-run.yml`,
`health-cursor-auth-check.yml`, a registry entry, dedicated scripts and tests,
and ten `agents/cursor-*.md` stubs from real pull requests.

And `docs/plans/provider-agnostic-coding-agents.md` records this file as
**Done** — twice, at lines 221 and 576 — listing the three-agent trigger as
evidence of completion.

So the capability check has never fired for Cursor, on any repo, and the
document tracking the migration cites the omission as proof it finished.

This is the pattern the local-harness log keeps circling: **a check that cannot
fail for the reason it exists**, plus a record asserting a state the code does
not hold. It is worth opening upstream as its own pull request, separately from
the re-sync, because it is a one-line fix with a three-month blast radius.
