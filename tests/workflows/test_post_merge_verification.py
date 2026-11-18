"""Static guard: merged agent work must be handed to the verifier.

Background — why this test exists
=================================
Independent verification of merged work was triggered by a job in
``eval-lane-automation.yml`` gated on::

    startsWith(github.event.pull_request.base.ref, 'eval/')

When ``main`` became the trunk the evaluation lanes were retired, and that
trigger went with them. Nothing replaced it and nothing reported its absence,
so agent PRs merged into ``main`` were never verified — the belt shipped code
and stopped checking what it shipped. The first full round after the pivot
(bukay #561) merged clean, closed its issue, and produced no verdict at all.

The failure mode is the one this repository keeps cataloguing in mirror image:
not a check that cannot fail, but a check that no longer runs, reported as
nothing rather than as a problem.

These tests pin the pieces that make it run, and the guards that keep it from
spending credit on work there is nothing to grade.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
GATE_FOLLOWUPS = (
    ROOT / "templates/consumer-repo/.github/workflows/agents-81-gate-followups.yml"
)
JOB = "request-verification"


def _workflow() -> dict:
    return yaml.safe_load(GATE_FOLLOWUPS.read_text(encoding="utf-8"))


def _triggers() -> dict:
    wf = _workflow()
    # A bare `on:` key parses as the boolean True.
    return wf.get("on") or wf[True]


def _job() -> dict:
    jobs = _workflow()["jobs"]
    assert JOB in jobs, (
        f"{JOB} is missing: merged agent work would reach main unverified, "
        "which is exactly the regression this file exists to prevent"
    )
    return jobs[JOB]


def test_the_workflow_hears_about_merges() -> None:
    """`closed` carries `merged`. Without it the job can never run."""
    types = _triggers()["pull_request_target"]["types"]
    assert "closed" in types, f"pull_request_target types are {types}"


def test_verification_is_requested_on_merge_into_the_default_branch() -> None:
    cond = " ".join(str(_job()["if"]).split())
    assert "github.event.action == 'closed'" in cond
    assert "github.event.pull_request.merged == true" in cond
    # The point of the fix: the default branch, not a hard-coded lane prefix.
    assert "github.event.repository.default_branch" in cond, cond
    assert "eval/" not in cond, "the retired eval-lane gate must not come back"


def test_only_agent_pull_requests_are_verified() -> None:
    script = _script()
    assert "startsWith('agent:')" in script.replace('"', "'"), script[:200]


def test_bookkeeping_only_merges_do_not_spend_credit() -> None:
    """A diff of pure belt bookkeeping has nothing to grade.

    Running the judges on one returns CONCERNS, which raises a follow-up issue,
    which consumes an agent round. That loop was the single largest source of
    wasted credit in the evaluation, and verify:compare bills two metered
    providers per run.
    """
    script = _script()
    assert "BOOKKEEPING" in script
    assert ".agents" in script
    assert "not requesting verify:compare" in script


def test_the_request_is_idempotent() -> None:
    assert "verify:compare already requested" in _script()


def test_the_label_is_applied_with_a_token_that_wakes_other_workflows() -> None:
    """A label applied with GITHUB_TOKEN does not trigger other workflows.

    GitHub's loop guard means the label would appear and the verifier would
    never wake — the hand-off would be inert while looking complete.
    """
    steps = _job()["steps"]
    assert any("create-github-app-token" in str(s.get("uses", "")) for s in steps)
    label_step = next(s for s in steps if "github-script" in str(s.get("uses", "")))
    token = str(label_step["with"]["github-token"])
    assert "app_token" in token and "GITHUB_TOKEN" in token, (
        "the App token must be preferred, with GITHUB_TOKEN only as a last resort"
    )


def _script() -> str:
    steps = _job()["steps"]
    step = next(s for s in steps if "github-script" in str(s.get("uses", "")))
    return str(step["with"]["script"])


@pytest.mark.parametrize(
    "other_job",
    [j for j in yaml.safe_load(GATE_FOLLOWUPS.read_text(encoding="utf-8"))["jobs"]
     if j != JOB],
)
def test_widening_the_trigger_did_not_let_other_jobs_fire_on_close(other_job: str) -> None:
    """Adding `closed` must not wake jobs that assume an open pull request.

    Each other job has to constrain the event or action itself, or sit behind
    `needs` on one that does.
    """
    job = _workflow()["jobs"][other_job]
    cond = str(job.get("if", "") or "")
    guarded = "github.event_name" in cond or "github.event.action" in cond
    assert guarded or job.get("needs"), (
        f"{other_job} has no event/action guard and no `needs`, so it would now "
        "also run when a pull request is merged"
    )


def test_guarded_merge_stays_the_last_job_in_the_file() -> None:
    """Nothing may be defined after `guarded-merge`.

    `guarded-merge-tasks.test.js` evaluates this workflow's inline script by
    slicing from `const listedIssues =` to the **end of the file** and running
    the result as JavaScript. A job appended after `guarded-merge` lands inside
    that slice, and the node suite fails 61 times with `Unexpected token ':'`,
    naming a temp-directory probe rather than this file -- which is a long way
    from the actual cause.

    Adding this job hit exactly that. The slice-to-EOF is the fragile part and
    fixing it belongs upstream; until then this turns a cryptic failure into a
    named one.
    """
    import re

    text = GATE_FOLLOWUPS.read_text(encoding="utf-8")
    job_names = [m.group(1) for m in re.finditer(r"^  ([a-z0-9_-]+):\s*$", text, re.M)]
    assert job_names[-1] == "guarded-merge", (
        f"{job_names[-1]!r} is defined after `guarded-merge`. Move it above, or "
        "guarded-merge-tasks.test.js will evaluate its YAML as JavaScript."
    )
