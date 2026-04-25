'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildMarkdownSummary,
  buildSyncRunReport,
  summarizeResults,
} = require('../sync_run_contract');

test('summarizeResults counts known statuses and buckets unknown as error', () => {
  assert.deepEqual(
    summarizeResults([
      { status: 'created_pr' },
      { status: 'existing_pr' },
      { status: 'created_pr' },
      { status: 'unexpected_status' },
    ]),
    {
      no_changes: 0,
      dry_run_changes: 0,
      existing_pr: 1,
      created_pr: 2,
      no_committed_changes: 0,
      create_pr_failed: 0,
      sync_failed: 0,
      label_failed: 0,
      error: 1,
    },
  );
});

test('buildSyncRunReport publishes the sync branch contract', () => {
  const report = buildSyncRunReport({
    generatedAt: '2026-04-25T08:00:00Z',
    targetRepos: ['stranske/Ready'],
    registeredRepos: ['stranske/Ready', 'stranske/Template'],
    templateHash: '91c0e7663c12',
    dryRun: true,
    force: false,
    run: {
      repository: 'stranske/Workflows',
      run_id: 123,
    },
    results: [
      {
        repo: 'stranske/Ready',
        status: 'dry_run_changes',
        changes_count: 7,
      },
    ],
  });

  assert.equal(report.schema, 'workflows-consumer-sync-run/v1');
  assert.equal(report.inputs.expected_branch, 'sync/workflows-91c0e7663c12');
  assert.equal(report.inputs.dry_run, true);
  assert.deepEqual(report.summary, {
    no_changes: 0,
    dry_run_changes: 1,
    existing_pr: 0,
    created_pr: 0,
    no_committed_changes: 0,
    create_pr_failed: 0,
    sync_failed: 0,
    label_failed: 0,
    error: 0,
  });
});

test('buildMarkdownSummary names the report artifact and non-zero statuses', () => {
  const markdown = buildMarkdownSummary(
    buildSyncRunReport({
      targetRepos: ['stranske/Ready'],
      templateHash: '91c0e7663c12',
      results: [{ status: 'created_pr' }, { status: 'no_changes' }],
    }),
  );

  assert.match(markdown, /workflows-consumer-sync-run\/v1/);
  assert.match(markdown, /sync\/workflows-91c0e7663c12/);
  assert.match(markdown, /\| created_pr \| 1 \|/);
  assert.match(markdown, /consumer-sync-run-report/);
});
