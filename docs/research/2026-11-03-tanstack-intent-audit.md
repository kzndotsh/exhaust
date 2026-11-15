# Audit: TanStack Intent, against exhaust's own skill-file/catalog/Rig/Harness design

Requested as a direct comparison between a new, real, shipping tool (TanStack Intent, alpha,
announced 2026) and the mechanisms exhaust already has: the vertical skill-file schema
(`skills/README.md`, `docs/artifacts/2026-10-29-skills-system-spec.md`), ADR 0016's
no-hand-maintained-catalog rule, the Rig's closed `ToolBridge`/`ToolInfo`/`MethodInfo` surface
(`src/exhaust/rig/bridges.py`), the Harness's closed `Action` set (`src/exhaust/harness/actions.py`),
and the generator/lint pair (`src/exhaust/catalog.py`, `src/exhaust/cli/skill_lint.py`). Every
claim below is cited to the exact page or repo file it came from, fetched live this session
(2026-11-03), not reconstructed from memory or secondary write-ups. Primary sources:

- <https://tanstack.com/intent/latest>
- <https://tanstack.com/intent/latest/docs/overview>
- <https://tanstack.com/intent/latest/docs/getting-started/quick-start-consumers>
- <https://tanstack.com/intent/latest/docs/getting-started/quick-start-maintainers>
- <https://tanstack.com/intent/latest/docs/registry>
- `github.com/TanStack/intent` — README, `docs/concepts/trust-model.md`,
  `docs/concepts/configuration.md`, `packages/intent/src/core/types.ts`,
  `packages/intent/src/commands/validate.ts`,
  `packages/intent/meta/generate-skill/references/skill-format.md`,
  `packages/intent/meta/templates/workflows/check-skills.yml`

This is a research input only. Nothing below proposes a settled change to any exhaust file,
ADR, or open design question — these are findings to react to, not a patch.

## The gems: patterns that would directly improve a named exhaust file

**1. A closed top-level frontmatter key set, enforced at validation time — missing from `src/exhaust/catalog.py`.**
Intent's `validate.ts` hard-fails on any top-level frontmatter scalar key outside a fixed set:
`const specTopLevelKeys = new Set(['name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'])`,
with everything else rejected as `` `non-spec top-level key "${key}" — move client-specific scalar
fields under "metadata"` `` (`packages/intent/src/commands/validate.ts`). exhaust's own spec states
the identical intent in prose — "No other top-level front-matter key is sanctioned by this
proposal... an unenforced field only one author adopted is exactly the kind of silent-drift risk
ADR 0016 exists to rule out" (`docs/artifacts/2026-10-29-skills-system-spec.md` §2) — but
`src/exhaust/catalog.py`'s `_entry_from_front_matter` only reads `name`, `required`, `gate`,
`description`, `keywords` out of the parsed dict; it never checks the dict for anything *else*
present. A fifth stray key one author adds (say, `priority: high`) would silently pass both
`exhaust catalog generate` and `exhaust skill lint` today, violating the spec's own prose rule
with nothing in the codebase to catch it. Intent's exact check — iterate the parsed mapping's
keys, fail on any key not in the allowed set — is a one-function addition to
`_entry_from_front_matter` or a new check in `src/exhaust/cli/skill_lint.py`, and it is the
literal mechanism the spec already asked for in prose but never built.

