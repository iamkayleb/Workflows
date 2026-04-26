from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_reusable_verifier_uploads_terminal_disposition_artifact() -> None:
    workflow = _load_yaml(ROOT / ".github/workflows/reusable-agents-verifier.yml")
    steps = workflow["jobs"]["verifier"]["steps"]

    collect_step = next(step for step in steps if step.get("name") == "Collect verifier metrics")
    write_step = next(
        step for step in steps if step.get("name") == "Write verifier terminal disposition"
    )
    upload_step = next(
        step for step in steps if step.get("name") == "Upload verifier terminal disposition"
    )

    assert "steps.unified_verdict.outputs.verdict" in collect_step["env"]["VERDICT"]
    assert write_step.get("if") == "always()"
    assert write_step["env"]["SOURCE_ISSUE_NUMBERS_JSON"] == (
        "${{ steps.context.outputs.issue_numbers || '[]' }}"
    )
    assert "verifier-terminal-disposition" in write_step["run"]
    assert "source-issue" in write_step["run"]
    assert "pull-request" in write_step["run"]
    assert "verified-pass" in write_step["run"]
    assert "needs-human" in write_step["run"]
    assert upload_step.get("if") == "always()"
    assert upload_step.get("uses") == "actions/upload-artifact@v7"
    assert upload_step["with"]["name"] == "verifier-terminal-disposition-${{ github.run_id }}"
    assert "agent-metrics/verifier-terminal-disposition.ndjson" in upload_step["with"]["path"]
    assert upload_step["with"]["if-no-files-found"] == "error"
    assert upload_step["with"]["retention-days"] == 14
