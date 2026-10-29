from pathlib import Path

import pytest

from exhaust.catalog import (
    MalformedSkillFileError,
    VerticalEntry,
    discover_verticals,
    generate_catalog,
    is_catalog_up_to_date,
    read_procedure,
    write_catalog,
)


def _write_skill(skills_dir: Path, slug: str, front_matter: str) -> None:
    skill_dir = skills_dir / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{front_matter}---\nBody.\n")


def test_empty_skills_dir_yields_empty_catalog(tmp_path: Path) -> None:
    assert discover_verticals(tmp_path / "skills") == []
    assert generate_catalog(tmp_path / "skills") == {"verticals": []}


def test_missing_skills_dir_yields_empty_catalog(tmp_path: Path) -> None:
    assert discover_verticals(tmp_path / "does-not-exist") == []


def test_template_directory_is_excluded(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "TEMPLATE", "name: REPLACE_ME\nrequired: true\n")
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")

    entries = discover_verticals(skills_dir)
    assert entries == [VerticalEntry(name="injection", required=True, gate=None)]


def test_required_vertical_with_no_gate(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")

    entries = discover_verticals(skills_dir)
    assert entries == [VerticalEntry(name="injection", required=True, gate=None)]


def test_gated_vertical_needs_a_gate_string(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "graphql",
        "name: graphql\nrequired: false\ngate: confirmed /graphql endpoint\n",
    )

    entries = discover_verticals(skills_dir)
    assert entries == [
        VerticalEntry(name="graphql", required=False, gate="confirmed /graphql endpoint")
    ]


def test_required_vertical_cannot_carry_a_gate(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\ngate: oops\n")

    with pytest.raises(MalformedSkillFileError):
        discover_verticals(skills_dir)


def test_gated_vertical_without_a_gate_is_rejected(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "graphql", "name: graphql\nrequired: false\n")

    with pytest.raises(MalformedSkillFileError):
        discover_verticals(skills_dir)


def test_missing_front_matter_is_rejected(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "injection"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("No front matter here.\n")

    with pytest.raises(MalformedSkillFileError):
        discover_verticals(skills_dir)


def test_duplicate_vertical_names_are_rejected(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "one", "name: dup\nrequired: true\n")
    _write_skill(skills_dir, "two", "name: dup\nrequired: true\n")

    with pytest.raises(MalformedSkillFileError):
        discover_verticals(skills_dir)


def test_catalog_is_sorted_by_name(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "z", "name: zeta\nrequired: true\n")
    _write_skill(skills_dir, "a", "name: alpha\nrequired: true\n")

    catalog = generate_catalog(skills_dir)
    assert [v["name"] for v in catalog["verticals"]] == ["alpha", "zeta"]


def test_write_then_check_round_trips(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    output = tmp_path / "catalog" / "verticals.generated.json"

    write_catalog(skills_dir, output)
    assert is_catalog_up_to_date(skills_dir, output) is True


def test_check_detects_drift(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    output = tmp_path / "catalog" / "verticals.generated.json"
    write_catalog(skills_dir, output)

    _write_skill(skills_dir, "access-control", "name: access_control\nrequired: true\n")
    assert is_catalog_up_to_date(skills_dir, output) is False


def test_check_against_missing_output_is_not_up_to_date(tmp_path: Path) -> None:
    assert is_catalog_up_to_date(tmp_path / "skills", tmp_path / "missing.json") is False


def test_read_procedure_returns_the_body_past_front_matter(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "injection"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: injection\nrequired: true\n---\nTry these payloads.\n"
    )

    assert read_procedure(skills_dir, "injection") == "Try these payloads."


def test_read_procedure_looks_up_by_declared_name_not_directory_slug(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "01-injection"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: injection\nrequired: true\n---\nProcedure text.\n"
    )

    assert read_procedure(skills_dir, "injection") == "Procedure text."


def test_read_procedure_rejects_an_unknown_vertical(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")

    with pytest.raises(MalformedSkillFileError):
        read_procedure(skills_dir, "nonexistent")
