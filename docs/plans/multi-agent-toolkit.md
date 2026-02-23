# Multi-Agent Toolkit Coverage (Codex + Claude)

## Context
- Claude now participates in the same automation loops (readiness, preflight, keepalive) as Codex.
- `agents-70-orchestrator.yml` + `reusable-16-agents.yml` still have Codex-specific toggles (e.g., preflight inputs) that make it easy for future contributors to accidentally add Codex-only logic.
- Several workflows already iterate over `.github/agents/registry.yml` to discover supported agents; the agents toolkit should follow the same pattern everywhere.

## Goals
1. **Single Source of Truth** – `.github/agents/registry.yml` describes every active agent (prompt overrides, tokens, PAT/PAT fallbacks). All workflows use that registry rather than hard-coded names.
2. **Per-Agent Stage Fan-Out** – Readiness, preflight, bootstrap, watchdog, keepalive, and verification stages must iterate over the registry and emit per-agent results so Gate/maintainers can see Codex vs. Claude health independently.
3. **Token Awareness** – Each agent can require different PAT/App combinations. The toolkit needs a dispatcher that selects the right token chain per agent and documents the fallbacks (service bot, app token, defaults).
4. **Easy Extensibility** – Adding a third agent is “edit registry + add prompts,” not “copy/paste every workflow.”

## Design
- **Registry helpers**: Extend `agent_registry.js` with helpers that expose `getAgents({ include_disabled: false })`, `getAgentTokens(agentKey)`, and `getPreflightConfig(agentKey)`.
- **Toolkit fan-out**: Update `reusable-16-agents.yml` so readiness/preflight/watchdog/keepalive steps load the registry helper and loop over `agents`. Each stage publishes JSON keyed by agent so the run summary can highlight Codex vs. Claude.
- **Input schema**: Replace `codex_user`/`codex_command_phrase` with generic `agent_preflight_overrides` (JSON) while keeping backwards compatibility via defaults pulled from the registry.
- **Keepalive/Watchdog**: Teach `scripts/keepalive-runner.js` and watchdog scripts to accept `agentKey` and branch on registry-specific prompts/tokens instead of global constants.
- **Docs**: Workflow guide + keepalive instructions already remind contributors about multi-agent coverage; link them to this plan for the architectural checklist.

## Tasks
1. **Registry API** – extend `agent_registry.js`; add unit tests.
2. **Toolkit Updates** – refactor `reusable-16-agents.yml` to use the registry API for stage fan-out and to emit per-agent outputs; update run summary to show Codex/Claude rows.
3. **Keepalive Runner** – accept `agentKey` and resolve prompts/tokens from the registry; document required fields.
4. **Watchdog/Diagnostics** – ensure branch-sync/diagnostic helpers loop through agents and respect dry-run toggles per agent.
5. **Docs** – once the refactor ships, update `WORKFLOW_GUIDE.md`/`keepalive/Agents.md` with the new input names and per-agent reporting screenshots.
