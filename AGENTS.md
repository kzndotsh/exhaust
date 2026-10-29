# exhaust

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `kzndotsh/exhaust`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels, each named after its role (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Vertical skill files

`skills/<vertical>/SKILL.md` and `skills/<vertical>/references/*.md` are read by the investigating agent mid-run, not by a human author. Every sentence in one must be something that agent needs to act — never rationale for why the file is shaped the way it is, never a pointer to an ADR by number, never "the project chose X because Y." That's explanation, and explanation belongs in `docs/adr/`, not in a file re-read on every turn. See `docs/artifacts/2026-10-29-skills-system-spec.md` §3 for the full rule and `docs/research/2026-10-29-procedural-writing-standards.md` for why. If a section has nothing actionable left to say (e.g. no sub-case has been split out yet), delete the section — don't fill it with reasoning about why it's empty.
