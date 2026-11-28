# Operational findings — building the local automation layer

**3–6 November 2026 · iamkayleb/bukay**

Everything below was found while replacing the cloud evaluation pipeline with a
local supervisor. They divide into four kinds: defects in the product that four
months of automated rounds never surfaced, defects in the new harness found by
running it, environment and credential problems, and one failure in the old
pipeline that was caused by a guard working exactly as designed.

Issue and pull request numbers are given where they exist, so each finding can
be checked rather than taken on trust.

---

## A. Product defects — found by trying to use the application

**A-01 · `POST /api/services` returned 500 on every request.** Issue #534,
fixed in #538. The route wrote `priceKobo` and `bufferMinutes` to Prisma;
neither is a column. Six files carried the same two names — route, helpers,
zod schema, the form component and three test files — all written 26 June in
one bot commit, `b6ea79f`, before the evaluation began.

The reason it survived fifteen rounds on all three lanes: `app/api/services/
route.ts` contained `prisma.service as unknown as {...}`, a type assertion that
disabled compiler checking on the create call, and every test replaced Prisma
with a mock that accepted a column which does not exist. The compiler could
have caught it; the cast silenced it. The tests could have caught it; the mock
accepted it.

**A-02 · `main` did not build.** Issue #539, fixed in #540. `app/(app)/today/
page.tsx` exported `TodayBooking`, `zonedDayRange`, `listTodaysBookings` and
`TodaySchedule` alongside its default. Next.js App Router pages may export only
a fixed set of names, so `next build` failed the Page type check.

The helpers were exported *so a test could import them* — a test reached into a
module whose exports the framework constrains. 413 tests passed. 93% of
declared files were present. The application did not compile, and no measure in
the evaluation asked whether it did.

**A-03 · A committed test file did not compile.** Fixed directly on `main`.
`__tests__/app/api/auth/auth-flow.test.ts` had two stacked `beforeEach`
headers, putting an `await` inside a non-async function. Nine end-to-end
authentication tests never ran. Identified during the evaluation, carried into
trunk by the lane promotion, and fixed by deleting one line.

**A-04 · The merchant dashboard never reads the session.** Issue #542, open.
This is the largest of them. `resolveTenant()` supports sessions — it returns
`source: "session"` when given one. Not one caller passes a session:

    app/(app)/services/services-list.tsx:20   resolveTenant({ headers })
    app/(app)/layout.tsx:19                   resolveTenant({ headers })
    app/api/services/_helpers.ts:49           resolveTenant({ headers: req.headers })

So resolution always falls through to an `x-tenant-id` header or a subdomain,
neither of which exists in ordinary use. The cookie is signed at sign-in,
`verifySession` and `readSessionTokenFromCookieHeader` both exist, and nothing
in the merchant interface reads any of it. `/calendar` answers "Unable to
determine your business" to a correctly signed-in merchant.

This is the mechanism behind the judgement that the frontend is poor. The
screens are not badly built. They are correctly built and permanently
disconnected from the thing that identifies who is looking at them.

**A-05 · The seeded tenant has no one who can sign in.** Folded into #542.
`prisma/seed.ts` gives the demo owner an email and no phone; sign-in is
phone-only; and an unrecognised number creates a *new* tenant. So the tenant
owning all the seeded data has no signable-in user, which makes every
"a merchant signs in and sees X" criterion unperformable as written.

**A-06 · Calendar and Clients were placeholders.** Issues #535 (done, #541)
and #536 (open). Both pages rendered `SectionPlaceholder` — *"Nothing here yet
— content will appear when available"* — inherited from 26 June. Rounds 4 and
5 specified both screens and both scored as delivered, because the conformance
measure asked whether a file existed and a file did.

---

## B. Harness defects — found by running what we built

Each of these would have appeared as a silent or misleading failure during an
unattended run. All are fixed.

**B-01 · The prompt was truncated at the first newline.** `codex.CMD` is a
batch wrapper, so `cmd.exe` cut a multi-line argument down to one sentence. The
agent received *"You are implementing one GitHub issue in this repository,
unattended"* and nothing else, went looking for the issue on GitHub, hit the
sandbox's network block, and correctly refused to invent requirements. Fixed by
passing the prompt on stdin.

The probe had passed because its prompt is a single line. A test that does not
resemble the real thing passes for the wrong reason.

**B-02 · The agent could not commit its own work.** A git worktree keeps its
index under the *main* repository's `.git/worktrees/<id>/`, outside the
sandbox's writable roots, so `git add` failed with permission denied. The agent
produced twelve correct files and could not save one. Fixed by having the
harness commit, which is where bookkeeping belongs anyway.

**B-03 · Cleanup deleted uncommitted work.** Following B-02, the harness
removed the worktree and destroyed twelve files and 18,730 tokens of work.
Fixed: a worktree with uncommitted changes is now kept, with a log line saying
where it is.

**B-04 · Build caches were committed.** `git add -A` swept `.pnpm-store/v11/
index.db` into PR #541, because `pnpm install` writes a local store into a
fresh worktree. Fixed with pathspec exclusions, and anything excluded is now
printed rather than silently dropped.

**B-05 · The probe matched its own question.** It asked the agent to reply
`PROBE_OK` and then searched the output for `PROBE_OK`. Codex echoes the prompt
in its transcript, so a dead agent — rejecting the model with a 400 — was
reported as working. Fixed: the prompt now *describes* the token rather than
spelling it, so a match can only have come from the model.

Same shape as A-01's mock: a check that cannot fail for the reason it exists.

**B-06 · The lock asked how old a file was, not whether a process was alive.**
A restart kills the supervisor without running its cleanup, leaving a lock with
a recent timestamp and a dead process behind it. The next logon refused to
start for up to six hours. Fixed with a real liveness check.

**B-07 · A failed round recorded no diagnosis.** The supervisor logged
`work.py`'s stdout and ignored stderr. The first unattended failure, 20:52 on 5
November, left one line and no cause. Fixed: stderr is captured and logged.

**B-08 · Recovery was invisible.** Only the last line of prerun was logged, and
recovery explains itself on the lines before the verdict — so a recovered round
looked identical to an idle one. Fixed.

**B-09 · `doctor` checked the wrong help page.** It validated `codex exec`'s
flags against `codex --help`, which lists only subcommands, so a correct flag
appeared missing and a wrong one appeared fine. Fixed by declaring the help
command per adapter.

**B-10 · The formatter was left to the agent.** `prettier --check` is a CI
gate; an agent that forgets it fails the build for a reason unrelated to
whether its change is correct. Fixed: the harness formats before committing.

---

## C. Environment and credentials

**C-01 · Cursor's Windows binary is `agent.ps1`.** Not `cursor-agent`, not an
executable, and not on Git Bash's PATH. A PowerShell script cannot be run by
`subprocess` the way a `.CMD` can; it must be handed to PowerShell explicitly.

**C-02 · The Codex CLI was 28 versions stale.** 0.138.0, defaulting to a model
(`gpt-5.5`) that a ChatGPT Plus plan does not serve over the CLI login path.
Every model name in `config/model_registry.json` — last updated 7 February —
was also dead. Updating to 0.166.0 fixed it; its default is now `gpt-6.1-sol`.

**C-03 · Claude's OAuth token expired mid-session**, and Cursor's cached login
was absent until `agent login` ran. Both presented as broken invocations rather
than as credential problems until the probe learned to say so.

**C-04 · Cursor's "flakiness" was cold-start authentication.** Three early runs
gave three different results — pass, hang, connection reset — all taken while
authentication was being set up. Ten consecutive runs afterwards were clean,
with times falling from 18.5s to 9.4s. The conclusion drawn from three
observations was wrong and reversed by measuring properly.

**C-05 · The cloud pipeline never ran on this account's entitlement.** CI wrote
a `CODEX_AUTH_JSON` secret to `~/.codex/auth.json` — a credential belonging to
some other account. "We ran Codex for fifteen rounds" meant "a secret ran Codex
for fifteen rounds", and nothing ever checked whose.

**C-06 · A scheduled task does not inherit a shell's exports.** `BUKAY_REPO_DIR`
set with `export` in Git Bash is invisible to Task Scheduler; it must be a
Windows user variable. This is the most likely cause of an unattended night
that produces nothing.

**C-07 · Task Scheduler defaults hostile to a laptop.** *"Start the task only
if the computer is on AC power"* is ticked by default, and its child *"Stop if
the computer switches to battery power"* stays set even when greyed out, and
cannot be cleared without an elevated shell.

---

## D. The old pipeline

**D-01 · A correct guard became the bug.** `eval-lane-base-guard.yml` fires on
`pull_request_target` for any branch named `claude/`, `codex/` or `cursor/` and
rewrites the pull request's base to `eval/<agent>`. Its own header explains
why it exists:

> Four components, four separate bugs, each found only after a PR landed on the
> wrong branch. This closes the class.

It did close the class. Then `main` became the trunk and the premise beneath it
— *an agent branch belongs to an eval lane* — stopped being true. The guard
carried on enforcing it, rewriting PR #541 from `main` to `eval/codex` and
turning a nine-file change into a hundred-file conflict.

This is a different failure from the others. A-01 and A-04 never worked. This
worked correctly, and kept working after it should have stopped.

**D-02 · Thirty-one workflows were still live**, including the belt dispatcher,
the keepalive loop, issue intake and the optimizer — all watching the same
issues the new supervisor works, and all holding metered API keys. Now
disabled; CI, Gate, Coverage Guard, Lighthouse and Dependabot remain.

**D-03 · `config/model_registry.json` is nine months stale** in the Workflows
repository and still drives routing and cost decisions there. Its newest entry
is `gpt-5.5`; nothing in it resolves today.

---

## What recurs

**A check that cannot fail for the reason it exists.** A mock accepting a
column that is not there (A-01). A probe matching its own question (B-05). A
test importing from a page, forcing exports that break the build (A-02).

**A question asked because it is easy, in place of the one that matters.** How
old is this lock file, rather than is that process running (B-06). Does this
file exist, rather than does the application build (A-02) or can anyone sign in
(A-04).

**Silence as the default failure mode.** A round that failed and recorded
nothing (B-07). A recovery indistinguishable from an idle tick (B-08). A
scheduled task that does not start because of a power setting, and says
nothing (C-07).

**Work that passes every test and cannot be used.** The three lanes produced
413 passing tests, 93% declared-file conformance, and an application that did
not compile, could not create a service, and did not read its own login.

---

## Where the two approaches differ, measured

| | Cloud evaluation | Local layer |
|---|---|---|
| Duration | ~6 weeks | 4 days |
| Issues raised | 202 | 5 |
| Pull requests | 295 | 4 |
| Metered spend | $43.66 | $0 |
| Trunk builds | no | yes |
| A UI criterion performed by a person | never | twice |

The cloud pipeline's output was not wrong so much as unverifiable. Nothing in
it ever asked whether a human could use the result, so nothing in it ever
found out.

---

# Addendum — 7 to 13 November

Seven more days of running the thing. The product defects slowed; the harness
defects did not, and a new category appeared.

## E. More harness defects

**E-01 · The formatting step vanished and nothing noticed.** A later patch
rewrote the block it lived in. Its only evidence was a `formatting...` line in
the round output, so its absence looked identical to it having nothing to do.
Two pull requests merged unformatted and `main` went red. It had also been
written with `check=False`, so even when present a failing formatter would have
been silent.

**E-02 · The guard preferred a lane that does not exist.** The rule was "drain
open pull requests before opening more", which is correct for a system with a
closer lane. Phase 3 has only an opener. So one open pull request made every
round a `no_op` — four rounds of a six-round daily ceiling in one sitting, with
every component behaving exactly as written and nothing logged as a failure.

The `no_op` was honest. The round genuinely did nothing. Correct reporting is
not the same as correct behaviour.

**E-03 · A kept worktree blocked every later round on its issue.** The fix for
"never delete uncommitted work" meant `git worktree add -B` refused, because
the branch was already checked out. Forty-two seconds, exit 2, no explanation,
three nights running. One fix caused the next defect.

**E-04 · The round inherited a terminal's stdin; the probe did not.** Cursor
printed its interactive startup tip and waited for input that was never coming.
The probe passed ten times out of ten because it closed stdin. The fourth
instance of a test that does not resemble the real thing.

**E-05 · Agents have different capabilities and nothing said so.** Claude ran
with `--permission-mode acceptEdits`, which forbids command execution, while
Codex ran with `--sandbox workspace-write`, which permits it. In consecutive
rounds on the same day, Claude reported "none of the acceptance criteria are
verified" and Codex reported a passing build, seventeen tests and a real
database check. Whether a round was verified depended on which agent the
rotation happened to pick.

## F. A new category: the agent ignored an instruction

The prompt says plainly: do not commit, push, open a pull request, or merge —
the harness does all of that. Cursor opened one anyway, with its own title and
the repository's pull-request template. Two consequences followed:

- The harness's own `POST /pulls` then failed with HTTP 422, and the round died
  at the last step with the work already pushed.
- Because the agent's body carried no `Closes #547`, GitHub never linked the
  pull request to the issue. The issue stayed open and labelled, and would have
  been handed to an agent a second time.

