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
from typing import Any, cast

import yaml

SKILL_FILENAME = "SKILL.md"
DEFAULT_OUTPUT_RELATIVE_PATH = Path("catalog") / "verticals.generated.json"

TEMPLATE_DIRECTORY_NAME = "TEMPLATE"
"""The scaffold directory a new vertical is copied from, never a real one."""


class MalformedSkillFileError(ValueError):
    """A skill file's front matter doesn't satisfy ADR 0011's schema."""


@dataclass(frozen=True)
class VerticalEntry:
    """One vertical, as declared by its own skill file.

    Attributes
    ----------
    name : str
        The vertical's stable identifier.
    required : bool
        Whether this vertical runs on every Workspace regardless of
        Target, or only once its `gate` is confirmed.
    gate : str | None
        The recon-confirmed trigger signal, set only when `required` is
        False.
    description : str
        ADR 0017's routing contract: what the vertical's procedure does,
        when to use it, and the nearest vertical it could be confused
        with. The only text read before a vertical's full body loads.
    keywords : tuple[str, ...]
        Acronyms, industry jargon, and specific techniques a human or
        agent might search by instead of this vertical's own name
        (e.g. "SQLi", "SSTI", "shell injection" for `injection`) — a
        glossary-style index, not a claim that each term is this
        vertical's own name or that this vertical is the only one that
        term could ever relate to. Never read for routing or dispatch;
        `description`'s own use-when/do-not-use-for clauses still own
        that. Empty by default.
    """

    name: str
    required: bool
    gate: str | None
    description: str
    keywords: tuple[str, ...] = ()


def _split_front_matter(text: str, source: Path) -> tuple[str, str]:
    """Split a skill file's text into its raw front matter and body.

    Parameters
    ----------
    text : str
        The skill file's full contents.
    source : Path
        The file `text` came from, used only for error messages.

    Returns
    -------
    tuple[str, str]
        The raw front matter block and everything after it.

    Raises
    ------
    MalformedSkillFileError
        If the front matter is missing or unterminated.
    """
    if not text.startswith("---\n"):
        raise MalformedSkillFileError(f"{source}: missing YAML front matter")
    try:
        _, raw_front_matter, body = text.split("---\n", 2)
    except ValueError as exc:
        raise MalformedSkillFileError(f"{source}: unterminated front matter") from exc
    return raw_front_matter, body


def _parse_front_matter(text: str, source: Path) -> dict[str, Any]:
    """Extract and parse a skill file's leading YAML front matter block.

    Parameters
    ----------
    text : str
        The skill file's full contents.
    source : Path
        The file `text` came from, used only for error messages.

    Returns
    -------
    dict[str, Any]
        The parsed front matter.

    Raises
    ------
    MalformedSkillFileError
        If the front matter is missing, unterminated, invalid YAML, or
        not a mapping.
    """
    raw_front_matter, _ = _split_front_matter(text, source)

    try:
        data = yaml.safe_load(raw_front_matter)
    except yaml.YAMLError as exc:
        raise MalformedSkillFileError(f"{source}: invalid YAML front matter") from exc

    if not isinstance(data, dict):
        raise MalformedSkillFileError(f"{source}: front matter is not a mapping")
    return cast(dict[str, Any], data)


def _entry_from_front_matter(data: dict[str, Any], source: Path) -> VerticalEntry:
    """Validate parsed front matter against ADR 0011's required/gate schema.

    Parameters
    ----------
    data : dict[str, Any]
        The front matter, as returned by `_parse_front_matter`.
    source : Path
        The file `data` came from, used only for error messages.

    Returns
    -------
    VerticalEntry
        The validated entry.

    Raises
    ------
    MalformedSkillFileError
        If `name` is missing or empty, `required` is not a bool, a
        required vertical carries a `gate`, a gated vertical is missing
        one, `description` is missing or empty, or `keywords` is present
        but isn't a list of non-empty strings.
    """
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise MalformedSkillFileError(f"{source}: missing or empty 'name'")

    required = data.get("required")
    if not isinstance(required, bool):
        raise MalformedSkillFileError(f"{source}: 'required' must be true or false")

    gate = data.get("gate")
    if required:
        if gate is not None:
            raise MalformedSkillFileError(f"{source}: 'gate' must be absent when required is true")
    else:
        if not isinstance(gate, str) or not gate:
            raise MalformedSkillFileError(
                f"{source}: 'gate' is required and must be non-empty when required is false"
            )

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        raise MalformedSkillFileError(f"{source}: missing or empty 'description'")

    keywords = _parse_keywords(data.get("keywords"), source)

    return VerticalEntry(
        name=name, required=required, gate=gate, description=description, keywords=keywords
    )


def _parse_keywords(raw_keywords: Any, source: Path) -> tuple[str, ...]:
    """Validate the optional `keywords` field, defaulting to empty.

    Raises
    ------
    MalformedSkillFileError
        If `keywords` is present but isn't a list of non-empty strings.
    """
    if raw_keywords is None:
        return ()
    if not isinstance(raw_keywords, list) or not all(
        isinstance(keyword, str) and keyword for keyword in cast("list[Any]", raw_keywords)
    ):
        raise MalformedSkillFileError(f"{source}: 'keywords' must be a list of non-empty strings")
    return tuple(cast("list[str]", raw_keywords))


