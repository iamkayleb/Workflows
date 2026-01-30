# System Architecture Diagram

> Comprehensive visualization of the stranske/Workflows repository architecture

## High-Level Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        stranske/Workflows (Central Hub)                       │
│                                                                              │
│   The single source of truth for all workflow automation infrastructure      │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
         ┌──────────────────┐ ┌─────────────┐ ┌──────────────────┐
         │  Reusable        │ │   Template  │ │   Shared         │
         │  Workflows       │ │   Sync      │ │   Scripts        │
         │  (called via     │ │   System    │ │   & Actions      │
         │   uses: @v1)     │ │             │ │                  │
         └────────┬─────────┘ └──────┬──────┘ └────────┬─────────┘
                  │                  │                  │
                  └─────────────────┬┴─────────────────┘
                                    │
                                    ▼
    ┌───────────────────────────────────────────────────────────────────────┐
    │                        Consumer Repositories                           │
    │  Travel-Plan-Permission │ Manager-Database │ Template │ trip-planner  │
    │  Portable-Alpha-Extension-Model │ Trend_Model_Project │ Collab-Admin  │
    └───────────────────────────────────────────────────────────────────────┘
```

## Repository Structure

```
stranske/Workflows/
│
├── .github/
│   ├── workflows/                    # 83 workflow files
│   │   ├── reusable-*.yml           # 13 reusable workflows (called by consumers)
│   │   ├── agents-*.yml             # 27 agent automation workflows
│   │   ├── health-*.yml             # 16 health/validation workflows
│   │   └── maint-*.yml              # 27 maintenance workflows
│   │
│   ├── scripts/                      # 130+ helper scripts
│   │   ├── *.js                     # JavaScript utilities (keepalive, API, etc.)
│   │   └── *.py                     # Python utilities
│   │
│   ├── actions/                      # 4 composite actions
│   │   ├── autofix/                 # Auto-format action
│   │   ├── python-ci-setup/         # Python environment setup
│   │   ├── build-pr-comment/        # PR comment helpers
│   │   └── signature-verify/        # Verification helpers
│   │
│   ├── codex/                        # Codex AI agent configuration
│   │   ├── prompts/                 # 5 prompt templates
│   │   └── AGENT_INSTRUCTIONS.md    # Base agent instructions
│   │
│   └── sync-manifest.yml             # CRITICAL: Defines what syncs to consumers
│
├── templates/
│   ├── consumer-repo/                # Template for consumer repos
│   │   ├── .github/workflows/       # Synced workflows
│   │   ├── .github/scripts/         # Synced scripts
│   │   ├── .github/codex/           # Synced prompts
│   │   └── docs/                    # Synced documentation
│   │
│   └── integration-repo/             # Integration test infrastructure
│
├── scripts/                          # Development & validation scripts
│   ├── dev_check.sh                 # Pre-commit validation
│   ├── check_branch.sh              # Comprehensive validation
│   └── *.py                         # Analysis & utility scripts
│
└── docs/                             # 100+ documentation files
    ├── keepalive/                   # Keepalive system docs
    ├── ci/                          # CI system reference
    ├── ops/                         # Operations guides
    └── guides/                      # How-to guides
