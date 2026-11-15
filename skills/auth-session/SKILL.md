---
name: auth-session
required: true
description: >
  Probes the Target's session-management and authentication-flow
  mechanics for logic flaws that let a session outlive or escape the
  boundary it should be scoped to: session fixation (a pre-chosen
  session identifier remains valid after authentication), missing
  session invalidation on logout or credential change (an old session
  identifier still grants access afterward), weak session-cookie
  attributes (`Secure`, `HttpOnly`, `SameSite`), and password-reset
  token weaknesses (predictability, reuse after redemption, missing
  expiration). Dispatches through `curl.get`/`curl.post_form`, reading
  the session identifier and its attributes off the leading status-line
  and header block their output carries, and setting a chosen session
  value via `headers`. Use when recon has confirmed a session-
  identifying cookie or header and a login endpoint on the Workspace's
  surface. Do not use for a request replayed cross-site using the
  victim's own ambient session — that's `CSRF`. Do not use for
  brute-forcing or rate-limiting a login, OTP, or reset endpoint —
  that's the reserved `rate-limiting / brute-force` vertical. Do not
  use for a JWT's own signing or structure weaknesses, an OAuth flow's
  own weaknesses, or a reset link poisoned via the Host header — that's
  the reserved `OAuth / JWT handling` or `Host header attacks`
  vertical respectively.
keywords:
  - session fixation
  - session hijacking
  - session invalidation
  - insecure cookie attributes
  - password reset token
  - broken authentication
  - account takeover
  - logout invalidation
---

## What this vertical investigates

Whether a session, once established, stays scoped to the identity and
the moment that created it: that authenticating actually issues a new
session rather than keeping one chosen beforehand, that logging out or
changing credentials actually ends every session that predates it, that
the session cookie itself carries the attributes that keep it from
leaking, and that a password-reset token can't be predicted, reused, or
outlive its own stated window.

## Procedure

1. MUST read the Workspace's enumerated surface before touching
   anything — this vertical does not enumerate the Target itself. From
   it, identify the session-identifying cookie or header (its name and
   which Rig method/parameter reaches it, as recon already recorded),
   the login endpoint, the logout endpoint if one is recorded, and any
   password-reset request/confirm endpoints. If recon has recorded no
   session-identifying cookie or header at all, this vertical has
   nothing to investigate; MUST report that plainly rather than closing
   with no findings as if every candidate had been checked.
2. MUST record a baseline before testing anything: authenticate
   normally and capture the issued session identifier verbatim,
   together with the full response header block `curl.get`/
   `curl.post_form`'s output leads with — specifically the session
   cookie's `Secure`, `HttpOnly`, `SameSite`, and `Expires`/`Max-Age`
   attributes exactly as the Target set them. Every later check in this
   procedure is compared against this recorded baseline, never against
   an assumed default.
3. MUST probe each applicable mechanism:
   - **Session fixation**: before authenticating, set a chosen session
     identifier value via `headers` (the same `Cookie`-setting
     mechanism `injection` already dispatches through), then
     authenticate while still carrying that value. MUST confirm
     fixation by checking whether the pre-chosen value — not a value
     the Target issued — now grants authenticated access, not merely
     whether login succeeded.
   - **Missing invalidation on logout**: after the baseline session
     logs out, replay the *same, pre-logout* session identifier
     against an endpoint that required authentication in step 2. MUST
     confirm by checking the replayed request actually returns the
     account's own authenticated data, not merely a non-error status.
   - **Missing invalidation on credential change**: after the baseline
     identity changes its own password (if the surface records a
     change-password endpoint), replay the session identifier issued
     *before* the change the same way. A session-management system
     that invalidates on logout can still fail to invalidate on
     credential change; MUST NOT treat one as covering the other.
   - **Cookie attribute weaknesses**: compare the baseline's recorded
     `Secure`/`HttpOnly`/`SameSite` attributes against what the
     Target's own transport actually is (an `HttpOnly`-missing cookie
     readable by script is a real finding regardless of transport; a
     missing `Secure` flag matters only when the Target is also
     reachable over plain HTTP).
   - **Password-reset token weaknesses**: request at least two reset
     tokens (for the same account, requested separately) and compare
     their structure for predictability — MUST NOT conclude
     predictable or unpredictable from a single token. Separately,
     MUST check whether a token still redeems successfully a second
     time after its first successful use, and, where the surface or
     the Target's own documentation states an expiration window,
     whether a token issued and then left unused still redeems after
     that window has passed. This bullet covers only the token's own
     predictability, reuse, and expiration — MUST NOT test whether the
     reset link's target host can be manipulated via the request's
     Host header; that is the reserved `Host header attacks`
     vertical's concern once gated.
