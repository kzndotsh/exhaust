"""The vertical catalog generator (ADR 0016).

Whatever lists the Playbook's verticals is computed by reading each
vertical's own skill file, never kept as a second, hand-maintained index.
This module is that reader: it globs `skills/*/SKILL.md`, parses each
file's YAML front matter, and emits the derived catalog. There is
deliberately no vertical list hardcoded anywhere in this module; an empty
`skills/` directory yields an empty catalog, since the Playbook's actual
catalog is not locked yet (ADR 0011).
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

SKILL_FILENAME = "SKILL.md"
DEFAULT_OUTPUT_RELATIVE_PATH = Path("catalog") / "verticals.generated.json"


class MalformedSkillFile(ValueError):
    """A skill file's front matter doesn't satisfy ADR 0011's schema."""


@dataclass(frozen=True)
class VerticalEntry:
    name: str
    required: bool
    gate: str | None


def _parse_front_matter(text: str, source: Path) -> dict:
    if not text.startswith("---\n"):
        raise MalformedSkillFile(f"{source}: missing YAML front matter")
    try:
        _, raw_front_matter, _ = text.split("---\n", 2)
    except ValueError as exc:
        raise MalformedSkillFile(f"{source}: unterminated front matter") from exc

    try:
        data = yaml.safe_load(raw_front_matter)
    except yaml.YAMLError as exc:
        raise MalformedSkillFile(f"{source}: invalid YAML front matter") from exc

    if not isinstance(data, dict):
        raise MalformedSkillFile(f"{source}: front matter is not a mapping")
    return data


def _entry_from_front_matter(data: dict, source: Path) -> VerticalEntry:
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise MalformedSkillFile(f"{source}: missing or empty 'name'")

    required = data.get("required")
    if not isinstance(required, bool):
        raise MalformedSkillFile(f"{source}: 'required' must be true or false")

    gate = data.get("gate")
    if required:
        if gate is not None:
            raise MalformedSkillFile(
                f"{source}: 'gate' must be absent when required is true"
            )
    else:
        if not isinstance(gate, str) or not gate:
            raise MalformedSkillFile(
                f"{source}: 'gate' is required and must be non-empty when "
                "required is false"
            )

    return VerticalEntry(name=name, required=required, gate=gate)


def discover_verticals(skills_dir: Path) -> list[VerticalEntry]:
    """Read every vertical skill file under `skills_dir`, sorted by name."""
    if not skills_dir.is_dir():
        return []

    entries = []
    for skill_file in sorted(skills_dir.glob(f"*/{SKILL_FILENAME}")):
        data = _parse_front_matter(skill_file.read_text(), skill_file)
        entries.append(_entry_from_front_matter(data, skill_file))

    names = [entry.name for entry in entries]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise MalformedSkillFile(f"duplicate vertical name(s): {sorted(duplicates)}")

    return sorted(entries, key=lambda entry: entry.name)


def generate_catalog(skills_dir: Path) -> dict:
    return {"verticals": [asdict(entry) for entry in discover_verticals(skills_dir)]}


def render_catalog(skills_dir: Path) -> str:
    return json.dumps(generate_catalog(skills_dir), indent=2, sort_keys=True) + "\n"


def write_catalog(skills_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_catalog(skills_dir))


def is_catalog_up_to_date(skills_dir: Path, output_path: Path) -> bool:
    if not output_path.is_file():
        return False
    return output_path.read_text() == render_catalog(skills_dir)
