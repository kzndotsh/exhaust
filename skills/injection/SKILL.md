---
name: injection
required: true
description: >
  Probes every discovered input for command, SQL, LDAP, template
  (SSTI), header/CRLF, and NoSQL injection by submitting a canonical
  boundary-breaking payload per class and diffing the observed response
  against a clean baseline. Use when recon has enumerated at least one
  request-shaped input (form field, query parameter, header, cookie,
  path segment, or uploaded filename) on any Workspace. Do not use for
  deserialization of structured payloads (pickle, YAML,
  XML, Java-object streams) — that's the `deserialization` vertical;
  this one is for payloads interpreted as code or query syntax, never
  payloads reconstructed as a data structure.
---

## What this vertical investigates

Whether any input the Target accepts crosses from data into an
interpreter's syntax: a shell, a SQL/NoSQL query engine, an LDAP
filter, a template engine, or an HTTP header parser reading past the
line it should stop at. The shared mechanism across every sub-case
below is the same: find a boundary character or sequence the target
interpreter treats specially, submit it, and check whether the
Target's behavior changes in a way only that interpretation explains.

## Procedure

1. **Enumerate inputs before touching any of them.** Every form field,
   query parameter, header, cookie, path segment, and upload filename
   the Target exposes is a candidate. An input not on this list before
   step 2 starts doesn't get probed — don't discover and test in the
   same pass, since an untracked input makes the exit condition in
   this file unverifiable.
2. **Baseline every input first.** Submit each input's own normal,
   well-formed value and record the response: status code, timing,
   body length, and any error text verbatim. Every later diff in this
   procedure is measured against this baseline, not against an assumed
   "should have succeeded" response.
3. **Probe each input with one canonical payload per applicable
   class**, boundary-breaking rather than exploit-complete (the goal
   at this stage is detecting a behavior diff, not achieving code
   execution or data exfiltration in the same request):
   - **Command injection**: a shell metacharacter sequence that would
     execute a harmless, uniquely-identifiable command if interpreted
     (e.g. a sentinel string echoed back) if the input reaches a shell
     at all.
   - **SQL injection**: a single-quote/boolean-logic pair (`' OR '1'='1`
     and `' AND '1'='2`) compared against each other and against
     baseline — a real SQL sink flips behavior between the two; a
     false positive doesn't.
   - **LDAP injection**: an LDAP filter metacharacter (`*`, `)`, `(`)
     that would widen or break a filter if the input reaches an LDAP
     query unescaped.
   - **Template injection (SSTI)**: a template-engine expression
     (e.g. `{{7*7}}`-shaped, adapted to whatever templating syntax the
     Target's stack uses once that's known) that evaluates to a
     distinctive value only if the engine actually parses the input.
   - **Header/CRLF injection**: a raw `\r\n` sequence in a header-
     reflected or redirect-target input, checked for a split response
     or an injected header in the Target's reply.
   - **NoSQL injection**: an operator-shaped payload (e.g. a `$ne`/`$gt`
     equivalent for the Target's actual NoSQL engine, once recon has
     identified which one) that would alter query logic if the input
     reaches a NoSQL query unescaped.
4. **Diff against baseline, not against expectation.** A probe is
   interesting only when its response differs from that same input's
   own baseline in a way the payload's mechanism specifically predicts
   (a timing delay for a sleep-based SQL probe, a reflected sentinel
   for command injection, a distinctive evaluated value for SSTI).
   Record every interesting diff as a candidate; do not record a
   non-diff as "tested clean" without the recorded baseline it was
   compared against.
5. **Escalate only a confirmed diff**, one payload class at a time, far
   enough to produce Oracle-checkable evidence (ADR 0008) before
   writing a Finding. Never escalate a class that produced no diff in
   step 4 on the theory that a stronger payload might still work; that
   belongs in a later recon-informed pass, not this one.

## Exit condition

Every enumerated input (step 1) has a recorded baseline (step 2) and
has been probed against every payload class applicable to its context
(step 3), and every diff recorded in step 4 has either been escalated
to a Finding or explicitly dismissed with the reason it isn't a real
signal (e.g. a timing diff within normal response-time variance). A
vertical that stops before every enumerated input has a recorded
baseline and probe result has not exhausted this vertical; it's
stopped early.

## Sub-cases

Command, SQL, LDAP, SSTI, header/CRLF, and NoSQL injection are kept
inline above rather than split into `references/` files: none of them
yet has enough Target-specific nuance to outgrow a few lines in this
file, and splitting now would cost a lookup for no actual context
savings (ADR 0013's progressive disclosure is a cost tradeoff, not a
default). Split one out into its own `references/<name>.md` the first
time its procedure needs engine-specific detail (e.g. a payload table
keyed on which SQL dialect or templating engine recon identified) long
enough to be worth deferring from every other turn's context.

## Known gaps

`curl.get`/`curl.post_form` (ADR 0027) dispatch steps 2 through 5 for
query-parameter and form-field inputs. Header/cookie inputs,
uploaded-filename inputs, and path-segment inputs have no Rig method
yet: treat those as blocked, name them in the run's own notes, and
don't skip them silently. See ADR 0027 for why.
