# LLM Model Evaluation for Task Completion Analysis

> **Last updated**: February 7, 2026
> **Source**: Model IDs sourced from OpenAI Python SDK (`openai/types/shared/chat_model.py`,
> `openai/types/shared/responses_model.py`) and Anthropic Python SDK
> (`anthropic/types/model.py`) as of this date.

## Requirements

The task completion analysis system needs:
- **Quick feedback cycles** (< 10 seconds response time)
- **Accurate task detection** from session outputs
- **Token efficiency** for cost control
- **Some reasoning** but not extended multi-minute reasoning
- **Structured output** (JSON responses)
- **Reliable fallback chain** for availability
- **Availability via GitHub Models** (preferred — uses `GITHUB_TOKEN`, no extra secrets)

---

## OpenAI Models

### GPT-5.x Generation (Current)

#### gpt-5.2 (Latest Flagship)
- **Model ID**: `gpt-5.2` (alias), `gpt-5.2-2025-12-11` (pinned)
- **Released**: December 11, 2025
- **Context Window**: 128K+ tokens
- **Reasoning**: Configurable via `reasoning_effort` (defaults to `medium`)
- **Structured Output**: ✅ Excellent JSON support
- **Verdict**: ✅ **STRONG CANDIDATE** — Latest flagship, fast, high accuracy

**Pros**:
- Newest and most capable general-purpose model
- Fast response times for a flagship model
- Excellent structured output and tool use
- Should be available on GitHub Models

**Cons**:
- Most expensive GPT-5.x option
- May be overkill — our task is relatively simple pattern matching
- Newer = less battle-tested than gpt-4.1

---

#### gpt-5.2-pro
- **Model ID**: `gpt-5.2-pro`, `gpt-5.2-pro-2025-12-11` (pinned)
- **Released**: December 11, 2025
- **Reasoning**: High effort only (extended reasoning)
- **Verdict**: ❌ **NOT SUITABLE** — Pro models use extended reasoning, too slow for CI/CD

---

#### gpt-5.1
- **Model ID**: `gpt-5.1`, `gpt-5.1-2025-11-13` (pinned)
- **Released**: November 13, 2025
- **Context Window**: 128K+ tokens
- **Reasoning**: Defaults to `none` — must explicitly set `reasoning_effort` for reasoning
- **Structured Output**: ✅ Excellent JSON support
- **Verdict**: ✅ **GOOD CANDIDATE** — Strong, well-tested, fast without reasoning overhead

**Pros**:
- Well-established by now (3+ months in production)
- Reasoning defaults to `none` — fast out of the box for structured tasks
- Can enable `low`/`medium`/`high` reasoning if needed
- Likely available on GitHub Models

**Cons**:
- Without reasoning enabled, may be less accurate on ambiguous task states
- Superseded by gpt-5.2

**Important Note**: `gpt-5.1` defaults to **no reasoning** (`effort=none`). For our task
completion analysis, we likely want `effort=low` or `effort=medium` to get some reasoning
about whether tasks are actually complete.

---

#### gpt-5.1-mini
- **Model ID**: `gpt-5.1-mini`
- **Released**: November 2025
- **Reasoning**: Configurable
- **Verdict**: 🤔 **POTENTIAL** — Cheaper alternative, but untested for our accuracy needs

**Pros**:
- Significantly cheaper than full gpt-5.1
- Fast response times
- Good for high-volume, simpler tasks

**Cons**:
- Smaller models historically too lenient for our use case (see gpt-4o-mini failure)
- Would need accuracy validation before production use
- Risk of false positives (marking incomplete tasks as done)

---

### OpenAI Codex Models

These are models specifically optimized for OpenAI's Codex coding agent product.

#### codex-mini-latest (Rolling Alias)
- **Model ID**: `codex-mini-latest`
- **API**: Chat Completions
- **Purpose**: Lightweight model for Codex (coding agent) tasks
- **Verdict**: ⚠️ **INVESTIGATE** — Purpose-built for coding tasks, may be well-suited