Everything else in this log is a check that could not fail, or a premise that
expired. This is different: **the rails assumed compliance.** "Deterministic
rails, agent judgment" only holds if the rails verify rather than trust their
own instructions. The fix was not a sterner prompt — it was a harness that
looks for an existing pull request before creating one.

## G. Three layers each reported success while the system was dead

The sharpest instance of the pattern this whole log circles.

Nothing had run for a day. Investigating:

- **Task Scheduler** reported the task `Status: Running`.
- **`schtasks /run`** reported `SUCCESS: Attempted to run the scheduled task`.
- **No `python.exe` running `supervisor.py` existed at all.**

The scheduler was holding a dead instance, which is why it refused to start a
new one — and why its refusal was reported as success. A fourth layer joined in
when the diagnostic tool written to catch exactly this crashed on a cp1252
console and, before that, reported "no supervisor started line at all" because
it did not read the rotated log.

Four components, four honest answers, one dead system.

## H. The tooling built to diagnose this had the same defect

Worth recording because it is the least comfortable entry.

The patch scripts shipped during this period failed in the way everything else
in this log fails. One looked for `def die(msg` where the signature was
`def die(message`, did not match, **silently fell back to appending at the end
of the file**, and produced code that parses cleanly and raises `NameError` at
runtime — because the definition landed after `if __name__ == "__main__"`.

