# Workflows Repository - System Architecture Diagram

> **Complete visual reference** for understanding the Workflows repository structure, component relationships, and data flows.

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Component Breakdown](#component-breakdown)
3. [Workflow Execution Flow](#workflow-execution-flow)
4. [Sync Mechanism](#sync-mechanism)
5. [Keepalive System](#keepalive-system)
6. [LangChain Integration](#langchain-integration)
7. [File Structure Tree](#file-structure-tree)
8. [Data Flow Diagrams](#data-flow-diagrams)

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "Workflows Repository (Central Library)"
        RW[Reusable Workflows<br/>13 workflows<br/>Called via uses:]
        SW[Synced Workflows<br/>27 agent workflows<br/>2 CI workflows]
        MW[Maintenance Workflows<br/>27 workflows<br/>Workflows-only]
        HW[Health & Selftest<br/>18 workflows<br/>Validation]

        SM[Sync Manifest<br/>sync-manifest.yml<br/>108+ files]

        SC[Scripts<br/>125+ files<br/>JS + Python]
        PR[Codex Prompts<br/>6 prompt files]
        DC[Documentation<br/>91+ files]

        RW --> CR
        SW --> SM
        SC --> SM
        PR --> SM
        DC --> SM

        SM --> SYNC[Sync Workflow<br/>maint-68]
    end

    subgraph "Consumer Repos (4 repos)"
        CR[Consumer Workflows<br/>Call reusable workflows]
        CS[Synced Artifacts<br/>Workflows, scripts, prompts]
        CL[Local Customizations<br/>ci.yml, README, .gitignore]

        CS --> EX[Execution<br/>Issue → PR → Keepalive]
    end

    SYNC -->|Creates PRs| CS
    MERGE[Auto-Merge<br/>maint-71] -->|Merges when CI passes| CS

    style RW fill:#e1f5ff
    style SW fill:#fff3cd
    style MW fill:#d4edda
    style HW fill:#f8d7da
    style SM fill:#ffc107
    style SYNC fill:#ff9800
    style MERGE fill:#4caf50
```

---

## Component Breakdown

### 1. Workflow Categories (88 total workflows)

```mermaid
pie title Workflow Distribution
    "Agent Workflows" : 27
    "Maintenance" : 27
    "Health & Selftest" : 18
    "Reusable" : 13
    "CI/Gate" : 2
    "Autofix" : 1
```

#### 1.1 Reusable Workflows (13 workflows)

**Purpose**: Core building blocks called by consumer repos via `uses: stranske/Workflows/.github/workflows/reusable-*.yml@v1`

```
├── CI Orchestration
│   ├── reusable-10-ci-python.yml ──────► Python lint, test, mypy
│   ├── reusable-11-ci-node.yml ────────► Node.js CI
│   └── reusable-12-ci-docker.yml ──────► Docker build/test
│
├── Agent System
│   ├── reusable-16-agents.yml ─────────► Core agent framework
│   ├── reusable-agents-issue-bridge.yml ► Bootstrap PRs from issues
│   ├── reusable-agents-verifier.yml ───► PR verification
│   ├── reusable-bot-comment-handler.yml ► Bot comment handling
│   └── reusable-codex-run.yml ─────────► Codex agent execution
│
├── Orchestration
│   ├── reusable-70-orchestrator-init.yml ► Orchestrator init
│   └── reusable-70-orchestrator-main.yml ► Orchestrator main loop
│
├── PR Management
│   ├── reusable-20-pr-meta.yml ────────► PR metadata tracking
│   └── reusable-pr-context.yml ────────► GraphQL PR context
│
└── Autofix
    └── reusable-18-autofix.yml ────────► Lint/format auto-fix

🔑 Key Characteristic: NOT synced to consumers (referenced instead)
```

#### 1.2 Agent Workflows (27 workflows - SYNCED)

**Purpose**: Consumer-facing automation and orchestration

```
├── Core Orchestration (5)
│   ├── agents-70-orchestrator.yml ─────► Scheduled orchestration
│   ├── agents-63-issue-intake.yml ─────► Issue → PR bootstrap
│   ├── agents-pr-meta.yml ─────────────► PR comment/dispatch handling
│   ├── agents-verifier.yml ────────────► PR verification checks
│   └── agents-auto-pilot.yml ──────────► Auto-pilot mode
│
├── Keepalive Loop (5)
│   ├── agents-keepalive-loop.yml ──────► CLI agent keepalive iteration
│   ├── agents-autofix-loop.yml ────────► Autofix iteration loop
│   ├── agents-bot-comment-handler.yml ─► Address bot comments
│   └── agents-debug-issue-event.yml ───► Debug issue triggers
│
├── Codex Belt System (4)
│   ├── agents-72-codex-belt-dispatcher.yml ► Route work to workers
│   ├── agents-72-codex-belt-worker.yml ────► Execute Codex tasks
│   ├── agents-72-codex-belt-worker-dispatch.yml ► Worker dispatch
│   └── agents-75-codex-belt-conveyor.yml ─► Belt orchestration
│
├── LangChain Integration (7)
│   ├── agents-issue-optimizer.yml ─────► Optimize issue format
│   ├── agents-issue-decompose.yml ─────► Break down complex issues
│   ├── agents-issue-dedup.yml ─────────► Deduplicate similar issues
│   ├── agents-capability-check.yml ────► Check agent capabilities
│   ├── agents-auto-label.yml ──────────► Auto-label issues/PRs
│   ├── agents-guard.yml ───────────────► Security guard checks
│   ├── agents-verify-to-issue.yml ─────► Create issues from verification
│   └── agents-verify-to-new-pr-*.yml ──► Verification variants (2)
│
└── Utility (6)
    ├── agents-moderate-connector.yml ──► Moderate bot connections
    ├── agents-pr-meta-v4.yml ──────────► PR meta v4 variant
    └── agents-weekly-metrics.yml ──────► Weekly metrics aggregation

🔑 Key Characteristic: Synced to all consumer repos via sync-manifest.yml
```

#### 1.3 Maintenance Workflows (27 workflows - NOT synced)

**Purpose**: Repository maintenance, sync operations, validation

```
├── Release & Versioning (4)
│   ├── maint-60-release.yml ───────────► Create releases
│   ├── maint-61-create-floating-v1-tag.yml ► Maintain v1 tag
│   ├── maint-50-tool-version-check.yml ► Check dependency versions
│   └── maint-51-dependency-refresh.yml ► Refresh dependencies
│
├── Sync Operations (6)
│   ├── maint-68-sync-consumer-repos.yml ► Sync to consumer repos
│   ├── maint-69-sync-integration-repo.yml ► Sync integration tests
│   ├── maint-69-sync-labels.yml ───────► Sync label definitions
│   ├── maint-71-merge-sync-prs.yml ────► Auto-merge sync PRs
│   ├── maint-72-fix-pr-body-conflicts.yml ► Fix PR body conflicts
│   └── maint-auto-update-pypi-versions.yml ► Update from PyPI
│
├── Integration & Testing (3)
│   ├── maint-62-integration-consumer.yml ► Consumer integration tests
│   ├── maint-70-fix-integration-formatting.yml ► Fix formatting
│   └── maint-71-auto-fix-integration.yml ► Auto-fix integration
│
├── Dependency Management (5)
│   ├── maint-52-sync-dev-versions.yml ─► Sync dev dependencies
│   ├── maint-dependabot-*.yml ─────────► Dependabot automation (3)
│   └── maint-sync-action-versions.yml ─► Sync GitHub Action versions
│
├── CI & Formatting (4)
│   ├── maint-46-post-ci.yml ───────────► Post-CI maintenance
│   ├── maint-45-cosmetic-repair.yml ───► Cosmetic repairs
│   ├── maint-47-disable-legacy-workflows.yml ► Disable old workflows
│   └── maint-coverage-guard.yml ───────► Coverage threshold guard
│
└── Validation (5)
    ├── maint-52-validate-workflows.yml ► Validate workflow syntax
    └── [Other validation workflows]

🔑 Key Characteristic: Workflows-only (NOT synced to consumers)
```

#### 1.4 Health & Selftest Workflows (18 workflows - NOT synced)

**Purpose**: Repository health monitoring, drift detection, security

```
├── CI Health (3)
│   ├── health-40-repo-selfcheck.yml ───► Repository self-check
│   ├── health-40-sweep.yml ────────────► Health sweep
│   └── health-41-repo-health.yml ──────► Overall repo health
│
├── Validation (6)
│   ├── health-42-actionlint.yml ───────► Actionlint validation
│   ├── health-68-consumer-sync-drift.yml ► Detect sync drift
│   ├── health-70-validate-sync-manifest.yml ► Validate manifest
│   ├── health-71-sync-health-check.yml ► Sync health status
│   ├── health-72-template-sync.yml ────► Template sync check
│   └── health-73-template-completeness.yml ► Template completeness
│
├── Security & Quality (3)
│   ├── health-43-ci-signature-guard.yml ► CI signature validation
│   ├── health-50-security-scan.yml ────► Security scanning
│   └── health-codex-auth-check.yml ────► Codex auth validation
│
└── Integration & Monitoring (6)
    ├── health-67-integration-sync-check.yml ► Integration sync
    ├── health-75-api-rate-diagnostic.yml ► API rate monitoring
    ├── health-keepalive-e2e.yml ───────► Keepalive end-to-end test
    └── [Other monitoring workflows]

🔑 Key Characteristic: Workflows-only (NOT synced to consumers)
```

### 2. Scripts Organization (125+ files)

```
scripts/
├── .github/scripts/ (58 files - Core Infrastructure)
│   │
│   ├── API & Caching (10)
│   │   ├── api-helpers.js
│   │   ├── github-api-retry.js
│   │   ├── github-api-with-retry.js
│   │   ├── github-api-cache.js
│   │   ├── github-api-cache-client.js
│   │   ├── rate-limit-aware-client.js
│   │   ├── pr-context-graphql.js
│   │   ├── token_load_balancer.js
│   │   └── timeout_config.js
│   │
│   ├── Keepalive System (13)
│   │   ├── keepalive_loop.js ────────────► Main keepalive loop logic
│   │   ├── keepalive_gate.js ────────────► Gate evaluation
│   │   ├── keepalive_contract.js ────────► Contract validation
│   │   ├── keepalive_prompt_composer.js ─► Compose prompts
│   │   ├── keepalive_prompt_routing.js ──► Route to correct prompt
│   │   ├── keepalive_state.js ───────────► State management
│   │   ├── keepalive_post_work.js ───────► Post-work processing
│   │   ├── keepalive_guard_utils.js ─────► Guard utilities
│   │   ├── keepalive_orchestrator_gate_runner.js ► Orchestrator gate
│   │   ├── keepalive_worker_gate.js ─────► Worker gate logic
│   │   └── keepalive_instruction_template.js ► Template generation
│   │
│   ├── Agent System (10)
│   │   ├── agents_orchestrator_resolve.js ► Orchestrator resolution
│   │   ├── agents_pr_meta_keepalive.js ──► PR meta for keepalive
│   │   ├── agents_pr_meta_orchestrator.js ► PR meta for orchestrator
│   │   ├── agents_pr_meta_update_body.js ► Update PR body
│   │   ├── agents_verifier_context.js ───► Verifier context
│   │   ├── agents_dispatch_summary.js ───► Dispatch summary
│   │   ├── agents_belt_scan.js ──────────► Belt system scanner
│   │   ├── agents_guard.js ──────────────► Security guards
│   │   ├── prompt_injection_guard.js ────► Prompt injection defense
│   │   └── prompt_integrity_guard.js ────► Prompt integrity check
│   │
│   ├── CI & Error Handling (12)
│   │   ├── detect-changes.js
│   │   ├── coverage-normalize.js
│   │   ├── error_classifier.js
│   │   ├── error_diagnostics.js
│   │   ├── failure_comment_formatter.js
│   │   ├── gate-docs-only.js
│   │   ├── verifier_ci_query.js
│   │   ├── verifier_issue_formatter.js
│   │   └── maint-post-ci.js
│   │
│   ├── Issue & PR Utilities (8)
│   │   ├── issue_context_utils.js
│   │   ├── issue_pr_locator.js
│   │   ├── issue_scope_parser.js
│   │   ├── checkout_source.js
│   │   ├── comment-dedupe.js
│   │   ├── conflict_detector.js
│   │   ├── merge_manager.js
│   │   └── post_completion_comment.js
│   │
│   └── Python Helpers (10)
│       ├── decode_raw_input.py
│       ├── parse_chatgpt_topics.py
│       ├── fallback_split.py
│       ├── autofix_emit_report.py
│       ├── gate_summary.py
│       ├── health_summarize.py
│       ├── label_rules_assert.py
│       ├── lockfile_status.py
│       ├── render_cosmetic_summary.py
│       └── restore_branch_snapshots.py
│
└── scripts/ (67+ files - Higher-Level Operations)
    │
    ├── Core CI/Metrics (10)
    │   ├── ci_metrics.py
    │   ├── ci_history.py
    │   ├── ci_coverage_delta.py
    │   ├── ci_cosmetic_repair.py
    │   ├── ci_failure_analyzer.py
    │   ├── coverage_history_append.py
    │   └── sync_test_dependencies.py
    │
    ├── LangChain System (scripts/langchain/ - 13 files)
    │   ├── capability_check.py ──────────► Check agent capabilities
    │   ├── context_extractor.py ─────────► Extract PR/issue context
    │   ├── followup_issue_generator.py ──► Generate follow-up issues
    │   ├── integration_layer.py ─────────► LangChain integration
    │   ├── issue_dedup.py ───────────────► Deduplicate issues
    │   ├── issue_formatter.py ───────────► Format issues for agents
    │   ├── issue_optimizer.py ───────────► Optimize issue structure
    │   ├── label_matcher.py ─────────────► Match labels semantically
    │   ├── pr_verifier.py ───────────────► Verify PR completeness
    │   ├── semantic_matcher.py ──────────► Semantic similarity
    │   ├── task_decomposer.py ───────────► Break down complex tasks
    │   ├── task_validator.py ────────────► Validate task format
    │   └── topic_splitter.py ────────────► Split topics
    │
    ├── Validation & Analysis (15)
    │   ├── validate_workflow_yaml.py
    │   ├── validate_template_completeness.py
    │   ├── validate_template_sync.py
    │   ├── validate_version_pins.py
    │   ├── validate_dependency_test_setup.py
    │   ├── check_consumer_sync_drift.py
    │   ├── check_issue_consistency.py
    │   ├── duplicate_detection.py
    │   └── issue_dedup_smoke.py
    │
    ├── Keepalive & Metrics (10)
    │   ├── keepalive_instruction_segment.js
    │   ├── keepalive-runner.js
    │   ├── keepalive_metrics_collector.py
    │   ├── keepalive_metrics_dashboard.py
    │   ├── keepalive_post_merge_metrics.py
    │   ├── aggregate_agent_metrics.py
    │   ├── aggregate_repo_metrics.py
    │   ├── generate_metrics_badges.py
    │   ├── autopilot_metrics_collector.py
    │   └── autopilot_step_timer.py
    │
    ├── Maintenance (12)
    │   ├── update_autofix_expectations.py
    │   ├── update_langchain_versions.py
    │   ├── update_readme_badges.py
    │   ├── update_residual_history.py
    │   ├── update_versions_from_pypi.py
    │   ├── sync_dev_dependencies.py
    │   ├── sync_tool_versions.py
    │   ├── mypy_autofix.py
    │   └── mypy_return_autofix.py
    │
    └── [Additional utilities and test files]

🔑 Total: 125+ scripts, 54 test files
```

### 3. Codex Prompts (6 files)

```
.github/codex/prompts/
├── keepalive_next_task.md ──────────► Normal work in keepalive loop
├── autofix_from_ci_failure.md ──────► Autofix CI/Gate failures
├── fix_ci_failures.md ───────────────► General CI failure resolution
├── fix_bot_comments.md ──────────────► Address bot review comments
├── verifier_acceptance_check.md ─────► Validate acceptance criteria
└── fix_merge_conflicts.md ───────────► Merge conflict resolution

AGENT_INSTRUCTIONS.md ────────────────► Security boundaries, operational guidelines
```

### 4. Documentation (91+ files)

```
docs/
├── Core Reference
│   ├── README.md ─────────────────► Documentation hub
│   ├── STRUCTURE.md ──────────────► Repository file organization
│   ├── INTEGRATION_GUIDE.md ──────► Consumer integration
│   ├── CONTRIBUTING.md ───────────► Contribution guidelines
│   └── USAGE.md ──────────────────► Quick start
│
├── ci/ (16 files)
│   ├── WORKFLOWS.md ──────────────► Workflow reference
│   ├── AUTOFIX.md ────────────────► Autofix system design
│   ├── LEDGER.md ─────────────────► Ledger tracking
│   ├── TOOL_VERSION_MANAGEMENT.md ► Version pinning
│   └── [12 more CI docs]
│
├── keepalive/ (10 files)
│   ├── GoalsAndPlumbing.md ───────► Canonical keepalive design
│   ├── SETUP_CHECKLIST.md ────────► Setup requirements
│   ├── Agents.md ─────────────────► Agent routing and contracts
│   ├── MULTI_AGENT_ROUTING.md ────► Multi-agent architecture
│   ├── Observability_Contract.md ─► Contract definitions
│   └── [5 more keepalive docs]
│
├── ops/ (15+ files)
│   ├── api-rate-limit-management.md
│   ├── ci-status-summary.md
│   ├── CODEX_TOKEN_REFRESH.md
│   └── [12+ more operational docs]
│
├── plans/ (10+ files)
│   ├── SHORT_TERM_PLAN.md
│   ├── LONG_TERM_PLAN.md
│   └── [8+ planning docs]
│
├── guides/ (8+ files)
│   ├── dual-location-sync-gotcha.md ► CRITICAL sync gotcha
│   └── [7+ guide docs]
│
├── templates/ (5 files)
│   ├── AGENT_ISSUE_TEMPLATE.md ───► Standard issue format
│   ├── WORKFLOW_TEMPLATE.md ──────► Workflow documentation template
│   └── SETUP_CHECKLIST.md ────────► Setup checklist template
│
└── archive/ (20+ files)
    └── Historical documents from phases 1-5

🔑 Total: 91+ documentation files
```

---

## Workflow Execution Flow

### Complete Issue-to-Merge Flow

```mermaid
sequenceDiagram
    participant U as User
    participant I as Issue
    participant IB as Issue Bridge<br/>(agents-63)
    participant PR as Pull Request
    participant G as Gate<br/>(pr-00-gate)
    participant KL as Keepalive Loop<br/>(agents-keepalive-loop)
    participant CX as Codex<br/>(reusable-codex-run)
    participant O as Orchestrator<br/>(agents-70)
    participant V as Verifier<br/>(agents-verifier)
    participant M as Merge

    U->>I: Create issue with<br/>label: agent:codex
    I->>IB: Issue labeled trigger
    IB->>PR: Create PR<br/>(checkout issue branch)
    PR->>G: Push triggers Gate

    rect rgb(255, 243, 205)
        Note over G: Gate Workflow
        G->>G: Run lint/test/mypy
        G->>G: Check coverage
        G-->>PR: Post status<br/>(pass/fail)
    end

    rect rgb(225, 245, 255)
        Note over KL,CX: Keepalive Loop (CLI Agent)
        KL->>KL: Evaluate gate status
        KL->>KL: Check remaining tasks

        alt Gate passed & tasks remain
            KL->>KL: Route to prompt<br/>(keepalive_next_task or fix_ci_failures)
            KL->>CX: Invoke Codex
            CX->>CX: Execute task
            CX->>PR: Push changes
            PR->>G: Gate runs again
            G-->>KL: Status feedback
        else Gate failed
            KL->>KL: Route to fix_ci_failures prompt
            KL->>CX: Invoke Codex (fix mode)
            CX->>PR: Push fixes
            PR->>G: Gate runs again
        else No tasks remain
            KL->>V: Trigger verifier
        end
    end

    rect rgb(212, 237, 218)
        Note over O: Orchestrator (Scheduled)
        O->>O: Sweep idle PRs<br/>(every 15 min)
        O->>O: Check stalled PRs<br/>(no CLI agent label)
        O->>PR: Post @codex comment<br/>(UI backup agent)
    end

    rect rgb(255, 235, 205)
        Note over V: Verifier
        V->>V: Check acceptance criteria
        V->>V: Validate all tasks complete
        V->>V: Check CI passing
        alt All checks pass
            V->>PR: Label: ready-to-merge
            V->>PR: Post approval comment
        else Checks fail
            V->>PR: Post issues found
            V->>KL: Continue keepalive
        end
    end

    PR->>M: Auto-merge<br/>(if approved + CI pass)
    M->>U: PR merged notification
```

### Keepalive Decision Tree

```mermaid
graph TD
    START[Keepalive Loop Triggered] --> CHECK_LABEL{Has agent:codex<br/>label?}

    CHECK_LABEL -->|No| SKIP[Skip - Not a CLI agent PR]
    CHECK_LABEL -->|Yes| CHECK_PAUSED{Has agents:paused<br/>label?}

    CHECK_PAUSED -->|Yes| SKIP
    CHECK_PAUSED -->|No| CHECK_GATE{Gate Status?}

    CHECK_GATE -->|Failed| PROMPT_FIX[Route to fix_ci_failures.md]
    CHECK_GATE -->|Passed| CHECK_TASKS{Remaining Tasks?}

    CHECK_TASKS -->|None| TRIGGER_VERIFIER[Trigger Verifier]
    CHECK_TASKS -->|Yes| PROMPT_NEXT[Route to keepalive_next_task.md]

    PROMPT_FIX --> COMPOSE[Compose Prompt]
    PROMPT_NEXT --> COMPOSE

    COMPOSE --> INVOKE_CODEX[Invoke Codex CLI<br/>via reusable-codex-run.yml]

    INVOKE_CODEX --> CODEX_WORK[Codex Executes]

    CODEX_WORK --> PUSH[Codex Pushes Changes]

    PUSH --> GATE_RUN[Gate Workflow Runs]

    GATE_RUN --> LOOP_AGAIN{Continue Loop?}

    LOOP_AGAIN -->|Max iterations reached| PAUSE[Add agents:paused label]
    LOOP_AGAIN -->|More work to do| CHECK_GATE

    TRIGGER_VERIFIER --> VERIFY[agents-verifier.yml]
    VERIFY --> VERIFY_CHECKS{All Checks Pass?}

    VERIFY_CHECKS -->|Yes| READY[Label: ready-to-merge]
    VERIFY_CHECKS -->|No| ISSUES[Post Issues Found]
    ISSUES --> LOOP_AGAIN

    READY --> END[End - Ready for Merge]
    SKIP --> END
    PAUSE --> END

    style START fill:#e1f5ff
    style INVOKE_CODEX fill:#fff3cd
    style READY fill:#d4edda
    style SKIP fill:#f8d7da
    style PAUSE fill:#f8d7da
```

---

## Sync Mechanism

### Sync Architecture

```mermaid
graph TB
    subgraph "Workflows Repository"
        TW[Templates<br/>templates/consumer-repo/]
        SM[Sync Manifest<br/>.github/sync-manifest.yml<br/>108+ files]

        TW --> SM

        CHANGE[Template Change] --> VALIDATE[Validation CI<br/>health-70-validate-sync-manifest]
        VALIDATE -->|Pass| SYNC[Sync Workflow<br/>maint-68-sync-consumer-repos]
        VALIDATE -->|Fail| FIX[Fix Missing Files]
        FIX --> VALIDATE
    end

    subgraph "Sync Process"
        SYNC --> LOOP[For Each Consumer Repo]
        LOOP --> CLONE[Clone Consumer]
        CLONE --> COPY[Copy Files from Template]
        COPY --> COMMIT[Create Commit]
        COMMIT --> PR[Create/Update Sync PR]
    end

    subgraph "Consumer Repos"
        PR --> CI[CI Runs on Sync PR]
        CI -->|Pass| MERGE[Auto-Merge Workflow<br/>maint-71-merge-sync-prs]
        CI -->|Fail| NOTIFY[Notify in PR]

        MERGE --> CHECK{All Checks Green?}
        CHECK -->|Yes| AUTO_MERGE[Auto-Merge PR]
        CHECK -->|No| MANUAL[Manual Review Required]

        AUTO_MERGE --> APPLIED[Changes Applied]
        MANUAL --> APPLIED
    end

    style SYNC fill:#ff9800
    style VALIDATE fill:#ffc107
    style MERGE fill:#4caf50
    style AUTO_MERGE fill:#4caf50
```

### Sync Manifest Structure

```yaml
# .github/sync-manifest.yml - Single Source of Truth

workflows:
  - source: .github/workflows/agents-70-orchestrator.yml
    description: "Scheduled orchestration"
  - source: .github/workflows/agents-keepalive-loop.yml
    description: "Keepalive iteration loop"
  # ... 35 total workflow entries

prompts:
  - source: .github/codex/prompts/keepalive_next_task.md
    description: "Normal work prompt"
  # ... 6 total prompt entries

scripts:
  - source: .github/scripts/keepalive_loop.js
    description: "Main keepalive loop logic"
  # ... 80+ script entries

templates:
  - source: .github/scripts/keepalive_instruction_template.js
    description: "Prompt generation template"

docs:
  - source: docs/ci/AGENT_ISSUE_FORMAT.md
    description: "Issue template format"
  # ... 4 doc entries

codex_config:
  - source: .github/codex/AGENT_INSTRUCTIONS.md
    description: "Agent security boundaries"

copilot_config:
  - source: .github/copilot/instructions.md
    description: "Copilot instructions"
  - source: .github/copilot/skills.yml
    description: "Copilot skills"

git_config:
  - source: .gitattributes
    description: "Git merge strategies"

# Special sync modes:
sync_modes:
  create_only:
    - .github/workflows/pr-00-gate.yml  # Repos customize coverage/python
    - .github/workflows/ci.yml           # Repo-specific CI config
    - .github/dependabot.yml             # Repo-specific dependencies
```

### Validation Flow

```mermaid
graph LR
    A[Template Change] --> B[Pre-commit Hooks]
    B --> C[validate_workflow_yaml.py]
    C --> D[CI: health-70-validate-sync-manifest]

    D --> E{All Files in Manifest?}
    E -->|No| F[CI FAILS]
    E -->|Yes| G{Files Exist in Templates?}

    G -->|No| F
    G -->|Yes| H[CI PASSES]

    H --> I[Sync Allowed]
    F --> J[Fix Required]

    style F fill:#f8d7da
    style H fill:#d4edda
```

---

## Keepalive System

### Keepalive Architecture

```mermaid
graph TB
    subgraph "Triggering"
        ISSUE[Issue Created<br/>label: agent:codex] --> BRIDGE[Issue Bridge<br/>agents-63-issue-intake]
        BRIDGE --> PR[Create PR<br/>with agent:codex label]
    end

    subgraph "Keepalive Loop (CLI Agent)"
        PR --> GATE[Gate Workflow<br/>pr-00-gate.yml]
        GATE -->|Pass/Fail| LOOP[Keepalive Loop<br/>agents-keepalive-loop.yml]

        LOOP --> EVAL[Evaluate State<br/>keepalive_loop.js]

        EVAL --> GATE_CHECK{Gate Status?}
        GATE_CHECK -->|Failed| ROUTE_FIX[Route to fix_ci_failures.md]
        GATE_CHECK -->|Passed| TASK_CHECK{Tasks Remain?}

        TASK_CHECK -->|Yes| ROUTE_NEXT[Route to keepalive_next_task.md]
        TASK_CHECK -->|No| VERIFY[Trigger Verifier]

        ROUTE_FIX --> COMPOSE[Compose Prompt<br/>keepalive_prompt_composer.js]
        ROUTE_NEXT --> COMPOSE

        COMPOSE --> CODEX[Invoke Codex<br/>reusable-codex-run.yml]
        CODEX --> WORK[Codex Executes]
        WORK --> PUSH[Push Changes]
        PUSH --> GATE
    end

    subgraph "Orchestrator (UI Backup)"
        SCHED[Schedule: Every 15 min] --> ORCH[Orchestrator<br/>agents-70-orchestrator.yml]
        ORCH --> SCAN[Scan All PRs<br/>keepalive-runner.js]
        SCAN --> FILTER{Has CLI Agent Label?}
        FILTER -->|Yes| SKIP[Skip - CLI Handles]
        FILTER -->|No| IDLE{Idle > Threshold?}
        IDLE -->|Yes| POST_COMMENT[Post @codex Comment<br/>UI Agent Trigger]
        IDLE -->|No| SKIP
    end

    subgraph "Verification"
        VERIFY --> VERIFIER[Verifier Workflow<br/>agents-verifier.yml]
        VERIFIER --> CHECK_AC{Acceptance<br/>Criteria Met?}
        CHECK_AC -->|No| ISSUE_LIST[Post Issues Found]
        CHECK_AC -->|Yes| READY[Label: ready-to-merge]
        ISSUE_LIST --> LOOP
    end

    READY --> MERGE[Auto-Merge]

    style CODEX fill:#fff3cd
    style GATE fill:#e1f5ff
    style READY fill:#d4edda
```

### Prompt Routing Logic

```mermaid
graph TD
    START[Keepalive Loop Invoked] --> GET_STATE[Get PR State<br/>keepalive_state.js]

    GET_STATE --> ROUTER[Prompt Router<br/>keepalive_prompt_routing.js]

    ROUTER --> CHECK_GATE{Gate Status?}

    CHECK_GATE -->|Failed| FIX_MODE[fix_ci_failures.md]
    CHECK_GATE -->|Passed| CHECK_BOT{Bot Comments<br/>Unresolved?}

    CHECK_BOT -->|Yes| BOT_MODE[fix_bot_comments.md]
    CHECK_BOT -->|No| CHECK_CONFLICT{Merge Conflicts?}

    CHECK_CONFLICT -->|Yes| CONFLICT_MODE[fix_merge_conflicts.md]
    CHECK_CONFLICT -->|No| CHECK_AUTOFIX{Autofix Needed?}

    CHECK_AUTOFIX -->|Yes| AUTOFIX_MODE[autofix_from_ci_failure.md]
    CHECK_AUTOFIX -->|No| NORMAL_MODE[keepalive_next_task.md]

    FIX_MODE --> COMPOSE[Compose Full Prompt<br/>keepalive_prompt_composer.js]
    BOT_MODE --> COMPOSE
    CONFLICT_MODE --> COMPOSE
    AUTOFIX_MODE --> COMPOSE
    NORMAL_MODE --> COMPOSE

    COMPOSE --> ADD_CONTEXT[Add PR Context<br/>+ Gate Results<br/>+ Issue Body<br/>+ Recent Comments]

    ADD_CONTEXT --> INVOKE[Invoke Codex CLI]

    style FIX_MODE fill:#f8d7da
    style BOT_MODE fill:#fff3cd
    style CONFLICT_MODE fill:#f8d7da
    style AUTOFIX_MODE fill:#fff3cd
    style NORMAL_MODE fill:#d4edda
```

### Keepalive Contracts

```
┌─────────────────────────────────────────────────────────────────┐
│              KEEPALIVE SYSTEM CONTRACTS                          │
│  (Canonical Reference: docs/keepalive/GoalsAndPlumbing.md)      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT CONTRACTS (What keepalive loop receives):                │
│  ├─ PR body: Automated Status Summary section                   │
│  │  └─ Format: Markdown with task checkboxes                    │
│  ├─ Gate workflow results: Pass/fail status                     │
│  ├─ PR labels: agent:codex, agents:paused, etc.                 │
│  └─ Issue body: Original tasks and acceptance criteria          │
│                                                                  │
│  OUTPUT CONTRACTS (What keepalive loop produces):               │
│  ├─ Codex invocation with composed prompt                       │
│  ├─ Updated PR body (Automated Status Summary)                  │
│  ├─ Labels: agents:paused (if max iterations)                   │
│  └─ Comments: Status updates, error messages                    │
│                                                                  │
│  STATE TRANSITIONS:                                              │
│  ├─ Gate Failed → Fix CI Mode                                   │
│  ├─ Gate Passed + Tasks → Normal Work Mode                      │
│  ├─ Gate Passed + No Tasks → Verification Mode                  │
│  ├─ Max Iterations → Pause (agents:paused label)                │
│  └─ Verification Pass → Ready to Merge                          │
│                                                                  │
│  OBSERVABILITY:                                                  │
│  ├─ keepalive_metrics_collector.py: Collect metrics             │
│  ├─ keepalive_metrics_dashboard.py: Generate dashboard          │
│  └─ Metrics schema: docs/keepalive/METRICS_SCHEMA.md            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## LangChain Integration

### LangChain System Architecture

```mermaid
graph TB
    subgraph "LangChain Workflows"
        OPT[Issue Optimizer<br/>agents-issue-optimizer]
        DEC[Task Decomposer<br/>agents-issue-decompose]
        DED[Issue Dedup<br/>agents-issue-dedup]
        CAP[Capability Check<br/>agents-capability-check]
        LBL[Auto-Label<br/>agents-auto-label]
        VER[PR Verifier<br/>agents-verify-to-issue]
    end

    subgraph "Core LangChain Scripts"
        OPT --> OPT_PY[issue_optimizer.py]
        DEC --> DEC_PY[task_decomposer.py]
        DED --> DED_PY[issue_dedup.py]
        CAP --> CAP_PY[capability_check.py]
        LBL --> LBL_PY[label_matcher.py]
        VER --> VER_PY[pr_verifier.py]
    end

    subgraph "Supporting Modules"
        OPT_PY --> INT[integration_layer.py]
        DEC_PY --> INT
        DED_PY --> INT
        CAP_PY --> INT
        LBL_PY --> INT
        VER_PY --> INT

        INT --> CTX[context_extractor.py]
        INT --> SEM[semantic_matcher.py]
        INT --> FMT[issue_formatter.py]
        INT --> VAL[task_validator.py]
    end

    subgraph "LangChain Providers"
        INT --> LC[LangChain Core]
        LC --> EMBED[Embeddings API]
        LC --> LLM[LLM Provider<br/>OpenAI/GitHub Models]
        LC --> VDB[Vector DB<br/>In-Memory FAISS]
    end

    style INT fill:#ffc107
    style LC fill:#ff9800
```

### LangChain Capabilities

```
┌─────────────────────────────────────────────────────────────────┐
│              LANGCHAIN INTEGRATION CAPABILITIES                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ISSUE OPTIMIZATION (issue_optimizer.py)                         │
│  ├─ Improve issue clarity and structure                         │
│  ├─ Add missing sections (Why, Scope, Non-Goals)                │
│  ├─ Format tasks as checkboxes                                  │
│  └─ Validate against AGENT_ISSUE_TEMPLATE                       │
│                                                                  │
│  TASK DECOMPOSITION (task_decomposer.py)                         │
│  ├─ Break complex issues into smaller tasks                     │
│  ├─ Identify dependencies between tasks                         │
│  ├─ Generate sub-issues with appropriate labels                 │
│  └─ Maintain traceability (Part X of Y)                         │
│                                                                  │
│  DEDUPLICATION (issue_dedup.py)                                  │
│  ├─ Semantic similarity detection (embeddings)                  │
│  ├─ Identify duplicate/related issues                           │
│  ├─ Suggest merging or closing duplicates                       │
│  └─ Link related issues for context                             │
│                                                                  │
│  CAPABILITY CHECKING (capability_check.py)                       │
│  ├─ Assess if issue is suitable for agent automation            │
│  ├─ Identify required tools/permissions                         │
│  ├─ Flag human-only tasks                                       │
│  └─ Estimate complexity                                          │
│                                                                  │
│  AUTO-LABELING (label_matcher.py)                                │
│  ├─ Semantic label matching (embeddings)                        │
│  ├─ Apply appropriate component/priority labels                 │
│  ├─ Detect issue type (bug, feature, docs)                      │
│  └─ Suggest agent assignments                                   │
│                                                                  │
│  PR VERIFICATION (pr_verifier.py)                                │
│  ├─ Check acceptance criteria completion                        │
│  ├─ Validate PR content against issue                           │
│  ├─ Identify missing test coverage                              │
│  └─ Generate verification report                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure Tree

```
Workflows Repository
├── .github/
│   ├── workflows/ (88 workflows)
│   │   ├── reusable-*.yml (13) ────────► Called via uses:
│   │   ├── agents-*.yml (27) ──────────► SYNCED to consumers
│   │   ├── maint-*.yml (27) ───────────► Workflows-only
│   │   ├── health-*.yml (16) ──────────► Validation
│   │   ├── selftest-*.yml (2) ─────────► Self-tests
│   │   ├── pr-00-gate.yml (1) ─────────► SYNCED (create_only)
│   │   └── autofix.yml (1) ────────────► SYNCED
│   │
│   ├── actions/ (5 composite actions)
│   │   ├── autofix/
│   │   ├── python-ci-setup/
│   │   ├── build-pr-comment/
│   │   ├── codex-bootstrap-lite/
│   │   └── signature-verify/
│   │
│   ├── scripts/ (58 files - Core Infrastructure)
│   │   ├── [API & Caching] (10 files)
│   │   ├── [Keepalive System] (13 files)
│   │   ├── [Agent System] (10 files)
│   │   ├── [CI & Error Handling] (12 files)
│   │   ├── [Issue & PR Utilities] (8 files)
│   │   └── [Python Helpers] (10 files)
│   │
│   ├── codex/
│   │   ├── prompts/ (6 prompt files)
│   │   │   ├── keepalive_next_task.md
│   │   │   ├── fix_ci_failures.md
│   │   │   ├── fix_bot_comments.md
│   │   │   ├── fix_merge_conflicts.md
│   │   │   ├── autofix_from_ci_failure.md
│   │   │   └── verifier_acceptance_check.md
│   │   └── AGENT_INSTRUCTIONS.md
│   │
│   ├── sync-manifest.yml ──────────────► Single source of truth (108+ files)
│   ├── copilot/
│   │   ├── instructions.md
│   │   └── skills.yml
│   └── ISSUE_TEMPLATE/
│       ├── agent_task.yml
│       └── config.yml
│
├── scripts/ (67+ files - Higher-Level Operations)
│   ├── [Core CI/Metrics] (10 files)
│   ├── langchain/ (13 files)
│   │   ├── capability_check.py
│   │   ├── issue_optimizer.py
│   │   ├── task_decomposer.py
│   │   ├── issue_dedup.py
│   │   ├── pr_verifier.py
│   │   └── [8 more LangChain modules]
│   ├── [Validation & Analysis] (15 files)
│   ├── [Keepalive & Metrics] (10 files)
│   └── [Maintenance] (12 files)
│
├── templates/consumer-repo/
│   ├── .github/
│   │   ├── workflows/ (34 workflow templates)
│   │   ├── scripts/ (80+ script templates)
│   │   ├── codex/ (6 prompts + AGENT_INSTRUCTIONS)
│   │   ├── copilot/ (instructions + skills)
│   │   └── ISSUE_TEMPLATE/
│   ├── scripts/langchain/ (13 LangChain helpers)
│   ├── config/
│   │   └── coverage-baseline.json.example
│   └── docs/
│       ├── ci/AGENT_ISSUE_FORMAT.md
│       └── [Other documentation]
│
├── docs/ (91+ files)
│   ├── README.md
│   ├── STRUCTURE.md
│   ├── INTEGRATION_GUIDE.md
│   ├── ci/ (16 files)
│   ├── keepalive/ (10 files)
│   │   ├── GoalsAndPlumbing.md ────────► Canonical keepalive reference
│   │   ├── SETUP_CHECKLIST.md
│   │   └── Agents.md
│   ├── ops/ (15+ files)
│   ├── plans/ (10+ files)
│   ├── guides/ (8+ files)
│   ├── templates/ (5 files)
│   └── archive/ (20+ files)
│
├── config/
│   ├── coverage-baseline.json
│   ├── labels-core.yml
│   └── labels.yml
│
├── CLAUDE.md ──────────────────────────► Project instructions
├── README.md
├── pyproject.toml ─────────────────────► Python config (line-length: 100)
├── .gitignore
├── .gitattributes
└── [Standard repo files]

Statistics:
├── 88 workflow files (~36,262 lines of YAML)
├── 125+ script files (58 in .github/scripts/, 67+ in scripts/)
├── 54 test files
├── 91+ documentation files
├── 6 Codex prompts
├── 5 GitHub Actions
└── 108+ files in sync manifest
```

---

## Data Flow Diagrams

### 1. Issue to PR Creation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant GH as GitHub
    participant IB as Issue Bridge
    participant OWNR as Owner PAT
    participant PR as Pull Request

    U->>GH: Create Issue
    U->>GH: Add label: agent:codex

    GH->>IB: Webhook: issues.labeled

    IB->>IB: Validate issue format
    IB->>IB: Check required sections

    IB->>OWNR: Auth as owner
    OWNR->>GH: Create branch<br/>(codex/issue-XXX)

    IB->>GH: Clone repo
    IB->>GH: Checkout new branch
    IB->>GH: Create placeholder commit
    IB->>GH: Push branch

    OWNR->>GH: Create PR<br/>(on behalf of owner)

    GH->>PR: PR created
    PR->>GH: Trigger pr-00-gate.yml

    Note over PR: Gate runs lint/test/mypy

    GH->>IB: PR created webhook
    IB->>PR: Add labels from issue
    IB->>PR: Update PR body with<br/>Automated Status Summary

    PR->>U: PR ready notification
```

### 2. Gate Workflow Data Flow

```mermaid
graph LR
    A[PR Push] --> B[pr-00-gate.yml]

    B --> C{Docs-Only?}
    C -->|Yes| SKIP[Skip Tests]
    C -->|No| FULL[Full CI]

    FULL --> D[Detect Changes<br/>detect-changes.js]
    D --> E[Python CI Setup<br/>python-ci-setup action]

    E --> F[Lint & Format Check]
    F --> G[Run Tests]
    G --> H[Type Check: mypy]
    H --> I[Coverage Analysis]

    I --> J[Coverage Delta<br/>ci_coverage_delta.py]
    J --> K{Coverage OK?}

    K -->|No| FAIL[Gate FAILS]
    K -->|Yes| PASS[Gate PASSES]

    F --> FAIL
    G --> FAIL
    H --> FAIL

    SKIP --> PASS

    PASS --> L[Post Status<br/>✅ Gate Success]
    FAIL --> M[Post Status<br/>❌ Gate Failed]

    M --> N[Post Comment<br/>Failure Details]

    L --> O[Update Check Status<br/>Keepalive can proceed]
    N --> P[Update Check Status<br/>Keepalive will fix]

    style PASS fill:#d4edda
    style FAIL fill:#f8d7da
```

### 3. Codex Invocation Data Flow

```mermaid
sequenceDiagram
    participant KL as Keepalive Loop
    participant PS as Prompt System
    participant GH as GitHub API
    participant CX as Codex CLI
    participant R as Repository

    KL->>PS: Request prompt routing
    PS->>PS: keepalive_prompt_routing.js<br/>Determine prompt type

    PS->>GH: Fetch PR context
    GH-->>PS: PR body, files, comments

    PS->>GH: Fetch gate results
    GH-->>PS: CI status, logs

    PS->>GH: Fetch issue body
    GH-->>PS: Original tasks, criteria

    PS->>PS: keepalive_prompt_composer.js<br/>Compose full prompt

    PS->>CX: Invoke with prompt

    Note over CX: Codex executes<br/>Reads code<br/>Makes changes

    CX->>R: Checkout branch
    CX->>R: Apply changes
    CX->>R: Create commit
    CX->>R: Push to remote

    R->>GH: Push event
    GH->>KL: Gate triggered

    KL->>GH: Check gate status
    GH-->>KL: Status + logs

    KL->>GH: Update PR body<br/>(Automated Status Summary)

    KL->>KL: Evaluate next iteration
```

### 4. Sync Process Data Flow

```mermaid
sequenceDiagram
    participant DEV as Developer
    participant WF as Workflows Repo
    participant VAL as Validation CI
    participant SYNC as Sync Workflow
    participant CR as Consumer Repo
    participant MERGE as Auto-Merge

    DEV->>WF: Modify template file
    DEV->>WF: Push to branch

    WF->>VAL: Trigger validation<br/>health-70-validate-sync-manifest

    VAL->>VAL: Check all files in manifest
    VAL->>VAL: Check manifest completeness

    alt Validation Fails
        VAL-->>DEV: ❌ Missing files in manifest
        DEV->>WF: Add files to manifest
        WF->>VAL: Re-trigger validation
    end

    VAL-->>WF: ✅ Validation passes

    DEV->>WF: Merge to main

    WF->>SYNC: Trigger maint-68-sync-consumer-repos

    loop For Each Consumer Repo
        SYNC->>CR: Clone consumer repo
        SYNC->>CR: Checkout sync branch
        SYNC->>CR: Copy files from template
        SYNC->>CR: Create commit
        SYNC->>CR: Push sync branch
        SYNC->>CR: Create/update sync PR
    end

    SYNC-->>WF: Report sync status

    CR->>CR: CI runs on sync PR

    alt CI Passes
        MERGE->>CR: Auto-merge PR
        CR-->>WF: ✅ Sync complete
    else CI Fails
        CR-->>WF: ❌ Manual review needed
    end
```

### 5. Agent Routing Data Flow

```mermaid
graph TD
    START[Issue/PR Event] --> ROUTER[Agent Router<br/>agents_orchestrator_resolve.js]

    ROUTER --> CHECK_LABEL{Has agent:<br/>label?}

    CHECK_LABEL -->|No| DEFAULT[No Agent]
    CHECK_LABEL -->|Yes| EXTRACT[Extract Agent Type]

    EXTRACT --> TYPE{Agent Type?}

    TYPE -->|agent:codex| CODEX[Codex CLI<br/>Via keepalive loop]
    TYPE -->|agent:verifier| VERIFIER[Verifier Workflow<br/>agents-verifier.yml]
    TYPE -->|agent:langchain| LANGCHAIN[LangChain Workflow<br/>agents-issue-optimizer.yml]
    TYPE -->|agent:autopilot| AUTOPILOT[Auto-Pilot Workflow<br/>agents-auto-pilot.yml]

    CODEX --> CODEX_WORK[Execute Codex]
    VERIFIER --> VERIFY_WORK[Execute Verification]
    LANGCHAIN --> LANG_WORK[Execute LangChain]
    AUTOPILOT --> AUTO_WORK[Execute Auto-Pilot]

    CODEX_WORK --> RESULT[Return Result]
    VERIFY_WORK --> RESULT
    LANG_WORK --> RESULT
    AUTO_WORK --> RESULT

    DEFAULT --> RESULT

    style CODEX fill:#fff3cd
    style VERIFIER fill:#e1f5ff
    style LANGCHAIN fill:#d4edda
    style AUTOPILOT fill:#f8d7da
```

---

## Consumer Repo Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                      CONSUMER REPO                              │
│               (e.g., Travel-Plan-Permission)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SYNCED FROM WORKFLOWS REPO (via maint-68):                     │
│  ├─ .github/workflows/agents-*.yml (27 workflows)               │
│  ├─ .github/scripts/*.js (48 files)                             │
│  ├─ .github/scripts/*.py (10 files)                             │
│  ├─ scripts/langchain/*.py (13 files)                           │
│  ├─ .github/codex/prompts/*.md (6 files)                        │
│  ├─ .github/codex/AGENT_INSTRUCTIONS.md                         │
│  └─ docs/ci/AGENT_ISSUE_FORMAT.md                               │
│                                                                  │
│  CALLS REUSABLE WORKFLOWS (from Workflows repo):                │
│  ├─ stranske/Workflows/.github/workflows/reusable-10-ci-python.yml@v1
│  ├─ stranske/Workflows/.github/workflows/reusable-codex-run.yml@v1
│  ├─ stranske/Workflows/.github/workflows/reusable-agents-verifier.yml@v1
│  └─ [10 more reusable workflows]                               │
│                                                                  │
│  LOCAL CUSTOMIZATIONS (NOT synced):                             │
│  ├─ .github/workflows/ci.yml ─────► Repo-specific CI config     │
│  ├─ .github/workflows/pr-00-gate.yml* ► Customizable gate       │
│  ├─ README.md ─────────────────────► Repo-specific docs         │
│  ├─ .gitignore ────────────────────► Repo-specific patterns     │
│  ├─ config/coverage-baseline.json ─► Per-repo coverage baseline │
│  └─ autofix-versions.env ──────────► Dependency versions        │
│                                                                  │
│  * = Synced with create_only mode (initial only, not overwritten)
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ uses:
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WORKFLOWS REPO (v1 Tag)                       │
├─────────────────────────────────────────────────────────────────┤
│  REUSABLE WORKFLOWS (called via uses:):                         │
│  └─ stranske/Workflows/.github/workflows/reusable-*.yml@v1      │
│                                                                  │
│  These are NOT copied to consumer repos.                        │
│  They are REFERENCED and executed in Workflows repo context.    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Insights Summary

### 1. Two-Level Architecture

**Reusable Workflows (13)**: Called via `uses:`, NOT synced
- CI orchestration (Python, Node, Docker)
- Agent execution framework
- Orchestrator infrastructure
- PR management utilities

**Synced Workflows (29)**: Copied to consumer repos, run locally
- Agent workflows (orchestrator, keepalive, verifier)
- Codex belt system
- LangChain integrations
- CI gate and autofix

### 2. Sync Policy Enforcement

**Single Source of Truth**: `.github/sync-manifest.yml`
- 108+ files tracked
- Validation CI prevents incomplete syncs
- Auto-merge workflow ensures consistency
- Drift detection catches desync

### 3. Keepalive System Design

**CLI Agent Primary**: Workflow-based automation
- Triggered by labels, not comments
- Prompt routing based on state
- Gate-aware execution
- Automatic verification

**UI Agent Backup**: Comment-based (@codex)
- Orchestrator posts comments for idle PRs
- Skips PRs with CLI agent labels
- Manual intervention fallback

### 4. LangChain Integration

**13 Python modules** for semantic analysis:
- Issue optimization and decomposition
- Deduplication via embeddings
- Capability checking
- Auto-labeling
- PR verification

### 5. Metrics & Observability

**Comprehensive tracking**:
- Ledger system for metadata
- Coverage delta calculation
- Keepalive metrics collection
- Weekly aggregation and dashboard
- Autopilot step timing

### 6. Security Boundaries

**Defense in depth**:
- Prompt injection guards
- Prompt integrity verification
- CI signature validation
- GitHub App auth (preferred)
- Token load balancing

---

## Visual Legend

```
Color Coding Used in Diagrams:
├─ 🟦 Blue (#e1f5ff) ────► Reusable workflows
├─ 🟨 Yellow (#fff3cd) ───► Agent system / Codex
├─ 🟩 Green (#d4edda) ────► Success / Maintenance
├─ 🟥 Red (#f8d7da) ──────► Health checks / Errors
├─ 🟧 Orange (#ff9800) ───► Sync operations
└─ 🟫 Amber (#ffc107) ────► Configuration / Manifest
```

---

## Quick Reference

### Most Important Files

| File | Purpose |
|------|---------|
| `.github/sync-manifest.yml` | Single source of truth for sync |
| `.github/workflows/reusable-codex-run.yml` | Codex agent execution |
| `.github/scripts/keepalive_loop.js` | Main keepalive logic |
| `scripts/langchain/integration_layer.py` | LangChain integration |
| `docs/keepalive/GoalsAndPlumbing.md` | Canonical keepalive design |
| `CLAUDE.md` | Project instructions and guidelines |

### Most Important Workflows

| Workflow | Frequency | Purpose |
|----------|-----------|---------|
| `pr-00-gate.yml` | Every push | CI validation gate |
| `agents-keepalive-loop.yml` | After gate | Codex CLI iteration |
| `agents-70-orchestrator.yml` | Every 15 min | Sweep idle PRs |
| `maint-68-sync-consumer-repos.yml` | On template change | Sync to consumers |
| `health-70-validate-sync-manifest.yml` | Every push | Validate manifest |

### Consumer Repos

| Repo | Status | Notes |
|------|--------|-------|
| Travel-Plan-Permission | Reference | Gold standard |
| Manager-Database | Consumer | Has custom ci.yml |
| Template | Consumer | Minimal Python template |
| trip-planner | Consumer | Has custom ci.yml |

---

## Related Documentation

- [Repository Structure](STRUCTURE.md) - Detailed file organization
- [Integration Guide](INTEGRATION_GUIDE.md) - How to integrate consumer repos
- [Keepalive System](keepalive/GoalsAndPlumbing.md) - Canonical keepalive design
- [CI System](ci/WORKFLOWS.md) - Workflow reference
- [CLAUDE.md](../CLAUDE.md) - Project instructions (READ THIS FIRST)

---

**Last Updated**: 2026-01-26
**Maintainer**: stranske organization
**Status**: Living document - updated with codebase changes