**Pros**:
- Specifically optimized for understanding code and development contexts
- Rolling alias — always points to latest version
- Available via Chat Completions API
- Likely fast and efficient for code-related analysis

**Cons**:
- Designed for Codex product, not general task completion analysis
- "Mini" designation — may have accuracy limitations similar to other mini models
- Limited documentation on capabilities outside Codex product
- Untested for our specific structured output requirements

---

#### gpt-5.1-codex
- **Model ID**: `gpt-5.1-codex`
- **API**: Chat Completions
- **Purpose**: GPT-5.1 variant optimized for Codex coding tasks
- **Verdict**: ✅ **STRONG CANDIDATE** — Code-tuned GPT-5.1, ideal for analyzing coding sessions

**Pros**:
- Full GPT-5.1 capability with coding optimization
- Specifically tuned for understanding development sessions
- Available via Chat Completions API (standard integration)
- Should excel at parsing Codex session logs and understanding task completion
- Our use case IS analyzing Codex sessions — this model is purpose-built for that domain

**Cons**:
- May not be available on GitHub Models (needs verification)
- Potentially more expensive than base gpt-5.1
- Less general — might over-focus on code aspects vs. task-level completion

---

#### gpt-5.1-codex-max
- **Model ID**: `gpt-5.1-codex-max`
- **API**: Responses API only (not Chat Completions)
- **Purpose**: Maximum reasoning for complex Codex tasks
- **Reasoning**: Supports `xhigh` reasoning effort
- **Verdict**: ❌ **NOT SUITABLE** — Responses API only, extended reasoning too slow

**Cons**:
- Only available via Responses API (our code uses Chat Completions)
- Extended reasoning adds latency
- Overkill for task completion detection
- Would require significant code changes to use Responses API

---

#### gpt-5-codex
- **Model ID**: `gpt-5-codex`
- **API**: Responses API only
- **Purpose**: GPT-5 variant for Codex tasks
- **Verdict**: ❌ **NOT SUITABLE** — Responses API only, superseded by gpt-5.1-codex

---

### GPT-5 Base Models

#### gpt-5
- **Model ID**: `gpt-5`, `gpt-5-2025-08-07` (pinned)
- **Released**: August 7, 2025
- **Reasoning**: Configurable (defaults to `medium`)
- **Verdict**: 🤔 **VIABLE** — Proven but superseded by 5.1 and 5.2

---

#### gpt-5-mini
- **Model ID**: `gpt-5-mini`, `gpt-5-mini-2025-08-07` (pinned)
- **Released**: August 7, 2025
- **Verdict**: ⚠️ **CAUTION** — Mini models have documented accuracy issues for our use case

---

#### gpt-5-nano
- **Model ID**: `gpt-5-nano`, `gpt-5-nano-2025-08-07` (pinned)
- **Released**: August 7, 2025
- **Verdict**: ❌ **NOT RECOMMENDED** — Too lightweight for reliable task analysis

---

#### gpt-5-pro
- **Model ID**: `gpt-5-pro`, `gpt-5-pro-2025-10-06` (pinned)
- **Released**: October 6, 2025
- **Reasoning**: High effort only
- **Verdict**: ❌ **NOT SUITABLE** — Extended reasoning too slow, Responses API only

---

### GPT-4.1 Generation

#### gpt-4.1
- **Model ID**: `gpt-4.1`, `gpt-4.1-2025-04-14` (pinned)
- **Released**: April 14, 2025
- **Context Window**: 128K+ tokens
- **Structured Output**: ✅ Excellent JSON support
- **Verdict**: ✅ **RECOMMENDED** — Battle-tested, excellent price/performance, likely on GitHub Models

**Pros**:
- 10+ months in production — highly stable and well-understood
- Excellent structured output reliability
- Strong instruction following
- Good balance of capability and speed
- Almost certainly available on GitHub Models
- Well-documented behavior characteristics