Another reported `could not find X — is this the current file?` when the only
thing wrong was that the patch had already been applied. Three of those in one
message read as three failures and were three successes.

A patch script whose failure mode is "quietly do the wrong thing" is the same
defect as a mock that accepts a column which does not exist. The replacement
refuses rather than guessing, and compiles the result before writing it.

## Running tally

| | Count |
|---|---|
| Product defects found by running the application | 7 |
| Harness defects found by running the harness | 21 |
| Of those, caused by a previous fix | 3 |
| Nights lost to a harness defect | 6 |
| Pull requests merged | 6 |

The models have been the reliable part. Every agent that was given a complete
prompt, a working credential and permission to run commands produced correct
work. The failures were in the plumbing around them, and a third of those were
introduced while fixing the previous one.

---

# Addendum — 16 to 28 November: the same findings, on the belt

The local layer was retired on 15 November and the work moved back to the
shared GitHub Actions belt, re-synced from upstream and extended with a
browser-run acceptance lane. Three agent rounds have run on it.

This section exists because of what the move settled. The obvious reading of
the first log was that a hand-built harness is fragile and a mature pipeline
would not be. Thirteen days on the pipeline produced the same four patterns,
in the same proportions, from entirely different code.

## I. Defects found by running the belt

**I-01 · A stale ledger stalled every round.** `.agents/issue-552-ledger.yml`
had seven tasks marked `done` with no `commit` field, because the local harness
committed each round as one commit rather than per task. Gate failed
`ledger validation` on *every branch*, since each inherits the file from the
trunk. Keepalive then waits on `gate-not-success` forever, so a correctly
created bootstrap PR sat doing nothing for a day. One malformed file, every
round after it.

