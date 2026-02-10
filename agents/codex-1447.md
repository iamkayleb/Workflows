<!--
needs-human:
Label: needs-human
Workflow updates required in .github/workflows/agents-auto-pilot.yml and .github/workflows/reusable-agents-verifier.yml. Add pinned installs (tools/requirements-llm.txt and .workflows-lib/tools/requirements-llm.txt for evaluate/compare), add actions/cache@v4 pip cache keyed by requirements hash + Python version, and remove any floating `pip install langchain*` lines. Workflow edits require agent-high-privilege.
-->
