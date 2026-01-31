# Unified Agent System Architecture

> **Single workflow to rule them all** - Add new AI agents without duplicating code.

## Overview

The Unified Agent System provides a pluggable architecture for running any AI agent (Codex, Claude, Gemini, or future agents) through a single reusable workflow.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED AGENT ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │     .github/agents/registry.yml │
                    │     (Configuration Hub)         │
                    │                                 │
                    │  • Agent definitions            │
                    │  • Secret requirements          │
                    │  • Error patterns               │
                    │  • Prompt mappings              │
                    └───────────────┬─────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ .github/actions │      │ .github/actions │      │ .github/actions │
│ /setup-codex    │      │ /setup-claude   │      │ /setup-gemini   │
│                 │      │                 │      │                 │
│ Agent-specific  │      │ Agent-specific  │      │ Agent-specific  │
│ setup steps     │      │ setup steps     │      │ setup steps     │
└────────┬────────┘      └────────┬────────┘      └────────┬────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────┐
                    │   reusable-agent-run.yml        │
                    │   (SINGLE Unified Workflow)     │
                    │                                 │
                    │   1. Load registry              │
                    │   2. Detect agent from labels   │
                    │   3. Validate secrets           │
                    │   4. Run setup action           │
                    │   5. Execute agent CLI          │
                    │   6. Push results               │
                    └───────────────┬─────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────┐
                    │   .github/scripts/              │
                    │   agent-router.js               │
                    │                                 │
                    │   • detectAgent()               │
                    │   • getAgentConfig()            │
                    │   • validateSecrets()           │
                    │   • hasCliAgentLabel()          │
                    └─────────────────────────────────┘
```

## Key Components

### 1. Agent Registry (`registry.yml`)

Central configuration file defining all supported agents:

```yaml
# .github/agents/registry.yml
agents:
  claude:
    name: "Claude"
    label: "agent:claude"
    cli: "claude"
    execution_mode: "cli"
    secrets:
      required:
        - AWS_ACCESS_KEY_ID
        - AWS_SECRET_ACCESS_KEY
        - AWS_REGION
    timeout_minutes: 45
```

### 2. Setup Actions

Each agent has a composite action for environment setup:

```
.github/actions/
├── setup-codex/action.yml    # OpenAI/Codex setup
├── setup-claude/action.yml   # AWS Bedrock setup
└── setup-gemini/action.yml   # Google AI setup
```

### 3. Unified Workflow

Single workflow that handles any agent:

```yaml
# Calling the unified workflow
jobs:
  run-agent:
    uses: stranske/Workflows/.github/workflows/reusable-agent-run.yml@v1
    with:
      pr_number: "123"
      # agent_type auto-detected from labels, or specify explicitly:
      # agent_type: "claude"
      prompt_context: "keepalive"
    secrets: inherit
```

### 4. Agent Router Script

JavaScript utility for routing logic:

```javascript
const { detectAgent, getAgentConfig } = require('./agent-router.js');

// Auto-detect from PR labels
const result = await detectAgent(github, context, prNumber);
console.log(result.agentId);  // "claude"
console.log(result.agentConfig.execution_mode);  // "cli"
```

## How to Add a New Agent

### Step 1: Add to Registry

```yaml
# .github/agents/registry.yml
agents:
  # ... existing agents ...

  my_new_agent:
    name: "My New Agent"
    label: "agent:my-new-agent"
    cli: "my-agent-cli"
    cli_install: "npm install -g my-agent-cli"
    execution_mode: "cli"  # or "github-app"
    secrets:
      required:
        - MY_AGENT_API_KEY
      optional:
        - MY_AGENT_MODEL
    env:
      MY_AGENT_API_KEY: "${{ secrets.MY_AGENT_API_KEY }}"
    timeout_minutes: 30
    capabilities:
      - code_generation
      - bug_fixing
```

### Step 2: Create Setup Action

```yaml
# .github/actions/setup-my-new-agent/action.yml
name: 'Setup My New Agent'
description: 'Installs and configures My New Agent CLI'

inputs:
  my_agent_api_key:
    required: true