```

## Workflow Categories

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WORKFLOW TAXONOMY                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  REUSABLE (13)              Called by consumer repos via uses: @v1         │
│  ├── reusable-10-ci-python.yml      Python CI (lint, test, mypy)           │
│  ├── reusable-11-ci-node.yml        Node.js CI                             │
│  ├── reusable-12-ci-docker.yml      Docker CI                              │
│  ├── reusable-16-agents.yml         Agent readiness probe                  │
│  ├── reusable-18-autofix.yml        Auto-format/lint fixes                 │
│  ├── reusable-20-pr-meta.yml        PR metadata handling                   │
│  ├── reusable-70-orchestrator-*.yml Orchestration (init + main)            │
│  ├── reusable-agents-issue-bridge   Issue → PR conversion                  │
│  ├── reusable-agents-verifier.yml   Agent verification                     │
│  ├── reusable-bot-comment-handler   Bot comment handling                   │
│  ├── reusable-codex-run.yml         Execute Codex agent                    │
│  └── reusable-pr-context.yml        PR context fetching                    │
│                                                                             │
│  AGENTS (27)                Run automation & AI agents                     │
│  ├── agents-63-issue-intake.yml     Issue processing → PR creation         │
│  ├── agents-70-orchestrator.yml     Main orchestration scheduler           │
│  ├── agents-71-belt-dispatcher      Batch work distribution                │
│  ├── agents-72-belt-worker          Parallel agent execution               │
│  ├── agents-73-belt-conveyor        Result processing                      │
│  ├── agents-80-pr-event-hub         PR event consolidation                 │
│  ├── agents-81-gate-followups       Post-gate automation                   │
│  ├── agents-keepalive-loop          Keepalive iteration                    │
│  └── agents-*                       (19 more specialized agents)           │
│                                                                             │
│  HEALTH (16)                Validation & monitoring                        │
│  ├── health-40-repo-selfcheck       Repository validation                  │
│  ├── health-42-actionlint           Workflow YAML linting                  │
│  ├── health-43-ci-signature-guard   CI integrity checks                    │
│  ├── health-68-consumer-sync-drift  Sync drift detection                   │
│  ├── health-70-validate-manifest    Manifest completeness                  │
│  └── health-72-template-sync        Template sync checks                   │
│                                                                             │
│  MAINTENANCE (27)           Sync, release & infrastructure                 │
│  ├── maint-60-release               Release automation                     │
│  ├── maint-61-floating-v1-tag       Keep @v1 current                       │
│  ├── maint-62-integration-consumer  Integration tests                      │
│  ├── maint-68-sync-consumer-repos   PRIMARY SYNC WORKFLOW                  │
│  └── maint-71-merge-sync-prs        Auto-merge synced PRs                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Sync System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYNC MECHANISM FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │   .github/sync-manifest.yml     │
                    │   (Single Source of Truth)      │
                    │                                 │
                    │   workflows:                    │
                    │     - source: agents-*.yml      │
                    │     - source: pr-00-gate.yml    │
                    │   prompts:                      │
                    │     - source: *.md              │
                    │   scripts:                      │
                    │     - source: *.js              │
                    └───────────────┬─────────────────┘
                                    │
                                    ▼
        ┌───────────────────────────────────────────────────────────────┐
        │              maint-68-sync-consumer-repos.yml                  │
        │                                                               │
        │   Triggers:                                                   │
        │   • Release published                                         │
        │   • Templates changed (push to main)                          │
        │   • Manual dispatch                                           │
        │                                                               │
        │   Process:                                                    │
        │   1. Read manifest                                            │
        │   2. Build sync matrix                                        │
        │   3. Create PRs in each consumer repo                         │
        └───────────────────────────┬───────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Travel-Plan-    │     │ Manager-        │     │ Template        │
│ Permission      │     │ Database        │     │                 │
│                 │     │                 │     │                 │
│ Sync PR →       │     │ Sync PR →       │     │ Sync PR →       │
│ CI runs →       │     │ CI runs →       │     │ CI runs →       │
│ Auto-merge      │     │ Auto-merge      │     │ Auto-merge      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────────┐
                    │  maint-71-merge-sync-prs.yml      │
                    │                                   │
                    │  • Auto-merge passing PRs         │
                    │  • Close stale duplicates         │
                    │  • Report failures                │
                    └───────────────────────────────────┘


SYNC MODES:
┌────────────────┬────────────────────────────────────────────────────────────┐
│ Mode           │ Behavior                                                   │
├────────────────┼────────────────────────────────────────────────────────────┤
│ default        │ Always overwrite with latest from Workflows               │
│ create_only    │ Create if missing, don't overwrite (allows customization) │
└────────────────┴────────────────────────────────────────────────────────────┘
```

## Keepalive System (Agent Automation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KEEPALIVE LIFECYCLE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

     GitHub Issue                              Pull Request
    ┌──────────────┐                         ┌──────────────┐
    │              │                         │              │
    │  Issue #42   │                         │  PR #43      │
    │              │                         │              │
    │  Labels:     │                         │  Labels:     │
    │  agent:codex │                         │  agent:codex │
    │  status:new  │                         │  status:wip  │
    │              │                         │              │
    │  ## Tasks    │         ───────►        │  ## Tasks    │
    │  - [ ] Do A  │                         │  - [x] Do A  │
    │  - [ ] Do B  │                         │  - [ ] Do B  │
    │  - [ ] Do C  │                         │  - [ ] Do C  │
    │              │                         │              │
    └──────────────┘                         └──────────────┘
           │                                        │
           ▼                                        ▼
┌──────────────────────┐              ┌──────────────────────────────────────┐
│ agents-63-issue-     │              │         KEEPALIVE LOOP               │
│ intake.yml           │              │                                      │
│                      │              │  1. Gate passes (CI green)           │
│ Creates PR from      │              │  2. agents-81-gate-followups.yml     │
│ issue body           │              │  3. Check conditions:                │
│                      │              │     - Has agent:codex label?         │
│ Calls:               │              │     - Gate passed?                   │
│ reusable-agents-     │              │     - Unchecked tasks remain?        │
│ issue-bridge.yml     │              │  4. Dispatch reusable-codex-run.yml  │
└──────────────────────┘              │  5. Codex works on next task         │
                                      │  6. Pushes commit → Gate runs        │
                                      │  7. Loop continues until done        │
                                      └──────────────────────────────────────┘


KEEPALIVE ACTIVATION CONDITIONS:
┌────────────────────────────────────────────────────────────────────────────┐
│  ✓ PR has `agent:codex` label                                              │
│  ✓ Gate workflow passed (CI green)                                         │
│  ✓ PR body contains unchecked tasks (- [ ])                                │
│  ✗ PR does NOT have `agents:paused` label                                  │
│  ✗ PR is NOT closed/merged                                                 │
└────────────────────────────────────────────────────────────────────────────┘