**2. `intent stale`'s source-fingerprint review ledger — a concrete answer to "has this procedure gone stale relative to the code it describes," which exhaust's lint currently can't catch.**
Intent lets a skill declare `sources: ['Owner/repo:src/relevant-file.ts']` in frontmatter
(`packages/intent/meta/generate-skill/references/skill-format.md`), and `intent maintainer review`
"uses Git changes and content fingerprints to find unreviewed work," requiring the maintainer or
agent to record an explicit outcome per changed source — `--unchanged "<reason>"` or
`--updated "<reason>"` — persisted in a committed `.intent/review-state.json`
(`docs/getting-started/quick-start-maintainers`, step 6). The docs are explicit that this is "a
review signal, not proof of bad guidance" (`tanstack.com/intent/latest`), i.e. it never asserts the
skill is wrong, only that it's due for a human look. exhaust's `exhaust skill lint`
(`src/exhaust/cli/skill_lint.py`, `_tool_drift_findings`) catches a procedure naming a Rig
tool/method that no longer exists or was renamed, but it has no equivalent for the harder case: a
Rig bridge's method keeps its name but its behavior, parameters, or semantics change in
`src/exhaust/rig/bridges.py` or a concrete bridge implementation, and the vertical's procedure in
`skills/<vertical>/SKILL.md` that describes how to use it goes stale without any lint ever firing,
because the string match still succeeds. Intent's pattern — an optional `sources` field per skill
pointing at the specific files whose change should trigger a review, plus a committed
review-outcome ledger an agent or human must positively update — is a concrete, scoped addition:
a vertical could declare `sources: [src/exhaust/rig/bridges.py, src/exhaust/rig/wrappers.py]`, and
a new `exhaust skill stale` check could flag (not fail) when those files changed since the
vertical's last recorded review, exactly mirroring `intent stale`'s non-blocking signal rather than
`exhaust skill lint`'s hard-fail checks.

## What looks similar but doesn't transfer

**The consumer/maintainer split is not exhaust's author/Harness split, because Intent's split exists to solve third-party trust, which exhaust doesn't have.**
Intent's "consumer" is a downstream developer who installed someone else's npm package and must
decide, via an interactive allowlist (`intent install`, `package.json#intent.skills`), whether to
let that stranger's bundled instructions reach their own coding agent at all — the entire
trust-model page (`docs/concepts/trust-model.md`) exists because "skills contain instructions for
an agent. Choosing which packages can supply those instructions is a trust decision." exhaust has
no analog to this boundary today: `docs/artifacts/2026-10-29-skills-system-spec.md` §4 states
plainly that "nothing in `skills/` currently comes from outside the project" and that ADR 0022's
signing requirement is "dormant" until that changes. exhaust's real split — a human author writing
a `SKILL.md` versus the investigating agent that reads it mid-run (`AGENTS.md`, "Vertical skill
files") — is an authoring/consumption split inside one trust domain, not a permission gate between
strangers. Importing Intent's wildcard-allowlist UX (`"*"`, `"@scope/*"`, exact
`"pkg#skill"` selectors, `docs/concepts/configuration.md`) into exhaust today would be solving a
problem exhaust doesn't have yet, ahead of the day ADR 0022's community-import path is actually
built.

**Intent's package-version-pinned skill loading has no exhaust equivalent, because exhaust's skill files and the Harness that reads them always live at the same repo revision.**
Intent's core problem is that a consumer's installed `@tanstack/query@5.2.0` must resolve to the
skill content shipped in *that exact npm tarball*, not whatever the latest skill on GitHub says —
"`load` uses the skill that matches the installed package version"
(`docs/getting-started/quick-start-consumers`), and the registry's own versioning section exists
because "publishing an npm version alone does not update plugin versions or consumer
installations" (`docs/registry.md`). exhaust's `read_procedure` (`src/exhaust/catalog.py`) just
reads `skills/<name>/SKILL.md` off disk at whatever commit the Harness is running — there is no
separate "installed version" to drift from the "authored version," so there is nothing here to
port.