**Cons**:
- Previous generation — less capable than gpt-5.x on complex reasoning
- May eventually be deprecated (but not yet)

---

#### gpt-4.1-mini
- **Model ID**: `gpt-4.1-mini`, `gpt-4.1-mini-2025-04-14` (pinned)
- **Released**: April 14, 2025
- **Verdict**: ⚠️ **CAUTION** — Cheaper but mini models have documented accuracy issues

**Pros**:
- Very fast and cheap
- Good for simpler analysis tasks
- Available on GitHub Models

**Cons**:
- Risk of "too lenient" behavior (documented with gpt-4o-mini)
- Would need validation testing

---

#### gpt-4.1-nano
- **Model ID**: `gpt-4.1-nano`, `gpt-4.1-nano-2025-04-14` (pinned)
- **Released**: April 14, 2025
- **Verdict**: ❌ **NOT RECOMMENDED** — Too lightweight for reliable task analysis

---

### Reasoning Models (o-series)

#### o4-mini
- **Model ID**: `o4-mini`, `o4-mini-2025-04-16` (pinned)
- **Released**: April 16, 2025
- **Reasoning**: Extended chain-of-thought reasoning
- **Verdict**: ⚠️ **POSSIBLE** — Fast reasoning model, but adds latency

**Pros**:
- Fastest reasoning model available
- Good accuracy for complex analysis
- Relatively affordable for a reasoning model

**Cons**:
- Reasoning adds 5-15 seconds latency vs. standard models
- Unnecessary complexity for our task
- Standard models with `reasoning_effort=low` may be sufficient

---

#### o3
- **Model ID**: `o3`, `o3-2025-04-16` (pinned)
- **Released**: April 16, 2025
- **Verdict**: ❌ **NOT SUITABLE** — Too slow. Extended reasoning not needed for task detection.

---

#### o3-mini
- **Model ID**: `o3-mini`, `o3-mini-2025-01-31` (pinned)
- **Released**: January 31, 2025
- **Verdict**: ❌ **NOT SUITABLE** — Superseded by o4-mini, still too slow for CI/CD

---

#### o3-pro / o3-deep-research / o4-mini-deep-research
- **Verdict**: ❌ **NOT SUITABLE** — These are specialized extended-reasoning models with
  response times measured in minutes. Not applicable to CI/CD feedback.

---

#### o1 / o1-mini / o1-preview (Legacy)
- **Verdict**: ❌ **LEGACY** — Superseded by o3/o4 series. Do not use.

---

### GPT-4o Generation (Legacy — Current Default)

#### gpt-4o (Current Default in Codebase)
- **Model ID**: `gpt-4o`, `gpt-4o-2024-11-20` (latest pinned)
- **Released**: May 2024 (latest update November 2024)
- **Context Window**: 128K tokens
- **Structured Output**: ✅ Excellent JSON support
- **Verdict**: ⚠️ **LEGACY BUT WORKING** — Currently used, should upgrade

**Pros**:
- Currently deployed and working
- Proven in our pipeline
- Available on GitHub Models
- Well-understood behavior

**Cons**:
- **Two generations behind** — gpt-4.1 and gpt-5.x are both newer and better
- Will eventually be deprecated
- Less capable than newer models
- Should plan migration path

---

#### gpt-4o-mini (Legacy)
- **Model ID**: `gpt-4o-mini`
- **Verdict**: ❌ **REJECTED** — Explicitly documented as "too lenient, passes obvious
  deficiencies" (see `llm_provider.py:36-37`). Do not use.

---

#### gpt-4-turbo / gpt-4 / gpt-3.5-turbo (Deprecated)
- **Verdict**: ❌ **DEPRECATED** — Multiple generations behind. Do not use for new work.

---

## Anthropic Models

### Claude 4.x Generation (Current)

#### claude-opus-4-6 (Latest)
- **Model ID**: `claude-opus-4-6`
- **Released**: ~February 5, 2026 (days ago!)
- **Context Window**: 200K tokens
- **Reasoning**: Strongest in Claude family
- **Structured Output**: ✅ Excellent JSON support
- **Verdict**: ❌ **TOO NEW / TOO EXPENSIVE** — Just released, untested, opus-tier pricing

