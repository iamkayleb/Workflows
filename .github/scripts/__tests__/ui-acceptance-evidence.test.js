'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const SCRIPT = path.resolve(__dirname, '..', 'ui_acceptance_evidence.js');

function run({ report, specCount = 1, runExit = 0 }) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'uiacc-'));
  const reportPath = path.join(dir, 'playwright.json');
  const outPath = path.join(dir, 'ui-acceptance.json');
  if (report !== undefined) {
    fs.writeFileSync(reportPath, typeof report === 'string' ? report : JSON.stringify(report));
  }
  execFileSync(process.execPath, [
    SCRIPT,
    '--report', reportPath,
    '--out', outPath,
    '--spec-count', String(specCount),
    '--base-url', 'http://localhost:3000',
    '--run-exit', String(runExit),
    '--run-url', 'https://example.invalid/run/1',
    '--commit', 'abc1234',
  ]);
  return JSON.parse(fs.readFileSync(outPath, 'utf8'));
}

/** A Playwright-shaped report. `tests` is [title, status] pairs. */
function reportOf(tests, file = 'e2e/booking.spec.ts') {
  return {
    suites: [
      {
        title: file,
        specs: tests.map(([title, status]) => ({
          file,
          title,
          tests: [{ results: [{ status }] }],
        })),
        suites: [],
      },
    ],
  };
}

test('a clean run is reported as passed with its tally', () => {
  const d = run({ report: reportOf([['[AC-1] slots appear', 'passed']]) });
  assert.equal(d.status, 'passed');
  assert.deepEqual(d.tests, { total: 1, passed: 1, failed: 0, skipped: 0 });
  assert.equal(d.reason, null);
});

test('a missing report is not_run, never passed', () => {
  const d = run({ report: undefined });
  assert.equal(d.status, 'not_run');
  assert.match(d.reason, /unreadable/);
  assert.equal(d.tests.total, 0);
});

test('an unparseable report is not_run, never passed', () => {
  const d = run({ report: '{ this is not json' });
  assert.equal(d.status, 'not_run');
  assert.match(d.reason, /unreadable/);
});

test('specs discovered but zero tests executed is not_run and says so', () => {
  const d = run({ report: { suites: [] }, specCount: 4 });
  assert.equal(d.status, 'not_run');
  assert.match(d.reason, /4 spec file\(s\) were discovered/);
});

test('a failing test fails the verdict and is listed', () => {
  const d = run({
    report: reportOf([
      ['[AC-1] slots appear', 'passed'],
      ['[AC-2] booking confirms', 'failed'],
    ]),
    runExit: 1,
  });
  assert.equal(d.status, 'failed');
  assert.equal(d.tests.failed, 1);
  assert.equal(d.failures.length, 1);
  assert.match(d.failures[0].title, /booking confirms/);
});

test('a criterion proven by two tests is met only if both pass', () => {
  const d = run({
    report: reportOf([
      ['[AC-3] merchant sees the week', 'passed'],
      ['[AC-3] merchant sees it after reload', 'failed'],
    ]),
    runExit: 1,
  });
  const ac3 = d.criteria.find((c) => c.id === 'AC-3');
  assert.equal(ac3.status, 'failed', 'half-proven is not met');
  assert.equal(ac3.tests.length, 2);
});

test('criteria are reported in numeric order, not lexical', () => {
  const d = run({
    report: reportOf([
      ['[AC-10] tenth', 'passed'],
      ['[AC-2] second', 'passed'],
    ]),
  });
  assert.deepEqual(d.criteria.map((c) => c.id), ['AC-2', 'AC-10']);
});

test('one test may prove several criteria', () => {
  const d = run({ report: reportOf([['[AC-4] and [AC-5] both hold', 'passed']]) });
  assert.deepEqual(d.criteria.map((c) => c.id), ['AC-4', 'AC-5']);
});

test('untagged tests are counted, so an untagged suite is visible', () => {
  // Regression guard: AC_TAG_ALL carries the global flag and `test()` on a
  // global regex advances lastIndex, so sharing one pattern made every other
  // title read as untagged. Alternating tagged/untagged catches that.
  const d = run({
    report: reportOf([
      ['[AC-1] tagged', 'passed'],
      ['plain one', 'passed'],
      ['[AC-2] tagged', 'passed'],
      ['plain two', 'passed'],
    ]),
  });
  assert.equal(d.untagged_tests, 2);
  assert.deepEqual(d.criteria.map((c) => c.id), ['AC-1', 'AC-2']);
});

test('a green tally with a non-zero runner exit is still failed', () => {
  // The runner's exit code is ground truth. If the two disagree the pessimistic
  // reading wins and the disagreement is stated, rather than being resolved
  // silently in favour of the cheerful one.
  const d = run({ report: reportOf([['[AC-1] ok', 'passed']]), runExit: 2 });
  assert.equal(d.status, 'failed');
  assert.match(d.reason, /runner exited 2/);
});

test('skipped tests do not count as passed', () => {
  const d = run({ report: reportOf([['[AC-1] skipped one', 'skipped']]) });
  assert.equal(d.tests.skipped, 1);
  assert.equal(d.tests.passed, 0);
});

test('the last retry decides a test outcome', () => {
  const report = {
    suites: [
      {
        title: 'e2e/flaky.spec.ts',
        specs: [
          {
            file: 'e2e/flaky.spec.ts',
            title: '[AC-7] retried',
            tests: [{ results: [{ status: 'failed' }, { status: 'passed' }] }],
          },
        ],
        suites: [],
      },
    ],
  };
  const d = run({ report });
  assert.equal(d.status, 'passed');
  assert.equal(d.criteria[0].status, 'passed');
});

test('nested suites are walked', () => {
  const report = {
    suites: [
      {
        title: 'outer',
        specs: [],
        suites: [
          {
            title: 'e2e/nested.spec.ts',
            specs: [
              {
                file: 'e2e/nested.spec.ts',
                title: '[AC-9] deep',
                tests: [{ results: [{ status: 'passed' }] }],
              },
            ],
            suites: [],
          },
        ],
      },
    ],
  };
  const d = run({ report });
  assert.equal(d.tests.total, 1);
  assert.deepEqual(d.criteria.map((c) => c.id), ['AC-9']);
});

test('evidence carries provenance for the verifier to cite', () => {
  const d = run({ report: reportOf([['[AC-1] ok', 'passed']]) });
  assert.equal(d.schema, 'workflows.ui-acceptance/v1');
  assert.equal(d.commit, 'abc1234');
  assert.equal(d.base_url, 'http://localhost:3000');
  assert.equal(d.run_url, 'https://example.invalid/run/1');
});
