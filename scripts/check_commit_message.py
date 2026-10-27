"""Check a commit message's subject line against Conventional Commits.

Standalone (no third-party dependency) so lefthook's commit-msg hook and
CI can both run it with nothing beyond the stdlib. Mirrors the type
list this project's own commits already use.
"""

import re
import sys
from pathlib import Path

TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)

SUBJECT_PATTERN = re.compile(r"^(" + "|".join(TYPES) + r")(\([a-z0-9-]+\))?: .+[^.]$")


def check(subject: str) -> str | None:
    """Validate a commit subject line.

    Parameters
    ----------
    subject : str
        The commit message's first line.

    Returns
    -------
    str | None
        An error message if `subject` is invalid, otherwise None.
    """
    if not subject:
        return "commit message is empty"
    if subject.startswith(("Merge ", "Revert ")):
        return None
    if not SUBJECT_PATTERN.match(subject):
        return (
            f"commit subject {subject!r} doesn't match Conventional Commits: "
            f"'<type>(<scope>)?: <subject>' with no trailing period, where "
            f"<type> is one of {', '.join(TYPES)}"
        )
    return None


def main() -> int:
    """Read the commit message file named in argv and check its subject.

    Returns
    -------
    int
        0 if the subject is valid, 1 otherwise (with an error on stderr).
    """
    if len(sys.argv) != 2:
        print("usage: check_commit_message.py <commit-message-file>", file=sys.stderr)
        return 1

    message_path = Path(sys.argv[1])
    with message_path.open(encoding="utf-8") as f:
        subject = f.readline().strip()

    error = check(subject)
    if error is not None:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
