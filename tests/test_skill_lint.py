from pathlib import Path

import pytest

from exhaust.catalog import MalformedSkillFileError
from exhaust.cli.skill_lint import lint_skills

_GOOD_DESCRIPTION = (
    "Probes for X. Use when recon finds Y. Do not use for Z, use the `other` vertical."
)


def _write_skill(
    skills_dir: Path, slug: str, *, description: str = _GOOD_DESCRIPTION, body: str = "Body.\n"
) -> Path:
    skill_dir = skills_dir / slug
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"---\nname: {slug}\nrequired: true\ndescription: {description}\n---\n{body}"
    )
    return skill_file


def test_a_clean_vertical_has_no_findings(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection")

    assert lint_skills(skills_dir) == []


def test_a_description_missing_use_when_is_an_error(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir, "injection", description="Probes for X. Do not use for Z, use `other`."
    )

    findings = lint_skills(skills_dir)
    assert any("use when" in f.message and f.severity == "error" for f in findings)


def test_a_description_missing_do_not_use_for_is_an_error(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", description="Probes for X. Use when recon finds Y.")

    findings = lint_skills(skills_dir)
    assert any("do not use for" in f.message and f.severity == "error" for f in findings)


def test_an_orphaned_reference_file_is_an_error(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_file = _write_skill(
        skills_dir, "access-control", body="Open `references/idor.md` for IDOR.\n"
    )
    references_dir = skill_file.parent / "references"
    references_dir.mkdir()
    (references_dir / "idor.md").write_text("idor detail\n")
    (references_dir / "bfla.md").write_text("bfla detail\n")

    findings = lint_skills(skills_dir)
    orphaned = [f for f in findings if f.path.name == "bfla.md"]
    assert len(orphaned) == 1
    assert orphaned[0].severity == "error"
    assert not any(f.path.name == "idor.md" for f in findings)


def test_a_referenced_file_is_not_flagged_when_mentioned_by_path(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_file = _write_skill(
        skills_dir, "access-control", body="Open `references/idor.md` for detail.\n"
    )
    references_dir = skill_file.parent / "references"
    references_dir.mkdir()
    (references_dir / "idor.md").write_text("idor detail\n")

    findings = lint_skills(skills_dir)
    assert findings == []


def test_naming_a_tool_that_is_not_pinned_is_an_error(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", body="Dispatch through `sqlmap.inject`.\n")

    findings = lint_skills(skills_dir)
    assert any("sqlmap" in f.message and f.severity == "error" for f in findings)


def test_naming_a_real_tools_unknown_method_is_an_error(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", body="Dispatch through `nmap.drop_everything`.\n")

    findings = lint_skills(skills_dir)
    assert any("nmap.drop_everything" in f.message and f.severity == "error" for f in findings)


def test_naming_a_real_pinned_tool_and_method_is_clean(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir, "injection", body="Dispatch through `curl.get` and `nmap.tcp_connect_scan`.\n"
    )

    assert lint_skills(skills_dir) == []


def test_citing_an_adr_by_number_is_an_error(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", body="Record it per ADR 0008 before writing a Finding.\n")

    findings = lint_skills(skills_dir)
    assert any("ADR 0008" in f.message and f.severity == "error" for f in findings)


def test_citing_an_adr_with_a_hyphen_is_also_caught(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", body="See ADR-0019 for the requirements shape.\n")

    findings = lint_skills(skills_dir)
    assert any("ADR-0019" in f.message and f.severity == "error" for f in findings)


def test_a_directory_slug_mismatched_from_the_declared_name_is_a_warning(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "01-injection"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: injection\nrequired: true\ndescription: {_GOOD_DESCRIPTION}\n---\nBody.\n"
    )

    findings = lint_skills(skills_dir)
    assert any(f.severity == "warning" and "01-injection" in str(f.path) for f in findings)


def test_the_template_directory_is_never_linted(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "TEMPLATE"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: REPLACE_ME\nrequired: true\n---\nnot even valid.\n"
    )
    _write_skill(skills_dir, "injection")

    assert lint_skills(skills_dir) == []


def test_a_malformed_catalog_raises_before_any_lint_check_runs(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "injection"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: injection\n---\nBody.\n")

    with pytest.raises(MalformedSkillFileError):
        lint_skills(skills_dir)
