# Adding Cursor as a Fleet Agent (`agent:cursor`) — Design Proposal

> Status: **proposal, not wired.** This sketches the concrete shape and effort of
> making Cursor a third coding agent alongside Codex and Claude, so the cost/effort
> trade-off can be judged before committing. Read `ADD_NEW_AGENT.md` first — this
> follows that contract but flags where Cursor breaks the on-runner-CLI assumption.

## The core difference from Codex/Claude

Codex and Claude runners (`reusable-codex-run.yml`, `reusable-claude-run.yml`) run a
**CLI on the GitHub runner**: they check out the branch, read a prompt file, edit the
working tree, and `git push` — all in one job. The keepalive model depends on this:
one round → the runner job produces one commit on the branch → keepalive inspects it.

Cursor background agents run on **Cursor's cloud**. You call an API to *launch* an
agent against a repo + branch + prompt; it works asynchronously and pushes commits
itself. So a Cursor runner does **not** edit a local checkout — it launches a remote
job and must decide how to reconcile with the keepalive's "one round = one commit"
cadence (see Execution model below).

This is the whole effort story: the registry is agent-agnostic and takes Cursor
trivially; the *runner* is a genuinely different integration.

## 1. Registry entry (`.github/agents/registry.yml`)

```yaml
  cursor:
    display_name: Cursor
    model: cursor-auto            # or a specific model id Cursor exposes for agents
    runner_workflow: .github/workflows/reusable-cursor-run.yml
    required_secrets:
      - CURSOR_API_KEY            # Cursor background-agent API key (per-repo secret)
    branch_prefix: cursor/issue-
    ui_mentions_allowed: false
    automation_logins:
      - kayleb-automation-bot     # the login Cursor's pushes appear as (confirm)
    readiness_candidates:
      - kayleb-automation-bot
    preflight:
      assign_user: kayleb-automation-bot
      command_phrase: ''
      enabled: true
    # NEW field — distinguishes API-launched cloud agents from on-runner CLIs.
    # Codex/Claude are implicitly "on-runner"; downstream logic can branch on this.
    execution: remote-async
    capabilities:
      pr_keepalive: true
      pr_autofix: true
      belt: true
      verifier_checkbox: true
```

The `execution: remote-async` key is new. Existing agents don't have it (treat absent
as `on-runner`). It's the honest flag that Cursor isn't a drop-in — anything that
assumes the runner commits synchronously should check it.

## 2. Runner skeleton (`reusable-cursor-run.yml`)

Must satisfy the same `workflow_call` contract the belt/keepalive already pass
(`prompt_file`, `branch`, `pr_number`, `base_ref`, `timeout`, `skip`). Internally it
launches a Cursor agent and — in the **synchronous** variant below — polls to
completion so the round still ends with commits on the branch, preserving the model.

```yaml
name: Reusable Cursor Run
on:
  workflow_call:
    inputs:
      skip:        { type: boolean, required: false, default: false }
      prompt_file: { type: string,  required: true }
      mode:        { type: string,  required: false, default: keepalive }
      pr_number:   { type: string,  required: false, default: '' }
      branch:      { type: string,  required: false, default: '' }
      base_ref:    { type: string,  required: false, default: '' }
      timeout:     { type: number,  required: false, default: 45 }
    secrets:
      CURSOR_API_KEY: { required: true }
    outputs:
      changes_made: { value: ${{ jobs.run.outputs.changes_made }} }

jobs:
  run:
    if: ${{ inputs.skip != true }}
    runs-on: ubuntu-latest
    timeout-minutes: ${{ inputs.timeout }}
    outputs:
      changes_made: ${{ steps.launch.outputs.changes_made }}
    steps:
      - uses: actions/checkout@v6
        with: { ref: ${{ inputs.branch }}, fetch-depth: 0 }

      - name: Launch Cursor background agent and wait
        id: launch
        env:
          CURSOR_API_KEY: ${{ secrets.CURSOR_API_KEY }}
          PROMPT_FILE: ${{ inputs.prompt_file }}
          BRANCH: ${{ inputs.branch }}
          BASE_REF: ${{ inputs.base_ref }}
        run: |
          set -euo pipefail
          PROMPT="$(cat "$PROMPT_FILE")"
          HEAD_BEFORE="$(git rev-parse HEAD)"

          # --- PLACEHOLDER: confirm against the current Cursor agent API ---
          # Launch an agent scoped to this repo + branch with the prompt.
          AGENT_ID="$(curl -sS -X POST https://api.cursor.com/v1/agents \
            -H "Authorization: Bearer $CURSOR_API_KEY" \
            -H 'Content-Type: application/json' \
            -d "$(jq -n --arg repo "$GITHUB_REPOSITORY" --arg branch "$BRANCH" \
                    --arg base "$BASE_REF" --arg prompt "$PROMPT" \
                    '{repo:$repo, branch:$branch, base:$base, prompt:$prompt, autopush:true}')" \
            | jq -r '.id')"

          # Poll until the remote agent finishes (or the job times out).
          while :; do
            STATUS="$(curl -sS https://api.cursor.com/v1/agents/$AGENT_ID \
              -H "Authorization: Bearer $CURSOR_API_KEY" | jq -r '.status')"
            case "$STATUS" in
              completed|succeeded) break ;;
              failed|cancelled) echo "::error::Cursor agent $STATUS"; exit 1 ;;
              *) sleep 20 ;;
            esac
          done

          # Cursor pushed to the branch; sync and report whether anything landed.
          git fetch origin "$BRANCH"
          git reset --hard "origin/$BRANCH"
          if [ "$(git rev-parse HEAD)" != "$HEAD_BEFORE" ]; then
            echo "changes_made=true"  >> "$GITHUB_OUTPUT"
          else
            echo "changes_made=false" >> "$GITHUB_OUTPUT"
          fi
```

