---
name: REPLACE_ME
required: true
# gate: "When <recon confirms a specific, named signal>, the REPLACE_ME vertical SHALL run."
# ^ delete the `gate` line entirely if required: true. If required: false, write the
#   gate as an EARS trigger clause (When/While/If-Then, docs/research/2026-10-29-
#   procedural-writing-standards.md finding 6): a confirmed observation, never a guess.
#   catalog.py rejects either name/required/gate combination done the wrong way.
description: >
  REPLACE_ME: what this vertical's procedure actually does, naming real
  techniques, not a restatement of its name. State the trigger: "Use
  when...". State the boundary: "Do not use for X, use the `<vertical>`
  vertical."
---

<!--
Everything below this line is the procedure an agent reads when this
vertical's turn starts. See docs/artifacts/2026-10-29-skills-system-spec.md
section 3 for what belongs here, and docs/research/2026-10-29-procedural-
writing-standards.md for why this shape (nine sources: RFC 2119, Diátaxis,
WHO checklist design, Google SRE, EARS, Matt Pocock's writing-for-agents,
pbakaus/impeccable, trailofbits/skills, usestrix/strix). Delete this
comment and every REPLACE_ME before merging.

Instruction strength (finding 1): MUST / MUST NOT / SHOULD / SHOULD NOT /
MAY, capitalized, inside Procedure and Exit condition only. Lowercase
must/should/may elsewhere is ordinary prose, not a rule — keep the two
visually distinct so a reader (or a future lint check) can tell them apart
at a glance.
-->

## What this vertical investigates

One or two sentences. State the trust boundary or bug class this
vertical exists to find. No history, no rationale, no "we chose this
because" — that belongs in an ADR, never here (Diátaxis names mixing
explanation into a how-to as a real anti-pattern, not a style
preference; this session's own "Known gaps" section got trimmed for
exactly this mistake).

## Procedure

1. MUST enumerate every REPLACE_ME before touching any of them. An
   input discovered mid-procedure MUST NOT be probed in the same pass
   it was found in — add it to the enumerated set first, so the Exit
   condition below can still account for it.
2. MUST record a baseline (the clean, expected result) for each
   REPLACE_ME before changing anything about it. Every later diff in
   this procedure is measured against this baseline, never against an
   assumed "should have succeeded" response (WHO Surgical Safety
   Checklist finding 3: a checklist's own reliability depends on
   recording the known-good state before acting, not after).
3. REPLACE_ME: the actual investigative steps, named concretely enough
   that a Rig tool call satisfies each one. Name only Rig tools and
   methods that are actually pinned (`default_bridges()`); if a step
   needs one that isn't, it belongs in Known gaps below, not invented
   here.
4. MUST NOT REPLACE_ME (a specific premature-conclusion failure this
   vertical is prone to), paired with the positive step it replaces:
   REPLACE_ME (what to do instead). State the target behavior, not
   just the ban — a standalone "don't" is a weak modifier next to the
   behavior it's trying to suppress (Matt Pocock's negation finding:
   prohibition without a positive pairing makes the banned behavior
   *more* available, not less).

## Exit condition

Render as a checklist once more than one independent condition has to
hold — a prose paragraph hides which conditions are still open
(trailofbits/skills' own `static-analysis/semgrep` skill uses an
18-item literal checklist as its Definition of Done; this is the
sharpest completion-condition convention found across the whole
research pass):

- [ ] Every REPLACE_ME enumerated in Procedure step 1 has a recorded
      baseline (step 2).
- [ ] REPLACE_ME: the vertical-specific closing conditions.
- [ ] Every candidate this vertical opened is closed as exactly one
      of: **confirmed** (Oracle-backed, ADR 0008, never the agent's
      own self-report), **ruled out** (name the specific control that
      blocks every reachable path to the sink — not just "looked
      safe"), or **open proof gap**, recorded as `needs_confirmation`
      with its `requirements` (ADR 0019). A candidate dropped without
      landing in one of these three is this vertical stopping early,
      not exhausting itself (usestrix/strix's closure discipline:
      "silently dropping an uncertain candidate is mislabelling an
      open_proof_gap as ruled_out, and is how real bugs get missed").

## Rationalizations to reject

Security verticals only (trailofbits/skills' own house convention,
required for their audit skills). List the excuses this vertical's own
investigation is likely to produce mid-task, and refute each in one
line, so the agent has already seen and dismissed them before it talks
itself into cutting the procedure short. Delete this whole section for
a vertical with no history of this failure mode.

- "REPLACE_ME excuse" — REPLACE_ME refutation.
- "REPLACE_ME excuse" — REPLACE_ME refutation.

## Sub-cases

If this vertical splits into named sub-classes, list them here and say
when to open which `references/<name>.md` file — see
`references/EXAMPLE-SUBCASE.md` in this same directory for the shape a
real one takes. Apply the branching test before splitting one out:
inline what every sub-case needs, push behind a `references/` pointer
only what just one sub-case reaches (Matt Pocock's writing-for-agents
skill: progressive disclosure is hierarchy protection, not a token
optimization — split when a sub-case needs detail no other branch
does, not pre-emptively). Delete this section if there are none yet.

## Known gaps

State fact and required action only: what's blocked, what to do about
it (name it in the run's own notes, never skip silently), and which
ADR explains why. No alternatives considered, no backstory — that's
explanation, and explanation belongs in the ADR, not in a file this
vertical's own turn re-reads every time it runs.
