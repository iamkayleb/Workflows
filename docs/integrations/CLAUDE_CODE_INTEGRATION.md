# Claude Code Integration Guide

This document describes the integration of Claude Code as a second AI agent in the Workflows repository, running alongside Codex via Amazon Bedrock.

## Overview

Claude Code is integrated as an alternative AI coding agent that can be assigned to issues using the `agent:claude` label. It uses Amazon Bedrock for inference instead of the Anthropic API directly.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Issue with Label                              │
│         agent:codex  OR  agent:claude                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              agents-keepalive-loop.yml                          │
│                                                                  │
│  ┌─────────────┐    ┌─────────────────────────────────────┐    │
│  │  evaluate   │───▶│  Determines agent_type from labels  │    │
│  └─────────────┘    └─────────────────────────────────────┘    │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Conditional Job Routing                     │    │
│  │                                                          │    │
│  │  if agent_type == 'codex'  ──▶  run-codex job           │    │
│  │  if agent_type == 'claude' ──▶  run-claude job          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│ reusable-codex-run.yml  │     │ reusable-claude-run.yml │
│                         │     │                         │
│  - CODEX_AUTH_JSON      │     │  - AWS_ACCESS_KEY_ID    │
│  - Codex CLI            │     │  - AWS_SECRET_ACCESS_KEY│
│  - OpenAI backend       │     │  - Amazon Bedrock       │
└─────────────────────────┘     └─────────────────────────┘
```

## Files Created/Modified

### 1. Reusable Claude Workflow

**File:** `.github/workflows/reusable-claude-run.yml`

The core workflow that executes Claude Code via Amazon Bedrock. Features include:

- **AWS Authentication**: Uses AWS credentials for Bedrock access
- **Claude Code CLI**: Installs and configures Claude Code with Bedrock backend
- **Fallback Mechanism**: Falls back to direct boto3 API calls if CLI fails
- **Session Analysis**: Analyzes Claude's output for task completion
- **LLM Task Analysis**: Uses LLM to determine if tasks are complete
- **Completion Checkpoints**: Posts progress comments to PRs
- **Error Classification**: Classifies failures as transient vs non-transient
- **Error Diagnostics**: Creates artifacts for debugging
- **Attention Labels**: Adds `agent:needs-attention` on non-transient failures

**Key Inputs:**
```yaml
inputs:
  pr_number:
    description: 'PR number to work on'
    required: true
  action:
    description: 'Action type: run, fix, or conflict'
    required: true
  repository:
    description: 'Repository in owner/repo format'
    required: true
```

**Required Secrets:**
```yaml
secrets:
  AWS_ACCESS_KEY_ID:
    required: true   # AWS authentication for Bedrock
  AWS_SECRET_ACCESS_KEY:
    required: true   # AWS authentication for Bedrock
  AWS_SESSION_TOKEN:
    required: false  # Only needed for assumed roles/SSO
  WORKFLOWS_APP_ID:
    required: false  # GitHub App auth (recommended)
  WORKFLOWS_APP_PRIVATE_KEY:
    required: false  # GitHub App auth (recommended)
```

### 2. Keepalive Loop Integration

**File:** `.github/workflows/agents-keepalive-loop.yml`

Added the `run-claude` job for conditional routing:

```yaml
run-claude:
  name: Keepalive next task (Claude)
  needs:
    - evaluate
    - mark-running
  if: |
    needs.evaluate.outputs.agent_type == 'claude' &&
    (needs.evaluate.outputs.action == 'run' ||
     needs.evaluate.outputs.action == 'fix' ||
     needs.evaluate.outputs.action == 'conflict')
  uses: stranske/Workflows/.github/workflows/reusable-claude-run.yml@main
  secrets:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    AWS_SESSION_TOKEN: ${{ secrets.AWS_SESSION_TOKEN }}
    WORKFLOWS_APP_ID: ${{ secrets.WORKFLOWS_APP_ID }}
    WORKFLOWS_APP_PRIVATE_KEY: ${{ secrets.WORKFLOWS_APP_PRIVATE_KEY }}
```

Updated the `summary` job to handle outputs from either agent:

```yaml
summary:
  needs:
    - evaluate
    - run-codex
    - run-claude
  if: always()
```

### 3. Labels Configuration

**File:** `.github/labels.yml`

Added two new labels:

```yaml
- name: "agent:claude"
  color: "d4a017"
  description: "Assign to Claude agent (via Amazon Bedrock)"

- name: "from:claude"
  color: "d4a017"
  description: "PR was created by or for Claude"
