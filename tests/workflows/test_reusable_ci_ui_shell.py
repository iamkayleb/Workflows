"""Static guard: every ``run:`` block in the UI lane must parse as bash when
its optional inputs are **empty**.

Background — why this test exists
=================================
`reusable-14-ci-ui.yml` failed on its first real run with

    /home/runner/work/_temp/....sh: line 4: syntax error near unexpected token

The install step read::

    if [ -n "${{ inputs.install-command }}" ]; then
      ${{ inputs.install-command }}
    else
      ...

`install-command` defaults to empty. GitHub substitutes expressions textually
before bash sees the script, so the body became an ``if`` with an **empty**
``then`` branch, which bash rejects outright. The step never ran.

The shape is general: a bare ``${{ inputs.x }}`` alone on a line disappears
when ``x`` is empty, and whatever construct contained it can collapse into
something unparseable.

Why the original check missed it
================================
The lane was validated by replacing every ``${{ ... }}`` with the placeholder
``X`` and running ``bash -n``. With ``X`` substituted the branch was never
empty, so the one case that breaks was the one case the check could not
produce. A check that cannot fail for the reason it exists is the defect this
repository keeps cataloguing; this is it, in the validation of a lane built to
catch exactly that.

So this test substitutes the **declared default** for every input, and empty
for every optional input that has no default — the configuration a consumer
gets when it sets only what it must.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/reusable-14-ci-ui.yml"

EXPR = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _inputs() -> dict[str, str]:
    # yaml parses a bare `on:` key as the boolean True.
    trigger = _workflow().get("on") or _workflow().get(True)
    return trigger["workflow_call"]["inputs"]


def _steps() -> list[dict]:
    return _workflow()["jobs"]["ui-acceptance"]["steps"]


def _substitute(script: str, inputs: dict[str, str], *, use_defaults: bool) -> str:
    """Replace GitHub expressions the way the runner does: textually."""

    def repl(match: re.Match[str]) -> str:
        expr = match.group(1)
        ref = expr.split(".", 1)
        if len(ref) == 2 and ref[0] == "inputs":
            name = ref[1]
            spec = inputs.get(name, {})
            if use_defaults:
                default = spec.get("default", "")
                return "" if default is None else str(default)
            # Worst case: the consumer set nothing it did not have to.
            return "" if not spec.get("required") else "placeholder"
        # steps/env/github expressions always resolve to *something*.
        return "placeholder"

    return EXPR.sub(repl, script)


def _run_blocks() -> list[tuple[str, str]]:
    return [(s.get("name", "<unnamed>"), s["run"]) for s in _steps() if s.get("run")]


@pytest.mark.parametrize("use_defaults", [True, False], ids=["defaults", "all-empty"])
def test_every_run_block_parses_as_bash(use_defaults: bool) -> None:
    failures: list[str] = []
    for name, script in _run_blocks():
        rendered = _substitute(script, _inputs(), use_defaults=use_defaults)
        proc = subprocess.run(["bash", "-n"], input=rendered, text=True, capture_output=True)
        if proc.returncode != 0:
            failures.append(f"{name}: {proc.stderr.strip()}")
    assert not failures, (
        "run blocks do not parse as bash when inputs take these values:\n  "
        + "\n  ".join(failures)
    )


def test_command_inputs_are_not_interpolated_into_the_script_body() -> None:
    """Free-text inputs must arrive through ``env``, never inline.

    An inline expression is both the empty-branch hazard above and a quoting
    one: a command containing a space, quote or newline changes the meaning of
    the surrounding script rather than being passed as a value.
    """
    offenders: list[str] = []
    for step in _steps():
        script = step.get("run")
        if not script:
            continue
        for expr in EXPR.findall(script):
            if expr.startswith("inputs."):
                offenders.append(f"{step.get('name', '<unnamed>')}: ${{{{ {expr} }}}}")
    assert not offenders, (
        "inputs referenced inline in a run block; pass them through `env:` and "
        "read them as shell variables instead:\n  " + "\n  ".join(offenders)
    )


def test_the_lane_refuses_rather_than_passing_when_it_checks_nothing() -> None:
    """The discover step must exit non-zero when no specs match.

    This is the property the whole lane rests on. A UI check that reports
    success against zero specs is worse than no check, because it reads as
    evidence.
    """
    discover = next(s for s in _steps() if s.get("name") == "Discover specs")
    assert "exit 1" in discover["run"]
    assert "::error" in discover["run"]
    # And it must happen before anything expensive, so a misconfigured path
    # fails in seconds rather than after installing a browser. Matched on a
    # substring: pinning the exact step name made this blow up with a
    # ValueError the moment the step was renamed, which reads as a broken test
    # rather than the ordering regression it is meant to catch.
    names = [s.get("name", "") for s in _steps()]
    discover = names.index("Discover specs")
    browser = next(i for i, n in enumerate(names) if "browser" in n.lower())
    assert discover < browser, f"discovery must precede the browser install: {names}"


def test_evidence_is_built_even_when_an_earlier_step_fails() -> None:
    """A run that fell over before the specs ran must still say so.

    Without `if: always()` the evidence step is skipped, no ui-acceptance.json
    exists, the upload fails and the verdict is blank -- three errors that
    between them say less than one honest `status: not_run`.
    """
    evidence = next(s for s in _steps() if s.get("name") == "Build acceptance evidence")
    assert evidence.get("if") == "always()"
    upload = next(s for s in _steps() if "Upload" in s.get("name", ""))
    assert upload.get("if") == "always()"


def test_the_project_s_own_playwright_is_preferred() -> None:
    """The version must come from the project's lockfile where there is one.

    A version pinned in this lane ages against the runner image: 1.56.1 was
    refused outright once ubuntu-latest moved to 26.04, with
    "Playwright does not support chromium on ubuntu26.04-x64".
    """
    resolve = next(s for s in _steps() if s.get("name") == "Resolve Playwright")
    script = resolve["run"]
    # It tries the project's binary first and only then falls back.
    assert script.index("local_runner") < script.index("npx --yes playwright@")
    assert "::warning" in script, "a fallback the project did not ask for must be visible"

    install = next(s for s in _steps() if s.get("name") == "Install browser")
    # --with-deps first, browser-only as a fallback, failure if neither works.
    assert "install --with-deps" in install["run"]
    assert "exit 1" in install["run"]
