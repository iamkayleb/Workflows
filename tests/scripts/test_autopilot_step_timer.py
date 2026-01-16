from pathlib import Path

from scripts import autopilot_step_timer as timer


def test_default_key_epoch_start() -> None:
    assert timer.default_key("start", "epoch-ms") == "AUTOPILOT_STEP_STARTED_AT_MS"


def test_default_key_iso_end() -> None:
    assert timer.default_key("end", "iso") == "AUTOPILOT_STEP_ENDED_AT"


def test_timestamp_value_epoch(monkeypatch) -> None:
    monkeypatch.setattr(timer, "_utc_now_epoch_ms", lambda: 1234)

    assert timer.timestamp_value("epoch-ms") == "1234"


def test_timestamp_value_iso(monkeypatch) -> None:
    monkeypatch.setattr(timer, "_utc_now_iso", lambda: "2025-01-02T03:04:05Z")

    assert timer.timestamp_value("iso") == "2025-01-02T03:04:05Z"


def test_append_env_writes_value(tmp_path: Path) -> None:
    path = tmp_path / "env.out"

    timer.append_env(path, "AUTOPILOT_STEP_STARTED_AT_MS", "999")

    assert path.read_text(encoding="utf-8") == "AUTOPILOT_STEP_STARTED_AT_MS=999\n"