CODEX PROMPT SELECTION:
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  Condition                          Prompt File                            │
│  ─────────────────────────────────  ─────────────────────────────────────  │
│  CI passing, tasks remain           keepalive_next_task.md                 │
│  CI failing                         fix_ci_failures.md                     │
│  Bot review comments                fix_bot_comments.md                    │
│  Merge conflicts                    fix_merge_conflicts.md                 │
│  Verification check                 verifier_acceptance_check.md           │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## CI Gate Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CI GATE FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────┘

                              Pull Request
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │     pr-00-gate.yml       │
                    │     (Gate Workflow)      │
                    └──────────────┬───────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │   Lint      │         │   Test      │         │   Type      │
    │   (ruff)    │         │   (pytest)  │         │   Check     │
    │             │         │             │         │   (mypy)    │
    └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
           │                       │                       │
           └───────────────────────┼───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │     summary (job)        │
                    │                          │
                    │  Aggregates all results  │
                    │  Publishes commit status │
                    │  "Gate / gate"           │
                    └──────────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
            ┌─────────────┐               ┌─────────────┐
            │  ✓ PASS     │               │  ✗ FAIL     │
            │             │               │             │
            │  Triggers:  │               │  Blocks:    │
            │  - Keepalive│               │  - Merge    │
            │  - Verifier │               │  - Keepalive│
            └─────────────┘               └─────────────┘
```

## Agent Belt System (Parallel Processing)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AGENT BELT ARCHITECTURE                                 │
│                  (Parallel Agent Execution System)                           │
└─────────────────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────────────────────────┐
         │                    Work Queue                            │
         │  PRs with agent:codex label needing work                │
         │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                     │
         │  │PR-1│ │PR-2│ │PR-3│ │PR-4│ │PR-5│  ...                │
         │  └────┘ └────┘ └────┘ └────┘ └────┘                     │
         └──────────────────────────┬──────────────────────────────┘
                                    │
                                    ▼
         ┌─────────────────────────────────────────────────────────┐
         │          agents-71-codex-belt-dispatcher.yml            │
         │                                                         │
         │  • Scans for eligible PRs                               │
         │  • Prioritizes by age, label, status                    │
         │  • Creates work batches                                 │
         │  • Respects concurrency limits                          │
         └──────────────────────────┬──────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  Worker 1        │  │  Worker 2        │  │  Worker 3        │
    │                  │  │                  │  │                  │
    │  agents-72-      │  │  agents-72-      │  │  agents-72-      │
    │  belt-worker.yml │  │  belt-worker.yml │  │  belt-worker.yml │
    │                  │  │                  │  │                  │
    │  Processing:     │  │  Processing:     │  │  Processing:     │
    │  PR-1            │  │  PR-2            │  │  PR-3            │
    └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
             │                     │                     │
             └─────────────────────┼─────────────────────┘
                                   │
                                   ▼
         ┌─────────────────────────────────────────────────────────┐
         │           agents-73-codex-belt-conveyor.yml             │
         │                                                         │
         │  • Collects worker results                              │
         │  • Updates PR status                                    │
         │  • Triggers follow-up actions                           │
         │  • Reports metrics                                      │
         └─────────────────────────────────────────────────────────┘
```

## Reusable Workflow Call Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   HOW CONSUMERS CALL REUSABLE WORKFLOWS                      │
└─────────────────────────────────────────────────────────────────────────────┘


Consumer Repo                              stranske/Workflows
(e.g., Travel-Plan-Permission)             (Central Hub)

┌─────────────────────────────┐            ┌─────────────────────────────┐
│ .github/workflows/ci.yml    │            │ .github/workflows/          │
│                             │            │ reusable-10-ci-python.yml   │
│ jobs:                       │            │                             │
│   python-ci:                │   uses:    │ on:                         │
│     uses: stranske/────────────────────► │   workflow_call:            │
│       Workflows/.github/    │            │     inputs:                 │
│       workflows/reusable-   │            │       python-version:       │
│       10-ci-python.yml@v1   │            │         type: string        │
│     with:                   │            │       coverage-min:         │
│       python-version: "3.11"│            │         type: string        │
│       coverage-min: "80"    │            │                             │
│     secrets: inherit        │            │ jobs:                       │
│                             │            │   lint: ...                 │
└─────────────────────────────┘            │   test: ...                 │
                                           │   mypy: ...                 │
                                           └─────────────────────────────┘


VERSION STRATEGIES:

  @v1      Floating tag - receives backward-compatible updates automatically
           Recommended for production use

  @v1.0.0  Pinned release - reproducible, no automatic updates
           Use when stability is critical

  @main    Latest development - may have breaking changes
           Use only for testing unreleased features
