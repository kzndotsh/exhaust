from pathlib import Path

import pytest

from exhaust.evidence import (
    EvidenceCopyVerificationError,
    EvidenceFileMissingError,
    PathEscapesScratchError,
    SymlinkEvidenceError,
    promote_evidence,
)


def test_promotes_a_real_file(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "poc.py").write_text("print('exploit')\n")
    evidence_dir = tmp_path / "evidence"

    result = promote_evidence(scratch, Path("poc.py"), evidence_dir)

    assert result == evidence_dir / "poc.py"
    assert result.read_text() == "print('exploit')\n"


def test_promoted_copy_is_byte_identical(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    payload = bytes(range(256)) * 10
    (scratch / "evidence.bin").write_bytes(payload)
    evidence_dir = tmp_path / "evidence"

    result = promote_evidence(scratch, Path("evidence.bin"), evidence_dir)

    assert result.read_bytes() == payload


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    evidence_dir = tmp_path / "evidence"

    with pytest.raises(EvidenceFileMissingError):
        promote_evidence(scratch, Path("does-not-exist.py"), evidence_dir)


def test_directory_is_rejected(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    (scratch / "a_directory").mkdir(parents=True)
    evidence_dir = tmp_path / "evidence"

    with pytest.raises(EvidenceFileMissingError):
        promote_evidence(scratch, Path("a_directory"), evidence_dir)


def test_symlinked_source_is_rejected(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    real_file = tmp_path / "outside_scratch.txt"
    real_file.write_text("not actually agent evidence")
    (scratch / "poc.py").symlink_to(real_file)
    evidence_dir = tmp_path / "evidence"

    with pytest.raises(SymlinkEvidenceError):
        promote_evidence(scratch, Path("poc.py"), evidence_dir)


def test_absolute_path_is_rejected(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    evidence_dir = tmp_path / "evidence"

    with pytest.raises(PathEscapesScratchError):
        promote_evidence(scratch, Path("/etc/passwd"), evidence_dir)


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    evidence_dir = tmp_path / "evidence"

    with pytest.raises(PathEscapesScratchError):
        promote_evidence(scratch, Path("../secret.txt"), evidence_dir)


def test_verification_catches_a_copy_that_doesnt_match_the_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "poc.py").write_text("original")
    evidence_dir = tmp_path / "evidence"

    def _corrupting_copy(src: Path, dst: Path, *, follow_symlinks: bool = True) -> None:
        Path(dst).write_text("tampered, does not match source")

    monkeypatch.setattr("exhaust.evidence.shutil.copy2", _corrupting_copy)

    with pytest.raises(EvidenceCopyVerificationError):
        promote_evidence(scratch, Path("poc.py"), evidence_dir)


def test_destination_becoming_a_symlink_after_copy_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "poc.py").write_text("original")
    evidence_dir = tmp_path / "evidence"
    elsewhere = tmp_path / "elsewhere.txt"
    elsewhere.write_text("planted outside evidence")

    def _copy_that_plants_a_symlink(src: Path, dst: Path, *, follow_symlinks: bool = True) -> None:
        Path(dst).symlink_to(elsewhere)

    monkeypatch.setattr("exhaust.evidence.shutil.copy2", _copy_that_plants_a_symlink)

    with pytest.raises(SymlinkEvidenceError):
        promote_evidence(scratch, Path("poc.py"), evidence_dir)

    assert not (evidence_dir / "poc.py").exists()
