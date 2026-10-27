from pathlib import Path

from typer.testing import CliRunner

from exhaust import __version__
from exhaust.cli import app

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