**The unobservable "Activated"/"Applied" lifecycle stages Intent names don't apply the same way, because exhaust's Harness owns both ends of the loop that Intent can't see into.**
Intent's trust-model page states plainly that stages 5 and 6 of its six-stage lifecycle —
whether "the agent selected or received the skill for a particular task" and whether "the model
followed the skill correctly" — are simply not observable by the tool (`docs/concepts/trust-model.md`,
"Lifecycle boundaries" table), because Intent only ships guidance into someone else's independently
running coding-agent session; it has no hook into what that agent actually does with it. exhaust's
situation is structurally different: the Harness itself dispatches the vertical's turn, validates
every `AgentAction` the agent proposes against the closed set in `src/exhaust/harness/actions.py`,
and forces a structured `SelfReport`/`ExhaustionAttestation` that gets checked against recorded
facts before exhaustion is accepted (ADR 0005, `docs/artifacts/2026-10-29-skills-system-spec.md`
§7.4). exhaust can and does verify far more of "was the guidance actually followed" than Intent
ever could, specifically because it controls the agent loop end-to-end — Intent's named
unobservability gap is a consequence of its distribution model, not a universal limit worth
importing as a caveat into exhaust's own design.

## 1. What problem Intent solves, and its registry mechanism

In its own words, Intent is "a CLI for library maintainers to generate, validate, and ship [Agent
Skills] alongside their npm packages. Auto-discovered, versioned with your code, and compatible
with the open Agent Skills standard" (`github.com/TanStack/intent` README). The landing page's
framing: "Your dependency can ship the knowledge required to use it" — Intent exists to keep a
library's agent-facing usage guidance in lockstep with that library's own releases, so "the skill
version" tracks "the package version" (`tanstack.com/intent/latest`). The overview page states the
same thing from the other direction: "two audiences: library consumers, who discover and load
skills that ship with their dependencies, and maintainers, who author, review, and publish those
skills alongside their code" (`docs/overview.md`).

The registry (`docs/registry.md`) is entirely computed, never hand-submitted: "There's no manual
submission process — publish skills in your package and the registry picks them up," by
periodically searching npm for the `tanstack-intent` keyword, downloading each matching tarball,
and indexing every `skills/**/SKILL.md` file found inside it — "Each new version you publish gets
indexed automatically." The only two requirements the registry states for inclusion are the
`tanstack-intent` npm keyword and the `skills/**/SKILL.md` path convention; the page gives no
registry-side schema validation beyond that, deferring all content and structure checks to the
maintainer-run `intent validate`/`maintainer check` tooling that runs before publish, not at
ingestion.

## 2. Consumer vs. maintainer, and whether it maps to exhaust's author/Harness split

Concretely, per the quick-starts: a **consumer** installs `@tanstack/intent` as a dev dependency,
runs interactive `install` to choose which installed packages' skills to trust (writing that choice
into `package.json#intent.skills`), gets a managed guidance block written into `AGENTS.md` telling
their own agent to run `intent list`/`intent load` before editing, and optionally installs
editor/session hooks that "hold edits until an `intent load` command is observed" — though the docs
are explicit these hooks "are not a security boundary"
(`docs/getting-started/quick-start-consumers`, `tanstack.com/intent/latest`). A **maintainer** runs
`maintainer setup` once per repo, authors skills with a coding agent against the library's own
source/tests/docs, tracks three planning artifacts (`domain_map.yaml`, `skill_spec.md`,
`skill_tree.yaml` under `_artifacts/`), runs a five-part validation pass, chooses a distribution
mode (npm-bundled by default, or `--distribution repo`), and runs a review/sync/check sequence
before every release (`docs/getting-started/quick-start-maintainers`).

As covered under "doesn't transfer" above, this is fundamentally a producer/distributor-across-a-
trust-boundary split (library author ships to strangers who must opt in), not exhaust's
author/runtime-reader split (one team writes `skills/<vertical>/SKILL.md`; the Harness reads it for
itself, same repo, same trust domain, no installation or permission step in between). The nearer
exhaust analog to Intent's "maintainer" role is whoever writes a new vertical per `skills/README.md`'s
five-step process; the nearer analog to Intent's "consumer" role doesn't really exist in exhaust at
all today, since the investigating agent is not a separate party making a trust decision — it's
handed whatever `read_procedure` returns, unconditionally, the moment its vertical's turn starts
(`docs/artifacts/2026-10-29-skills-system-spec.md` §7.3).