```

## Script Ecosystem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SCRIPT ORGANIZATION                                 │
└─────────────────────────────────────────────────────────────────────────────┘


.github/scripts/  (Synced to Consumers)
├── KEEPALIVE CORE
│   ├── keepalive_loop.js              Main loop implementation
│   ├── keepalive_gate.js              Gate validation logic
│   ├── keepalive_prompt_composer.js   Prompt generation
│   ├── keepalive_state.js             State management
│   └── keepalive_instruction_template.js
│
├── API & INTEGRATION
│   ├── github-api-with-retry.js       Exponential backoff retry
│   ├── rate-limit-aware-client.js     Proactive rate limiting
│   ├── pr-context-graphql.js          GraphQL PR data fetching
│   └── octokit-helpers.js             Octokit utilities
│
├── AGENT INFRASTRUCTURE
│   ├── agents_orchestrator_resolve.js Orchestration state
│   ├── agents_verifier_context.js     Verification context
│   ├── agents_belt_scan.js            Belt system scanning
│   ├── agents_pr_meta_keepalive.js    PR metadata handling
│   └── agents_issue_bridge.js         Issue → PR conversion
│
├── UTILITIES
│   ├── comment-dedupe.js              Prevent duplicate comments
│   ├── conflict_detector.js           Merge conflict detection
│   ├── error_classifier.js            CI error classification
│   ├── issue_pr_locator.js            Find PRs for issues
│   └── sha256.js                       Hashing utilities
│
└── TESTS (__tests__/)
    ├── keepalive_loop.test.js
    ├── github-api-with-retry.test.js
    └── ... (80+ test files)


scripts/  (Development Only - Not Synced)
├── VALIDATION
│   ├── dev_check.sh                   Pre-commit validation
│   ├── check_branch.sh                Comprehensive validation
│   ├── validate_fast.sh               Pre-push validation
│   └── validate_yaml.py               YAML syntax checking
│
├── ANALYSIS
│   ├── autopilot_metrics_collector.py Metrics aggregation
│   ├── analyze_api_rate_limits.py     Rate limit analysis
│   └── ci_cosmetic_repair.py          Automated repairs
│
└── UTILITIES
    └── ... (60+ utility scripts)
```

## Data Flow: Issue to Completion

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    END-TO-END AUTOMATION FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘


    ┌───────────────────────────────────────────────────────────────┐
 1  │  USER CREATES ISSUE                                           │
    │                                                               │
    │  ## Tasks                                                     │
    │  - [ ] Implement feature X                                    │
    │  - [ ] Add tests                                              │
    │  - [ ] Update documentation                                   │
    │                                                               │
    │  Labels: agent:codex                                          │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
 2  │  ISSUE INTAKE (agents-63-issue-intake.yml)                    │
    │                                                               │
    │  • Detects new issue with agent:codex label                   │
    │  • Creates branch: claude/issue-42-abc123                     │
    │  • Creates PR with issue body                                 │
    │  • Copies tasks to PR description                             │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
 3  │  GATE RUNS (pr-00-gate.yml)                                   │
    │                                                               │
    │  • Lint check (ruff)                                          │
    │  • Test suite (pytest)                                        │
    │  • Type check (mypy)                                          │
    │  • Publishes "Gate / gate" commit status                      │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                          ┌─────────────┴─────────────┐
                          │                           │
                          ▼                           ▼
                    ┌───────────┐               ┌───────────┐
                    │  ✗ FAIL   │               │  ✓ PASS   │
                    │           │               │           │
                    │  Codex    │               │  Continue │
                    │  fixes CI │               │  to step 4│
                    └─────┬─────┘               └─────┬─────┘
                          │                           │
                          └─────────────┬─────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
 4  │  KEEPALIVE TRIGGERED (agents-81-gate-followups.yml)           │
    │                                                               │
    │  • Checks: Has agent:codex? Gate passed? Tasks remain?        │
    │  • Dispatches reusable-codex-run.yml                          │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
 5  │  CODEX EXECUTES                                               │
    │                                                               │
    │  • Reads prompt: keepalive_next_task.md                       │
    │  • Analyzes PR context and unchecked tasks                    │
    │  • Implements next task                                       │
    │  • Commits and pushes changes                                 │
    │  • Checks off completed task in PR body                       │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
 6  │  LOOP CONTINUES                                               │
    │                                                               │
    │  Push → Gate runs → Gate passes → Keepalive checks →          │
    │  Codex executes → Push → ...                                  │
    │                                                               │
    │  Until: All tasks checked OR agents:paused label added        │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
 7  │  VERIFICATION (agents-verifier.yml)                           │
    │                                                               │
    │  • Checks acceptance criteria                                 │
    │  • Validates implementation quality                           │
    │  • Reports status                                             │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
 8  │  READY FOR REVIEW                                             │
    │                                                               │
    │  • All tasks completed                                        │
    │  • CI passing                                                 │
    │  • PR ready for human review and merge                        │
    └───────────────────────────────────────────────────────────────┘
