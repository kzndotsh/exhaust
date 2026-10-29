"""`exhaust skill lint`: structural checks the catalog generator's schema can't make.

`exhaust catalog check` already enforces the hard schema (`name`,
`required`, `gate`, `description` all present and well-typed) by
construction: generation itself fails on a malformed file. This module
is the second pass the skills-system spec names
(`docs/artifacts/2026-10-29-skills-system-spec.md` §6): checks that are
structural, not type-level, so a schema-valid file can still fail them.
Four checks, each catching a distinct failure mode: a `description`
missing one of ADR 0017's two routing-contract clauses, a
`references/` file nothing in the body ever points to, a procedure
naming a Rig tool or method that isn't actually pinned, and a directory
slug that doesn't match its own front matter's `name`.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import typer
import yaml

from exhaust.catalog import (
    SKILL_FILENAME,
    TEMPLATE_DIRECTORY_NAME,
    MalformedSkillFileError,
    discover_verticals,
)
from exhaust.rig.wrappers import default_bridges

app = typer.Typer(name="skill", no_args_is_help=True)

_SLUG_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_REFERENCE_MENTION_PATTERN = re.compile(r"references/([\w\-./]+\.md)")
_TOOL_METHOD_PATTERN = re.compile(r"`([a-z][a-z0-9_-]*)\.([a-z][a-z0-9_]*)`")


@dataclass(frozen=True)
class LintFinding:
    """One lint result.

    Attributes
    ----------
    path : Path
        The file the finding is about.
    message : str
        What's wrong, in one sentence.
    severity : str
        `"error"` (fails the command) or `"warning"` (printed, doesn't).
    """

    path: Path
    message: str
    severity: str


def _front_matter_name(skill_file: Path) -> str:
    """Read just the `name` field back out of an already schema-valid skill file."""
    text = skill_file.read_text()
    _, raw_front_matter, _ = text.split("---\n", 2)
    data = yaml.safe_load(raw_front_matter)
    return str(data["name"])


def _description_findings(skill_file: Path, description: str) -> list[LintFinding]:
    lowered = description.lower()
    findings: list[LintFinding] = []
    if "use when" not in lowered:
        findings.append(
            LintFinding(
                skill_file, "description has no 'use when' trigger clause (ADR 0017)", "error"
            )
        )
    if "do not use for" not in lowered:
        findings.append(
            LintFinding(
                skill_file,
                "description has no 'do not use for' routing-boundary clause (ADR 0017)",
                "error",
            )
        )
    return findings


def _orphaned_reference_findings(skill_dir: Path, body: str) -> list[LintFinding]:
    references_dir = skill_dir / "references"
    if not references_dir.is_dir():
        return []
    mentioned = {match.group(1) for match in _REFERENCE_MENTION_PATTERN.finditer(body)}
    return [
        LintFinding(ref_file, "not mentioned by name anywhere in SKILL.md's body", "error")
        for ref_file in sorted(references_dir.glob("*.md"))
        if ref_file.name not in mentioned
    ]


def _tool_drift_findings(skill_file: Path, body: str) -> list[LintFinding]:
    bridges = default_bridges()
    findings: list[LintFinding] = []
    for match in _TOOL_METHOD_PATTERN.finditer(body):
        tool, method = match.group(1), match.group(2)
        bridge = bridges.get(tool)
        if bridge is None:
            findings.append(
                LintFinding(skill_file, f"names `{tool}`, which isn't a pinned Rig tool", "error")
            )
            continue
        if method not in {m.name for m in bridge.methods}:
            findings.append(
                LintFinding(
                    skill_file,
                    f"names `{tool}.{method}`, which isn't one of {tool}'s methods",
                    "error",
                )
            )
    return findings


def _slug_findings(skill_dir: Path, declared_name: str) -> list[LintFinding]:
    slug = skill_dir.name
    findings: list[LintFinding] = []
    if not _SLUG_PATTERN.fullmatch(slug):
        findings.append(
            LintFinding(skill_dir, f"directory name {slug!r} isn't lowercase kebab-case", "warning")
        )
    if slug != declared_name:
        findings.append(
            LintFinding(
                skill_dir,
                f"directory name {slug!r} doesn't match its own front matter's name "
                f"{declared_name!r}",
                "warning",
            )
        )
    return findings


def lint_skills(skills_dir: Path) -> list[LintFinding]:
    """Run every structural check against `skills_dir`, after the hard schema already passed.

    Parameters
    ----------
    skills_dir : Path
        The directory `exhaust catalog generate` reads from.

    Returns
    -------
    list[LintFinding]
        Every finding across every vertical, in discovery order.

    Raises
    ------
    MalformedSkillFileError
        If the hard schema itself fails first (`discover_verticals`);
        lint only ever runs against a schema-valid catalog.
    """
    entries = {entry.name: entry for entry in discover_verticals(skills_dir)}

    findings: list[LintFinding] = []
    for skill_file in sorted(skills_dir.glob(f"*/{SKILL_FILENAME}")):
        if skill_file.parent.name == TEMPLATE_DIRECTORY_NAME:
            continue

        declared_name = _front_matter_name(skill_file)
        entry = entries[declared_name]
        body = skill_file.read_text().split("---\n", 2)[2]

        findings.extend(_description_findings(skill_file, entry.description))
        findings.extend(_orphaned_reference_findings(skill_file.parent, body))
        findings.extend(_tool_drift_findings(skill_file, body))
        findings.extend(_slug_findings(skill_file.parent, declared_name))

    return findings


@app.command("lint")
def lint(
    skills_dir: Path = typer.Option(Path("skills"), help="Where vertical skills live."),
) -> None:
    """Run the skills-system spec's structural checks (§6) against every vertical skill file."""
    try:
        findings = lint_skills(skills_dir)
    except MalformedSkillFileError as exc:
        typer.echo(f"catalog schema error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not findings:
        typer.echo("skill lint: clean")
        return

    for finding in findings:
        typer.echo(f"{finding.severity}: {finding.path}: {finding.message}", err=True)

    if any(finding.severity == "error" for finding in findings):
        raise typer.Exit(code=1)
