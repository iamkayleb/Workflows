import json
import urllib.error

import pytest
from scripts import state_fingerprint


class MemoryStorage:
    def __init__(self, value: str | None = None) -> None:
        self.value = value
        self.writes: list[str] = []

    def read_fingerprint(self, workflow_name: str) -> str | None:
        return state_fingerprint._extract_hash(self.value, workflow_name)

    def write_fingerprint(self, workflow_name: str, fingerprint_hash: str) -> None:
        self.value = state_fingerprint._build_marker(workflow_name, fingerprint_hash)
        self.writes.append(fingerprint_hash)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class FakeApi:
    def __init__(self, values: dict[str, object] | None = None) -> None:
        self.repo = "owner/repo"
        self.values = values or {}
        self.requests: list[tuple[str, str, dict | None]] = []

    def request(self, method: str, path: str, body: dict | None = None) -> object:
        self.requests.append((method, path, body))
        key = f"{method} {path}"
        value = self.values.get(key)
        if isinstance(value, Exception):
            raise value
        return value


def test_compute_fingerprint_canonicalizes_key_order() -> None:
    first = state_fingerprint.compute_fingerprint("wf", {"b": 2, "a": {"d": 4, "c": 3}})
    second = state_fingerprint.compute_fingerprint("wf", {"a": {"c": 3, "d": 4}, "b": 2})

    assert first == second


def test_compare_detects_changed_inputs() -> None:
    prior = state_fingerprint.compute_fingerprint("wf", {"head_sha": "old"})
    storage = MemoryStorage(state_fingerprint._build_marker("wf", prior))

    decision = state_fingerprint.compare_fingerprint("wf", {"head_sha": "new"}, storage)

    assert decision.should_run is True
    assert decision.reason == "fingerprint-changed"
    assert decision.prior_hash == prior
    assert decision.current_hash != prior


def test_compare_skips_when_state_is_unchanged() -> None:
    current = {"head_sha": "abc", "labels": ["autofix"]}
    prior = state_fingerprint.compute_fingerprint("wf", current)
    storage = MemoryStorage(state_fingerprint._build_marker("wf", prior))

    decision = state_fingerprint.compare_fingerprint("wf", current, storage)

    assert decision.should_run is False
    assert decision.reason == "fingerprint-match"
    assert decision.prior_hash == decision.current_hash


def test_missing_marker_is_first_run_behavior() -> None:
    storage = MemoryStorage()

    decision = state_fingerprint.compare_fingerprint("wf", {"head_sha": "abc"}, storage)

    assert decision.should_run is True
    assert decision.reason == "no-prior-fingerprint"
    assert decision.prior_hash is None


def test_warning_mode_bypasses_skip_and_logs_delta(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    current = {"head_sha": "abc"}
    prior = state_fingerprint.compute_fingerprint("wf", current)
    storage = MemoryStorage(state_fingerprint._build_marker("wf", prior))

    monkeypatch.setattr(state_fingerprint, "_storage_from_name", lambda _name, _workflow: storage)

    exit_code = state_fingerprint.main(
        [
            "compare",
            "--workflow",
            "wf",
            "--inputs",
            json.dumps(current),
            "--storage",
            "pr-comment",
            "--mode",
            "warning",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "state fingerprint warning mode" in captured.err
    outputs = json.loads(captured.out)
    assert outputs["should_run"] == "true"
    assert outputs["reason"] == "warning-mode:fingerprint-match"
    assert storage.writes == [prior]


def test_malformed_prior_marker_is_tolerated() -> None:
    storage = MemoryStorage('<!-- fingerprint:wf:v1 {"hash": -->')

    decision = state_fingerprint.compare_fingerprint("wf", {"head_sha": "abc"}, storage)

    assert decision.should_run is True
    assert decision.reason == "no-prior-fingerprint"
    assert decision.prior_hash is None


def test_extract_hash_accepts_raw_json_storage_value() -> None:
    fingerprint_hash = "a" * 64

    assert (
        state_fingerprint._extract_hash(json.dumps({"hash": fingerprint_hash}), "wf")
        == fingerprint_hash
    )


def test_variable_name_is_stable_and_within_github_limit() -> None:
    workflow_name = "Verifier " + ("very-long-name-" * 20)

    first = state_fingerprint._variable_name(workflow_name)
    second = state_fingerprint._variable_name(workflow_name)

    assert first == second
    assert first.startswith("STATE_FINGERPRINT_VERIFIER_")
    assert len(first) <= 100


def test_repo_variable_storage_reads_existing_variable() -> None:
    fingerprint_hash = "b" * 64
    api = FakeApi(
        {
            "GET /repos/owner/repo/actions/variables/STATE_FINGERPRINT_TEST": {
                "value": json.dumps({"hash": fingerprint_hash})
            }
        }
    )
    storage = state_fingerprint.RepoVariableStorage(api, "STATE_FINGERPRINT_TEST")  # type: ignore[arg-type]

    assert storage.read_fingerprint("wf") == fingerprint_hash


def test_repo_variable_storage_creates_missing_variable() -> None:
    api = FakeApi(
        {
            "PATCH /repos/owner/repo/actions/variables/STATE_FINGERPRINT_TEST": RuntimeError(
                "GitHub API PATCH /repos/owner/repo/actions/variables/STATE_FINGERPRINT_TEST failed: 404 missing"
            )
        }
    )
    storage = state_fingerprint.RepoVariableStorage(api, "STATE_FINGERPRINT_TEST")  # type: ignore[arg-type]

    storage.write_fingerprint("wf", "c" * 64)

    assert api.requests[0][0] == "PATCH"
    assert api.requests[1][0] == "POST"
    assert api.requests[1][1] == "/repos/owner/repo/actions/variables"


def test_github_api_wraps_url_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_url_error(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(state_fingerprint.urllib.request, "urlopen", raise_url_error)

    api = state_fingerprint.GitHubApi("owner/repo", "token")
    with pytest.raises(RuntimeError, match=r"GitHub API GET /repos/owner/repo failed:"):
        api.request("GET", "/repos/owner/repo")


def test_github_api_wraps_json_decode_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        state_fingerprint.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b"{not json"),
    )

    api = state_fingerprint.GitHubApi("owner/repo", "token")
    with pytest.raises(
        RuntimeError, match=r"GitHub API GET /repos/owner/repo returned invalid JSON:"
    ):
        api.request("GET", "/repos/owner/repo")


def test_main_catches_unexpected_exceptions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_value_error(_name: str, _workflow: str) -> MemoryStorage:
        raise ValueError("storage exploded")

    monkeypatch.setattr(state_fingerprint, "_storage_from_name", raise_value_error)

    exit_code = state_fingerprint.main(
        ["compare", "--workflow", "wf", "--inputs", "{}", "--storage", "pr-comment"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.strip() == "storage exploded"
