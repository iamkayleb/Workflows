'use strict';

const REPORT_SCHEMA = 'workflows-consumer-sync-run/v1';

function summarizeResults(results) {
  const counts = {
    no_changes: 0,
    dry_run_changes: 0,
    existing_pr: 0,
    created_pr: 0,
    no_committed_changes: 0,
    create_pr_failed: 0,
    sync_failed: 0,
    label_failed: 0,
    error: 0,
  };
  for (const result of results || []) {
    const status = result.status || 'error';
    if (Object.prototype.hasOwnProperty.call(counts, status)) {
      counts[status] += 1;
    } else {
      counts.error += 1;
    }
  }
  return counts;
}

function buildSyncRunReport({
  results = [],
  targetRepos = [],
  registeredRepos = [],
  templateHash = '',
  dryRun = false,
  force = false,
  run = {},
  generatedAt = new Date().toISOString(),
} = {}) {
  return {
    schema: REPORT_SCHEMA,
    generated_at: generatedAt,
    run,
    inputs: {
      repos: targetRepos,
      registered_repos: registeredRepos,
      template_hash: templateHash,
      expected_branch: templateHash ? `sync/workflows-${templateHash}` : '',
      dry_run: Boolean(dryRun),
      force: Boolean(force),
    },
    summary: summarizeResults(results),
    results,
  };
}

function buildMarkdownSummary(report) {
  const inputs = report.inputs || {};
  const summary = report.summary || {};
  const lines = [
    '## Consumer Repo Sync Summary',
    '',
    `Schema: \`${report.schema || REPORT_SCHEMA}\``,
    `Template hash: \`${inputs.template_hash || ''}\``,
    `Expected branch: \`${inputs.expected_branch || ''}\``,
    `Processed repos: ${Array.isArray(inputs.repos) ? inputs.repos.length : 0}`,
    `Dry run: ${inputs.dry_run ? 'true' : 'false'}`,
    `Force: ${inputs.force ? 'true' : 'false'}`,
    '',
    '| Status | Count |',
    '| --- | ---: |',
  ];
  for (const [status, count] of Object.entries(summary)) {
    if (count) {
      lines.push(`| ${status} | ${count} |`);
    }
  }
  lines.push('', 'Artifact: `consumer-sync-run-report`');
  return `${lines.join('\n')}\n`;
}

module.exports = {
  REPORT_SCHEMA,
  summarizeResults,
  buildSyncRunReport,
  buildMarkdownSummary,
};
