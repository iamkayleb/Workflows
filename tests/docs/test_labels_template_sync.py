"""Keep the consumer-synced label guide aligned with the canonical guide."""

from pathlib import Path


def test_consumer_template_labels_doc_matches_canonical_doc() -> None:
    canonical = Path("docs/LABELS.md").read_text(encoding="utf-8")
    template = Path("templates/consumer-repo/docs/LABELS.md").read_text(encoding="utf-8")

    assert template == canonical
