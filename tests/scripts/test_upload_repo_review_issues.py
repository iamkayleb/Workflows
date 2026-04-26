import json
from pathlib import Path

from scripts import upload_repo_review_issues as uploader


def test_load_queue_returns_issue_list(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps({"issues": [{"repo": "owner/repo", "title": "Do work"}]}),
        encoding="utf-8",
    )

    assert uploader.load_queue(queue) == [{"repo": "owner/repo", "title": "Do work"}]


def test_upload_dry_run_skips_exact_title_duplicates(monkeypatch) -> None:
    def fake_fetch_open_issues(repo: str, prefix: list[str]):
        assert repo == "owner/repo"
        assert prefix == ["gh"]
        return [
            {
                "number": 5,
                "title": "Existing issue",
                "url": "https://github.test/owner/repo/issues/5",
                "labels": [],
            }
        ]

    monkeypatch.setattr(uploader, "fetch_open_issues", fake_fetch_open_issues)
    issues = [
        {"repo": "owner/repo", "title": "Existing issue", "labels": []},
        {"repo": "owner/repo", "title": "New issue", "labels": []},
    ]

    summary = uploader.upload_issues(issues, prefix=["gh"], apply=False)

    assert summary["skipped_duplicates"] == [
        {
            "repo": "owner/repo",
            "title": "Existing issue",
            "number": 5,
            "url": "https://github.test/owner/repo/issues/5",
        }
    ]
    assert summary["would_create"] == [{"repo": "owner/repo", "title": "New issue"}]
