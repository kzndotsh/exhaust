<!--
This file is not a real sub-case. It exists only to show the shape a
real references/<name>.md file takes once a vertical's Sub-cases
section decides one is warranted (docs/artifacts/2026-10-29-skills-
system-spec.md section 1). Delete this whole file, or replace its
content, when a real sub-case actually needs splitting out — don't
leave this example sitting in a real vertical's references/ directory.

A reference file has no YAML frontmatter of its own: the Playbook
catalog generator never reads it directly (ADR 0016, ADR 0013's
progressive disclosure), only the owning vertical's SKILL.md body
decides when to point here. It loads only when the agent actually
reaches this specific sub-case, not on every turn of the parent
vertical the way SKILL.md's own body does.
-->

# REPLACE_ME sub-case name

State the one fact that makes this sub-case need its own file: what
engine, dialect, payload table, or Target-specific detail doesn't fit
on a line or two in the parent `SKILL.md`'s Sub-cases section.

## Procedure

Steps specific to this sub-case only, same RFC 2119 MUST/SHOULD
convention as the parent file. Don't repeat steps the parent
`SKILL.md`'s own Procedure already states for every sub-case — this
file is the delta, not a second copy of the whole vertical.

1. MUST REPLACE_ME.
2. REPLACE_ME.

## Exit condition

State only what's different from the parent vertical's own Exit
condition checklist. If this sub-case closes exactly the same way the
parent does, say so in one line and don't restate the checklist.
