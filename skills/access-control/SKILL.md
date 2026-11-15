---
name: access-control
required: true
description: >
  Probes whether a confirmed authenticated identity can reach or act on an
  object, record, or function outside its own ownership or role boundary:
  object-level bypass (IDOR, BOLA) and function-level bypass (BFLA), both
  horizontal (same privilege tier, a different owner's data) and vertical
  (a lower-privileged identity reaching a higher-privileged action).
  Replays the same request as a second, distinct identity and diffs the
  result against what that identity is and isn't entitled to see or do.
  Use when the Workspace's enumerated surface carries an object-id-shaped
  input (a numeric or UUID path segment, an `id`/`*_id`-named query
  parameter or hidden form field) or a role-gated endpoint, and the
  Workspace has credentials for at least two distinct Target identities.
  Do not use for a resource reachable with no authentication at all —
  that's the `information disclosure` vertical. Do not use for the
  session token or cookie itself being guessable, forgeable, or otherwise
  weak — that's `auth/session`.
keywords:
  - IDOR
  - BOLA
  - BFLA
  - broken object level authorization
  - broken function level authorization
  - horizontal privilege escalation
  - vertical privilege escalation
  - broken access control
---

## What this vertical investigates

Whether the Target enforces *who*, not merely *whether*, is allowed to
reach a given object or action: the ownership boundary behind IDOR and
BOLA, and the role boundary behind BFLA.

## Procedure

1. MUST read the Workspace's enumerated surface before touching
   anything — this vertical does not enumerate the Target itself.
   From it, identify every object-id-shaped input (a numeric or UUID
   path segment; an `id`/`*_id`-named query parameter, form field, or
   header) and every endpoint that looks role-gated (an admin-prefixed
   path, or any route whose own baseline response is a 401/403 or a
   redirect to login for a normal-privilege identity). MUST obtain at
   least two distinct authenticated Target identities from the
   Workspace's own engagement material before probing anything — one
   baseline identity, plus at least one other: a second
   normal-privilege identity for a horizontal check, an
   elevated-privilege identity for a vertical check. MUST NOT guess at
   or fabricate a second identity. If the Workspace provides only one
   identity, this vertical cannot investigate anything; MUST report
   that plainly rather than closing with no findings as if every
   candidate had been checked.
2. MUST record a baseline for every candidate object-id input and every
   candidate role-gated endpoint first: submit it as the identity that
   actually owns the object, or that actually holds the required role,
   and record the full response. Every later diff in this procedure is
   measured against this baseline, never against an assumed "should
   have succeeded" response.
3. MUST probe each candidate with the mechanism matching its shape:
   - **IDOR / BOLA (object-level)**: authenticated as one identity,
     replace the object-id input's value with an id that same identity
     does not own — one the second identity owns instead. MUST
     actually confirm who owns the swapped-in id first (a value
     recorded from that second identity's own baseline, never a
     guessed or sequential id), so a diff can be attributed to the
     access check and not to the id simply not existing.
   - **BFLA (function-level)**: attempt the same role-gated endpoint
     or action as an identity that does not hold the required role.
     MUST try every HTTP method and every equivalent route the surface
     records for that action (a UI may hide a button without the
     underlying route being protected), not only the one path the
     normal-privilege baseline used.
   - **Horizontal vs. vertical**: the mechanism above is the same
     either way — horizontal swaps to a same-tier identity's owned
     object or action, vertical swaps to a lower-tier identity
     attempting a higher-tier one. Run both whenever the available
     identities support them; MUST NOT treat a confirmed horizontal
     bypass as having also ruled out a vertical one, or vice versa.
4. MUST diff against the recorded baseline, never against expectation.
   A probe is interesting only when the response actually contains the
   other identity's own data, or the role-gated action actually took
   effect — not merely a different status code or body length, which
   a generic error page can produce with nothing granted. MUST record
   every interesting diff as a candidate; MUST NOT record a non-diff
   as "tested clean" without the recorded baseline it was compared
   against.
5. MUST escalate only a confirmed diff far enough to produce
   Oracle-checkable evidence before writing a Finding: the specific
   other identity's own record, or a durable, independently-visible
   side effect that only the attempted action could have caused — not
   this vertical's own interpretation of an ambiguous response. MUST
   NOT escalate a candidate that produced no diff in step 4 on the
   theory that a different swapped id or a different identity pairing
   might still work — that belongs in a later recon-informed pass, not
   this one.

## Exit condition

- [ ] Every object-id input and every role-gated endpoint identified in
      step 1 has a recorded baseline (step 2).
- [ ] Every one has been probed under every available other identity
      the horizontal/vertical mechanisms in step 3 apply to.
- [ ] Every candidate diff recorded in step 4 is closed as exactly one
      of: **confirmed** (Oracle-backed, never this vertical's own
      self-report), **ruled out** (the specific, named reason the diff
      isn't a real signal — e.g. "swapped id returned the second
      identity's own 404-shaped empty state, not their data" — not
      just "looked clean"), or **open proof gap**, recorded as
      `needs_confirmation` with its `requirements`. A candidate dropped
      without landing in one of these three is this vertical stopping
      early, not exhausting itself.

## Rationalizations to reject

- "It returned 403, so access control is working." — A 403 proves
  nothing if the response body still carried the other identity's data
  before the status line, or if a sibling route for the same object
  (an export, a PDF, a cached API variant) was never tried with the
  same swapped id.
- "This is an admin feature, no normal user would stumble onto it." —
  Obscurity isn't enforcement. MUST actually attempt the call as a
  lower-privileged identity; a link's absence from that identity's own
  UI says nothing about whether the route behind it checks anything.
- "The id is a UUID, not sequential, so this isn't exploitable." —
  Unguessability is a different question (how an id might leak) from
  whether the access check holds once an id is already known from
  somewhere — a shared link, a prior response, another identity's own
  baseline. The check MUST hold regardless of how the id was obtained.
- "I only have one identity; I'll infer the boundary from the docs or
  the UI." — MUST NOT infer. If no second identity exists, this
  vertical cannot investigate anything and MUST say so plainly rather
  than guessing at what the boundary probably does.

## Known gaps

Nothing in the Workspace or Scope Contract today provisions or
declares a second Target identity: this vertical depends entirely on
credentials for at least one additional identity being supplied through
the Workspace's own engagement material. When that material supplies
only one identity, name it as blocked in the run's own notes rather
than skipping silently, and do not substitute a guessed or fabricated
second identity to work around it.

## References

- MITRE CWE-639, Authorization Bypass Through User-Controlled Key:
  <https://cwe.mitre.org/data/definitions/639.html>
- MITRE CWE-862, Missing Authorization: <https://cwe.mitre.org/data/definitions/862.html>
- MITRE CWE-863, Incorrect Authorization: <https://cwe.mitre.org/data/definitions/863.html>
- PortSwigger, Access control vulnerabilities (testing technique):
  <https://portswigger.net/web-security/access-control>
- OWASP API Security Top 10, API1:2023 Broken Object Level Authorization:
  <https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/>
- OWASP API Security Top 10, API5:2023 Broken Function Level Authorization:
  <https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/>
