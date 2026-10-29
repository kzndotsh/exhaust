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

## Known gaps

If a step above needs a Rig tool or method that isn't pinned yet, name
the gap explicitly here. Never invent a tool call the Rig doesn't
register, and never silently skip the step without saying so.
