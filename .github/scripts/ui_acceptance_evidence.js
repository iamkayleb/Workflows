#!/usr/bin/env node
'use strict';

/**
 * Turn a Playwright JSON report into acceptance evidence a verifier can read.
 *
 * The verifier that reviews a pull request is a reader, not a runner -- its
 * prompt forbids running test suites and tells it to rely on CI results. So the
 * useful output here is not "the tests passed"; it is a per-criterion table
 * that answers "is acceptance criterion 2 met" without anyone opening a
 * browser.
 *
 * The contract is the test title. A spec that proves a criterion tags it:
 *
 *     test('[AC-2] a client sees available slots after picking a date', ...)
 *
 * Every `[AC-n]` found becomes a row in `criteria[]` with its outcome. A
 * criterion proven by more than one test is met only if every one of them
 * passed, because a criterion half-proven is not met.
 *
 * Refusing to guess
 * -----------------
 * Three things are reported as `not_run` rather than as a pass:
 *
 *   - no report file, or one that does not parse
 *   - a report containing zero tests
 *   - a run that produced no tests despite specs having been discovered
 *
 * That distinction is the whole point. "Ran and everything passed" and "never
 * ran" produce identical output in most harnesses, and a check that cannot
 * fail for the reason it exists is the defect this repository keeps finding.
 */

const fs = require('fs');

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const reportPath = arg('report');
const outPath = arg('out', 'ui-acceptance.json');
const specCount = Number(arg('spec-count', '0'));
const baseUrl = arg('base-url', '');
const runExit = Number(arg('run-exit', '1'));
const runUrl = arg('run-url', '');
const commit = arg('commit', '');

// Two patterns on purpose: `matchAll` needs the global flag, and `test()`
// on a global regex is stateful via lastIndex -- reusing one here would
// make every other title read as untagged.
const AC_TAG_ALL = /\[(AC-\d+)\]/g;
const AC_TAG_ANY = /\[AC-\d+\]/;

/** Walk Playwright's nested suite tree and yield one row per test. */
function* walk(suite, trail = []) {
  const here = suite.title ? [...trail, suite.title] : trail;
  for (const spec of suite.specs || []) {
    for (const test of spec.tests || []) {
      const results = test.results || [];
      // Playwright records a result per retry; the last one is the outcome.
      const last = results[results.length - 1] || {};
      yield {
        spec: spec.file || here[0] || 'unknown',
        title: spec.title || '(untitled)',
        status: last.status || 'unknown',
        error: (last.error && (last.error.message || last.error.value)) || null,
      };
    }
  }
  for (const child of suite.suites || []) yield* walk(child, here);
}

function emit(doc) {
  fs.writeFileSync(outPath, JSON.stringify(doc, null, 2) + '\n', 'utf8');
  return doc;
}

const base = {
  schema: 'workflows.ui-acceptance/v1',
  base_url: baseUrl,
  commit,
  run_url: runUrl,
  specs_discovered: specCount,
};

let report;
try {
  report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
} catch (err) {
  emit({
    ...base,
    status: 'not_run',
    reason: `playwright report unreadable: ${err.message}`,
    tests: { total: 0, passed: 0, failed: 0, skipped: 0 },
    criteria: [],
    failures: [],
  });
  // Unreadable evidence is a failure of the lane, not a passing run.
  process.exit(0);
}

const rows = [...walk({ suites: report.suites || [] })];

if (rows.length === 0) {
  emit({
    ...base,
    status: 'not_run',
    reason:
      specCount > 0
        ? `${specCount} spec file(s) were discovered but the run produced no tests`
        : 'no specs and no tests',
    tests: { total: 0, passed: 0, failed: 0, skipped: 0 },
    criteria: [],
    failures: [],
  });
  process.exit(0);
}

const tally = { total: rows.length, passed: 0, failed: 0, skipped: 0 };
for (const r of rows) {
  if (r.status === 'passed' || r.status === 'expected') tally.passed += 1;
  else if (r.status === 'skipped') tally.skipped += 1;
  else tally.failed += 1;
}

// One row per criterion. A criterion is met only when every test tagged with
// it passed: a criterion proven by two tests, one of which fails, is not met.
const byCriterion = new Map();
for (const r of rows) {
  const tags = [...r.title.matchAll(AC_TAG_ALL)].map((m) => m[1]);
  for (const id of tags) {
    const entry = byCriterion.get(id) || { id, spec: r.spec, tests: [], status: 'passed' };
    entry.tests.push({ title: r.title, status: r.status });
    if (!(r.status === 'passed' || r.status === 'expected')) entry.status = 'failed';
    byCriterion.set(id, entry);
  }
}

const criteria = [...byCriterion.values()].sort((a, b) =>
  Number(a.id.slice(3)) - Number(b.id.slice(3))
);

const failures = rows
  .filter((r) => !(r.status === 'passed' || r.status === 'expected' || r.status === 'skipped'))
  .map((r) => ({ spec: r.spec, title: r.title, error: r.error }));

// The runner's exit code is ground truth for "did the suite pass". The tally
// is how it passed. They are reported together so a disagreement between them
// is visible rather than resolved silently in favour of the cheerful one.
const status = tally.failed === 0 && runExit === 0 ? 'passed' : 'failed';

emit({
  ...base,
  status,
  reason:
    status === 'passed'
      ? null
      : tally.failed > 0
        ? `${tally.failed} of ${tally.total} test(s) failed`
        : `runner exited ${runExit} with no failing test recorded`,
  tests: tally,
  criteria,
  untagged_tests: rows.filter((r) => !AC_TAG_ANY.test(r.title)).length,
  failures,
});
