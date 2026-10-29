# Procedural writing standards: what established fields say, checked against `skills/injection/SKILL.md`

Requested after the "Known gaps" section in `skills/injection/SKILL.md` got trimmed this
session — it had accumulated explanation that belonged in an ADR, not in a file an agent
re-reads every turn. Rather than keep improvising the house style for vertical skill files
by trial and error, this doc checks it against fields that have already solved "how do you
write a procedure a person or system can execute reliably, with no missed steps and no
ambiguity": IETF requirement-level language, the Diátaxis documentation framework, checklist
design in medicine and aviation, SRE runbook/troubleshooting convention, the EARS requirements-syntax
templates, and a working agent-prompt-engineering practitioner's own distilled reference for
writing documents agents consume. Every claim below is cited to a primary source actually
fetched this session (2026-10-29), with the exact passage quoted. Where a source couldn't be
fetched or confirmed, that's stated plainly instead of guessed.

Findings are checked against `skills/injection/SKILL.md`'s actual current structure (What
this vertical investigates / Procedure / Exit condition / Sub-cases / Known gaps) and against
`docs/artifacts/2026-10-29-skills-system-spec.md` §3 ("The body: a vertical's procedure"),
which already states several of these rules as policy. Each finding says explicitly whether it
**confirms** something already done, or **suggests a change**.

## 1. RFC 2119 / RFC 8174 — requirement-level keywords

Sources: <https://www.rfc-editor.org/rfc/rfc2119> and <https://www.rfc-editor.org/rfc/rfc8174>,
both fetched live.

RFC 2119 defines a fixed vocabulary so a spec's instruction strength never has to be inferred
from tone:

- **MUST** / **REQUIRED** / **SHALL**: "the definition is an absolute requirement of the
  specification."
- **MUST NOT** / **SHALL NOT**: "the definition is an absolute prohibition of the
  specification."
- **SHOULD** / **RECOMMENDED**: there may be valid reasons to ignore it in particular
  circumstances, but "the full implications must be understood and carefully weighed before
  choosing a different course."
- **SHOULD NOT** / **NOT RECOMMENDED**: the mirror case — acceptable or even useful in some
  circumstances, but the case must be "carefully weighed before implementing any behavior
  described with this label."
- **MAY** / **OPTIONAL**: "an item is truly optional."

RFC 2119 also constrains its own use: these words are "Imperatives" that "must be used with
care and sparingly" — reserved for points that actually affect interoperation, not sprinkled
onto every sentence for emphasis.

RFC 8174 (2017) closes a real ambiguity the original text left open: "The words have the
meanings specified herein only when they are in all capitals." Lowercase "must" or "should"
"have their normal English meanings and are not affected by this document." This is exactly
the gap a numbered procedure step can fall into silently — a step that says "the agent should
record the baseline" reads, without the capitalization convention, as indistinguishable from
a step that says "this should correlate with recon."

