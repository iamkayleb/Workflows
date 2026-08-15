# LangSmith Metrics Dashboard

This file is a stable pointer, not a generated snapshot. Scheduled dashboard
runs no longer commit changing reports directly to the default branch because a
concurrent merge can reject that push after the report and issue have already
been published.

Use these authoritative live surfaces instead:

- [LangSmith Trace Coverage Dashboard issue](https://github.com/stranske/Workflows/issues/2415)
  for the latest human-readable report and source workflow-run link.
- [LangSmith Metrics Dashboard workflow](https://github.com/stranske/Workflows/actions/workflows/maint-80-langsmith-metrics-dashboard.yml)
  for retained report, JSON, diagnostics, and combined-NDJSON artifacts.
- [LangSmith Fleet Observability Contract](../contracts/langsmith-observability-contract.md)
  for the meaning of tracing, rollout, artifact, and freshness states.

The issue and report artifact are produced before publication completes. They
remain available even when a later, unrelated repository change lands on
`main`; the scheduled workflow therefore has no branch-write permission.