> The `api.cursor.com/v1/agents` calls are **placeholders** — Cursor's background-agent
> API and pricing change often; confirm endpoints, launch params (does it take a branch
> or open its own?), auth, and the push identity before building.

### Execution model: two options

- **Synchronous poll (shown above).** The runner job blocks until Cursor finishes, so
  one keepalive round still yields commits. Keeps the whole belt/keepalive model
  intact — *no other file needs to change* — but the GitHub runner sits idle-billing
  minutes while Cursor's cloud works. Simplest to integrate.
- **Fire-and-forget.** Launch, return immediately, and let a *later* keepalive round
  detect Cursor's pushed commits. Cheaper on runner minutes, but breaks the
  "one round = one commit" cadence and needs the keepalive to tolerate a round that
  launched work without producing a commit yet. More integration surface.

Start with synchronous poll.

## 3. What else has to change

| Area | Change | Why |
|---|---|---|
| `registry.yml` (+ template) | add the `cursor` block | agent definition |
| `reusable-cursor-run.yml` (+ sync manifest) | new runner | the launch-and-wait job |
| Secret `CURSOR_API_KEY` in the consumer repo | provision | auth |
| `maint-68` label provisioning | add `agent:cursor`, `from:cursor`, `runner:cursor` | routing labels |
| `maint-53-agent-version-check` | (optional) track Cursor agent/API version | currency |
| Cost boundary decision | where Cursor spend sits vs `LLM_ALLOW_METERED` | **see below** |

Because the resolver is already agent-agnostic (and now honors `from:`/`runner:`
affinity), routing `agent:cursor` needs no code change beyond the registry entry.

## 4. The cost/auth decision (do this first)

Your entire model rests on **flat-rate subscription auth** for code production
(ChatGPT sub, Claude OAuth), so code generation has *no per-token bill* and metered
keys are reserved for `verify:compare` behind `LLM_ALLOW_METERED`.

Cursor background agents bill on **Cursor's** usage/compute model — a third cost
regime that is neither your flat-rate subscription nor your reserved verify budget.
Decide explicitly:

- Is Cursor usage acceptable as a **separate, metered** code-production budget you
  consciously accept (breaking the "no metered spend on code" rule on purpose)?
- Or do you gate it so it only runs on demand (e.g. an explicit `agent:cursor` +
  `capability:override`-style opt-in), never in the automatic keepalive sweep?

This is the same "don't mix the budgets" trap that caused the original OpenAI overspend
— resolve it before wiring, not after.

## 5. Effort & risk summary

- **Low effort:** registry entry, labels, routing (agent-agnostic design already
  supports it).
- **Medium effort:** the runner — a launch-and-poll job against an external API, plus
  handling the push identity and timeouts.
- **The real cost is operational, not code:** a third auth to keep alive, a third
  spend regime to reconcile, and runner-minutes burned while blocking on Cursor's
  cloud (synchronous variant).
- **Verdict:** worth it only if the goal is a genuine three-way *autonomous* quality
  comparison. If you mainly want Cursor's help on the human/review side, use it as the
  local IDE (Role A) and skip all of the above.
