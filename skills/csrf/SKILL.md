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
  - SameSite bypass
  - state-changing GET
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
   - **Token not bound to the session**: obtain a token from a second,
     independent session or an unauthenticated page load, and submit
     it alongside the first session's own cookie. A server validating
     only "does a valid-shaped token exist somewhere" rather than
     "does this exact session own this exact token" will still accept
     it.
   - **Origin/Referer not enforced**: resubmit with the `Origin` and
     `Referer` headers omitted entirely (the shape a plain HTML form
     submission produces, with no script able to set them) and
     separately with a value naming a different, attacker-chosen
     origin. If the mutation takes effect either way, the server isn't
     checking the header at all. Where the surface shows the server
     does check but matches loosely (a substring/prefix check against
     the Target's own domain), MUST try a value a weak check could
     still satisfy (e.g. `https://target.example.attacker.com`).
   - **State-changing GET**: where a state-changing action is reachable
     via `curl.get` rather than `curl.post_form`, MUST check whether
     the mutation takes effect from a bare GET carrying no token or
     custom header at all — this is the cheapest-to-forge case (a
     plain `<img>`-shaped request) — and MUST NOT be assumed safe
     merely because a POST-based equivalent of the same action
     requires a token.
   - **Content-Type-based bypass**: where the endpoint's own baseline
     request used a non-simple `Content-Type` (e.g. `application/json`)
     that a plain cross-site form cannot send without triggering a
     CORS preflight, resubmit the identical body with the
     `Content-Type` header changed to a simple type (`text/plain` or
     `application/x-www-form-urlencoded`) via `headers`. If the server
     still parses and accepts the body, a `Content-Type` check was the
     only defense in place and it never actually examined the body's
     real shape.
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
and MUST NOT be reported as one.

## References

- MITRE CWE-352, Cross-Site Request Forgery (CSRF): <https://cwe.mitre.org/data/definitions/352.html>
- PortSwigger, Cross-site request forgery (CSRF) (testing technique):
  <https://portswigger.net/web-security/csrf>
- OWASP Cheat Sheet Series, Cross-Site Request Forgery Prevention:
  <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>