**I-02 · Machine-written bookkeeping failed a formatter gate.** `prettier
--check` flagged `.agents/issue-552-ledger.yml`, a file the belt writes itself,
one per issue. CI was red for four days. `.prettierignore` already excluded
`.github/` and `prisma/migrations/`; `.agents/` had been missed.

**I-03 · A test that could never pass, merged.** `business-hours/route.test.ts`
asserted `/aria-label="\w+ closed" checked=""/`. React emits attributes in its
own order, so `checked` never sits adjacent to `aria-label`; the filter matched
nothing and reported *every day as open*. The page was correct. The test
arrived with the feature it covered, so it had never passed. Thirteen days of
red CI.

**I-04 · Post-merge verification had stopped firing.** It was requested by a
job gated on `startsWith(base.ref, 'eval/')`. When `main` became the trunk the
evaluation lanes were retired and the trigger went with them. Nothing replaced
it and nothing reported its absence, so merged agent work was no longer
verified at all. The first full round merged, closed its issue and produced no
verdict.

**I-05 · Keepalive had no concept of a merged pull request.**
`keepalive_loop.js` contained no reference to `merged`. The loop kept waking on
a PR that had already landed. Harmless only because every wake resolved to
`agent-run-skipped`.

**I-06 · The belt checked formatting and never wrote it.** The Node CI lane
runs `prettier --check`; autofix normalised Python with Ruff and Black and had
no JavaScript equivalent. An agent that forgot to format left a red build that
no later step could repair — and a PR merged red put two unformatted files in
the trunk, so every branch cut afterwards started red for a reason unrelated to
its own work.

