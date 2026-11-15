---
name: csrf
required: true
description: >
  Probes whether a Target's state-changing endpoint accepts a request
  shaped the way a true cross-site forgery would arrive: no CSRF token
  (or a token not bound to the requesting session), no Origin/Referer
  header matching the Target's own origin, or a state change reachable
  via a plain GET request — while still carrying the victim's own
  ambient session cookie. Dispatches through `curl.get`/`curl.post_form`,
  varying only the token/header shape of an otherwise-legitimate
  request and diffing whether the mutation still takes effect. Use
  when the Workspace's surface records a state-changing endpoint
  reached by `post_form` or `get` whose baseline request includes a
  session cookie. Do not use for the session cookie's own attributes
  (`Secure`/`HttpOnly`/`SameSite`) — that's `auth-session`, which
  already records and tests them; read its recorded `SameSite` value
  here rather than re-testing it. Do not use for an attacker who
  already possesses a second identity's own valid credentials — that's
  `access-control`'s cross-identity bypass, a different trust boundary
  than one exploited through a victim's unwitting browser. Do not use
  for a script-based cross-origin read primitive stealing the token
  itself — that's `client-side`.
keywords:
  - CSRF
  - cross-site request forgery
  - anti-CSRF token
  - synchronizer token
  - double submit cookie
  - SameSite bypass
  - state-changing GET
  - method override
  - method confusion
  - Origin header validation
  - Referer header validation
---

## What this vertical investigates

Whether a state-changing action can be triggered using only the
ambient credentials a victim's browser would automatically attach to a
cross-site request — nothing the forging page could not also produce
or omit — because the server authenticates the request by session
cookie alone, trusting that only the Target's own page could have sent
it.

## Procedure

1. MUST read the Workspace's enumerated surface before touching
   anything — this vertical does not enumerate the Target itself. From
   it, identify every state-changing endpoint reached via
   `curl.post_form` or `curl.get`, together with any CSRF token field
   or header the form or a prior response recorded, and the
   session-identifying cookie or header already captured on the
   surface. If the surface records no session-identifying cookie at
   all, or no state-changing endpoint, this vertical has nothing to
   investigate; MUST report that plainly rather than closing with no
   findings as if every candidate had been checked.
