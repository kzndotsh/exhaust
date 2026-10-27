# Decision trail: initial codebase bootstrap

The repo held only docs before this: `GLOSSARY.md`, 22 ADRs, research audits,
and the unlocked Playbook proposal. This is the first real code, built as a
narrow, verified-unit-by-unit slice rather than a full scaffold dumped at
once.

## What got built, and why this slice

- **Package scaffolding** (`pyproject.toml`, `src/exhaust/`, `uv.lock`):
  Python, Typer, uv per ADR 0002. Verified with `uv run exhaust --version`
  and `--help`.
- **`ScopeContract` gate** (`src/exhaust/scope_contract.py`): the ADR 0003
  gate as a pure, testable module, independent of any Harness. Seven unit
  tests cover the fail-closed cases explicitly, since ADR 0003's entire
  point is that a missing or malformed contract denies real-Target action
  rather than permitting it: no contract, mismatched target, unknown
  `basis`, malformed YAML, a non-mapping document, and a missing field all
  assert `is_in_scope() is False`.
- **Workspace scaffolding** (`src/exhaust/workspace.py`, `exhaust new`):
  creates `AGENTS.md` (referencing `BRIEF.md` explicitly, per ADR 0006),
  `BRIEF.md`, a `sandbox/` placeholder, `poc/`, and `findings/`. Verified
  with a CLI smoke test against a real temp directory, plus a test that
  asserts scaffolding never creates a `SCOPE_CONTRACT.yaml` (the gate must
  stay closed by default) and a test that it refuses to overwrite an
  existing Workspace.
- **Vertical catalog generator** (`src/exhaust/catalog.py`, `exhaust
  catalog generate`/`check`): the committed, CI-checked generator ADR 0016
  requires. It reads `skills/*/SKILL.md` front matter (`name`, `required`,
  `gate`), validates the ADR 0011 required/gate schema (a required vertical
  may not carry a gate; a gated one must), rejects duplicate names, and
  emits a sorted, deterministic JSON catalog. `skills/` is real but empty:
  the Playbook's catalog is explicitly not locked (ADR 0011, the
  2026-10-26 playbook-proposal draft), so no vertical is hardcoded
  anywhere in this code or committed as a second list. The committed
  `catalog/verticals.generated.json` is `{"verticals": []}`, matching that.
- **CI** (`.github/workflows/ci.yml`): runs the test suite and `exhaust
  catalog check`, so a skill file added later that drifts from the
  committed catalog fails the pull request, per ADR 0016's actual
  requirement (a generator alone isn't enough without the CI check).

## What this doesn't build yet

No Harness, no agent loop, no Rig tool catalog, no Finding/Verdict storage,
no Oracle. Those need the Playbook's vertical catalog and the eval
machinery (ADR 0014) decided first, or they'd be built against a shape
that's still explicitly open. This slice is the part that doesn't depend
on any of that: packaging, the Scope Contract gate, Workspace scaffolding,
and the catalog mechanism.

## Verification

`uv run pytest` passes (25 tests). `uv run exhaust catalog check` passes
against the real, empty `skills/` directory. `exhaust new` and `exhaust
catalog generate` were each smoke-tested against a real temp directory, not
just through the test suite. Every commit in this run is a single file or
tightly coupled pair (module plus its test), built and verified before the
next one started.