runs:
  using: 'composite'
  steps:
    - name: Install CLI
      shell: bash
      run: npm install -g my-agent-cli

    - name: Configure auth
      shell: bash
      env:
        MY_AGENT_API_KEY: ${{ inputs.my_agent_api_key }}
      run: |
        echo "MY_AGENT_API_KEY=${MY_AGENT_API_KEY}" >> "$GITHUB_ENV"
```

### Step 3: Add Error Patterns (Optional)

```yaml
# In registry.yml
error_patterns:
  my_new_agent:
    rate_limit: "rate limit|too many requests"
    auth_failure: "unauthorized|invalid key"
    timeout: "timeout|timed out"
```

### Step 4: Add Secrets to Consumer Repos

```bash
# For each consumer repo
gh secret set MY_AGENT_API_KEY --repo owner/consumer-repo
```

### Step 5: Use the Agent

```yaml
# Apply label to PR
gh pr edit 123 --add-label "agent:my-new-agent"

# Or call directly
jobs:
  run:
    uses: stranske/Workflows/.github/workflows/reusable-agent-run.yml@v1
    with:
      pr_number: "123"
      agent_type: "my_new_agent"
    secrets: inherit
```

## Migration Guide

### Before (Duplicated Workflows)

```yaml
# agents-keepalive-loop.yml (905 lines)
jobs:
  run-codex:
    if: contains(needs.evaluate.outputs.agent_type, 'codex')
    uses: ./.github/workflows/reusable-codex-run.yml
    # ... 50 lines of Codex-specific config ...

  run-claude:
    if: contains(needs.evaluate.outputs.agent_type, 'claude')
    uses: ./.github/workflows/reusable-claude-run.yml
    # ... 50 lines of Claude-specific config (mostly identical) ...

  run-gemini:
    if: contains(needs.evaluate.outputs.agent_type, 'gemini')
    uses: ./.github/workflows/reusable-gemini-run.yml
    # ... 50 lines of Gemini-specific config (mostly identical) ...
```

### After (Unified Workflow)

```yaml
# agents-keepalive-loop.yml (simplified)
jobs:
  run-agent:
    needs: evaluate
    if: needs.evaluate.outputs.action == 'dispatch_agent'
    uses: ./.github/workflows/reusable-agent-run.yml
    with:
      pr_number: ${{ needs.evaluate.outputs.pr_number }}
      # Agent auto-detected from labels!
      prompt_context: ${{ needs.evaluate.outputs.prompt_mode }}
    secrets: inherit
```

## Comparison: Old vs New

| Aspect | Old (Per-Agent) | New (Unified) |
|--------|-----------------|---------------|
| Workflows | 3+ (one per agent) | 1 |
| Lines of code | ~3000+ | ~500 |
| Add new agent | Copy & modify workflow | Add to registry |
| Bug fix | Fix in N workflows | Fix once |
| Consistency | Manual alignment | Guaranteed |
| Testing | Test each workflow | Test one workflow |

## File Inventory

```
.github/
├── agents/
│   └── registry.yml           # Agent configuration (NEW)
├── actions/
│   ├── setup-codex/           # Codex setup (NEW)
│   │   └── action.yml
│   ├── setup-claude/          # Claude setup (NEW)
│   │   └── action.yml
│   └── setup-gemini/          # Gemini setup (NEW)
│       └── action.yml
├── scripts/
│   └── agent-router.js        # Routing logic (NEW)
└── workflows/
    ├── reusable-agent-run.yml # Unified workflow (NEW)
    ├── reusable-codex-run.yml # Legacy (can deprecate)
    └── reusable-claude-run.yml# Legacy (can deprecate)
```

## Benefits

1. **Zero-duplication** - Single workflow handles all agents
2. **Easy extension** - Add agent in registry, not by copying workflows
3. **Consistent behavior** - All agents follow identical patterns
4. **Centralized config** - Change settings in one place
5. **Better testing** - Test one workflow, not N workflows
6. **Cleaner codebase** - Fewer files, less maintenance

## Execution Modes

The system supports two execution modes:

### CLI Mode (`execution_mode: "cli"`)
- Agent runs directly in GitHub Actions runner
- Uses installed CLI tool (claude, gemini, etc.)
- Secrets passed via environment variables
- Used by: Claude, Gemini

### GitHub App Mode (`execution_mode: "github-app"`)
- Agent triggered via PR assignment
- External service (chatgpt-codex-connector) handles execution
- No CLI installation needed
- Used by: Codex

## Prompts

Prompts are mapped in the registry:

```yaml
prompts:
  base_path: ".github/codex/prompts"
  contexts:
    keepalive: "keepalive_next_task.md"
    ci_fix: "fix_ci_failures.md"
    bot_comments: "fix_bot_comments.md"
