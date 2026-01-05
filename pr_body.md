<!-- pr-preamble:start -->
> **Source:** Issue #483

<!-- pr-preamble:end -->

<!-- auto-status-summary:start -->
## Automated Status Summary
#### Scope
Related to master tracking issue #484 (LangChain Issue Intake Enhancement).

The `capability_check.py` module is P0 priority as it's designed to prevent wasted agent iterations by pre-validating task compatibility before engaging the keepalive pipeline.

<!-- Updated WORKFLOW_OUTPUTS.md context:start -->
## Context for Agent

### Design Decisions & Constraints
- The `capability_check.py` module is P0 priority as it's designed to prevent wasted agent iterations by pre-validating task compatibility before engaging the keepalive pipeline.

### Related Issues/PRs
- [#484](https://github.com/stranske/Workflows/issues/484)
- [#540](https://github.com/stranske/Workflows/issues/540)

### References
- https://github.com/stranske/Workflows/compare/main...codex/issue-540?expand=1
<!-- Updated WORKFLOW_OUTPUTS.md context:end -->

#### Tasks
- [x] Create `tests/scripts/test_capability_check.py` with tests for:
- [x] `classify_capabilities()` main function
- [x] `_normalize_result()` JSON normalization
- [x] `_parse_tasks_from_text()` markdown parsing
- [x] Fallback behavior when LLM unavailable
- [x] CLI argument handling in `main()`
- [x] Improve `issue_optimizer.py` coverage (target: 70%):
- [x] Test LLM chain invocation paths
- [x] Test suggestion extraction and formatting
- [x] Test edge cases for empty/malformed inputs
- [ ] Improve `semantic_matcher.py` coverage (target: 70%):
- [x] Test embedding generation paths
- [ ] Test fallback when no embedding client available
- [ ] Improve `task_decomposer.py` coverage (target: 70%):
- [x] Test LLM decomposition paths
- [x] Test normalization edge cases

#### Acceptance criteria
- [ ] All langchain modules have corresponding test files
- [ ] Overall langchain module coverage reaches 70%+
- [ ] No module below 50% coverage
- [x] Tests run successfully in CI

<!-- auto-status-summary:end -->
