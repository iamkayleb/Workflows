'use strict';

/**
 * A merged or closed pull request must stop the keepalive loop.
 *
 * Background
 * ==========
 * bukay #564 merged with its checklist reading 0/13 complete. Completion had
 * been recorded in an `agent-completion-checkpoint` comment that never reached
 * the body the counter reads (Workflows #120), so the loop kept waking against
 * a pull request that was already merged.
 *
 * It was harmless only by accident: every wake resolved to
 * `run (agent-run-skipped)`, which dispatches nothing. Had the counter ever
 * agreed, or had another branch been reached first, the loop would have
 * dispatched an agent against merged work -- spending credit and an agent's
 * round budget on a change that can no longer land anywhere.
 *
 * Before this guard, `keepalive_loop.js` contained no reference to `merged` at
 * all. The loop had no concept of a terminal pull request.
 *
 * Scope of this test
 * ==================
 * Structural, deliberately. Reaching the decision chain through
 * `evaluateKeepaliveLoop` requires stubbing the GitHub client, the API cache,
 * the PR fetch and gate-run resolution; a test built on that much scaffolding
 * tends to assert the scaffolding. This asserts the two properties that
 * actually failed: that the terminal branches exist, and that they are reached
 * before anything that can dispatch.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const SOURCE = fs.readFileSync(
  path.resolve(__dirname, '..', 'keepalive_loop.js'),
  'utf8',
);

/** The if/else chain that turns state into an action. */
function decisionChain() {
  const start = SOURCE.indexOf('A merged or closed pull request is terminal');
  assert.notEqual(
    start, -1,
    'the terminal-pull-request guard is gone; a merged PR would keep the loop alive',
  );
  const end = SOURCE.indexOf("reason = 'no-checklists'", start);
  assert.notEqual(end, -1, 'could not find the end of the decision chain');
  return SOURCE.slice(start, end);
}

test('a merged pull request stops the loop', () => {
  const chain = decisionChain();
  assert.match(chain, /pr\?\.merged === true/);
  assert.match(chain, /reason = 'pull-request-merged'/);
});

test('a closed pull request stops the loop', () => {
  const chain = decisionChain();
  assert.match(chain, /pr\?\.state === 'closed'/);
  assert.match(chain, /reason = 'pull-request-closed'/);
});

test('merged_at is honoured as well as merged', () => {
  // `merged` is absent from some webhook payload shapes while `merged_at` is
  // present. Relying on one alone leaves the loop running on the other.
  assert.match(decisionChain(), /Boolean\(pr\?\.merged_at\)/);
});

test('the terminal check precedes every branch that can dispatch', () => {
  const chain = decisionChain();
  const terminal = chain.indexOf("reason = 'pull-request-merged'");

  // Each of these can lead to an agent run, or guards one that can. All must
  // sit after the terminal check, or a merged PR can still reach them.
  for (const later of [
    'pausedByLabel',
    'humanBlocked',
    'hasDefinitiveConflict',
    'keepaliveEnabled',
  ]) {
    const at = chain.indexOf(later);
    assert.ok(
      at === -1 || at > terminal,
      `${later} is evaluated before the terminal check, so a merged pull `
      + 'request can still reach a dispatching branch',
    );
  }
});

test('the guard reads the pull request, not the task counter', () => {
  // The counter is exactly what was wrong on #564: it read 0/13 on merged
  // work. A guard that waited for it to agree would never fire.
  const chain = decisionChain();
  const terminal = chain.slice(0, chain.indexOf("reason = 'pull-request-closed'"));
  for (const counterish of ['tasksPresent', 'allComplete', 'checkboxCounts', 'tasks_total']) {
    assert.ok(
      !terminal.includes(counterish),
      `the terminal check consults ${counterish}; it must depend only on the `
      + 'pull request itself',
    );
  }
});
