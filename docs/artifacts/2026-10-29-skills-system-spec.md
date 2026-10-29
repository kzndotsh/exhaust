# The skills system: directory shape, authoring rules, template, and linting

This is a proposal, not a locked spec. It governs the *shape* every vertical skill file must take: the directory layout, the front-matter schema, the authoring rules, the scaffold template, and the linting mechanism. It does not touch the Playbook's actual vertical catalog, which stays explicitly unlocked per `docs/artifacts/2026-10-26-playbook-proposal.md` and ADR 0011. A skill file can be written in this shape the day that catalog locks, with zero rework, because this document settles nothing about which verticals exist, only how any vertical is expressed once chosen.

Everything here is built from decisions already made, not invented fresh: ADR 0011 (required/gate), ADR 0013 (progressive disclosure), ADR 0016 (generated catalog, no hand-maintained index), ADR 0017 (routing-contract descriptions), ADR 0022 (signed community content), and `src/exhaust/catalog.py`'s existing generator, which already implements the front-matter schema this document only writes down in full.

## 1. Directory layout

```
skills/
├── README.md
├── TEMPLATE/
│   └── SKILL.md
├── injection/
│   └── SKILL.md
├── access-control/
│   ├── SKILL.md
│   └── references/
│       ├── idor.md
│       ├── bola.md
│       └── bfla.md
└── ssrf/
    └── SKILL.md
```

One directory per vertical, under `skills/`. Each carries exactly one `SKILL.md`, found by `exhaust catalog generate`'s glob over `skills/*/SKILL.md` (`src/exhaust/catalog.py:discover_verticals`). A vertical may also carry a `references/` subdirectory holding deeper material split out by sub-class. This is the second tier of ADR 0013's progressive disclosure: `SKILL.md`'s body is loaded whenever that vertical takes a turn (`catalog.py:read_procedure`), but a `references/*.md` file is loaded only when the running agent's own procedure tells it to open that specific file for that specific sub-case, never preloaded. A vertical with no sub-classes worth splitting out just omits `references/` entirely; it's optional, never required scaffolding.

The directory's own name is a slug and is never read as the vertical's identity. `catalog.py:discover_verticals` and `_find_skill_file` read the vertical's name from the front matter's `name` field, not the directory name, exactly so a directory can be renamed for filesystem hygiene (collisions, length, casing) without that being an identity change. In practice keep them matching unless there's a concrete reason not to: a mismatch is legal but adds a lookup step for a human skimming the tree.

`TEMPLATE/` is not a real vertical. It is excluded from the generator by name (see section 5) and exists purely as the thing a human or agent copies to start a new vertical.

## 2. Front-matter schema

Every `SKILL.md` opens with YAML front matter, already enforced by `catalog.py`:

```yaml
---
name: injection
required: true
description: >
  Probes for command, SQL, LDAP, and template injection by submitting
  boundary-breaking payloads to every discovered input and diffing
  observed behavior against a baseline. Use for any vertical turn once
  recon has enumerated at least one request-shaped input (form field,
  query param, header, uploaded file). Do not use for deserialization
  of structured payloads (pickle, YAML, XML) — that's the
  `deserialization` vertical; this one is for payloads interpreted as
  code or query syntax, not as data structures.
keywords:
  - SQLi
  - OS command injection
---
```

`name` and `required` are exactly as `catalog.py` validates them today: `name` a non-empty string, `required` a bool. When `required: false`, `gate` is mandatory and must be a non-empty string naming the recon-confirmed trigger signal (ADR 0011); when `required: true`, `gate` must be absent, and `catalog.py` already raises `MalformedSkillFileError` on either violation.

`description` carries ADR 0017's four-part routing contract and nothing else: what the vertical's procedure actually does, naming real techniques; an explicit "use when" trigger; and a "do not use for X, use `<other-vertical>`" clause naming the nearest vertical it could be confused with. This is the one field an agent (or a human skimming the catalog) sees before deciding whether a vertical's full body is worth loading, so it has to do real routing work, not restate the vertical's name in a sentence. `catalog.py` enforces it as a required, non-empty string.

`keywords` is optional and defaults to empty: a flat list of acronyms, industry jargon, and named techniques (`SQLi`, `IDOR`, `shell injection`) a human or agent might search by instead of this vertical's own name — a glossary-style discovery index, never read for routing or dispatch, and never a claim that a term belongs exclusively to one vertical. The same keyword legitimately appearing under two verticals (`privilege escalation` under both `access-control` and `business-logic`, say) is not an error; only a duplicate `name` is. `catalog.py` validates it as a list of non-empty strings when present, nothing more.

No other top-level front-matter key is sanctioned by this proposal. A vertical that needs more structured metadata than `name`/`required`/`gate`/`description`/`keywords` is a signal to raise it as a change to this spec, not to quietly add a field one skill file uses and the rest don't — the generator reads every file through the same schema, and an unenforced field only one author adopted is exactly the kind of silent-drift risk ADR 0016 exists to rule out.