**Pros**:
- Most capable Claude model available
- Excellent at complex reasoning and analysis
- Latest improvements in instruction following

**Cons**:
- Released days ago — no production track record
- Opus-tier pricing (most expensive Anthropic tier)
- Requires `CLAUDE_API_STRANSKE` API key
- Not available via GitHub Models
- Overkill for task completion detection

---

#### claude-opus-4-5
- **Model ID**: `claude-opus-4-5`, `claude-opus-4-5-20251101` (pinned)
- **Released**: November 1, 2025
- **Context Window**: 200K tokens
- **Verdict**: ❌ **TOO EXPENSIVE** — Opus-tier pricing, overkill for our use case

---

#### claude-sonnet-4-5
- **Model ID**: `claude-sonnet-4-5`, `claude-sonnet-4-5-20250929` (pinned)
- **Released**: September 29, 2025
- **Context Window**: 200K tokens
- **Reasoning**: Strong, balanced
- **Structured Output**: ✅ Excellent JSON support
- **Verdict**: ✅ **RECOMMENDED ALTERNATIVE** — Best Anthropic option if API available

**Pros**:
- Excellent capability/cost balance
- Strong structured output
- Good at understanding development contexts
- 200K context handles very large sessions
- 4+ months of production maturity

**Cons**:
- Requires `CLAUDE_API_STRANSKE` API key
- Not available via GitHub Models
- Additional infrastructure dependency

---

#### claude-sonnet-4-0
- **Model ID**: `claude-sonnet-4-0`, `claude-sonnet-4-20250514` (pinned)
- **Released**: May 14, 2025
- **Verdict**: 🤔 **VIABLE** — Previous Sonnet, proven but superseded by 4.5

---

#### claude-haiku-4-5
- **Model ID**: `claude-haiku-4-5`, `claude-haiku-4-5-20251001` (pinned)
- **Released**: October 1, 2025
- **Context Window**: 200K tokens
- **Verdict**: 🤔 **POTENTIAL** — Fast and cheap, but untested for our accuracy needs

**Pros**:
- Very fast responses (< 3 seconds)
- Cheapest Claude 4 option
- Good structured output

**Cons**:
- Haiku models may be too lenient (same risk as GPT mini models)
- Requires Anthropic API key
- Would need validation testing

---

#### claude-opus-4-0 / claude-opus-4-1 (Previous Opus)
- **Model ID**: `claude-opus-4-0`, `claude-opus-4-1-20250805`
- **Verdict**: ❌ **TOO EXPENSIVE** — Opus pricing, superseded by newer versions

---

### Claude 3.x Generation (Legacy)

#### claude-3-7-sonnet (Latest Claude 3)
- **Model ID**: `claude-3-7-sonnet-latest`, `claude-3-7-sonnet-20250219` (pinned)
- **Released**: February 19, 2025
- **Verdict**: 🤔 **LEGACY** — Last Claude 3 model, superseded by Claude 4 Sonnet

---

#### claude-3-5-haiku
- **Model ID**: `claude-3-5-haiku-latest`, `claude-3-5-haiku-20241022` (pinned)
- **Verdict**: 🤔 **LEGACY** — Superseded by claude-haiku-4-5

---

#### claude-3-opus / claude-3-haiku (Deprecated)
- **Verdict**: ❌ **DEPRECATED** — Multiple generations behind. Do not use.

---

## Implementation Issues Identified

### 1. Model ID is Two Generations Behind

The codebase uses `gpt-4o` as `DEFAULT_MODEL`. This is now **two generations behind**
(gpt-4.1 → gpt-5.x). While it still works, it's increasingly likely to be
deprecated and is less capable than current options.

### 2. Anthropic Model ID is Invalid

The code uses:
```python
model="claude-4.5-sonnet"  # WRONG — This model ID does not exist
```