## 3. Schema/manifest comparison

Intent's `SKILL.md` frontmatter (`packages/intent/meta/generate-skill/references/skill-format.md`,
cross-checked against the actual validator in `packages/intent/src/commands/validate.ts`):

- `name`: lowercase letters/numbers/hyphens only, must equal the parent directory's name, ≤64
  chars — enforced by `agentSkillNamePattern` and a direct string-equality check in `validate.ts`.
- `description`: ≤1024 chars, required, carries "Use when..." activation conditions — enforced as a
  required non-empty field and a hard length cap.
- `metadata`: a free-form string-valued map (`purpose`, `type`, `library`, `library_version`), the
  sanctioned place for anything Intent-specific that isn't a spec-level key; every value must be a
  string, enforced in `validate.ts` (`metadata values must be strings`).
- `sources` / `requires`: Intent-specific top-level arrays (explicitly flagged in `validate.ts` as a
  temporary carve-out pending a migration to live under `metadata`, tracked as an open issue in the
  source comments — Intent's own authors consider this not fully settled either).
- A hard 500-line body cap, enforced in `validate.ts` with a message that explicitly forbids raising
  the limit as a workaround: "Rewrite for conciseness... Do not simply raise the limit."
- `type: framework` skills must carry a non-empty `requires` array — a structural, not semantic,
  dependency-declaration check.

Against exhaust's schema (`docs/artifacts/2026-10-29-skills-system-spec.md` §2,
`src/exhaust/catalog.py`): `name`, `required`, `gate` (conditionally mandatory), `description`
(ADR 0017's four-part routing contract, validated via `skill_lint.py`'s "use when"/"do not use for"
substring checks, not a length cap), `keywords` (optional list, glossary-only, "never read for
routing or dispatch"). exhaust has no `metadata` escape hatch — the spec's position is that a
vertical needing more structured fields than the five sanctioned ones is itself a signal to amend
the spec, not to add an unenforced field, which is a stricter stance than Intent's "put anything
else under `metadata`" compromise. Neither schema has an exhaust equivalent of Intent's `sources`
field (see Gem 2 above) or its hard line-count cap (see minor note below). exhaust's lint has no
per-file size limit at all today, where Intent's exists specifically to keep a skill from growing
into something an agent can't actually hold in context — worth noting as a candidate gap given
`docs/artifacts/2026-10-29-skills-system-spec.md`'s own progressive-disclosure rationale (ADR 0013)
already argues for the same discipline, just not as a numeric threshold anywhere enforced.

Against the Rig's `ToolInfo`/`MethodInfo` (`src/exhaust/rig/bridges.py`): these aren't the same kind
of object as a skill manifest — `ToolInfo`/`MethodInfo` describe a *tool a procedure may call*, not
a *procedure itself*. The closer Intent analog to `ToolInfo.doc` (a pointer to a tool's canonical
docs) is a skill's `sources` array pointing at `Owner/repo:path` — both are "point at the thing,
don't inline it" patterns, independently arrived at.

## 4. CLI tooling and CI wiring

Intent ships one CLI (`npx @tanstack/intent`) with `validate`, `maintainer check`, `maintainer sync`,
`maintainer review`, and `stale` as the relevant build-time commands. `intent maintainer setup`
copies a GitHub Actions template, `check-skills.yml`
(`packages/intent/meta/templates/workflows/check-skills.yml`), into the consuming repo, pinned to
"the commit of the Intent release that copied this file" and updated the same way Dependabot/Renovate
bump any other action reference — a deliberate choice to avoid both a floating version tag and a
copy that silently drifts from Intent's own released workflow logic. That workflow runs `validate`
on every pull request (with `repair: true`, i.e. CI can auto-fix certain frontmatter issues) and a
separate `review` job on release/manual-dispatch that can optionally open a review-reminder PR,
gated behind an explicit `INTENT_REVIEW_PULL_REQUESTS` repository variable — nothing writes to the
repo by default.

Against exhaust: `exhaust catalog generate` / `exhaust catalog check` / `exhaust skill lint`
(`src/exhaust/catalog.py`, `src/exhaust/cli/skill_lint.py`) are exhaust's own in-repo commands,
already wired into `just check`/CI per `docs/artifacts/2026-10-29-skills-system-spec.md` §4 and §6 —
there's no cross-repo template-distribution problem for exhaust to solve, since the generator and
the skill files it reads always live in the same repository. The one idea worth naming from
Intent's CI design that doesn't require adopting anything else: `--fix`/`repair: true`'s auto-repair
of mechanical frontmatter issues in CI is a step further than `exhaust skill lint` currently goes
(it only reports, per `src/exhaust/cli/skill_lint.py`'s `LintFinding` severity split between
hard-failing errors and non-failing warnings) — Intent's `repair` plan in `validate.ts`
(`planFrontmatterRepair`) only touches frontmatter it can deterministically rewrite (e.g. migrating
a field's shape), never the procedure body, so the scope of what it auto-fixes is narrow by design,
not a precedent for auto-rewriting procedure content.

## 5. Versioning, trust boundaries, and closed/enumerated operation sets

Versioning: Intent versions skills with their package ("the package version becomes the skill
version," `tanstack.com/intent/latest`), and `intent stale` separately tracks three kinds of drift:
version drift (installed package version vs. skill's declared version), missing sync SHAs, and
source-fingerprint drift (`docs/registry.md`, `docs/getting-started/quick-start-maintainers` step 9).
exhaust has no versioning concept for skill files at all — they're read at whatever commit HEAD is,
with no separate "installed version" to compare against (see "doesn't transfer" above).

Trust boundaries: Intent's `intent.skills` allowlist (`docs/concepts/trust-model.md`,
`docs/concepts/configuration.md`) is the full mechanism — npm vs. workspace source kinds kept
strictly separate (`foo` only permits npm, `workspace:foo` only permits workspace, by design, so a
same-named malicious npm package can't ride in on a trusted workspace entry), trust explicitly
"does not propagate to dependencies," and a reserved-but-rejected `git:` source kind that "Intent
parses and validates the shape, then rejects it until a future version can pin the resolved ref and
content hash" — a close relative of the Rig's own posture on `UnknownToolError`/`UnknownMethodError`
(`src/exhaust/rig/bridges.py`): both refuse an operation outside a known-good set rather than
attempting it cautiously. Intent's closed enumeration is over *which packages may supply
instructions at all*; the Rig's is over *which methods a known tool may be asked to run*, and the
Harness's `AgentAction` union (`src/exhaust/harness/actions.py`) is a third, narrower kind of closed
set again — a fixed vocabulary of *requests an agent is even capable of expressing*, with "deliberately
no field anywhere in this module" for an agent to supply its own Oracle result or human-only ledger
transition. All three are real instances of the same "closed enumeration beats runtime filtering"
design choice, arrived at independently for three different trust problems (which guidance to trust,
which tool call to allow, which request vocabulary to expose) — convergent validation of the
approach, not a borrowed idea in either direction.

Static, non-executing discovery is Intent's other closed-boundary rule worth naming on its own:
"Intent reads package data as files. It never imports, requires, or executes the code of a
discovered package to find or load a skill... An ESLint rule enforces this invariant in the
discovery code" (`docs/concepts/trust-model.md`). exhaust's nearest equivalent is the Rig's refusal
to invoke an unregistered method before a bridge's `run` is ever called (`bridges.py`'s `call`) —
both are "validate before touching the risky thing" patterns, but Intent's is about never executing
a third party's code to find its skills, where exhaust's is about never executing a tool call outside
its enumerated closed list; different risks, same shape of defense.
