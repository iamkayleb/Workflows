#!/bin/bash
# Test script for the Unified Agent System
# Usage: ./scripts/test-unified-agent-system.sh

set -e

echo "=== Testing Unified Agent System ==="
echo ""

# Install dependencies if needed
if ! node -e "require('js-yaml')" 2>/dev/null; then
  echo "Installing js-yaml dependency..."
  npm install --silent js-yaml 2>/dev/null || npm install js-yaml
  echo ""
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

# 1. Test registry YAML syntax
echo "1. Testing registry.yml syntax..."
if python3 -c "import yaml; yaml.safe_load(open('.github/agents/registry.yml'))" 2>/dev/null; then
  pass "registry.yml is valid YAML"
else
  fail "registry.yml has invalid YAML syntax"
fi

# 2. Test registry contents
echo ""
echo "2. Testing registry contents..."
AGENTS=$(python3 -c "
import yaml
reg = yaml.safe_load(open('.github/agents/registry.yml'))
print(' '.join(reg.get('agents', {}).keys()))
")
if [[ "$AGENTS" == *"codex"* ]] && [[ "$AGENTS" == *"claude"* ]]; then
  pass "Registry contains codex and claude agents"
  echo "   Found agents: $AGENTS"
else
  fail "Registry missing required agents (codex, claude)"
fi

# 3. Test workflow YAML syntax
echo ""
echo "3. Testing workflow YAML syntax..."
for workflow in \
  .github/workflows/reusable-agent-run.yml \
  .github/workflows/agents-capability-check.yml; do
  if [ -f "$workflow" ]; then
    if python3 -c "import yaml; yaml.safe_load(open('$workflow'))" 2>/dev/null; then
      pass "$workflow is valid YAML"
    else
      fail "$workflow has invalid YAML syntax"
    fi
  else
    warn "$workflow not found"
  fi
done

# 4. Test setup actions exist
echo ""
echo "4. Testing setup actions..."
for action in setup-codex setup-claude setup-gemini; do
  if [ -f ".github/actions/$action/action.yml" ]; then
    if python3 -c "import yaml; yaml.safe_load(open('.github/actions/$action/action.yml'))" 2>/dev/null; then
      pass ".github/actions/$action/action.yml exists and is valid"
    else
      fail ".github/actions/$action/action.yml has invalid YAML"
    fi
  else
    warn ".github/actions/$action/action.yml not found"
  fi
done

# 5. Test agent-router.js syntax
echo ""
echo "5. Testing agent-router.js..."
if [ -f ".github/scripts/agent-router.js" ]; then
  if node --check .github/scripts/agent-router.js 2>/dev/null; then
    pass "agent-router.js has valid JavaScript syntax"
  else
    fail "agent-router.js has JavaScript syntax errors"
  fi
else
  fail ".github/scripts/agent-router.js not found"
fi

# 6. Test agent-router.js functionality
echo ""
echo "6. Testing agent-router.js functions..."
node -e "
const router = require('./.github/scripts/agent-router.js');

// Test loadRegistry
const registry = router.loadRegistry();
if (!registry.agents) throw new Error('No agents in registry');
console.log('   loadRegistry(): OK');

// Test getAgentConfig
const claude = router.getAgentConfig('claude');
if (!claude) throw new Error('Claude config not found');
if (claude.label !== 'agent:claude') throw new Error('Claude label wrong');
console.log('   getAgentConfig(claude): OK');

// Test getAgentLabels
const labels = router.getAgentLabels();
if (!labels.includes('agent:claude')) throw new Error('Missing agent:claude label');
console.log('   getAgentLabels(): OK');

// Test isCliAgent
if (!router.isCliAgent('claude')) throw new Error('Claude should be CLI agent');
if (router.isCliAgent('codex')) throw new Error('Codex should not be CLI agent');
console.log('   isCliAgent(): OK');

// Test validateSecrets
const validation = router.validateSecrets('claude', {});
if (validation.valid) throw new Error('Should fail with no secrets');
if (!validation.missing.includes('AWS_ACCESS_KEY_ID')) throw new Error('Should require AWS key');
console.log('   validateSecrets(): OK');

console.log('');
" && pass "agent-router.js functions work correctly"

# 7. Check for actionlint (optional)
echo ""
echo "7. Testing with actionlint (optional)..."
if command -v actionlint &> /dev/null; then
  ERRORS=$(actionlint .github/workflows/reusable-agent-run.yml 2>&1 || true)
  if [ -z "$ERRORS" ]; then
    pass "reusable-agent-run.yml passes actionlint"
  else
    warn "actionlint found issues:"
    echo "$ERRORS" | head -5
  fi
else
  warn "actionlint not installed (skipping)"
fi

# Summary
echo ""
echo "=== Summary ==="
echo ""
echo "Core files created:"
echo "  ✓ .github/agents/registry.yml"
echo "  ✓ .github/workflows/reusable-agent-run.yml"
echo "  ✓ .github/actions/setup-codex/action.yml"
echo "  ✓ .github/actions/setup-claude/action.yml"
echo "  ✓ .github/actions/setup-gemini/action.yml"
echo "  ✓ .github/scripts/agent-router.js"
echo ""
echo "To test in GitHub:"
echo "  1. Push to a branch"
echo "  2. Create a PR with 'agent:claude' label"
echo "  3. Watch the workflow run: gh run watch"
echo ""
echo "To test capability check:"
echo "  1. Create an issue with ## Tasks section"
echo "  2. Add 'agent:claude' label"
echo "  3. Check for capability report comment"