```

## Consumer Repository Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  CONSUMER REPO FILE ORGANIZATION                             │
└─────────────────────────────────────────────────────────────────────────────┘


Consumer Repo (e.g., Travel-Plan-Permission)
│
├── .github/
│   ├── workflows/
│   │   │
│   │   │  SYNCED FROM WORKFLOWS (don't edit locally)
│   │   ├── agents-63-issue-intake.yml      Issue → PR automation
│   │   ├── agents-70-orchestrator.yml      Scheduled orchestration
│   │   ├── agents-keepalive-loop.yml       Keepalive iteration
│   │   ├── agents-pr-meta.yml              PR metadata handling
│   │   ├── agents-verifier.yml             Verification checks
│   │   ├── agents-bot-comment-handler.yml  Bot comment handling
│   │   ├── autofix.yml                     Auto-format/lint
│   │   └── pr-00-gate.yml                  PR gate (customizable)
│   │   │
│   │   │  REPO-SPECIFIC (not synced)
│   │   ├── ci.yml                          Custom CI configuration
│   │   └── autofix-versions.env            Tool versions
│   │
│   ├── scripts/                            SYNCED from Workflows
│   │   ├── keepalive_loop.js
│   │   ├── github-api-with-retry.js
│   │   └── ... (60+ scripts)
│   │
│   └── codex/                              SYNCED from Workflows
│       ├── AGENT_INSTRUCTIONS.md
│       └── prompts/
│           ├── keepalive_next_task.md
│           ├── fix_ci_failures.md
│           └── ...
│
├── src/                                    Repo-specific code
├── tests/                                  Repo-specific tests
├── docs/                                   Partially synced
├── pyproject.toml                          Repo-specific config
└── README.md                               Repo-specific
```

## Authentication & Secrets

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AUTHENTICATION ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘


                    ┌─────────────────────────────────────────┐
                    │         GITHUB APP (Preferred)          │
                    │                                         │
                    │  GH_APP_ID + GH_APP_PRIVATE_KEY         │
                    │                                         │
                    │  Benefits:                              │
                    │  • Higher rate limits                   │
                    │  • Fine-grained permissions             │
                    │  • Audit trail per installation         │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
    ┌─────────────────────────────┐    ┌─────────────────────────────┐
    │    Agent Operations         │    │    PR/Issue Operations      │
    │                             │    │                             │
    │    SERVICE_BOT_PAT          │    │    OWNER_PR_PAT             │
    │                             │    │                             │
    │    Used for:                │    │    Used for:                │
    │    • Posting comments       │    │    • Creating PRs           │
    │    • Adding labels          │    │    • Merging PRs            │
    │    • Triggering workflows   │    │    • Admin operations       │
    └─────────────────────────────┘    └─────────────────────────────┘


SECRET NAMING CONVENTION:
┌────────────────────────────────────────────────────────────────────────────┐
│  workflow_call definitions use lowercase: gh_app_id, service_bot_pat       │
│  Organization secrets use UPPER_CASE: GH_APP_ID, SERVICE_BOT_PAT          │
│                                                                            │
│  Mapping happens via secrets: inherit                                      │
└────────────────────────────────────────────────────────────────────────────┘
```

## Health & Validation System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     VALIDATION PIPELINE                                      │
└─────────────────────────────────────────────────────────────────────────────┘


                    ┌─────────────────────────────────────────┐
                    │          LOCAL DEVELOPMENT              │
                    │                                         │
                    │  scripts/dev_check.sh                   │
                    │  • YAML syntax validation               │
                    │  • Workflow linting (actionlint)        │
                    │  • Python type checking (mypy)          │
                    │  • JavaScript tests (jest)              │
                    │                                         │
                    │  scripts/check_branch.sh                │
                    │  • Full test suite                      │
                    │  • Integration tests                    │
                    │  • Coverage analysis                    │
                    └─────────────────────────────────────────┘
                                      │
                                      │ git push
                                      ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                            CI PIPELINE                               │
    │                                                                     │
    │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
    │  │ health-40-repo  │  │ health-42-      │  │ health-43-ci-   │     │
    │  │ selfcheck       │  │ actionlint      │  │ signature-guard │     │
    │  │                 │  │                 │  │                 │     │
    │  │ Validates repo  │  │ Lints workflow  │  │ Checks CI       │     │
    │  │ structure       │  │ YAML files      │  │ integrity       │     │
    │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
    │                                                                     │
    │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
    │  │ health-68-      │  │ health-70-      │  │ health-72-      │     │
    │  │ consumer-sync   │  │ validate-       │  │ template-sync   │     │
    │  │ drift           │  │ manifest        │  │                 │     │
    │  │                 │  │                 │  │                 │     │
    │  │ Detects sync    │  │ Ensures all     │  │ Validates       │     │
    │  │ drift           │  │ files declared  │  │ templates       │     │
    │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
```