4. MUST diff against the recorded baseline, never against expectation.
   A candidate is interesting only when a stale or fixed session
   identifier actually still grants access to the account's own
   authenticated data, or a reset token is demonstrably reused,
   outlives its stated window, or shares a predictable structure across
   at least two independently requested samples — never from a single
   observation. MUST record every interesting diff as a candidate;
   MUST NOT record a non-diff as "tested clean" without the recorded
   baseline it was compared against.
5. MUST escalate only a confirmed diff far enough to produce
   Oracle-checkable evidence before writing a Finding: the specific
   account's own authenticated data returned to a session that should
   have been dead, or a reset token demonstrably reused or predicted —
   not this vertical's own interpretation of an ambiguous response.

## Exit condition

- [ ] The session-identifying cookie/header and every endpoint
      identified in step 1 has a recorded baseline (step 2).
- [ ] Every mechanism in step 3 applicable to what step 1 found has
      been probed (a Target with no password-reset endpoint recorded
      skips that bullet; every other bullet always applies once a
      session-identifying cookie/header exists).
- [ ] Every candidate diff recorded in step 4 is closed as exactly one
      of: **confirmed** (Oracle-backed, never this vertical's own
      self-report), **ruled out** (the specific, named reason the diff
      isn't a real signal — e.g. "replayed pre-logout session returned
      a fresh anonymous-session redirect, not the account's own data" —
      not just "looked clean"), or **open proof gap**, recorded as
      `needs_confirmation` with its `requirements`. A candidate dropped
      without landing in one of these three is this vertical stopping
      early, not exhausting itself.

## Rationalizations to reject

- "The cookie has the `Secure` flag, so session handling is fine." —
  A correct attribute on one axis says nothing about whether logout or
  a credential change actually invalidates the session server-side.
  MUST still test invalidation directly.
- "The reset link looks random." — One token is not a sample. MUST
  request at least two independently before concluding either way.
- "It redirected to the login page, so the old session is dead." — A
  redirect is what an expired *client-side* cookie produces too; MUST
  replay the old session identifier itself against an authenticated
  endpoint to confirm the server, not just the client, treats it as
  dead.
- "The user is logged out client-side, so the session is invalid." —
  Clearing a cookie client-side proves nothing about server-side
  state. MUST replay the actual old value to confirm.

## Known gaps

Nothing in the Rig can wait out, schedule, or otherwise simulate the
passage of time: an expiration-window claim (a session idle timeout, a
password-reset token's stated TTL) can only be tested by a probe issued
after that real-world interval has actually elapsed within the run, not
fabricated. Where a window is longer than this vertical's run can
practically wait out, record it as `needs_confirmation` rather than
guessing at a pass or fail.

## References

- MITRE CWE-384, Session Fixation: <https://cwe.mitre.org/data/definitions/384.html>
- MITRE CWE-613, Insufficient Session Expiration: <https://cwe.mitre.org/data/definitions/613.html>
- MITRE CWE-640, Weak Password Recovery Mechanism: <https://cwe.mitre.org/data/definitions/640.html>
- PortSwigger, Authentication vulnerabilities (testing technique):
  <https://portswigger.net/web-security/authentication>
