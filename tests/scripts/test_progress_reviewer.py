from __future__ import annotations

import json
import subprocess
import sys

from scripts.langchain import progress_reviewer


def test_build_review_payload_includes_review_fields():
    result = progress_reviewer.review_progress(
        acceptance_criteria=["Add guard to progress review comments"],
        recent_commits=["chore: update progress reviewer"],
        files_changed=["scripts/langchain/progress_reviewer.py"],
        rounds_without_completion=2,
        use_llm=False,
    )

    payload = progress_reviewer.build_review_payload(result)
    review = payload.get("review")

    assert isinstance(review, dict)
    assert review["score"] == result.alignment_score
    assert review["feedback"] == result.feedback_for_agent
    assert "suggestions" in review


def test_json_output_contains_review_fields():
    result = progress_reviewer.review_progress(
        acceptance_criteria=[],
        recent_commits=[],
        files_changed=[],
        rounds_without_completion=0,
        use_llm=False,
    )

    payload = progress_reviewer.build_review_payload(result)
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)

    assert "review" in decoded
    assert set(decoded["review"].keys()) == {"score", "feedback", "suggestions"}


def test_heuristic_alignment_handles_snake_case_tokens():
    result = progress_reviewer.review_progress(
        acceptance_criteria=[
            "Running `render_cprs_ch_png(...)` generates PNGs without errors.",
        ],
        recent_commits=[
            "Define explicit CPRS-CH PNG column layout",
        ],
        files_changed=[
            "src/counter_risk/renderers/table_png.py",
        ],
        rounds_without_completion=22,
        use_llm=False,
    )

    assert result.alignment_score > 0
    assert result.recommendation != "STOP"


def test_cli_accumulates_repeated_flags(tmp_path):
    script = "scripts/langchain/progress_reviewer.py"
    proc = subprocess.run(
        [
            sys.executable,
            script,
            "--acceptance-criteria",
            "Criterion one",
            "--acceptance-criteria",
            "Criterion two",
            "--recent-commits",
            "commit one",
            "--recent-commits",
            "commit two",
            "--files-changed",
            "a.py",
            "--files-changed",
            "b.py",
            "--rounds-without-completion",
            "10",
            "--json",
            "--no-llm",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.stdout
    payload = json.loads(proc.stdout)
    assert "summary" in payload
    # The heuristic summary embeds the denominator; ensure it saw both commits.
    assert "/2 commits" in payload["summary"]