def discover_verticals(skills_dir: Path) -> list[VerticalEntry]:
    """Read every vertical skill file under `skills_dir`, sorted by name.

    Parameters
    ----------
    skills_dir : Path
        The directory to glob `*/SKILL.md` under. A missing directory
        yields an empty list rather than raising.

    Returns
    -------
    list[VerticalEntry]
        Every discovered vertical, sorted by name.

    Raises
    ------
    MalformedSkillFileError
        If any skill file fails validation, or two verticals share a
        name. `keywords` are a search-term index, not an identity
        claim, so the same keyword legitimately appearing under more
        than one vertical is not an error.
    """
    if not skills_dir.is_dir():
        return []

    entries: list[VerticalEntry] = []
    for skill_file in sorted(skills_dir.glob(f"*/{SKILL_FILENAME}")):
        if skill_file.parent.name == TEMPLATE_DIRECTORY_NAME:
            continue
        data = _parse_front_matter(skill_file.read_text(), skill_file)
        entries.append(_entry_from_front_matter(data, skill_file))

    names: list[str] = [entry.name for entry in entries]
    duplicates: set[str] = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise MalformedSkillFileError(f"duplicate vertical name(s): {sorted(duplicates)}")

    return sorted(entries, key=lambda entry: entry.name)


def required_gate_signals(entries: list[VerticalEntry]) -> frozenset[str]:
    """Every distinct `gate` some gated vertical in `entries` declares.

    Recon's own worklist, derived from the catalog rather than kept as a
    second, hand-maintained list (ADR 0016): a new gated vertical's `gate`
    is picked up here automatically the moment its skill file is
    discovered, with nothing for a human to keep in sync.

    Parameters
    ----------
    entries : list[VerticalEntry]
        A catalog, as returned by `discover_verticals`.

    Returns
    -------
    frozenset[str]
        Every distinct gate a non-required vertical in `entries` declares.
    """
    return frozenset(
        entry.gate for entry in entries if not entry.required and entry.gate is not None
    )


def _find_skill_file(skills_dir: Path, name: str) -> Path:
    """Locate the skill file that declares vertical `name` under `skills_dir`.

    Mirrors `discover_verticals`'s own rule that front matter, not the
    directory's own name, is what names a vertical: a skill directory
    is free to be slugged differently from the `name` its front matter
    declares, so this re-parses front matter to find the match rather
    than guessing `skills_dir / name / SKILL_FILENAME`.

    Raises
    ------
    MalformedSkillFileError
        If no skill file under `skills_dir` declares `name`.
    """
    for skill_file in sorted(skills_dir.glob(f"*/{SKILL_FILENAME}")):
        data = _parse_front_matter(skill_file.read_text(), skill_file)
        if data.get("name") == name:
            return skill_file
    raise MalformedSkillFileError(f"{skills_dir}: no skill file declares vertical {name!r}")


def read_procedure(skills_dir: Path, name: str) -> str:
    """Read one vertical's procedure: its skill file's body, past the front matter (ADR 0013).

    Meant to be called just-in-time for the vertical actually taking a
    turn, never for every vertical in the catalog: that's what keeps an
    inactive vertical's procedure out of context.

    Parameters
    ----------
    skills_dir : Path
        The directory `discover_verticals` reads from.
    name : str
        The vertical whose procedure to read.

    Returns
    -------
    str
        The skill file's body, with leading and trailing whitespace
        stripped.

    Raises
    ------
    MalformedSkillFileError
        If no skill file under `skills_dir` declares `name`.
    """
    skill_file = _find_skill_file(skills_dir, name)
    _, body = _split_front_matter(skill_file.read_text(), skill_file)
    return body.strip()


def generate_catalog(skills_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Build the catalog dict for every vertical under `skills_dir`.

    Parameters
    ----------
    skills_dir : Path
        The directory to read vertical skill files from.

    Returns
    -------
    dict[str, list[dict[str, Any]]]
        A single `"verticals"` key holding each entry as a plain dict.
    """
    return {"verticals": [asdict(entry) for entry in discover_verticals(skills_dir)]}


def render_catalog(skills_dir: Path) -> str:
    """Render the catalog for `skills_dir` as deterministic, sorted JSON.

    Parameters
    ----------
    skills_dir : Path
        The directory to read vertical skill files from.

    Returns
    -------
    str
        The rendered JSON, newline-terminated.
    """
    return json.dumps(generate_catalog(skills_dir), indent=2, sort_keys=True) + "\n"


def write_catalog(skills_dir: Path, output_path: Path) -> None:
    """Regenerate and write the catalog for `skills_dir` to `output_path`.

    Parameters
    ----------
    skills_dir : Path
        The directory to read vertical skill files from.
    output_path : Path
        Where to write the rendered catalog. Parent directories are
        created if needed.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_catalog(skills_dir))


def is_catalog_up_to_date(skills_dir: Path, output_path: Path) -> bool:
    """Check whether `output_path` matches a fresh render of `skills_dir`.

    Parameters
    ----------
    skills_dir : Path
        The directory to read vertical skill files from.
    output_path : Path
        The committed catalog file to check.

    Returns
    -------
    bool
        True if `output_path` exists and matches the current render.
    """
    if not output_path.is_file():
        return False
    return output_path.read_text() == render_catalog(skills_dir)
