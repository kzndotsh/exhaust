"""Evidence promotion is parent-trusted, never agent-written (ADR 0010).

An investigating agent only ever writes to its own scratch space.
Nothing it writes becomes part of a Finding's permanent evidence
directly: this module is the separate, trusted step that copies one
allowlisted file out of that scratch space into a Finding's retained
evidence, rejecting symlinks and path traversal, and re-checking the
copy's identity after it completes. An agent under adversarial pressure
from a hostile Target, or simply mistaken, should not be able to plant
whatever file it wants into a Finding's permanent record by writing to
the right path.
"""

import hashlib
import shutil
from pathlib import Path


class SymlinkEvidenceError(ValueError):
    """Raised when a file to promote is, or resolves through, a symlink."""


class EvidenceFileMissingError(ValueError):
    """Raised when the file to promote doesn't exist, or isn't a regular file."""


class PathEscapesScratchError(ValueError):
    """Raised when the requested path would resolve outside the scratch dir."""


class EvidenceCopyVerificationError(ValueError):
    """Raised when the copy doesn't match the source after copying."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_within_scratch(scratch_dir: Path, relative_path: Path) -> Path:
    # Lexical only, never resolved: resolving here would follow a symlink
    # before the symlink check below gets to see it, misreporting a
    # malicious symlink as merely "escapes scratch".
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise PathEscapesScratchError(str(relative_path))
    return scratch_dir / relative_path


def promote_evidence(scratch_dir: Path, relative_path: Path, evidence_dir: Path) -> Path:
    """Copy one allowlisted file from scratch into permanent evidence.

    Parameters
    ----------
    scratch_dir : Path
        The agent's own scratch space.
    relative_path : Path
        The file to promote, relative to `scratch_dir`. Must not be
        absolute or escape `scratch_dir` via `..`.
    evidence_dir : Path
        Where to copy the file to. Created if it doesn't exist.

    Returns
    -------
    Path
        The copy's path inside `evidence_dir`.

    Raises
    ------
    PathEscapesScratchError
        If `relative_path` is absolute or resolves outside `scratch_dir`.
    SymlinkEvidenceError
        If the source path is a symlink.
    EvidenceFileMissingError
        If the resolved source path doesn't exist or isn't a regular file.
    EvidenceCopyVerificationError
        If the copy's hash doesn't match the source's after copying.
    """
    source = _resolve_within_scratch(scratch_dir, relative_path)

    if source.is_symlink():
        raise SymlinkEvidenceError(str(source))
    if not source.is_file():
        raise EvidenceFileMissingError(str(source))

    source_hash = _sha256(source)

    evidence_dir.mkdir(parents=True, exist_ok=True)
    destination = evidence_dir / relative_path.name
    shutil.copy2(source, destination, follow_symlinks=False)

    if destination.is_symlink():
        destination.unlink()
        raise SymlinkEvidenceError(str(destination))
    if _sha256(destination) != source_hash:
        raise EvidenceCopyVerificationError(str(destination))

    return destination
