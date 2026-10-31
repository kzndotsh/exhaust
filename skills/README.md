This directory holds the Playbook's vertical skill files, one subdirectory
per vertical, each with a `SKILL.md` carrying the front matter `exhaust
catalog generate` reads (ADR 0016): `name`, `required`, `gate` (only when
`required: false`), `description`, and an optional `keywords` list (acronyms
and jargon a search might use instead of this vertical's own name — a
glossary-style discovery index, never a routing signal). The full shape, the
authoring rules, and the linting plan are specced in
`docs/artifacts/2026-10-29-skills-system-spec.md`; this file is just the
short version for whoever's about to write one.

The Playbook's actual vertical catalog is still not locked (see
`docs/artifacts/2026-10-26-playbook-proposal.md` and ADR 0011), and ADR
0016 forbids a second, hand-maintained list of verticals anywhere,
including here: the only source of truth is the skill files themselves,
read by the generator, never a list written in this README. `injection`
and `recon` are the first two real ones, written against the required
set the proposal currently describes; this is not a declaration that the
catalog has locked.

## Writing a new vertical

1. Copy `skills/TEMPLATE/SKILL.md` into `skills/<slug>/SKILL.md`. Never
   start from a blank file, and never copy an existing vertical in place
   of the template — that carries its procedure along with its shape.
2. Set `required`/`gate` per ADR 0011. `required: true` means it runs on
   every Workspace regardless of Target; `required: false` needs a
   non-empty `gate` naming the recon-confirmed signal that turns it on.
   `exhaust catalog generate` rejects either combination done wrong.
3. Write `description` as the four-part routing contract: what the
   procedure actually does, naming real techniques; an explicit "use
   when" trigger; and a "do not use for X, use `<vertical>`" clause
   naming the nearest vertical it could be confused with.
4. Write the body: what this vertical investigates, its numbered
   procedure, its own exit condition, an optional `Rationalizations to
   reject` section for security verticals, its sub-cases (inline until
   one needs detail no other sub-case does, then split into
   `references/<name>.md` — see `skills/TEMPLATE/references/EXAMPLE-SUBCASE.md`
   for the shape), a `Known gaps` section naming any step that needs a
   Rig tool or method that isn't pinned yet, and, last, an optional
   `References` section pointing at any stable third-party doc the
   procedure actually relies on (mirrors `ToolInfo.doc`, placed with
   the sub-case that needs it rather than centrally). Never invent a
   tool call the Rig doesn't register. Use capitalized MUST/MUST
   NOT/SHOULD/MAY (RFC 2119) inside Procedure and Exit condition only,
   and render Exit condition as a checklist once more than one
   independent condition closes it. Never cite an ADR by number
   anywhere in the body — the investigating agent reads this file
   mid-run, not a human author, and a design-rationale pointer is
   explanation it has no use for; state the rule itself. A section
   with nothing left to say once stripped of explanation (no sub-case
   split out yet, nothing currently blocked) gets deleted entirely,
   never filled with prose justifying why it's empty. See
   `docs/research/2026-10-29-procedural-writing-standards.md` for why
   each of these conventions earned a place in the template.
5. Run `uv run exhaust catalog generate && uv run exhaust catalog check
   && uv run exhaust skill lint`. The last of these fails the build on
   any ADR citation or other lint violation. One vertical per PR.

`skills/injection/SKILL.md` is a worked example of the full template:
seven inline sub-cases, a checklist Exit condition with the
confirmed/ruled-out/open-proof-gap closure rule, a Rationalizations to
reject section, and a diversified References list (MITRE CWE entries
alongside PortSwigger's own testing guides, not one vendor for
everything). It has no Known gaps section because every input shape
its own enumeration step names now has a real Rig method to dispatch
through.
