import contextlib
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from exhaust import __version__
from exhaust.cli import app
from exhaust.harness.pi_adapter import PiAgentSession

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_new_scaffolds_a_workspace(tmp_path: Path) -> None:
    target_dir = tmp_path / "roundcube"
    result = runner.invoke(app, ["new", "roundcube", "--path", str(target_dir)])
    assert result.exit_code == 0
    assert (target_dir / "BRIEF.md").is_file()


def test_new_refuses_to_overwrite(tmp_path: Path) -> None:
    target_dir = tmp_path / "roundcube"
    runner.invoke(app, ["new", "roundcube", "--path", str(target_dir)])
    result = runner.invoke(app, ["new", "roundcube", "--path", str(target_dir)])
    assert result.exit_code == 1


def test_catalog_generate_writes_an_empty_catalog(tmp_path: Path) -> None:
    output = tmp_path / "catalog.json"
    result = runner.invoke(
        app,
        [
            "catalog",
            "generate",
            "--skills-dir",
            str(tmp_path / "skills"),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.is_file()


def test_catalog_generate_reports_a_malformed_skill_file(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "injection"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("no front matter here\n")

    result = runner.invoke(
        app,
        [
            "catalog",
            "generate",
            "--skills-dir",
            str(tmp_path / "skills"),
            "--output",
            str(tmp_path / "catalog.json"),
        ],
    )
    assert result.exit_code == 1


def test_catalog_check_passes_once_generated(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    output = tmp_path / "catalog.json"
    runner.invoke(
        app,
        ["catalog", "generate", "--skills-dir", str(skills_dir), "--output", str(output)],
    )

    result = runner.invoke(
        app, ["catalog", "check", "--skills-dir", str(skills_dir), "--output", str(output)]
    )
    assert result.exit_code == 0


def test_catalog_check_fails_on_drift(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    output = tmp_path / "catalog.json"
    runner.invoke(
        app,
        ["catalog", "generate", "--skills-dir", str(skills_dir), "--output", str(output)],
    )

    skill_dir = skills_dir / "injection"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: injection\nrequired: true\n---\nBody.\n")

    result = runner.invoke(
        app, ["catalog", "check", "--skills-dir", str(skills_dir), "--output", str(output)]
    )
    assert result.exit_code == 1


def test_catalog_check_reports_a_malformed_skill_file(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    output = tmp_path / "catalog.json"
    # A prior committed output must exist, or is_catalog_up_to_date() short-circuits
    # on the missing file before ever reading skills_dir, and the malformed skill
    # file would never actually be parsed.
    output.write_text('{"verticals": []}\n')

    skill_dir = skills_dir / "injection"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("no front matter here\n")

    result = runner.invoke(
        app, ["catalog", "check", "--skills-dir", str(skills_dir), "--output", str(output)]
    )
    assert result.exit_code == 1


class _FakeSession:
    def step(self, request: object) -> None:  # pragma: no cover - never called in these tests
        raise AssertionError("step() should not be called when no verticals exist")

    def observe(self, outcome: object) -> None:  # pragma: no cover - never called
        raise AssertionError("observe() should not be called when no verticals exist")


@contextlib.contextmanager
def _fake_launch(cfg: object, *, socket_path: Path) -> Generator[_FakeSession, None, None]:
    yield _FakeSession()


def test_run_refuses_a_missing_workspace(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "roundcube", "--workspace", str(tmp_path / "nope"), "--model", "some-model"],
    )
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_run_drives_a_workspace_with_no_verticals_to_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No skill files means no verticals at all, so Harness.run() sees the Workspace
    # as trivially done before ever calling the agent's step()/observe() — this
    # exercises the CLI's own wiring (PiLaunchConfig, Harness.open/run, output
    # formatting) without spawning a real pi subprocess.
    monkeypatch.setattr(PiAgentSession, "launch", _fake_launch)

    workspace_dir = tmp_path / "roundcube"
    workspace_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "run",
            "roundcube",
            "--workspace",
            str(workspace_dir),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--model",
            "some-model",
        ],
    )
    assert result.exit_code == 0
    assert "(no verticals)" in result.output


def test_doctor_reports_each_pinned_tool() -> None:
    result = runner.invoke(app, ["doctor"])
    assert "nmap: pinned" in result.output