2. MUST record a baseline for every candidate first: submit the
   endpoint's own legitimate request exactly as the Target's own page
   would (its real token, its real session cookie, an Origin/Referer
   header matching the Target's own origin), and confirm the mutation
   actually took effect by re-reading the resulting state through a
   separate request — never inferred from a success-shaped status
   alone. Every later probe is compared against this confirmed
   baseline mutation, never an assumed one.
3. MUST probe each mechanism, always keeping the victim's own session
   cookie intact (the ambient part of the ambient-credential model)
   while varying only what a true cross-site request could not supply:
   - **Missing or invalid token**: resubmit with the token field or
     header omitted entirely, and separately with an arbitrary,
     mismatched value, and check whether the mutation still takes
     effect either way.
   - **Synchronizer-token flaw**: obtain a token from a second,
     independent session or an unauthenticated page load, and submit
     it alongside the first session's own cookie. Tests whether the
     server validates the token against the specific session that
     owns it, the shape a server-side-stateful token-store implies. A
     server validating only "does a valid-shaped token exist
     somewhere" rather than "does this exact session own this exact
     token" will still accept it.
   - **Double-submit-cookie flaw**: independent of any legitimate
     token, submit an attacker-invented value as both the request's
     token parameter/header and, via `headers` (the same
     `Cookie`-setting mechanism `auth-session` already uses for
     fixation), the cookie value a double-submit scheme reads — with
     the victim's real session cookie otherwise left intact if the
     implementation uses a separate cookie for this purpose. Tests
     whether the server does anything beyond comparing the submitted
     value against whatever cookie value arrived with the request, the
     shape a stateless double-submit scheme implies. MUST NOT treat a
     pass on either of these two tests as covering the other — a
     Target's token-binding architecture determines which test is
     meaningful, and this vertical cannot assume which one is in play
     without trying both.
   - **Origin/Referer not enforced**: resubmit with the `Origin` and
     `Referer` headers omitted entirely (the shape a plain HTML form
     submission produces, with no script able to set them) and
     separately with a value naming a different, attacker-chosen
     origin. If the mutation takes effect either way, the server isn't
     checking the header at all. Where the surface shows the server
     does check but matches loosely, MUST try both of two distinct weak
     shapes: a **prefix check**, satisfied by a subdomain naming the
     Target first (`https://target.example.attacker.com`), and a
     **substring/contains check**, satisfied by placing the Target's
     domain anywhere in the URL including the query string
     (`https://attacker.example/csrf-attack?target.example`) — a value
     satisfying the prefix shape can pass a substring check too without
     proving which, if either, the Target actually implements.
   - **State-changing GET**: where a state-changing action is reachable
     via `curl.get` rather than `curl.post_form`, MUST check whether
     the mutation takes effect from a bare GET carrying no token or
     custom header at all. This is the cheapest-to-forge case once
     delivered via a top-level navigation (a plain link, a top-level
     script redirect, or a GET-method form submission that replaces
     the page) — not a background request such as an `<img>`
     tag, which a cookie defaulting to `SameSite=Lax` (the behavior of
     any cookie with no explicit `SameSite` attribute in a modern
     browser) will not carry cross-site at all. A Target relying on
     `SameSite=Lax` is still exposed here: Lax's own carve-out
     specifically allows a cross-site top-level navigation through.
     Read `auth-session`'s recorded `SameSite` value for context, but
     MUST NOT be assumed safe merely because a POST-based equivalent of
     the same action requires a token, or because the cookie is
     Lax-scoped.
   - **Method confusion**: resubmit the identical baseline mutation to
     the same endpoint URL via `curl.get` even when the endpoint's own
     recorded, primary interface is `curl.post_form` (and vice versa)
     — a server that validates the token only for its documented
     method can skip that check entirely for the other one. Separately,
     where the Target's own stack is known to use a method-override
     convention (a `_method`-shaped form field, or an equivalent the
     Target's own framework documents), resubmit the baseline mutation
     as a plain GET or simple-Content-Type POST carrying that field set
     to the real method, to check whether the token/Origin check that
     gated the real method also gates the overridden one.
   - **Content-Type-based bypass**: where the endpoint's own baseline
     request used a non-simple `Content-Type` (e.g. `application/json`)
     and the body is a flat set of key/value pairs `curl.post_form`'s
     `data` can reproduce field-by-field, resubmit those same fields
     with the `Content-Type` header changed to a simple type
     (`text/plain` or `application/x-www-form-urlencoded`) via
     `headers`. If the server still parses and accepts the body, a
     `Content-Type` check was the only defense in place and it never
     actually examined the body's real shape. Where the real body is
     not flat (nested JSON, an array), this vertical's own dispatch
     tools cannot reproduce it faithfully at all — MUST record it as
     `needs_confirmation` with the requirement "baseline body is not
     flat-key/value shaped; confirming this bypass needs a raw-body
     POST capability this Rig doesn't currently pin," not silently
     skip the candidate or assume the bypass works.
4. MUST diff against the confirmed baseline mutation, never against a
   status code alone: a probe is interesting only when the targeted
   state actually changed as a result of the stripped-down request,
   confirmed by re-reading it afterward — not merely a 200/302
   response, which a server can return without ever having applied the
   mutation. MUST record every confirmed mutation as a candidate; MUST
   NOT record a non-mutation as "tested clean" without having actually
   re-read the state to confirm it didn't change.
5. MUST escalate only a confirmed mutation far enough to produce
   Oracle-checkable evidence before writing a Finding: the specific
   state read back as changed by a request this vertical's own
   procedure sent — not an assumed side effect of a success-shaped
   response.

## Exit condition

- [ ] Every candidate endpoint identified in step 1 has a confirmed
      baseline mutation (step 2).
- [ ] Every candidate has been probed against every mechanism in step 3
      applicable to it (the state-changing-GET bullet only applies to
      a `curl.get`-reached candidate; every other bullet always applies
      once a session cookie and a state-changing endpoint exist).
- [ ] Every candidate mutation recorded in step 4 is closed as exactly
      one of: **confirmed** (Oracle-backed via a re-read of the actual
      state, never this vertical's own self-report), **ruled out** (the
      specific, named reason the request didn't mutate anything — e.g.
      "token omitted, response was a success-shaped redirect, but the
      re-read state was unchanged" — not just "looked clean"), or
      **open proof gap**, recorded as `needs_confirmation` with its
      `requirements`. A candidate dropped without landing in one of
      these three is this vertical stopping early, not exhausting
      itself.

## Rationalizations to reject

- "It returned a 302 redirect to a success page, so the action went
  through." — A redirect is what a generic post-submit handler often
  returns regardless of validation outcome. MUST re-read the actual
  state to confirm the mutation, not infer it from a success-shaped
  response.
- "The form has a hidden field that looks like a CSRF token, so it's
  protected." — A field existing is not the same as the server
  validating it. MUST actually omit or alter it and confirm whether
  the mutation still happens.
- "The cookie has `SameSite=Strict`, so CSRF can't happen here." — A
  strict `SameSite` cookie blocks most but not every real-world
  delivery path (a top-level navigation, a same-site subdomain, a
  misconfigured proxy). Read what `auth-session` actually recorded
  rather than assuming the attribute alone closes every case, and
  still test the endpoint directly.
- "This is a GET request, GETs are supposed to be safe, so it's out of
  scope." — Idempotent-by-convention is not idempotent-by-
  implementation. MUST check whether the GET actually mutates state
  before excluding it.

## Known gaps

This vertical has no real browser or cross-origin rendering context to
host an actual forged page in: it confirms the *missing defense*
itself (an accepted token-less, origin-mismatched, or GET-shaped
request) via direct request manipulation rather than staging a literal
third-party HTML proof-of-concept. A confirmed mutation under step 4
is sufficient evidence the defense is absent, which is what this
vertical investigates; it is not, on its own, a working delivery page,
and MUST NOT be reported as one. A real browser also strips the query
string from an outgoing `Referer` header by default, which this
vertical's own direct request manipulation doesn't reproduce — a
weak-match finding here is still a real defense gap, just not
automatically proof that an unmodified browser delivers it as written.

`curl.post_form` can only submit a flat, form-urlencoded body: a
Target whose real endpoint requires a raw JSON (or other non-flat)
request body cannot have its exact shape reproduced by this vertical's
own dispatch, narrowing the Content-Type-bypass sub-case to flat-bodied
JSON endpoints only.

## References

- MITRE CWE-352, Cross-Site Request Forgery (CSRF): <https://cwe.mitre.org/data/definitions/352.html>
- MITRE CWE-1275, Sensitive Cookie with Improper SameSite Attribute:
  <https://cwe.mitre.org/data/definitions/1275.html>
- MITRE CWE-346, Origin Validation Error: <https://cwe.mitre.org/data/definitions/346.html>
- PortSwigger, Cross-site request forgery (CSRF) (testing technique):
  <https://portswigger.net/web-security/csrf>
- OWASP Cheat Sheet Series, Cross-Site Request Forgery Prevention:
  <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>
