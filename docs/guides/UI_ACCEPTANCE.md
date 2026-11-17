# UI acceptance: making interface criteria machine-checkable

> How a criterion like *"the booking page shows available slots"* stops being
> something a person has to perform, and becomes something CI answers.

## The problem this solves

The verifier that reviews a pull request is **a reader, not a runner**. Its own
prompt says so:

> Do not run test suites locally; rely on CI results for test pass/fail
> verification.

That is the right design — an independent verifier that re-runs the author's
tests is just a slower author. But it means a criterion about the interface has
never been checkable. The verifier can read the diff and infer that a component
probably renders slots; it cannot open the page and look.

In practice that left UI criteria to be performed by hand. Over one fourteen-day
evaluation, a UI criterion was performed by a person **twice**. Everything else
was scored on whether a file existed — which is how three agent lanes produced
413 passing tests, 93% declared-file conformance, and an application that did
not compile, could not create a service, and did not read its own login.

## How it works

This lane does not change the verifier's contract. CI drives a real browser
against the running application, writes `ui-acceptance.json`, and the verifier
reads that the same way it already reads unit-test results.

The link between an issue's criteria and the browser run is **the test title**.

```ts
test('[AC-2] a client sees available slots after picking a date', async ({ page }) => {
  await page.goto('/demo/book');
  await page.getByLabel('Date').fill('2026-12-01');
  await expect(page.getByTestId('slot')).not.toHaveCount(0);
});
```

Every `[AC-n]` tag found becomes a row in the evidence:

```json
{
  "schema": "workflows.ui-acceptance/v1",
  "status": "failed",
  "tests": { "total": 6, "passed": 5, "failed": 1, "skipped": 0 },
  "criteria": [
    { "id": "AC-1", "status": "passed", "spec": "e2e/booking.spec.ts", "tests": [...] },
    { "id": "AC-2", "status": "failed", "spec": "e2e/booking.spec.ts", "tests": [...] }
  ],
  "failures": [{ "spec": "e2e/booking.spec.ts", "title": "[AC-2] ...", "error": "..." }],
  "commit": "…", "run_url": "…"
}
```

The verifier can now answer *"is criterion 2 met"* by reading a row, with a run
URL to cite. No one opens a browser.

## Writing criteria that can be checked

This is the part that actually matters, and it belongs in the issue, not the
test. A criterion that names no observable is unverifiable by any reader,
human or otherwise.

| Don't | Do |
|---|---|
| The booking page shows available slots | **[AC-2]** On `/{slug}/book`, after selecting a date with business hours, at least one `[data-testid="slot"]` is visible |
| The dashboard works when signed in | **[AC-3]** A merchant signed in via the session cookie sees their business name in the app bar, not "Unable to determine your business" |
| Mobile layout is fixed | **[AC-4]** At 390×844 the booking form has no horizontal scroll and every control is at least 44px tall |

Three rules:

1. **Name the route.** A criterion that does not say where to look cannot be
   automated and usually cannot be reviewed either.
2. **Name the observable.** A `data-testid`, visible text, a computed style.
   "Looks right" is not an observable.
3. **Number it.** `AC-1`, `AC-2`, … The number is what ties the criterion to its
   spec. Without it the lane still runs, and the evidence reports
   `untagged_tests` so the gap is visible rather than silent.

## What the lane refuses to do

It will not report success for work it did not check. Three cases fail with
`status: not_run` rather than passing:

- **The spec glob matched no files.** Checked before anything expensive. A suite
  that matches nothing otherwise passes for the same reason an empty `grep`
  succeeds.
- **The application never became reachable.** The lane prints the last 40 lines
  of the app's output and stops, rather than running specs against nothing.
- **The Playwright report is missing or unparseable.**

A fourth guard: if the runner exits non-zero but records no failing test, the
verdict is `failed` and says so. When the two disagree, the pessimistic reading
wins and the disagreement is stated, rather than being resolved silently in
favour of the cheerful one.

This is deliberate, and it is the whole point. "Ran and everything passed" and
"never ran at all" produce identical output in most harnesses — which is how a
probe that searched its own prompt for the token it had just supplied reported a
dead agent as healthy for three days.

## Adopting it in a project

1. **Take the caller.** `ui-acceptance.yml` syncs from
   `templates/consumer-repo/.github/workflows/`. It is `create_only`: the build,
   start and setup commands are yours, the reusable it calls is not.

2. **Set `setup-command`.** Whatever the app needs before it can answer a
   request — migrations, a seeded tenant, fixtures. A UI lane run against an
   empty database tests the empty state and nothing else.

3. **Write specs under `e2e/`.** Tag each with the criterion it proves.

4. **Leave `required: true`.** Set it false only while the first specs are being
   written. A lane that reports without enforcing is advisory, and an advisory
   UI check is the manual check it was meant to replace.

## Cost

A UI lane installs a browser, builds the app and starts it — a few minutes per
pull request, against a manual check that in practice did not happen. Keep the
specs to acceptance criteria. This is not where a component library gets its
unit tests.
