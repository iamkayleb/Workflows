"""Keep the consumer label guide bound to its consumer-specific source."""

from pathlib import Path

import yaml


def test_consumer_template_labels_doc_is_the_manifest_source() -> None:
    manifest = yaml.safe_load(Path(".github/sync-manifest.yml").read_text(encoding="utf-8"))
    entries = manifest.get("docs") or []
    labels_entry = [entry for entry in entries if entry.get("target") == "docs/LABELS.md"]

    assert labels_entry == [
        {
            "source": "templates/consumer-repo/docs/LABELS.md",
            "target": "docs/LABELS.md",
            "description": "Label definitions and usage",
        }
    ]


def test_consumer_template_labels_exclude_workflows_only_retry_surfaces() -> None:
    root = Path("docs/LABELS.md").read_text(encoding="utf-8")
    template = Path("templates/consumer-repo/docs/LABELS.md").read_text(encoding="utf-8")

    assert "agents-keepalive-loop.yml" in root
    assert "agents-keepalive-loop.yml" not in template
    assert "agents-pr-meta-v4.yml" not in template
    assert "agents-81-gate-followups.yml" in template