## Release & Versioning

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RELEASE FLOW                                            │
└─────────────────────────────────────────────────────────────────────────────┘


    ┌───────────────────────────────────────────────────────────────┐
    │  Developer creates release (maint-60-release.yml)             │
    │                                                               │
    │  • Semantic versioning: v1.2.3                                │
    │  • Release notes auto-generated                               │
    │  • Tags created                                               │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
    │  Floating tag updated (maint-61-create-floating-v1-tag.yml)   │
    │                                                               │
    │  v1 ──────► points to latest v1.x.x release                   │
    │                                                               │
    │  Consumer repos using @v1 automatically get updates           │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
    │  Sync triggered (maint-68-sync-consumer-repos.yml)            │
    │                                                               │
    │  • Templates synced to all consumer repos                     │
    │  • PRs created in each consumer                               │
    │  • CI runs on sync PRs                                        │
    └───────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────┐
    │  Auto-merge (maint-71-merge-sync-prs.yml)                     │
    │                                                               │
    │  • Merges passing sync PRs                                    │
    │  • Closes stale duplicates                                    │
    │  • Reports failures for investigation                         │
    └───────────────────────────────────────────────────────────────┘
```

## Multi-Agent Architecture (Codex + Claude + Gemini)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-AGENT ROUTING SYSTEM                              │
│                                                                             │
│  Supports multiple AI backends: Codex (OpenAI), Claude (Anthropic),        │
│  Gemini (Google). Agent selection via PR/Issue labels.                      │
└─────────────────────────────────────────────────────────────────────────────┘


                         Issue/PR with agent label
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       LABEL DETECTION         │
                    │                              │
                    │   agent:codex  → Codex      │
                    │   agent:claude → Claude     │
                    │   agent:gemini → Gemini     │
                    │   (no label)   → Codex      │
                    └──────────────┬───────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   CODEX         │     │   CLAUDE        │     │   GEMINI        │
│                 │     │                 │     │                 │
│ reusable-       │     │ reusable-       │     │ reusable-       │
│ codex-run.yml   │     │ claude-run.yml  │     │ gemini-run.yml  │
│                 │     │                 │     │                 │
│ Backend:        │     │ Backend:        │     │ Backend:        │
│ OpenAI API      │     │ Amazon Bedrock  │     │ Google AI       │
│                 │     │ (Claude API)    │     │ Platform        │
│                 │     │                 │     │                 │
│ Secrets:        │     │ Secrets:        │     │ Secrets:        │
│ OPENAI_API_KEY  │     │ AWS_ACCESS_KEY  │     │ GOOGLE_API_KEY  │
│                 │     │ AWS_SECRET_KEY  │     │                 │
│                 │     │ AWS_REGION      │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘


AGENT EXECUTION ENVIRONMENTS:
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  Codex:   chatgpt-codex-connector (GitHub App) - OpenAI infrastructure    │
│  Claude:  claude-code CLI - Runs in GitHub Actions runner via Bedrock     │
│  Gemini:  gemini-cli - Runs in GitHub Actions runner via Google AI        │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## Agent Integration Points Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              FILES REQUIRING MULTI-AGENT SUPPORT                             │
│                                                                             │
│  Legend: ✅ Has Claude support | 🔴 Needs Claude support | ⚪ N/A          │
└─────────────────────────────────────────────────────────────────────────────┘


REUSABLE WORKFLOWS (Core Agent Execution)
─────────────────────────────────────────
.github/workflows/
├── ✅ reusable-codex-run.yml           Codex agent execution
├── ✅ reusable-claude-run.yml          Claude agent execution (CREATED)
├── ⚪ reusable-gemini-run.yml          Gemini agent execution (future)
└── ✅ reusable-bot-comment-handler.yml Has routing for all agents


AGENT TRIGGER WORKFLOWS (Entry Points)
──────────────────────────────────────
.github/workflows/
├── 🔴 agents-capability-check.yml      Only triggers on agent:codex
├── 🔴 agents-63-issue-intake.yml       May need Claude label support
├── 🔴 agents-70-orchestrator.yml       Orchestrator agent sweeps
└── ✅ agents-keepalive-loop.yml        Has run-claude job (UPDATED)


AUTOMATION WORKFLOWS (CI/Auto-fix)
──────────────────────────────────
.github/workflows/
├── 🔴 agents-autofix-loop.yml          Calls reusable-codex-run only
├── 🔴 agents-auto-pilot.yml            References agent:codex only
└── 🔴 agents-81-gate-followups.yml     Triggers keepalive (check routing)


BELT SYSTEM (Parallel Processing)
─────────────────────────────────
.github/workflows/
├── 🔴 agents-71-codex-belt-dispatcher.yml   Dispatcher - Codex only
├── 🔴 agents-72-codex-belt-worker-dispatch  Worker dispatch - Codex only
├── 🔴 agents-72-codex-belt-worker.yml       Worker execution - Codex only
└── 🔴 agents-73-codex-belt-conveyor.yml     Conveyor - Codex only


SCRIPTS (Logic & Routing)
─────────────────────────
.github/scripts/
├── 🔴 keepalive_loop.js                Agent routing logic
├── 🔴 agents_orchestrator_resolve.js   Agent label recognition
├── 🔴 error_classifier.js              Add AWS/Bedrock error patterns
└── ⚪ github-api-with-retry.js         Agent-agnostic (no changes)

scripts/
└── 🔴 keepalive-runner.js              CLI agent label detection


CONSUMER TEMPLATES (Must Mirror Main)
─────────────────────────────────────
templates/consumer-repo/.github/workflows/
├── 🔴 agents-capability-check.yml
├── 🔴 agents-autofix-loop.yml
├── 🔴 agents-auto-pilot.yml
├── 🔴 agents-71-codex-belt-dispatcher.yml
├── 🔴 agents-72-codex-belt-worker-dispatch.yml
├── 🔴 agents-72-codex-belt-worker.yml
├── 🔴 agents-73-codex-belt-conveyor.yml
└── ✅ agents-keepalive-loop.yml

templates/consumer-repo/.github/scripts/
├── 🔴 keepalive_loop.js
└── 🔴 agents_orchestrator_resolve.js


LABELS CONFIGURATION
────────────────────
├── 🔴 .github/labels.yml               Add agent:claude label
├── 🔴 .github/labels-core.yml          Add agent:claude label
└── 🔴 templates/.../labels.yml         Add agent:claude label


DOCUMENTATION
─────────────
docs/keepalive/
├── 🔴 MULTI_AGENT_ROUTING.md           Update "not implemented"
├── 🔴 Agents.md                        Add Claude section
└── 🔴 SETUP_CHECKLIST.md               Add AWS secrets setup
```