```

Use via workflow input:
```yaml
with:
  prompt_context: "ci_fix"  # Uses fix_ci_failures.md
```

Or override with custom file:
```yaml
with:
  prompt_file: "path/to/custom_prompt.md"
```

## Making Workflows Dynamic (Registry-Driven)

When workflows are hardcoded for specific agents, they need updating every time you add a new agent. The solution is to make them **registry-driven**.

### Pattern: Dynamic Label Detection

Instead of:
```yaml
# ❌ HARDCODED - needs update for each new agent
jobs:
  my-job:
    if: github.event.label.name == 'agent:codex'
```

Use this pattern:
```yaml
# ✅ DYNAMIC - reads from registry
jobs:
  check-agent-label:
    runs-on: ubuntu-latest
    outputs:
      is_agent_label: ${{ steps.check.outputs.is_agent_label }}
      agent_id: ${{ steps.check.outputs.agent_id }}
      agent_name: ${{ steps.check.outputs.agent_name }}
      agent_label: ${{ steps.check.outputs.agent_label }}
    steps:
      - name: Checkout for registry
        uses: actions/checkout@v6
        with:
          sparse-checkout: .github/agents/registry.yml

      - name: Check if label is an agent label
        id: check
        uses: actions/github-script@v8
        with:
          script: |
            const fs = require('fs');
            const yaml = require('js-yaml');

            const labelName = context.payload.label?.name || '';

            // Load registry
            const content = fs.readFileSync('.github/agents/registry.yml', 'utf8');
            const registry = yaml.load(content);

            // Check if label matches any agent
            for (const [agentId, config] of Object.entries(registry.agents)) {
              if (config.label === labelName) {
                core.setOutput('is_agent_label', 'true');
                core.setOutput('agent_id', agentId);
                core.setOutput('agent_name', config.name);
                core.setOutput('agent_label', labelName);
                return;
              }
            }

            core.setOutput('is_agent_label', 'false');

  main-job:
    needs: check-agent-label
    if: needs.check-agent-label.outputs.is_agent_label == 'true'
    # Now use outputs: ${{ needs.check-agent-label.outputs.agent_id }}
```

### Pattern: Dynamic Label Removal

Instead of:
```yaml
# ❌ HARDCODED
- name: Remove label
  run: gh issue edit $NUMBER --remove-label "agent:codex"
```

Use:
```yaml
# ✅ DYNAMIC
- name: Remove label
  env:
    AGENT_LABEL: ${{ needs.check-agent-label.outputs.agent_label }}
  run: gh issue edit $NUMBER --remove-label "$AGENT_LABEL"
```

### Pattern: Dynamic Comments

Instead of:
```yaml
# ❌ HARDCODED
body: "Codex cannot complete this issue"
```

Use:
```yaml
# ✅ DYNAMIC
body: "${{ needs.check-agent-label.outputs.agent_name }} cannot complete this issue"
```

### Files Already Converted

| File | Status |
|------|--------|
| `agents-capability-check.yml` | ✅ Dynamic |
| `reusable-agent-run.yml` | ✅ Dynamic (new) |
| `reusable-bot-comment-handler.yml` | ✅ Dynamic |

### Files To Convert

| File | Pattern Needed |
|------|----------------|
| `agents-autofix-loop.yml` | Label detection + agent routing |
| `agents-auto-pilot.yml` | Label detection + agent routing |
| `agents-71-belt-dispatcher.yml` | Label detection + agent routing |
| `agents-keepalive-loop.yml` | Already uses evaluate job, add registry check |

### Fallback Behavior

The registry check includes a fallback for unknown agents:

```javascript
// If label has agent: prefix but isn't in registry, still process it
if (labelName.startsWith('agent:')) {
  const agentId = labelName.replace('agent:', '');
  core.setOutput('is_agent_label', 'true');
  core.setOutput('agent_id', agentId);
  // ...
}
```

This allows experimentation with new agents before formally adding them to the registry.