## 3. The body: a vertical's procedure

Everything after the closing `---` is the vertical's procedure, read verbatim by `catalog.py:read_procedure` and handed to the agent only when that vertical's turn actually starts. Rules for what goes in it:

- **It is instructions to the agent, not documentation about the vertical.** Write imperative steps ("enumerate every input the Target exposes, then..."), not descriptive prose about what SSRF is in the abstract. An agent reading this mid-run needs a procedure to execute, not a primer.
- **It names the Rig tools and Rig methods it expects to call**, by their actual registered name (`ToolBridge.methods`), never a tool the Rig doesn't currently pin. A procedure that assumes a tool not in `PINNED_TOOLS` is broken the day it's written, not merely incomplete.
- **It states its own exit condition.** When has this vertical genuinely exhausted its angles on this Target, as opposed to just having run out of obvious ideas? This is what a `SelfReport`'s exhaustion claim gets checked against (ADR 0005), so a vague or missing exit condition makes that check meaningless for this vertical specifically.
- **It defers sub-class detail to `references/`.** If the vertical splits into named sub-cases (IDOR/BOLA/BFLA under access control, say), the top-level body names them and says when to branch into which reference file; it does not inline all three procedures. That's the progressive-disclosure line ADR 0013 draws, and this is where a skill file actually earns or fails that discipline.
- **It never claims a Verdict.** A procedure drives investigation and `SelfReport`; recording `confirmed` goes through the Oracle (ADR 0008), not through anything a skill file's prose can assert on its own authority.
- **A canonical third-party doc gets a pointer, never inlined explanation.** Mirrors `ToolInfo.doc` (`src/exhaust/rig/bridges.py`): a stable, well-known external reference (an RFC, a CWE page, a specific product's own published API docs) earns a one-line `## References` entry, `- <name>: <url>`, placed where the procedure that actually needs it lives — the vertical's own `SKILL.md` if every sub-case needs it, a specific `references/<name>.md` if only that sub-case does (e.g., a reverse proxy's own API docs belong in the gated vertical or sub-case that fires once that specific product is confirmed, not in a `required` vertical that doesn't care which proxy is in front of it). A named standard with no real URL payoff (an RFC number, a CWE ID) doesn't need an entry at all — type it directly into prose, since the model already carries priors for it and a citation would just be a pointer to nothing the agent needs to fetch. This section is pointers only: explaining *why* the reference matters is the same explanation-in-a-how-to mistake ADR 0013's progressive disclosure and this session's "Known gaps" trim both already ruled out.

## 4. Authoring rules

- **A new vertical starts by copying `skills/TEMPLATE/SKILL.md`**, never a blank file and never a copy of an existing vertical edited in place (that copies the existing vertical's procedure along with its shape, which is a worse starting point than the deliberately empty template).
- **One vertical, one PR**, reviewed like any other change to `src/`. A skill file is executable instruction content the agent acts on against a real Target; it gets the same scrutiny as code, not the lighter review a markdown-only diff might otherwise get.
- **`exhaust catalog check` runs in CI on every PR that touches `skills/`**, same as it does today — this proposal doesn't change that, it extends what "passing" means (section 6).
- **Community-contributed skill content is signed per ADR 0022.** Nothing in `skills/` currently comes from outside the project, so this is dormant today, but the rule is already decided: the day exhaust accepts a vertical or reference file from outside its own authored tree, that file carries a publisher signature checked before the Harness ever loads it. Don't build an unsigned community-import path and bolt signing on afterward; there is no such path to build.
- **Renaming a vertical is a `name` change in front matter, reviewed as a breaking change**, since any Workspace ledger state keyed on the old name needs an explicit migration note in the PR, not a silent rename.

## 5. The template

`skills/TEMPLATE/SKILL.md`:

```markdown
---
name: REPLACE_ME
required: true
# gate: "the recon-confirmed signal that turns this vertical on"
# ^ delete the `gate` line entirely if required: true; add it, non-empty,
#   if required: false. catalog.py rejects either combination the wrong way.
description: >
  REPLACE_ME: what this vertical's procedure actually does, naming real
  techniques, not a restatement of its name. State the trigger: "use
  when...". State the boundary: "do not use for X, use the `<vertical>`
  vertical."
---

<!--
Everything below this line is the procedure an agent reads when this
vertical's turn starts. See docs/artifacts/2026-10-29-skills-system-spec.md
section 3 for what belongs here. Delete this comment before merging.
-->

## What this vertical investigates

## Procedure

1.
2.

## Exit condition

State when this vertical has genuinely exhausted its angles on this
Target, distinct from having merely run out of attempts.

## Sub-cases

If this vertical splits into named sub-classes, list them here and say
when to open which `references/<name>.md` file. Delete this section if
there are none.
```

`TEMPLATE` is excluded from the generator by name: `discover_verticals` globbing `skills/*/SKILL.md` would otherwise try to parse this file's `REPLACE_ME` placeholder as a real vertical and fail loudly. The cheapest fix that doesn't special-case the generator's own logic is a directory-name denylist of exactly one entry (`TEMPLATE`), checked before the glob result is parsed — simpler than teaching the parser to recognize and skip a placeholder front matter shape, and it can't silently swallow a real vertical that happens to use `REPLACE_ME` as a coincidence, because no real vertical would.

## 6. Linting

`exhaust catalog check` already enforces the hard schema (`MalformedSkillFileError` on missing/malformed `name`, `required`, `gate`, `description`, and on a stale generated file) by construction, since generation itself fails on a malformed file. `exhaust skill lint` is the second pass, run as part of the same `just check`/CI gate, checking what the generator's schema can't by itself:

- **Description shape.** `description` is present, non-empty, and contains a `use when` (or equivalent imperative trigger) clause and a `do not use for` (or equivalent routing-boundary) clause. This is a structural pattern check, not a semantic one — it can't verify the routing boundary it names is the *right* one, only that the four-part contract ADR 0017 requires is actually present, the same gap Cloudflare's own body-template convention left unchecked even though its description contract held.
- **No orphaned references.** Every file under a vertical's `references/` is mentioned by name somewhere in that vertical's own `SKILL.md` body. An unreferenced file is either dead content or a vertical that forgot to wire in a sub-case it already wrote — either way, worth failing the build over rather than letting it silently rot the way Lynis's second index did (ADR 0016's own cited case).
- **No tool name drift.** Every Rig tool name the procedure body mentions by its bracketed/code-formatted form is cross-checked against `default_bridges()`'s actual registry. A procedure that references a tool the Rig doesn't pin is wrong the moment it's written, and this catches it at review time instead of at the first real run that hits that line.
- **Slug hygiene.** The directory name is lowercase kebab-case, with a warning (not a failure) when it doesn't match the front matter's `name` — legal per section 1, but worth a human's attention when it happens.

This is deliberately closer to `claude plugin validate`'s per-file schema and path checking (confirmed as the closest real-world precedent during the Agent Skills ecosystem audit) than to a semantic reviewer: it catches shape violations a human would also catch on a careful read, cheaply and deterministically, and leaves judgment calls (is this routing boundary actually correct, is this procedure actually good) to PR review, where they belong.

## 7. How the Harness actually uses this at runtime

Nothing here is new; this section just states the existing pieces as one flow, since that flow is what every rule above is actually in service of.

1. **Build time / CI**: `exhaust catalog generate` reads every `skills/*/SKILL.md`'s front matter (never the body) and writes `catalog/verticals.generated.json`. `exhaust catalog check` fails the build if that file is stale. This is the Playbook's one source of truth for which verticals exist and whether each is required or gated — never a second list anywhere else (ADR 0016).
2. **Workspace creation**: the ledger (`src/exhaust/ledger.py`) seeds one entry per vertical from the generated catalog. A required vertical starts `pending`. A gated vertical starts in a state that waits on its named `gate` signal being confirmed by recon before it becomes eligible to run at all.
3. **A vertical's turn**: only when the Harness actually dispatches that vertical does it call `read_procedure(skills_dir, name)` to load that one vertical's body into the agent's context (ADR 0013). No other vertical's procedure, and no `references/` file, loads until that specific vertical, or that specific sub-case within it, is the one running.
4. **Exhaustion**: the vertical's own stated exit condition (section 3) is what a `SelfReport` claiming that vertical is done gets checked against, alongside the Findings store and attempt log (ADR 0005) — the procedure's exit condition and the Harness's own exhaustion check are supposed to agree, which is why a vertical without a real exit condition written down is a gap in the check, not just the doc.

## What this doesn't settle

**Resolved**: `description` is now a required field in `catalog.py`'s schema, validated non-empty the same way `name`/`required`/`gate` already are. `exhaust skill lint` is built too (`src/exhaust/cli/skill_lint.py`), run as its own `just check`/CI gate alongside `exhaust catalog check`: it enforces the `description`'s "use when"/"do not use for" routing contract, flags a `references/` file nothing in the body points to, flags a procedure naming a Rig tool or method that isn't actually pinned (cross-checked against `default_bridges()`), and warns (doesn't fail) on a directory slug that doesn't match its own front matter's `name`. The `TEMPLATE` exclusion (denylist by directory name) was implemented in `discover_verticals` at the same time `skills/TEMPLATE/SKILL.md` and `skills/injection/SKILL.md` were written.

- Nothing here picks, adds, or removes a single actual vertical. That catalog stays unlocked, governed entirely by `docs/artifacts/2026-10-26-playbook-proposal.md` and its own open questions.
