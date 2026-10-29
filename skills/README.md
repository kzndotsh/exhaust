This directory holds the Playbook's vertical skill files, one subdirectory
per vertical, each with a `SKILL.md` carrying the front matter `exhaust
catalog generate` reads (ADR 0016): `name`, `required`, `gate` (only when
`required: false`), and `description`. The full shape, the authoring
rules, and the linting plan are specced in
`docs/artifacts/2026-10-29-skills-system-spec.md`; this file is just the
short version for whoever's about to write one.

The Playbook's actual vertical catalog is still not locked (see
`docs/artifacts/2026-10-26-playbook-proposal.md` and ADR 0011), and ADR
0016 forbids a second, hand-maintained list of verticals anywhere,
including here: the only source of truth is the skill files themselves,
read by the generator, never a list written in this README. `injection`
is the first real one, written against the required set the proposal
currently describes; it is not a declaration that the catalog has
locked.

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
   for the shape), and a `Known gaps` section naming any step that
   needs a Rig tool or method that isn't pinned yet. Never invent a
   tool call the Rig doesn't register. Use capitalized MUST/MUST
   NOT/SHOULD/MAY (RFC 2119) inside Procedure and Exit condition only,
   and render Exit condition as a checklist once more than one
   independent condition closes it. See
   `docs/research/2026-10-29-procedural-writing-standards.md` for why
   each of these conventions earned a place in the template.
5. Run `uv run exhaust catalog generate && uv run exhaust catalog check
   && uv run exhaust skill lint`. One vertical per PR.

`skills/injection/SKILL.md` is a worked example of steps 1 through 3
and the `Known gaps` discipline (written honestly rather than papered
over: no Rig tool currently submits a payload to a Target, so most of
its procedure was blocked on a tool that isn't pinned yet). It
predates the RFC 2119 keyword, checklist Exit condition, and
Rationalizations-to-reject conventions `skills/TEMPLATE/SKILL.md` now
specifies — retrofitting it is a separate, deliberate pass, not
something to do piecemeal while writing the next vertical.
