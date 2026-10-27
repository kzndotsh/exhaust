from pathlib import Path

import pytest

from exhaust.workspace import scaffold_workspace


def test_scaffold_creates_expected_layout(tmp_path: Path) -> None:
    workspace = tmp_path / "roundcube"
    scaffold_workspace(workspace, "roundcube")

    assert (workspace / "AGENTS.md").is_file()
    assert (workspace / "BRIEF.md").is_file()
    assert (workspace / "sandbox" / "docker-compose.yml").is_file()
    assert (workspace / "poc").is_dir()
    assert (workspace / "findings").is_dir()
    assert "roundcube" in (workspace / "BRIEF.md").read_text()


def test_scaffold_never_creates_a_scope_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "roundcube"
    scaffold_workspace(workspace, "roundcube")

    assert not (workspace / "SCOPE_CONTRACT.yaml").exists()


def test_scaffold_refuses_to_overwrite_existing_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "roundcube"
    scaffold_workspace(workspace, "roundcube")

    with pytest.raises(FileExistsError):
        scaffold_workspace(workspace, "roundcube")
