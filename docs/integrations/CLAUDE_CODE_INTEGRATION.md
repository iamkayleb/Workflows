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
    required: true
  AWS_SECRET_ACCESS_KEY:
    required: true
  AWS_SESSION_TOKEN:
    required: false  # Optional for temporary credentials
  SERVICE_BOT_PAT:
    required: true
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
    SERVICE_BOT_PAT: ${{ secrets.SERVICE_BOT_PAT }}
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

## Required Secrets Setup

Consumer repos need these secrets configured:

| Secret | Description | Required |
|--------|-------------|----------|
| `AWS_ACCESS_KEY_ID` | AWS access key with Bedrock permissions | Yes |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | Yes |
| `AWS_SESSION_TOKEN` | Session token (for temporary credentials) | No |
| `SERVICE_BOT_PAT` | GitHub PAT for bot operations | Yes |

### AWS IAM Policy

The AWS credentials need these Bedrock permissions:

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
