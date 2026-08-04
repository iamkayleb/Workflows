import os
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.check_deliberate_break as deliberate_break
from scripts.check_deliberate_break import (
    PYTEST_RUNTIME_DEPENDENCIES,
    VERDICT_BROKEN,
    VERDICT_HOLLOW,
    VERDICT_PASS,
    parse_deliberate_break_spec,
    verify_spec,
)


def _run(repo: Path, *args: str) -> None:
    subprocess.run(args, cwd=repo, check=True, text=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.email", "test@example.com")
    _run(repo, "git", "config", "user.name", "Test User")


def _commit(repo: Path, message: str) -> str:
    _run(repo, "git", "add", ".")
    _run(repo, "git", "commit", "-qm", message)
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
    ).strip()


def _write_app(repo: Path, value: int) -> None:
    (repo / "app.py").write_text(
        f"def value():\n    return {value}\n",
        encoding="utf-8",
    )


def _write_test(repo: Path, expected: int) -> None:
    test_file = repo / "tests" / "test_app.py"
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text(
        f"import app\n\n\ndef test_value():\n    assert app.value() == {expected}\n",
        encoding="utf-8",
    )


def test_hollow_detected(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_app(repo, 1)
    base = _commit(repo, "base behavior")
    _write_test(repo, 1)
    _commit(repo, "candidate test")
    monkeypatch.chdir(repo)

    spec = parse_deliberate_break_spec(
        "<!-- deliberate-break: "
        "test=tests/test_app.py::test_value "
        "test-file=tests/test_app.py "
        "break-file=app.py -->"
    )
    assert spec is not None

    result = verify_spec(spec, base=base, enforce_tamper=False)

    assert result["verdict"] == VERDICT_HOLLOW


def test_sound_passes(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_app(repo, 0)
    base = _commit(repo, "base behavior")
    _write_app(repo, 1)
    _write_test(repo, 1)
    _commit(repo, "implementation and test")
    monkeypatch.chdir(repo)

    spec = parse_deliberate_break_spec(
        "<!-- deliberate-break: "
        "test=tests/test_app.py::test_value "
        "test-file=tests/test_app.py "
        "break-file=app.py -->"
    )
    assert spec is not None

    result = verify_spec(spec, base=base, enforce_tamper=False)

    assert result["verdict"] == VERDICT_PASS


def test_no_marker_returns_none() -> None:
    assert parse_deliberate_break_spec("## Acceptance Criteria\n- [ ] normal check") is None


def test_issue_acceptance_wording_is_supported() -> None:
    spec = parse_deliberate_break_spec(
        "## Acceptance Criteria\n\n"
        "- [ ] Named test: add `tests/scripts/test_check_deliberate_break.py` "
        "with `test_hollow_detected` (build a tmp git repo).\n"
        "- [ ] **Deliberate-break gate:** temporarily edit "
        "`scripts/check_deliberate_break.py` to skip the base-rerun.\n"
    )

    assert spec is not None
    assert spec.test_id == "tests/scripts/test_check_deliberate_break.py::test_hollow_detected"
    assert spec.test_file == "tests/scripts/test_check_deliberate_break.py"
    assert spec.break_file == "scripts/check_deliberate_break.py"


def test_assertion_tamper_is_flagged(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_app(repo, 0)
    _write_test(repo, 0)
    base = _commit(repo, "base test")
    _write_app(repo, 1)
    _write_test(repo, 1)
    _commit(repo, "tampered candidate")
    monkeypatch.chdir(repo)

    spec = parse_deliberate_break_spec(
        "<!-- deliberate-break: "
        "test=tests/test_app.py::test_value "
        "test-file=tests/test_app.py "
        "break-file=app.py -->"
    )
    assert spec is not None

    result = verify_spec(spec, base=base)

    assert result["verdict"] == VERDICT_BROKEN
    assert result["reason"] == "test-assertion-tamper"


def test_tamper_git_failure_is_broken(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_app(repo, 0)
    _write_test(repo, 0)
    base = _commit(repo, "base test")
    spec = parse_deliberate_break_spec(
        "<!-- deliberate-break: "
        "test=tests/test_app.py::test_value "
        "test-file=tests/test_app.py "
        "break-file=app.py -->"
    )
    assert spec is not None

    def fail_tamper_check(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            128,
            ["git", "diff", f"{base}...HEAD"],
            output="",
            stderr="bad revision",
        )

    monkeypatch.setattr(deliberate_break, "_changed_assertions", fail_tamper_check)

    result = verify_spec(spec, base=base, cwd=repo)

    assert result == {
        "verdict": VERDICT_BROKEN,
        "reason": "tamper-check-failed",
        "command": ["git", "diff", f"{base}...HEAD"],
        "returncode": 128,
        "stdout": "",
        "stderr": "bad revision",
    }


def test_new_assertion_in_existing_test_file_is_not_tamper(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_app(repo, 0)
    test_file = repo / "tests" / "test_app.py"
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text(
        "def test_existing_value():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    base = _commit(repo, "base test")
    _write_app(repo, 1)
    test_file.write_text(
        "import app\n\n\n"
        "def test_existing_value():\n"
        "    assert 1 + 1 == 2\n\n\n"
        "def test_value():\n"
        "    assert app.value() == 1\n",
        encoding="utf-8",
    )
    _commit(repo, "implementation and added assertion")
    monkeypatch.chdir(repo)

    spec = parse_deliberate_break_spec(
        "<!-- deliberate-break: "
        "test=tests/test_app.py::test_value "
        "test-file=tests/test_app.py "
        "break-file=app.py -->"
    )
    assert spec is not None

    result = verify_spec(spec, base=base)

    assert result["verdict"] == VERDICT_PASS


def test_added_acceptance_test_is_not_tamper(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_app(repo, 0)
    base = _commit(repo, "base behavior")
    _write_app(repo, 1)
    _write_test(repo, 1)
    _commit(repo, "implementation and new test")
    monkeypatch.chdir(repo)

    spec = parse_deliberate_break_spec(
        "<!-- deliberate-break: "
        "test=tests/test_app.py::test_value "
        "test-file=tests/test_app.py "
        "break-file=app.py -->"
    )
    assert spec is not None

    result = verify_spec(spec, base=base)

    assert result["verdict"] == VERDICT_PASS


def test_cli_skips_without_marker(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "scripts" / "check_deliberate_break.py"),
            "--base",
            "HEAD",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env={**os.environ, "PR_BODY": "## Acceptance Criteria\n- [ ] normal"},
    )

    assert completed.returncode == 0
    assert "skipped: no deliberate-break marker" in completed.stdout


@pytest.mark.parametrize("installed_version", [None, "6.0.2"])
def test_runtime_dependency_installer_uses_locked_pyyaml(monkeypatch, installed_version) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    def package_version(_name):
        if installed_version is None:
            raise deliberate_break.metadata.PackageNotFoundError
        return installed_version

    def record_install(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(deliberate_break.metadata, "version", package_version)
    monkeypatch.setattr(deliberate_break, "import_module", lambda _name: object())
    monkeypatch.setattr(deliberate_break.subprocess, "run", record_install)

    deliberate_break._ensure_pytest_runtime_deps()

    assert calls == [
        (
            (
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    *PYTEST_RUNTIME_DEPENDENCIES,
                ],
            ),
            {
                "check": True,
                "text": True,
                "capture_output": True,
                "timeout": deliberate_break.DEFAULT_TIMEOUT_SECONDS,
            },
        )
    ]


def test_runtime_dependency_installer_accepts_exact_locked_pyyaml(monkeypatch) -> None:
    calls: list[object] = []

    monkeypatch.setattr(
        deliberate_break.metadata,
        "version",
        lambda _name: deliberate_break.PYYAML_VERSION,
    )
    monkeypatch.setattr(deliberate_break, "import_module", lambda _name: object())
    monkeypatch.setattr(
        deliberate_break.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    deliberate_break._ensure_pytest_runtime_deps()

    assert calls == []


@pytest.mark.parametrize("import_error", [ImportError, OSError, AttributeError, SyntaxError])
def test_runtime_dependency_installer_repairs_broken_pyyaml_import(
    monkeypatch, import_error
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    imports = 0
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    def broken_import(_name):
        nonlocal imports
        imports += 1
        if imports == 1:
            raise import_error("broken PyYAML install")
        return object()

    monkeypatch.setattr(
        deliberate_break.metadata,
        "version",
        lambda _name: deliberate_break.PYYAML_VERSION,
    )
    monkeypatch.setattr(deliberate_break, "import_module", broken_import)
    monkeypatch.setattr(
        deliberate_break.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    deliberate_break._ensure_pytest_runtime_deps()

    assert len(calls) == 1
    assert calls[0][0][0][-1] == f"pyyaml=={deliberate_break.PYYAML_VERSION}"
    assert "--force-reinstall" in calls[0][0][0]
    assert imports == 2


def test_runtime_dependency_installer_preserves_initial_import_failure(
    monkeypatch,
) -> None:
    initial_error = OSError("broken PyYAML install")
    imports = 0
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    def broken_import(_name):
        nonlocal imports
        imports += 1
        if imports == 1:
            raise initial_error
        raise AttributeError("still broken after reinstall")

    monkeypatch.setattr(
        deliberate_break.metadata,
        "version",
        lambda _name: deliberate_break.PYYAML_VERSION,
    )
    monkeypatch.setattr(deliberate_break, "import_module", broken_import)
    monkeypatch.setattr(
        deliberate_break.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )

    with pytest.raises(ImportError, match="still broken after reinstall") as caught:
        deliberate_break._ensure_pytest_runtime_deps()

    assert caught.value.__cause__ is initial_error
    assert imports == 2


def test_runtime_dependency_installer_does_not_modify_local_environment(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(
        deliberate_break.metadata,
        "version",
        lambda _name: (_ for _ in ()).throw(deliberate_break.metadata.PackageNotFoundError),
    )
    monkeypatch.setattr(
        deliberate_break.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("local dependency install should not run"),
    )

    with pytest.raises(ImportError, match="install pyyaml=="):
        deliberate_break._ensure_pytest_runtime_deps()


def test_runtime_dependencies_are_not_installed_for_successful_custom_command(
    tmp_path, monkeypatch
) -> None:
    completed = subprocess.CompletedProcess(["custom-check"], 0, "ok", "")
    monkeypatch.setattr(deliberate_break, "_run", lambda *_args: completed)
    monkeypatch.setattr(
        deliberate_break,
        "_ensure_pytest_runtime_deps",
        lambda: pytest.fail("dependency repair should not run"),
    )

    assert deliberate_break._run_with_runtime_deps(("custom-check",), tmp_path) is completed


def test_runtime_dependencies_are_not_installed_for_unrelated_failure(
    tmp_path, monkeypatch
) -> None:
    completed = subprocess.CompletedProcess(["custom-check"], 1, "", "assertion failed")
    monkeypatch.setattr(deliberate_break, "_run", lambda *_args: completed)
    monkeypatch.setattr(
        deliberate_break,
        "_ensure_pytest_runtime_deps",
        lambda: pytest.fail("dependency repair should not run"),
    )

    assert deliberate_break._run_with_runtime_deps(("custom-check",), tmp_path) is completed


def test_runtime_dependencies_are_not_installed_for_unrelated_pyyaml_mention(
    tmp_path, monkeypatch
) -> None:
    completed = subprocess.CompletedProcess(
        ["custom-check"], 1, "", "test_pyyaml_behavior: assertion failed"
    )
    monkeypatch.setattr(deliberate_break, "_run", lambda *_args: completed)
    monkeypatch.setattr(
        deliberate_break,
        "_ensure_pytest_runtime_deps",
        lambda: pytest.fail("dependency repair should not run"),
    )

    assert deliberate_break._run_with_runtime_deps(("custom-check",), tmp_path) is completed


def test_runtime_dependencies_retry_pyyaml_import_failure(tmp_path, monkeypatch) -> None:
    attempts = [
        subprocess.CompletedProcess(
            ["pytest"],
            1,
            "",
            "ModuleNotFoundError: No module named 'yaml'",
        ),
        subprocess.CompletedProcess(["pytest"], 0, "passed", ""),
    ]
    repairs: list[bool] = []
    monkeypatch.setattr(deliberate_break, "_run", lambda *_args: attempts.pop(0))
    monkeypatch.setattr(
        deliberate_break,
        "_ensure_pytest_runtime_deps",
        lambda: repairs.append(True),
    )

    completed = deliberate_break._run_with_runtime_deps(("pytest",), tmp_path)

    assert completed.returncode == 0
    assert repairs == [True]
    assert attempts == []


def test_runtime_dependencies_retry_broken_pyyaml_traceback(tmp_path, monkeypatch) -> None:
    attempts = [
        subprocess.CompletedProcess(
            ["pytest"],
            1,
            "",
            'File "/venv/lib/site-packages/yaml/__init__.py", line 1\nSyntaxError: invalid syntax',
        ),
        subprocess.CompletedProcess(["pytest"], 0, "passed", ""),
    ]
    repairs: list[bool] = []
    monkeypatch.setattr(deliberate_break, "_run", lambda *_args: attempts.pop(0))
    monkeypatch.setattr(
        deliberate_break,
        "import_module",
        lambda _name: (_ for _ in ()).throw(SyntaxError("broken wheel")),
    )
    monkeypatch.setattr(
        deliberate_break,
        "_ensure_pytest_runtime_deps",
        lambda: repairs.append(True),
    )

    completed = deliberate_break._run_with_runtime_deps(("pytest",), tmp_path)

    assert completed.returncode == 0
    assert repairs == [True]
    assert attempts == []


def test_runtime_dependencies_retry_stale_pyyaml_traceback(tmp_path, monkeypatch) -> None:
    attempts = [
        subprocess.CompletedProcess(
            ["pytest"],
            1,
            "",
            'File "/venv/lib/site-packages/yaml/__init__.py", line 1\nRuntimeError: stale',
        ),
        subprocess.CompletedProcess(["pytest"], 0, "passed", ""),
    ]
    repairs: list[bool] = []
    monkeypatch.setattr(deliberate_break, "_run", lambda *_args: attempts.pop(0))
    monkeypatch.setattr(deliberate_break.metadata, "version", lambda _name: "6.0.2")
    monkeypatch.setattr(
        deliberate_break,
        "_ensure_pytest_runtime_deps",
        lambda: repairs.append(True),
    )

    completed = deliberate_break._run_with_runtime_deps(("pytest",), tmp_path)

    assert completed.returncode == 0
    assert repairs == [True]
    assert attempts == []


def _sound_spec(repo: Path) -> tuple[str, object]:
    _write_app(repo, 0)
    base = _commit(repo, "base behavior")
    _write_app(repo, 1)
    _write_test(repo, 1)
    _commit(repo, "implementation and test")
    spec = parse_deliberate_break_spec(
        "<!-- deliberate-break: "
        "test=tests/test_app.py::test_value "
        "test-file=tests/test_app.py "
        "break-file=app.py -->"
    )
    assert spec is not None
    return base, spec


def test_dependency_install_timeout_is_broken(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    base, spec = _sound_spec(repo)
    command = [sys.executable, "-m", "pip", "install", *PYTEST_RUNTIME_DEPENDENCIES]

    monkeypatch.setattr(
        deliberate_break,
        "_run_with_runtime_deps",
        lambda *_args: (_ for _ in ()).throw(
            deliberate_break.RuntimeDependencyError(subprocess.TimeoutExpired(command, 17))
        ),
    )

    result = verify_spec(spec, base=base, cwd=repo, enforce_tamper=False)

    assert result == {
        "verdict": VERDICT_BROKEN,
        "reason": "command-timeout",
        "command": command,
        "timeout": 17,
    }


def test_dependency_install_failure_preserves_subprocess_context(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    base, spec = _sound_spec(repo)
    error = subprocess.CalledProcessError(
        17,
        ["pip", "install", "pyyaml==6.0.3"],
        output="resolver output",
        stderr="pip denied",
    )

    monkeypatch.setattr(
        deliberate_break,
        "_run_with_runtime_deps",
        lambda *_args: (_ for _ in ()).throw(deliberate_break.RuntimeDependencyError(error)),
    )

    result = verify_spec(spec, base=base, cwd=repo, enforce_tamper=False)

    assert result == {
        "verdict": VERDICT_BROKEN,
        "reason": "dependency-install-failed",
        "command": ["pip", "install", "pyyaml==6.0.3"],
        "returncode": 17,
        "stdout": "resolver output",
        "stderr": "pip denied",
    }


def test_dependency_install_unavailable_is_broken(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    base, spec = _sound_spec(repo)

    monkeypatch.setattr(
        deliberate_break,
        "_run_with_runtime_deps",
        lambda *_args: (_ for _ in ()).throw(
            deliberate_break.RuntimeDependencyError(OSError("pip unavailable"))
        ),
    )

    result = verify_spec(spec, base=base, cwd=repo, enforce_tamper=False)

    assert result == {
        "verdict": VERDICT_BROKEN,
        "reason": "dependency-install-unavailable",
        "detail": "pip unavailable",
    }


def test_dependency_import_failure_is_broken(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    base, spec = _sound_spec(repo)
    original = OSError("original import failed")

    def failed() -> None:
        try:
            raise ImportError("retry failed") from original
        except ImportError as exc:
            raise deliberate_break.RuntimeDependencyError(exc) from exc

    monkeypatch.setattr(
        deliberate_break,
        "_run_with_runtime_deps",
        lambda *_args: failed(),
    )

    result = verify_spec(spec, base=base, cwd=repo, enforce_tamper=False)

    assert result == {
        "verdict": VERDICT_BROKEN,
        "reason": "dependency-import-failed",
        "detail": "retry failed",
        "cause": "original import failed",
    }


def test_base_archive_command_failure_is_not_dependency_failure(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    base, spec = _sound_spec(repo)
    error = subprocess.CalledProcessError(
        17,
        ["git", "archive", base],
        output="archive output",
        stderr="bad ref",
    )
    monkeypatch.setattr(
        deliberate_break,
        "_archive_ref",
        lambda *_args: (_ for _ in ()).throw(error),
    )

    result = verify_spec(spec, base=base, cwd=repo, enforce_tamper=False)

    assert result == {
        "verdict": VERDICT_BROKEN,
        "reason": "archive-command-failed",
        "command": ["git", "archive", base],
        "returncode": 17,
        "stdout": "archive output",
        "stderr": "bad ref",
    }


def test_base_setup_failure_is_not_dependency_failure(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    base, spec = _sound_spec(repo)
    monkeypatch.setattr(
        deliberate_break,
        "_archive_ref",
        lambda *_args: (_ for _ in ()).throw(OSError("disk unavailable")),
    )

    result = verify_spec(spec, base=base, cwd=repo, enforce_tamper=False)

    assert result == {
        "verdict": VERDICT_BROKEN,
        "reason": "base-setup-failed",
        "detail": "disk unavailable",
    }


def test_base_command_launch_failure_is_reported_as_command_unavailable(
    tmp_path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    base, spec = _sound_spec(repo)
    calls = 0

    def run_command(*_args):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(spec.command, 0, "", "")
        error = FileNotFoundError("base-only command is unavailable")
        raise deliberate_break.CommandUnavailableError(error) from error

    monkeypatch.setattr(deliberate_break, "_run_with_runtime_deps", run_command)

    result = verify_spec(spec, base=base, cwd=repo, enforce_tamper=False)

    assert result == {
        "verdict": VERDICT_BROKEN,
        "reason": "command-unavailable",
        "command": list(spec.command),
        "detail": "base-only command is unavailable",
    }