Valid Anthropic model IDs use the format `claude-{tier}-{major}-{minor}` (e.g.,
`claude-sonnet-4-5`). The ID `claude-4.5-sonnet` has never existed in Anthropic's API.

### 3. Fallback Chain Reality Mismatch

**Documented Intent** (`llm_provider.py` docstring):
```
1. OpenAI API (primary) — uses OPENAI_API_KEY
2. Anthropic API (secondary) — uses CLAUDE_API_STRANSKE
3. GitHub Models API (fallback) — uses GITHUB_TOKEN
4. Regex patterns (last resort) — no API calls
```

**Actual Reality** in CI/CD:
- ❌ `OPENAI_API_KEY` not set → OpenAI skipped
- ❌ `CLAUDE_API_STRANSKE` not set → Anthropic skipped (and model ID is wrong anyway)
- ✅ `GITHUB_TOKEN` always available → **GitHub Models is always the one used**
- ✅ Regex always available → Ultimate fallback

### 4. No Codex-Optimized Model Considered

We are analyzing **Codex sessions** but using a general-purpose model. The
`gpt-5.1-codex` model is specifically optimized for understanding coding sessions
and could provide better accuracy for our exact use case.

---

## Recommendations

### Primary Recommendation: **Upgrade to gpt-4.1 on GitHub Models**

**Immediate action** — low risk, high value:

```python
DEFAULT_MODEL = "gpt-4.1"  # Upgraded from legacy gpt-4o
```

**Why gpt-4.1 over gpt-5.x**:
- ✅ 10+ months battle-tested (released April 2025)
- ✅ Almost certainly available on GitHub Models
- ✅ Excellent structured output and instruction following
- ✅ Better than gpt-4o in every dimension
- ✅ No code changes needed beyond the model string
- ✅ Conservative upgrade — well-understood behavior

### Secondary Recommendation: **Evaluate gpt-5.1-codex**

**Investigate and potentially adopt** — our use case (analyzing Codex coding sessions)
is exactly what this model was optimized for:

1. Verify `gpt-5.1-codex` availability on GitHub Models
2. Run comparison tests: gpt-4.1 vs gpt-5.1-codex on historical sessions
3. If accuracy is better, switch to `gpt-5.1-codex`

### Anthropic Fallback: **claude-sonnet-4-5**

If Anthropic API is configured:

```python
model="claude-sonnet-4-5"  # Fixed from non-existent "claude-4.5-sonnet"
```

### Fix Immediately

1. **Update DEFAULT_MODEL** from `gpt-4o` to at least `gpt-4.1`
2. **Fix Anthropic model ID** from `claude-4.5-sonnet` to `claude-sonnet-4-5`
3. **Update docstrings** to reflect that GitHub Models is the de facto primary
4. **Test `gpt-5.1-codex`** for potential accuracy improvement

---

## Model Comparison Matrix

### Recommended Candidates (Full Evaluation)

| Model | Response Time | Relative Cost | Reasoning | Structured Output | GitHub Models | Verdict |
|-------|--------------|---------------|-----------|-------------------|---------------|---------|
| **gpt-4.1** | ~2-4s | $$ | Standard | ✅ Excellent | ✅ Yes | ✅ **RECOMMENDED** |
| **gpt-5.1-codex** | ~2-5s | $$$ | Configurable | ✅ Excellent | ❓ Verify | ✅ **INVESTIGATE** |
| **gpt-5.1** | ~2-5s | $$$ | Configurable¹ | ✅ Excellent | ✅ Likely | ✅ Good |
| **gpt-5.2** | ~2-5s | $$$$ | Configurable | ✅ Excellent | ✅ Likely | ✅ Good |
| **claude-sonnet-4-5** | ~3-6s | $$$ | Strong | ✅ Excellent | ❌ No | ✅ Alt |
| **codex-mini-latest** | ~1-3s | $ | Light | ✅ Good | ❓ Verify | ⚠️ Test first |
| **gpt-4.1-mini** | ~1-3s | $ | Standard | ✅ Good | ✅ Yes | ⚠️ Test first |