**Against `skills/injection/SKILL.md`:** the file already writes in a consistently imperative,
near-unambiguous register — "Enumerate inputs before touching any of them," "Diff against
baseline, not against expectation" — but it does this through sentence construction, not
through a keyword convention, and it does use plain lowercase "should" at least once ("the
goal at this stage is detecting a behavior diff... never escalate a class that produced no
diff... on the theory that a stronger payload might still work") without it being load-bearing
in the RFC 2119 sense. **This is a concrete, adoptable delta**: reserve capitalized MUST /
MUST NOT / SHOULD / MAY in Procedure and Exit Condition sections for the exact RFC 2119
meanings, state that convention once (in the TEMPLATE file or §3 of the spec), and apply RFC
8174's capitals-only rule so a lowercase "should" elsewhere in prose is never misread as a
requirement-level claim. This is the single most mechanical, CI-checkable delta in this whole
document — `exhaust skill lint` could grep for lowercase must/should/may in Procedure bodies
the same way it already checks for tool-name drift (spec §6).

## 2. Diátaxis — how-to guides exclude explanation by name

Sources, all fetched live: <https://diataxis.fr/>, <https://diataxis.fr/how-to-guides/>,
<https://diataxis.fr/explanation/>, <https://diataxis.fr/compass/>.

Diátaxis divides documentation into four modes along two axes (the "compass"): whether
content "informs action" (practical steps, doing) or "informs cognition" (theoretical or
propositional knowledge, thinking), crossed with whether it serves "acquisition of skill"
(study) or "application of skill" (work). Action + application = **how-to guide**; cognition +
acquisition = **explanation**. A vertical's `SKILL.md` Procedure is squarely a how-to guide in
this scheme (action, applied against a live Target, not studied in the abstract).

This is not a soft style preference — the how-to guide page states the exclusion of
explanation **by name**, as one of the guide's defining characteristics: "no digression,
explanation, teaching." It goes further on why: "Anything else that's added distracts both you
and the user and dilutes the useful power of the guide," and names the exact failure mode this
session just hit — "Typically, the temptations are to explain or to provide reference for
completeness... Neither of these are part of guiding the user in their work." The explanation
page confirms the same boundary from the other side: explanation "tends to absorb other
things," and "allowing them to creep in interferes with the explanation itself" — i.e. the
anti-pattern runs both directions, not just procedure-absorbing-explanation.

**Against the "Known gaps" trim this session:** this **confirms**, with a named citation, that
the trim was correct discipline rather than an arbitrary cut. Diátaxis treats "explain why
this gap exists" as content that belongs in a different document (here, the ADR) by the same
logic that keeps a recipe from teaching you why eggs emulsify. **Concrete change to encode
this going forward**: `docs/artifacts/2026-10-29-skills-system-spec.md` §3 already says a
procedure is "instructions to the agent, not documentation about the vertical" — that's the
right rule, but it doesn't yet say explanation specifically is the excluded mode, or point at
why. Recommend adding one sentence to §3 and to the TEMPLATE's Known-gaps guidance: *state the
fact and the required action (what's blocked, what to do instead); if the reader needs the
reasoning, link the ADR — don't inline it.* That's a direct, quotable rule an author or a
linter can check against, instead of relying on everyone having just watched this exact
over-trim happen once.

## 3. Checklist design — WHO Surgical Safety Checklist

Source: WHO Surgical Safety Checklist program page, fetched live
(<https://www.who.int/teams/integrated-health-services/patient-safety/research/safe-surgery/tool-and-resources>).

Confirmed from the primary source: the checklist is deliberately short (19 items) and is
built around mandatory pause points, not optional best-practice framing — "The 19-item
checklist has gone on to show significant reduction in both morbidity and mortality." Crucial
for reliability under pressure: it is read from an external reference, never from memory —
"The goal is to use a tool for reference to ensure every item is covered, e.g., a form,
poster, or computer screen" — and the team's own self-test asks three things: does the whole
team pause at three fixed points (pre-anesthesia, pre-incision, before the patient leaves the
OR); does the whole team verbally confirm each item; are items verified "without reliance on
memory." It explicitly flags partial compliance as a design failure, not a discipline failure:
items are often "verified most of the time, but not every time, i.e., not consistently," and
the fix offered is structural — "If not, redesign your processes to ensure it does" — i.e. a
checklist that isn't followed reliably is a documentation defect, not a people problem.

**Caveat, stated plainly:** the WHO page does not use or define "read-do" vs. "do-confirm"
terminology, and does not discuss "killer items" as a named concept. I could not independently
confirm those two specific terms-of-art against a primary source this session — attempts to
fetch Skybrary's checklist article and Degani & Wiener's NASA/FAA cockpit-checklist paper both
failed (Skybrary returned a JS stub with no article text; the NASA paper is a scanned PDF with
no extractable text layer in this environment). Treat "read-do vs. do-confirm" as a real and
commonly cited aviation-human-factors distinction, but **not one this research confirmed
against a primary source** — do not cite it in the spec as if it were.

**Against the current SKILL.md shape:** this **confirms** two things the injection file
already does right — it externalizes the check ("Record every interesting diff as a candidate;
do not record a non-diff as 'tested clean' without the recorded baseline it was compared
against" is structurally a do-confirm pattern: baseline recorded, then confirmed against) and
it names its own failure-mode self-test in the Exit condition ("A vertical that stops before
every enumerated input has a recorded baseline and probe result has not exhausted this
vertical; it's stopped early"). It also **suggests one gap**: WHO's checklist names fixed,
non-skippable pause points before the team can proceed. The injection procedure has no
equivalent explicit "do not proceed to step N+1 until step N's artifact exists" gate — step 5
("Escalate only a confirmed diff") implies this but doesn't state it as a hard stop the way
WHO's checklist does. Worth considering for the TEMPLATE: an explicit "stop condition" per
step, not just a terminal exit condition for the whole vertical.

## 4. Google SRE Book — troubleshooting and incident procedure

Sources, all fetched live: <https://sre.google/sre-book/effective-troubleshooting/>,
<https://sre.google/sre-book/monitoring-distributed-systems/>,
<https://sre.google/sre-book/managing-incidents/>, <https://sre.google/sre-book/being-on-call/>.

**Caveat up front:** none of these four chapters contains a dedicated "runbook/playbook
structure" section with a template — I looked for one specifically and it isn't there in this
edition of the book. "Being On-Call" and "Managing Incidents" mention "playbook entries" and
procedures only in passing, without specifying their contents. Report this gap plainly rather
than inventing a structure and attributing it to Google.

What **effective-troubleshooting** does establish, concretely:

- Troubleshooting is framed as hypothesis-testing, explicitly: "iteratively hypothesize
  potential causes for the failure and try to test those hypotheses," with tests ordered so
  that "An ideal test should have mutually exclusive alternatives, so that it can rule one
  group of hypotheses in and rule another set out."
- A problem report's required content is stated directly: it should "tell you the *expected*
  behavior, the *actual* behavior, and, if possible, how to reproduce the behavior" — this is
  effectively trigger-condition + symptom + repro, the same three facts a well-formed Finding
  needs.
- Changes made while diagnosing must be reversible and tracked: "making changes in a
  systematic and documented fashion will help you return the system to its pre-test setup."

**monitoring-distributed-systems** contributes one durable principle for any
agent-facing trigger condition: "Every page should be actionable," tested by "Can I take
action in response to this alert?" — a procedure (or a vertical's `gate`) that can't name a
concrete next action when triggered fails this test.

**managing-incidents** contributes a structural convention worth citing even though it isn't
about SOPs specifically: the incident-state document is explicitly allowed to be messy but
"must be functional," and "keeping the most important information at the top makes it more
usable" — ordering by what's acted on first, not narrative order.

**Against the current SKILL.md shape:** this mostly **confirms** existing practice rather than
suggesting new structure. The injection file's step 2 ("Baseline every input first... Every
later diff in this procedure is measured against this baseline, not against an assumed
'should have succeeded' response") is the same expected/actual/repro discipline SRE's
problem-report convention states directly, independently arrived at. One genuine, small
**suggested change**: the SRE book's "every page should be actionable" test is a good one-line
addition to spec §3's bullet about exit conditions — a vertical's `gate` (ADR 0011) should pass
the same test the book applies to a monitoring alert, i.e. the `description`'s gate clause
should itself be phrasable as "can the agent take a concrete next action when this fires,"
which `exhaust skill lint`'s description-shape check (spec §6) could extend to check for.

## 5. ISO / regulatory SOP conventions

I attempted to fetch two candidate primary sources for what a Standard Operating Procedure
document is formally required to contain: an FDA guidance PDF
(`fda.gov/media/97057/download`) and EPA's "Guidance for Preparing Standard Operating
Procedures" (`epa.gov/sites/default/files/2015-06/documents/g6-final.pdf`). **Both fetches
failed to produce readable text** — both are scanned/compressed PDFs with no extractable text
layer available in this environment, and the PDF-rendering fallback (`pdftoppm`) is not
installed here either. I could not confirm this item against a primary source this session.
Rather than cite either document secondhand or substitute a content-marketing summary dressed
up as authoritative, this is flagged as an open gap: **no ISO/regulatory SOP source was
confirmed in this research pass.** If this convention is needed later, re-run this fetch in an
environment with PDF text extraction, or locate an HTML-rendered edition of one of these
guidance documents.

## 6. EARS (Easy Approach to Requirements Syntax) — trigger-first requirement templates

Sources: <https://alistairmavin.com/ears/> (the format's originator's own site, fetched live)
and <https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax> (checked as a
cross-reference, not the primary claim). EARS was developed at Rolls-Royce (Alistair Mavin and
colleagues) analysing airworthiness regulations for a jet engine control system, first
published at IEEE RE'09.

EARS fixes a small set of templates, each naming its clauses in a fixed temporal order
(precondition, then trigger, then system, then response), confirmed from the originator's own
site:

- **Ubiquitous** (no keyword — always active): "The `<system name>` shall `<system
  response>`"
- **State-driven** (*While*): "While `<precondition(s)>`, the `<system name>` shall `<system
  response>`"
- **Event-driven** (*When*): "When `<trigger>`, the `<system name>` shall `<system
  response>`"
- **Optional feature** (*Where*): "Where `<feature is included>`, the `<system name>` shall
  `<system response>`"
- **Unwanted behaviour** (*If...Then*): "If `<trigger>`, then the `<system name>` shall
  `<system response>`"
- **Complex** (two or more keywords combined): "While `<precondition(s)>`, When `<trigger>`,
  the `<system name>` shall `<system response>`"

The originator's site states the clause order is fixed "following temporal logic," and that
keywords were chosen to match ordinary English usage specifically so authors find them
intuitive rather than needing to learn new vocabulary. Each requirement has zero-or-more
preconditions, zero-or-one trigger, exactly one system name, and one-or-more responses — a
closed shape, not free prose.

**Direct relevance to exhaust's own schema**: a Playbook vertical's `gate` field (ADR 0011,
`required: false` + a `gate` string) is structurally an EARS State-driven or Event-driven
precondition/trigger clause with no fixed syntax enforced on it today. `skills/injection/SKILL.md`
has no `gate` (it's `required: true`), but the reserved gated verticals in
`docs/artifacts/2026-10-26-playbook-proposal.md` §4 (e.g. "A confirmed `/graphql`-equivalent
endpoint responding to an introspection probe") are already *written* in something close to
EARS's own When-clause shape, just not against a checked template. **Concrete, low-cost
change**: when the Playbook's gated verticals actually get written as real skill files, require
each `gate` string to parse as an EARS When/While clause (a trigger or precondition, stated as
a confirmed observation, never a guess) and have `exhaust skill lint` check the string starts
with one of EARS's own keywords (When/While/Where/If) or an equivalent confirmed-observation
phrasing. This doesn't change any `gate` text already written — it's a shape exhaust could hold
new ones to once a real gated vertical skill file gets authored.

What EARS does *not* help with: it's a requirements-statement syntax (what a system shall do),
not a procedure syntax (the ordered steps an agent takes to find out). It complements RFC
2119's keyword vocabulary (one states the trigger shape, the other states the instruction
strength) rather than competing with it — exhaust's `gate` field is the EARS-shaped piece;
`Procedure`'s numbered steps are the RFC-2119-shaped piece.

## 7. Matt Pocock's `writing-for-agents` skill — context load vs. cognitive load, and a sharper framing of progressive disclosure

Source: `writing-for-agents/SKILL.md` and its companion `SKILL-MECHANICS.md`, from the
`mattpocock-skills` plugin already installed in this very session (cached at
`~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/1.3.1/skills/productivity/writing-for-agents/`,
upstream `github.com/mattpocock/skills`). This isn't a standards body or an academic source the
way the others in this document are — it's a working agent-prompt-engineering practitioner's
own distilled reference — but it's the single most directly applicable source found in this
whole pass, because it's written specifically about the exact kind of document exhaust's skill
files are (documents consumed by an agent to do procedural work), not adapted from a different
domain the way RFC 2119, Diátaxis, WHO, and SRE all are.

Three findings, each concrete enough to check against `skills/injection/SKILL.md` directly:

1. **Two distinct costs, not one.** The skill names "context load" (the token/attention cost of
   always-loaded material, like a `description`) and "cognitive load" (the cost on the *human*
   of remembering a document exists and when to reach for it) as separate budgets that trade
   against each other. This sharpens something this session's audits only gestured at:
   `disable-model-invocation` (found in `cursor/plugins`' `pstack` and confirmed as a real
   Claude Code field) isn't just "a flag for sub-verticals the Harness can dispatch
   deterministically" — it's a context-load-vs-cognitive-load trade, and the skill states the
   actual decision rule plainly: "Pick model-invocation only when the agent must reach the
   skill on its own, or another skill must. If it only ever fires by hand, make it
   user-invoked and pay no context load." This is a direct, actionable answer to the open
   question already on this project's own list (`docs/research/2026-10-28-agent-skills-ecosystem-audit.md`'s
   closing deltas) — worth citing by name when that question actually gets decided.
2. **Progressive disclosure is framed as hierarchy protection, not a token optimisation** —
   a sharper claim than ADR 0013's own framing. Quote: "Not primarily a token optimisation: it
   is how the hierarchy is protected... Branching is the cleanest disclosure test: inline what
   every branch needs, and push behind a pointer what only some branches reach." Checked
   against `skills/injection/SKILL.md`'s own §Sub-cases decision (keeping command/SQL/LDAP/SSTI
   inline rather than splitting into `references/` files yet): that decision already used
   exactly this branching test in its own stated reasoning ("none of them yet has enough
   Target-specific nuance to outgrow a few lines... split one out the first time its procedure
   needs engine-specific detail") — independent convergence, not something this document
   introduced.
3. **Negation is a named failure mode, with a mechanism, not just folk wisdom.** Quote: "steering
   by prohibition drags the forbidden behaviour into context and makes it more available, not
   less... Prompt the positive: state the target behaviour... so the banned one is never
   spoken." Checked directly against `skills/injection/SKILL.md`'s own body: its one explicit
   prohibition ("Never escalate a class that produced no diff in step 4 on the theory that a
   stronger payload might still work") is paired with the positive instruction immediately
   before it ("Escalate only a confirmed diff, one payload class at a time"), which already
   follows this rule — the negative is a restatement of a boundary already set positively, not
   doing standalone work. No change needed here, but worth naming as a check for any future
   vertical's procedure: a standalone prohibition with no accompanying positive statement of
   the target behaviour is now a named thing to watch for, not just a vague "don't phrase
   things negatively" intuition.

Also directly relevant, though not yet actionable for exhaust specifically: the "Steps and
completion criteria" section's distinction between a criterion's **clarity** (can the agent
tell done from not-done) and its **demand** (how much work it actually requires) gives a
sharper vocabulary than this document's own §3/§4 findings for evaluating an Exit condition's
quality — `skills/injection/SKILL.md`'s current exit condition ("every enumerated input has a
recorded baseline and has been probed against every payload class... every diff has either been
escalated or explicitly dismissed with the reason") is checkable (clear) and exhaustive
(high-demand) by this vocabulary's own test, which is a second, independent confirmation of the
same soundness the WHO checklist comparison already found in §3.

## Summary of concrete deltas against the current spec/injection file

| # | Finding | Confirms or changes? |
|---|---|---|
| 1 | RFC 2119/8174 MUST/SHOULD/MAY, capitals-only | **Change**: adopt capitalized keywords in Procedure/Exit Condition text; add a lint check for lowercase must/should/may in those sections. |
| 2 | Diátaxis: how-to guides name-exclude explanation; explanation page confirms the boundary cuts both ways | **Confirms** this session's "Known gaps" trim was correct discipline, not overcorrection; **change**: add one explicit sentence to spec §3 and TEMPLATE.md stating explanation goes in the ADR, only fact+action stays in the skill file. |
| 3 | WHO checklist: short, externally-referenced, non-skippable pause points, partial compliance = design defect | **Confirms** injection's baseline-then-diff and stated exit condition are structurally sound; **suggests** adding an explicit per-step stop condition, not just a whole-vertical exit condition. Read-do/do-confirm terminology **not confirmed** — don't cite it as fact. |
| 4 | SRE book: hypothesis-driven troubleshooting, expected/actual/repro problem reports, "every page actionable" | Mostly **confirms** existing discipline already present in injection's baseline step; **small change**: extend the gate-description lint check to require the gate be phrasable as a concrete next action. No runbook template found in this edition — flagged, not invented. |
| 5 | ISO/regulatory SOP structure | **Not confirmed.** Both candidate primary sources failed to extract as text in this environment; stated as an open gap rather than guessed. |
| 6 | EARS: fixed trigger-clause templates (When/While/Where/If-Then), temporal clause order | **New, additive**: a `gate` string's shape isn't checked today; once real gated verticals get written, hold each `gate` to an EARS When/While/If-Then shape and lint the keyword. Doesn't apply to `Procedure` steps — EARS states requirements, not actions. |
| 7 | Matt Pocock's `writing-for-agents`: context load vs. cognitive load, disclosure-as-hierarchy-protection, negation as a named failure mode | **Confirms** injection's Sub-cases decision and its one prohibition's positive pairing independently; **directly answers** the still-open `disable-model-invocation`-equivalent question from the Agent Skills audit with a concrete decision rule, worth citing when that question is actually decided. |

## Sources fetched this session

- <https://www.rfc-editor.org/rfc/rfc2119>
- <https://www.rfc-editor.org/rfc/rfc8174>
- <https://diataxis.fr/>
- <https://diataxis.fr/how-to-guides/>
- <https://diataxis.fr/explanation/>
- <https://diataxis.fr/compass/>
- <https://www.who.int/teams/integrated-health-services/patient-safety/research/safe-surgery/tool-and-resources>
- <https://sre.google/sre-book/effective-troubleshooting/>
- <https://sre.google/sre-book/monitoring-distributed-systems/>
- <https://sre.google/sre-book/managing-incidents/>
- <https://sre.google/sre-book/being-on-call/>
- <https://alistairmavin.com/ears/>
- <https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax> (cross-reference only, not the primary claim)
- `writing-for-agents/SKILL.md` and `SKILL-MECHANICS.md`, `mattpocock-skills` plugin v1.3.1, cached locally, upstream `github.com/mattpocock/skills` — not a web fetch, but a real, installed, versioned source read in full

## Sources attempted and not usable (stated explicitly, not substituted)

- `https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_120-71A.pdf` — HTTP 403.
- `https://skybrary.aero/articles/normal-checklists` and
  `https://www.skybrary.aero/index.php/Checklists` — returned no extractable article text
  (JS-rendered page, fetched as an empty stub).
- `https://en.wikipedia.org/wiki/The_Checklist_Manifesto` — checked as a fallback for
  Gawande's design principles; the article is a plot/overview summary and does not state his
  design recommendations (read-do/do-confirm, killer items, 5–9 item guidance), so nothing
  from it is cited above.
- NASA/FAA cockpit-checklist paper (Degani & Wiener), via NTRS — scanned PDF, no text layer.
- `https://www.fda.gov/media/97057/download` and
  `https://www.epa.gov/sites/default/files/2015-06/documents/g6-final.pdf` — both scanned/
  compressed PDFs with no extractable text in this environment.