## Multi-Agent Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   MULTI-AGENT KEEPALIVE FLOW                                 │
└─────────────────────────────────────────────────────────────────────────────┘


    Issue labeled with agent:claude
              │
              ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  agents-63-issue-intake.yml                                          │
    │                                                                     │
    │  • Detects agent:claude label                                       │
    │  • Creates PR with same label                                       │
    │  • Branch: claude/issue-XX-hash                                     │
    └──────────────────────────────────┬──────────────────────────────────┘
                                       │
                                       ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  pr-00-gate.yml (Gate)                                              │
    │                                                                     │
    │  • Runs CI checks (lint, test, mypy)                                │
    │  • Agent-agnostic - same for all agents                             │
    │  • Publishes "Gate / gate" status                                   │
    └──────────────────────────────────┬──────────────────────────────────┘
                                       │
                                       ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  agents-81-gate-followups.yml                                        │
    │                                                                     │
    │  • Gate passed, check conditions                                    │
    │  • Dispatch to agents-keepalive-loop.yml                            │
    └──────────────────────────────────┬──────────────────────────────────┘
                                       │
                                       ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  agents-keepalive-loop.yml                                           │
    │                                                                     │
    │  AGENT ROUTING:                                                     │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │  if: has_label('agent:claude')                              │   │
    │  │      → run-claude job → reusable-claude-run.yml             │   │
    │  │  elif: has_label('agent:codex')                             │   │
    │  │      → run-codex job → reusable-codex-run.yml               │   │
    │  │  else:                                                      │   │
    │  │      → default to Codex                                     │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    └──────────────────────────────────┬──────────────────────────────────┘
                                       │
              ┌────────────────────────┴────────────────────────┐
              │                                                 │
              ▼                                                 ▼
    ┌───────────────────────┐                     ┌───────────────────────┐
    │  reusable-codex-run   │                     │  reusable-claude-run  │
    │                       │                     │                       │
    │  • OpenAI backend     │                     │  • Bedrock backend    │
    │  • OPENAI_API_KEY     │                     │  • AWS credentials    │
    │  • chatgpt-codex-     │                     │  • claude-code CLI    │
    │    connector          │                     │  • Runs in GH runner  │
    └───────────┬───────────┘                     └───────────┬───────────┘
                │                                             │
                └─────────────────────┬───────────────────────┘
                                      │
                                      ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  Agent pushes commits                                                │
    │                                                                     │
    │  • Checks off completed task in PR body                             │
    │  • Push triggers Gate → Loop continues                              │
    │  • Until all tasks complete                                         │
    └─────────────────────────────────────────────────────────────────────┘
