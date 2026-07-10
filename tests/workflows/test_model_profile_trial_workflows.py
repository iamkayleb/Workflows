from __future__ import annotations

import re
from pathlib import Path

import yaml


SHIM = Path(".github/workflows/agents-model-profile-trial.yml")
RUNNER = Path(".github/workflows/reusable-model-profile-trial.yml")
REGISTRY = Path(".github/agents/registry.yml")


def _workflow(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    # PyYAML 1.1 parses the unquoted GitHub Actions `on` key as True.
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def test_dispatch_shim_is_single_arm_and_calls_only_pinned_reusable_runner():
    workflow = _workflow(SHIM)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {
        "trial_id",
        "request_id",
        "request_hash",
        "trial_run_id",
        "profile_id",
        "packet_hash",
        "launch_ordinal",
        "expected_source_sha",
    }
    assert all(value["required"] is True for value in inputs.values())
    assert inputs["profile_id"]["options"] == [
        "codex-5.6-sol-high",
        "codex-5.6-terra-high",
        "codex-5.6-luna-high",
    ]
    assert list(workflow["jobs"]) == ["trial"]
    runner_ref = workflow["jobs"]["trial"]["uses"]
    assert re.fullmatch(
        r"stranske/Workflows/\.github/workflows/"
        r"reusable-model-profile-trial\.yml@[0-9a-f]{40}",
        runner_ref,
    )
    assert workflow["permissions"] == {"contents": "read"}
    assert "inherit" not in str(workflow["jobs"]["trial"].get("secrets"))


def test_reusable_runner_is_read_only_exact_cli_and_has_no_write_lane():
    workflow = _workflow(RUNNER)
    assert set(workflow["on"]) == {"workflow_call"}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["run-single-arm"]
    assert job["permissions"] == {"contents": "read"}
    source = RUNNER.read_text(encoding="utf-8")
    assert '@openai/codex@0.144.1' in source
    assert "--sandbox read-only" in source
    assert "model_reasoning_effort=\"high\"" in source
    assert "--ignore-user-config" in source
    assert "persist-credentials: false" in source
    assert "provider_resolved" not in source
    forbidden = (
        "git commit",
        "git push",
        "gh pr",
        "gh issue",
        "create-pull-request",
        "refresh-codex",
        "OPENAI_API_KEY",
        "CLAUDE_API",
    )
    assert not [token for token in forbidden if token in source]


def test_runner_uploads_one_unique_attempt_and_enforces_source_integrity():
    workflow = _workflow(RUNNER)
    steps = workflow["jobs"]["run-single-arm"]["steps"]
    uploads = [step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact@")]
    assert len(uploads) == 1
    name = uploads[0]["with"]["name"]
    assert "github.run_id" in name and "github.run_attempt" in name
    source = RUNNER.read_text(encoding="utf-8")
    assert "source-sha-before" in source
    assert "source-sha-after" in source
    assert "git status --porcelain --untracked-files=all" in source
    assert "model_profile_trial_contract.py artifact" in source


def test_registry_trial_profiles_share_exact_pinned_read_only_contract():
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    trial = registry["model_profile_trial_contract"]
    assert trial["mode"] == "read-only"
    assert trial["artifact_schema"] == "workflows.model-profile-trial-result/v1"
    assert trial["identity_authority"] == "workflows-read-only-trial-artifact/v1"
    assert trial["cli_version"] == "0.144.1"
    assert trial["runtime_fallback_allowed"] is False
    assert trial["auxiliary_evaluator_allowed"] is False
    for profile_id in (
        "codex-5.6-sol-high",
        "codex-5.6-terra-high",
        "codex-5.6-luna-high",
    ):
        profile = registry["execution_profiles"][profile_id]
        assert profile["runner"] == "reusable-model-profile-trial"
        assert profile["runner_ref"] == trial["runner_ref"]
        assert profile["capacity_pool"] == "codex-standard"
        assert profile["reasoning_effort"] == "high"
        assert profile["permission_mode"] == "read-only"
        assert profile["safety"] == "read-only"