¹ gpt-5.1 defaults to `reasoning_effort=none`. Must set `low` or `medium` explicitly.

### Not Recommended

| Model | Reason |
|-------|--------|
| gpt-4o | Legacy — two generations behind, should upgrade |
| gpt-4o-mini | **Rejected** — documented as "too lenient, passes obvious deficiencies" |
| gpt-5-mini / gpt-5-nano | Mini/nano models risk "too lenient" behavior |
| gpt-5.2-pro / gpt-5-pro | Pro models force extended reasoning — too slow |
| gpt-5.1-codex-max | Responses API only — requires code architecture change |
| gpt-5-codex | Responses API only, superseded by gpt-5.1-codex |
| o3 / o3-pro / o4-mini | Reasoning models add unnecessary latency |
| o1 / o1-mini / o1-preview | Legacy reasoning models — superseded |
| claude-opus-4-6 | Too new (released 2 days ago), too expensive |
| claude-opus-4-5 / 4-1 / 4-0 | Opus pricing overkill for task detection |
| claude-3-7-sonnet | Legacy — superseded by claude-sonnet-4-5 |
| claude-3-opus / claude-3-haiku | Deprecated — two generations behind |
| gpt-4-turbo / gpt-4 / gpt-3.5-turbo | Deprecated |

---

## Proposed Implementation Changes

### 1. Upgrade DEFAULT_MODEL

```python
# tools/llm_provider.py
DEFAULT_MODEL = "gpt-4.1"  # Upgraded from gpt-4o (legacy, 2 generations behind)
```

### 2. Fix Anthropic Model ID

```python
# tools/llm_provider.py — AnthropicProvider
return ChatAnthropic(
    model="claude-sonnet-4-5",  # Fixed from non-existent "claude-4.5-sonnet"
    anthropic_api_key=os.environ.get(ANTHROPIC_API_KEY_ENV),
    temperature=0.1,
)
```

### 3. Add Reasoning Effort Configuration (if using gpt-5.1+)

```python
# Only needed if upgrading to gpt-5.1 or gpt-5.2
return ChatOpenAI(
    model="gpt-5.1",
    extra_body={"reasoning_effort": "low"},  # Enable light reasoning
    temperature=0.1,
)
```

### 4. Optional: Test Codex-Optimized Model

```python
# Experimental — compare accuracy against gpt-4.1
CODEX_MODEL = "gpt-5.1-codex"  # Purpose-built for coding session analysis
```

### 5. Add Model Override Input

```yaml
inputs:
  llm_model:
    description: 'Override LLM model for analysis'
    required: false
    default: 'gpt-4.1'
    type: string
```

---

## Conclusion

**Current state**: The system uses `gpt-4o` (a legacy model, two generations behind)
via GitHub Models. The Anthropic fallback references a non-existent model ID
(`claude-4.5-sonnet`). Despite these issues, the system works because `gpt-4o`
is still functional.

**Recommended upgrade path**:

1. **Immediate** (low risk): Change `DEFAULT_MODEL` from `gpt-4o` → `gpt-4.1`
2. **Immediate**: Fix Anthropic model ID to `claude-sonnet-4-5`
3. **Short-term**: Test `gpt-5.1-codex` — it's purpose-built for our exact use case
4. **Medium-term**: Consider `gpt-5.1` or `gpt-5.2` with `reasoning_effort=low`

**Do NOT use**:
- Mini/nano models (documented leniency issues)
- Pro models (forced extended reasoning, too slow)
- Reasoning-only models like o3/o4-mini (unnecessary latency)
- Opus-tier Anthropic models (cost overkill)
- Any deprecated/legacy model older than gpt-4.1

**Key insight**: The `gpt-5.1-codex` model deserves serious investigation. We are
literally analyzing Codex sessions, and this model was built for that domain. If it's
available on GitHub Models, it could be the optimal choice.