**I-07 · CI and the developer's machine ran different runtimes.** `jsdom@31`
declares `node: "^22.22.2 || ^24.15.0 || >=26"` and pulls `undici@8.13.0`,
which cannot load on Node 20. `ci.yml` pinned 20; the machine ran 22.23.4. CI
failed with 472 tests passing, 76 files passing and 100% coverage, reporting

    TypeError: Cannot read properties of undefined (reading 'bind')
      node_modules/.pnpm/undici@8.13.0/.../interceptor/decompress.js

`package.json` declared no `engines` field, so there was nothing to compare a
runtime against. A dependency outgrowing the runner surfaced as a TypeError
inside `node_modules` rather than a version error naming the cause — and every
local run passed while CI failed, which is the worst possible arrangement for
diagnosing it. The belt's own workflows already ran Node 24; only the
project's own CI lagged.

This is the most mundane entry in either log and probably the most common
defect in real codebases: **two environments that are assumed to be the same
and are never checked.** The fix is one line of `engines`, and its value is
not the version — it is that the next mismatch fails at install, by name.

## J. The churn

Round three (issue #556, empty states) accumulated **210 commits**: 12 on the
first day, then **117 and 80** on two consecutive days, nearly all variations
of `test(#556): assert empty-region testids…`.

The loop could not stop, for two compounding reasons:

- The task counter read **0/11** throughout, because completion is recorded in
  an `agent-completion-checkpoint` comment and the counter reads the issue and
  pull request bodies. The two never meet, so the loop never concluded the work
  was done.
- Eight of twelve browser specs failed, and kept failing, because the agent's
  sign-in helper could not establish a merchant session — every attempt
  redirected to `/login`. The agent wrote more tests against a fixture that
  could not support them.

Neither is a model failure. The agent's code was sound; the work it did on
days two and three was spent against a goal it had already met and a fixture
that could not prove it.

**This is the first instance in either log of plumbing costing money rather
than time.** Everything in the first log cost nights. This cost roughly two
hundred agent invocations.

## What the second log says that the first did not

The four patterns held without modification:

| Pattern | First log | Second log |
|---|---|---|
| A check that cannot fail for the reason it exists | mock accepting a missing column; probe matching its own prompt | a regex requiring adjacency React never emits (I-03) |
| A question asked because it is easy | lock file age rather than process liveness | the task counter rather than the pull request's merged state (I-05) |
| Silence as the default failure mode | a round that failed and recorded nothing | a verification trigger that stopped firing and said nothing (I-04) |
| Work that passes every test and cannot be used | 413 passing tests, no compiling application | 472 tests, 100% coverage, a build that cannot load its own dependency (I-07) |

And one shape the first log did not contain, because a single-machine harness
has no trunk to poison:

**A red merge poisons every round after it.** Three times — the stale ledger,
the formatter gate, the unformatted trunk — one bad file reached `main` and
every branch cut afterwards failed for a reason that had nothing to do with its
own work. Each individual gate worked correctly. Nothing enforced that the
trunk stay green, so each failure was inherited rather than contained.

## The conclusion both logs support

Across six weeks of cloud evaluation, fourteen days of a local harness and
thirteen days of the re-synced belt, **the models were never the bottleneck**.
Every agent given a complete prompt, a working credential and permission to run
commands produced correct, tested work — including, on the belt, a Playwright
spec correctly tagged to the acceptance criterion it proved, written
unprompted because the convention was in its instructions.

What fails is the plumbing, and it fails in four recognisable ways. That is now
two independent systems reaching the same conclusion, which is worth more than
either reaching it alone.