```

### 4. Consumer Repo Templates

**Files copied to `templates/consumer-repo/`:**
- `.github/labels.yml` - For label sync
- `.github/workflows/agents-keepalive-loop.yml` - For workflow sync

## Secrets Reference

This section explains all secrets used by the agent system, their purposes, and requirements.

### Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECRET CATEGORIES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐     ┌─────────────────────┐            │
│  │   AI BACKEND        │     │   GITHUB ACCESS     │            │
│  │   (Choose One)      │     │   (Choose One)      │            │
│  ├─────────────────────┤     ├─────────────────────┤            │
│  │ For Codex:          │     │ Option A:           │            │
│  │  • CODEX_AUTH_JSON  │     │  • WORKFLOWS_APP_ID │            │
│  │                     │     │  • WORKFLOWS_APP_   │            │
│  │ For Claude:         │     │    PRIVATE_KEY      │            │
│  │  • AWS_ACCESS_KEY_ID│     │                     │            │
│  │  • AWS_SECRET_      │     │ Option B:           │            │
│  │    ACCESS_KEY       │     │  • SERVICE_BOT_PAT  │            │
│  │  • AWS_SESSION_     │     │                     │            │
│  │    TOKEN (optional) │     │                     │            │
│  └─────────────────────┘     └─────────────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### AI Backend Secrets

These authenticate with the AI service. **They are NOT interchangeable** - each agent requires its specific backend.

#### For Claude (Amazon Bedrock)

| Secret | Purpose | Required |
|--------|---------|----------|
| `AWS_ACCESS_KEY_ID` | Identifies the AWS IAM user/role | **Yes** |
| `AWS_SECRET_ACCESS_KEY` | Authenticates the AWS IAM user/role | **Yes** |
| `AWS_SESSION_TOKEN` | Temporary credential token | **No** (see below) |

**When is `AWS_SESSION_TOKEN` needed?**

| Credential Type | SESSION_TOKEN Required |
|-----------------|------------------------|
| IAM User (long-term) | No |
| IAM Role (assumed via STS) | Yes |
| AWS SSO / Identity Center | Yes |
| EC2 Instance Role | No (handled by SDK) |

**AWS IAM Policy Required:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
      ]
    }
  ]
}
```

#### For Codex (OpenAI)

| Secret | Purpose | Required |
|--------|---------|----------|
| `CODEX_AUTH_JSON` | ChatGPT subscription authentication | **Yes** for Codex |

**Not interchangeable with AWS credentials.** Codex uses OpenAI's API, Claude uses AWS Bedrock.

### GitHub Access Secrets

These allow the workflow to interact with GitHub (post comments, push commits, manage labels). **Choose ONE method** - they ARE interchangeable.

#### Option A: GitHub App (Recommended)

| Secret | Purpose | Required |
|--------|---------|----------|
| `WORKFLOWS_APP_ID` | GitHub App installation ID | **Yes** (if using App) |
| `WORKFLOWS_APP_PRIVATE_KEY` | GitHub App private key (PEM format) | **Yes** (if using App) |

**Benefits:**
- Higher rate limits (5,000 requests/hour per installation)
- Better audit trail (actions attributed to App)
- Granular permissions per repository
- No personal account dependency

**Optional dedicated keepalive pool:**

| Secret | Purpose |
|--------|---------|
| `KEEPALIVE_APP_ID` | Separate App for keepalive (isolates rate limits) |
| `KEEPALIVE_APP_PRIVATE_KEY` | Private key for keepalive App |

If not set, falls back to `WORKFLOWS_APP_*`.

#### Option B: Personal Access Token

| Secret | Purpose | Required |
|--------|---------|----------|
| `SERVICE_BOT_PAT` | GitHub PAT with repo permissions | **Yes** (if not using App) |

**Required PAT scopes:**
- `repo` - Full repository access
- `workflow` - Workflow management (if modifying workflows)

**Drawbacks:**
- Lower rate limits (5,000 requests/hour total)
- Tied to a personal account
- Less granular permissions

### Summary Table

| Secret | Used By | Purpose | Required When |
|--------|---------|---------|---------------|
| `AWS_ACCESS_KEY_ID` | Claude | AWS authentication | Using Claude agent |
| `AWS_SECRET_ACCESS_KEY` | Claude | AWS authentication | Using Claude agent |
| `AWS_SESSION_TOKEN` | Claude | Temporary AWS creds | Using assumed roles/SSO |
| `CODEX_AUTH_JSON` | Codex | OpenAI authentication | Using Codex agent |
| `WORKFLOWS_APP_ID` | Both | GitHub App auth | Using GitHub App |
| `WORKFLOWS_APP_PRIVATE_KEY` | Both | GitHub App auth | Using GitHub App |
| `SERVICE_BOT_PAT` | Both | GitHub PAT auth | Not using GitHub App |