```

## Secrets Architecture for Multi-Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SECRETS BY AGENT TYPE                                   │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│  AI BACKEND SECRETS (NOT interchangeable)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CODEX (OpenAI)                                                             │
│  ├── OPENAI_API_KEY            API key for OpenAI                          │
│  └── (managed by chatgpt-codex-connector GitHub App)                       │
│                                                                             │
│  CLAUDE (Amazon Bedrock)                                                    │
│  ├── AWS_ACCESS_KEY_ID         AWS IAM access key                          │
│  ├── AWS_SECRET_ACCESS_KEY     AWS IAM secret key                          │
│  ├── AWS_REGION                Region (e.g., us-east-1)                    │
│  └── ANTHROPIC_MODEL           Model ID (claude-sonnet-4-20250514)   │
│                                                                             │
│  GEMINI (Google AI)                                                         │
│  ├── GOOGLE_API_KEY            Google AI Platform key                      │
│  └── GEMINI_MODEL              Model ID                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│  GITHUB ACCESS SECRETS (ARE interchangeable)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Option A: GitHub App (Preferred)                                           │
│  ├── GH_APP_ID                 App ID                                      │
│  └── GH_APP_PRIVATE_KEY        App private key (PEM)                       │
│                                                                             │
│  Option B: Personal Access Token                                            │
│  ├── SERVICE_BOT_PAT           For comments, labels                        │
│  └── OWNER_PR_PAT              For PR creation                             │
│                                                                             │
│  Either option works for any agent - GitHub access is agent-agnostic        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


CONSUMER REPO SECRET SETUP:
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  For Codex only:                                                           │
│    • Install chatgpt-codex-connector GitHub App                            │
│    • No additional secrets needed (App handles OpenAI auth)                │
│                                                                            │
│  For Claude:                                                               │
│    • Add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION              │
│    • Ensure IAM user has bedrock:InvokeModel permission                    │
│                                                                            │
│  For Both (multi-agent):                                                   │
│    • All of the above                                                      │
│    • Use labels to route: agent:codex or agent:claude                      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## Integration Status Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLAUDE INTEGRATION PROGRESS                               │
└─────────────────────────────────────────────────────────────────────────────┘

                                    COMPLETE
                                    ────────
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  ✅ reusable-claude-run.yml          Core Claude execution workflow     │
  │  ✅ agents-keepalive-loop.yml        Added run-claude job              │
  │  ✅ reusable-bot-comment-handler     Already has Claude routing        │
  │  ✅ docs/integrations/CLAUDE_CODE_INTEGRATION.md  Documentation        │
  └─────────────────────────────────────────────────────────────────────────┘

                                  REMAINING
                                  ─────────
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  WORKFLOWS (10 files)                                                   │
  │  ────────────────────                                                   │
  │  🔴 agents-capability-check.yml      Add agent:claude trigger          │
  │  🔴 agents-autofix-loop.yml          Add Claude routing                │
  │  🔴 agents-auto-pilot.yml            Add Claude routing                │
  │  🔴 agents-63-issue-intake.yml       Verify Claude label support       │
  │  🔴 agents-70-orchestrator.yml       Add Claude to sweeps              │
  │  🔴 agents-71-belt-dispatcher        Add Claude to belt system         │
  │  🔴 agents-72-belt-worker-dispatch   Add Claude routing                │
  │  🔴 agents-72-belt-worker            Add Claude execution              │
  │  🔴 agents-73-belt-conveyor          Add Claude support                │
  │  🔴 agents-81-gate-followups         Verify routing                    │
  │                                                                         │
  │  SCRIPTS (4 files)                                                      │
  │  ─────────────────                                                      │
  │  🔴 keepalive_loop.js                Add Claude routing logic          │
  │  🔴 agents_orchestrator_resolve.js   Recognize agent:claude            │
  │  🔴 error_classifier.js              Add AWS/Bedrock patterns          │
  │  🔴 keepalive-runner.js              Add agent:claude to CLI labels    │
  │                                                                         │
  │  TEMPLATES (10+ files)                                                  │
  │  ─────────────────────                                                  │
  │  🔴 Mirror all workflow changes to templates/consumer-repo/            │
  │                                                                         │
  │  LABELS (3 files)                                                       │
  │  ────────────────                                                       │
  │  🔴 Add agent:claude label definition to all label configs             │
  │                                                                         │
  │  DOCUMENTATION (5+ files)                                               │
  │  ────────────────────────                                               │
  │  🔴 Update MULTI_AGENT_ROUTING.md, Agents.md, SETUP_CHECKLIST.md       │
  └─────────────────────────────────────────────────────────────────────────┘

  TOTAL: ~32 files need updates for full Claude integration
```

## Key Files Reference

| File | Purpose | Location |
|------|---------|----------|
| `sync-manifest.yml` | Defines all files to sync | `.github/` |
| `CLAUDE.md` | Repository policies & standards | Root |
| `GoalsAndPlumbing.md` | Canonical keepalive contract | `docs/keepalive/` |
| `AGENT_INSTRUCTIONS.md` | Base Codex instructions | `.github/codex/` |
| `reusable-10-ci-python.yml` | Main Python CI workflow | `.github/workflows/` |
| `reusable-codex-run.yml` | Codex agent execution | `.github/workflows/` |
| `reusable-claude-run.yml` | Claude agent execution | `.github/workflows/` |
| `maint-68-sync-consumer-repos.yml` | Primary sync workflow | `.github/workflows/` |
| `keepalive_loop.js` | Core keepalive logic | `.github/scripts/` |
| `MULTI_AGENT_ROUTING.md` | Agent routing architecture | `docs/keepalive/` |

---

*Generated for stranske/Workflows - Central Workflow Library*
