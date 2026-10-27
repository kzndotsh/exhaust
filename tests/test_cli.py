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