### Are They Interchangeable?

| Category | Interchangeable? | Notes |
|----------|------------------|-------|
| AWS vs CODEX credentials | **No** | Different AI backends entirely |
| GitHub App vs PAT | **Yes** | Both provide GitHub access |
| KEEPALIVE_APP vs WORKFLOWS_APP | **Yes** | KEEPALIVE is optional isolation |

### Minimum Configuration

**For Claude only:**
```yaml
# Required
AWS_ACCESS_KEY_ID: "AKIA..."
AWS_SECRET_ACCESS_KEY: "..."

# Plus ONE of:
WORKFLOWS_APP_ID: "123456"
WORKFLOWS_APP_PRIVATE_KEY: "-----BEGIN RSA PRIVATE KEY-----..."
# OR
SERVICE_BOT_PAT: "ghp_..."
```

**For Codex only:**
```yaml
# Required
CODEX_AUTH_JSON: '{"token": "..."}'

# Plus ONE of:
WORKFLOWS_APP_ID: "123456"
WORKFLOWS_APP_PRIVATE_KEY: "-----BEGIN RSA PRIVATE KEY-----..."
# OR
SERVICE_BOT_PAT: "ghp_..."
```

**For both agents:**
```yaml
# Claude backend
AWS_ACCESS_KEY_ID: "AKIA..."
AWS_SECRET_ACCESS_KEY: "..."

# Codex backend
CODEX_AUTH_JSON: '{"token": "..."}'

# GitHub access (choose one)
WORKFLOWS_APP_ID: "123456"
WORKFLOWS_APP_PRIVATE_KEY: "-----BEGIN RSA PRIVATE KEY-----..."
```

## Usage

### Assigning Claude to an Issue

1. Create an issue with clear tasks using checkbox format
2. Add the `agent:claude` label to the issue
3. The keepalive system will:
   - Create a PR from the issue
   - Route work to Claude via the keepalive loop
   - Claude will work through tasks autonomously

### Switching Agents

To switch from Codex to Claude (or vice versa):
1. Remove the current agent label (`agent:codex`)
2. Add the new agent label (`agent:claude`)
3. The next keepalive iteration will route to the new agent

## Feature Parity with Codex

The Claude workflow has full feature parity with Codex:

| Feature | Codex | Claude |
|---------|-------|--------|
| Task execution | ✅ | ✅ |
| CI fix mode | ✅ | ✅ |
| Conflict resolution | ✅ | ✅ |
| Session analysis | ✅ | ✅ |
| LLM task completion | ✅ | ✅ |
| Checkpoint comments | ✅ | ✅ |
| Error classification | ✅ | ✅ |
| Error diagnostics | ✅ | ✅ |
| Needs-attention labels | ✅ | ✅ |
| Prompt integrity check | ✅ | ✅ |
| Merge conflict surfacing | ✅ | ✅ |

## Differences from Codex

| Aspect | Codex | Claude |
|--------|-------|--------|
| Backend | OpenAI API | Amazon Bedrock |
| Authentication | `CODEX_AUTH_JSON` | AWS credentials |
| CLI Tool | `codex` | `claude` |
| Model | GPT-4 variants | Claude 3.5 Sonnet |

## Troubleshooting

### Claude workflow not triggering

1. Check PR has `agent:claude` label (not `agent:codex`)
2. Verify AWS credentials are configured in repo secrets
3. Check keepalive loop evaluation outputs

### Authentication failures

1. Verify AWS credentials have Bedrock permissions
2. Check region configuration (defaults to `us-east-1`)
3. Ensure Claude models are enabled in your AWS account

### CLI installation failures

The workflow has a fallback mechanism:
1. First attempts Claude Code CLI with Bedrock backend
2. Falls back to direct boto3 API calls if CLI fails
3. Check workflow logs for specific error messages

## Next Steps

To complete the integration in consumer repos:

1. **Sync templates**: Run the sync workflow to distribute changes
   ```bash
   gh workflow run maint-68-sync-consumer-repos.yml
   ```

2. **Configure secrets**: Add AWS credentials to each consumer repo

3. **Test the integration**: Create a test issue with `agent:claude` label

4. **Monitor**: Watch the keepalive loop for successful Claude runs
