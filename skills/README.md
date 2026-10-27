This directory holds the Playbook's vertical skill files, one subdirectory
per vertical, each with a `SKILL.md` carrying the front matter `exhaust
catalog generate` reads (ADR 0016): `name`, `required`, and `gate` (only
when `required: false`).

It is empty right now on purpose. The Playbook's actual vertical catalog
is not locked yet (see `docs/artifacts/2026-10-26-playbook-proposal.md`
and ADR 0011) and ADR 0016 forbids a second, hand-maintained list of
verticals anywhere, including here: the only source of truth is the skill
files themselves, read by the generator, never a list written in this
README.
