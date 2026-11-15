# Session management and authentication-flow vulnerabilities: primary-source findings, and an audit of `skills/auth-session/SKILL.md`

Researched against primary sources only, fetched live on 2026-11-15. ASVS 5.0.0 chapter markdown
files could not be located by filename on GitHub (the `5.0/docs_en/en/` tree render came back
empty in this session), so ASVS citations below are drawn from the official 5.0.0 CSV
(`OWASP_Application_Security_Verification_Standard_5.0.0_en.csv`, tag `v5.0.0`), read directly —
the content is the same normative text, just without chapter-markdown prose around it. The
Bugcrowd VRT was read from the repository's `vulnerability-rating-taxonomy.json` (GitHub raw,
`master` branch) rather than a PDF edition. OWASP WSTG's authentication/session subchapter text
was not independently fetched this session (out of scope of what the brief named); PortSwigger
and ASVS cover the same ground in more procedural detail regardless.

## 1. Primary-source findings on the category

### OWASP ASVS 5.0.0 — Chapter V7, Session Management

The chapter is organized V7.1 (documentation) through V7.6 (federated re-authentication).
Requirements most relevant to a testing procedure:

- **V7.2.4**: "the application generates a new session token on user authentication, **including
  re-authentication**," and the old token is terminated. The scope is explicitly broader than
  "login" alone — a step-up/re-authentication event (e.g. confirming a sensitive action) must
  also rotate the session token, not only the initial login.
- **V7.4.1**: on session termination (logout or expiration) the old session/token must no longer
  work — stateful sessions invalidated server-side, self-contained tokens needing "a revocation
  list or per-user key rotation" mechanism.
- **V7.4.2**: "the application terminates all active sessions when a user account is disabled or
  deleted" — a distinct invalidation trigger from logout or credential change.
- **V7.4.3**: "the application gives the option to terminate all other active sessions after a
  successful change or removal" of an authentication factor — the "log out all devices" feature
  named explicitly as a testable control, not just an invalidation side effect.
- **V7.4.5**: "application administrators are able to terminate active sessions for an individual
  user or for all users" — an admin-initiated invalidation path.
- **V7.1.2** and **V7.5.2**: concurrent-session handling is its own documented control — how many
  parallel sessions one account may hold, what happens past the limit, and that a user can "view
  and ... terminate any or all" of their own active sessions.
- **V7.5.1**: "the application requires full re-authentication before allowing modifications to
  sensitive account attributes" (credentials, recovery contacts) — ties session-management
  testing to the credential-change case the skill file already probes.

### OWASP ASVS 5.0.0 — Chapter V6, Authentication (credential recovery / password reset)

- **V6.4.3**: "a secure process for resetting a forgotten password is implemented," and it "must
  not bypass any enabled multi-factor authentication" the account has configured — a password
  reset that silently drops an account's MFA requirement is itself a finding this chapter names.
- **V6.4.1**: system-generated initial passwords/activation codes must be "securely randomly
  generated," follow the password policy, and "expire quickly or after first use" — directly
  supports testing a reset token for both predictability and single-use enforcement.
- **V6.4.6**: an admin-initiated password reset "does not allow" the admin to choose or learn the
  user's new password — a reset-flow variant (admin-triggered) outside the self-service case.
- **V6.5.5**: out-of-band authentication codes/tokens "at most 10 minutes" lifetime (TOTP: 30
  seconds) — a concrete figure against which an open-ended reset-token TTL claim can be checked.
- **V6.3.7**: "users are notified after updates to authentication details, such as credential
  resets" — a verifiable side channel (does a notification fire) independent of replaying the
  token itself.

### OWASP Top 10 (2021), A07:2021 Identification and Authentication Failures

Description opens: "Confirmation of the user's identity, authentication, and session management
is critical." Its own example failure modes, as enumerated on the page, explicitly include:
permitting automated attacks (credential stuffing, brute force); permitting default, weak, or
well-known passwords; weak or ineffective credential-recovery processes, "such as knowledge-based
answers" (secret questions); plaintext, encrypted, or weakly hashed password storage; missing or
ineffective multi-factor authentication; **session identifiers exposed in the URL**; session
identifiers **not rotated after successful login**; and session identifiers/session tokens **not
properly invalidated during logout or a period of inactivity**. The category maps to 22 CWEs,
including CWE-255, 259, 287, 288, 290, 294, 295, 297, 300, 302, 304, 306, 307, 346, **384**,
521, **613**, 620, **640**, 798, 940, 1216.

### MITRE CWE

- **CWE-384 (Session Fixation).** Description: "Authenticating a user, or otherwise establishing
  a new user session, without invalidating any existing session identifier gives an attacker the
  opportunity to steal authenticated sessions." Three named scenarios: (1) authenticating without
  invalidating the pre-existing session; (2) an attacker forcing a known identifier onto a victim
  before they authenticate; (3) predictable session identifiers. `ChildOf` CWE-610 (Externally
  Controlled Reference to a Resource in Another Sphere) and CWE-1462 (Improper Session
  Management); `CanFollow` CWE-340 (Generation of Predictable Numbers or Identifiers). Its own
  demonstrative example explicitly notes XSS or HTTP response splitting as alternate vectors for
  forcing a chosen session value onto a victim, alongside the "capture it at a public terminal"
  case — i.e. the generic test (set a value, see if it survives authentication) is exactly what
  the CWE describes; it does not prescribe a more elaborate mechanism.
- **CWE-613 (Insufficient Session Expiration) is deprecated.** MITRE's page states: "This entry
  has been deprecated because it was insufficiently clear. Consider CWE-1462 and its
  descendants," naming **CWE-1463 (Insufficient Session Timeout Value)** and **CWE-1464 (Improper
  Session Invalidation)** as the current, split replacements.
- **CWE-640 (Weak Password Recovery Mechanism).** Named failure patterns: guessable/discoverable
  security questions; a reset flaw that sends the new credential to an attacker-reachable address
  instead of the real owner's; no throttling, letting an attacker "repeatedly trigger resets" (DoS
  on the legitimate user, via account lockout from the eBay demonstrative example); sending the
  *original* password rather than a generated temporary one. `ChildOf` CWE-1390 (Weak
  Authentication) and CWE-287 (Improper Authentication, View-1003). One cited observed example,
  CVE-2024-5277, is specifically a reset token **not invalidated after use**, reused to change a
  victim's password — directly the skill's reuse-after-redemption sub-case.
- **CWE-294 (Authentication Bypass by Capture-replay).** "A capture-replay flaw exists when the
  design of the product makes it possible for a malicious user to sniff network traffic and
  bypass authentication by replaying it to the server ... (or with minor changes)." `ChildOf`
  CWE-1390 and CWE-287.
- **CWE-287 (Improper Authentication).** "When an actor claims to have a given identity, the
  product does not prove or insufficiently proves that the claim is correct." `ChildOf` CWE-284
  (Improper Access Control, pillar). `ParentOf`: CWE-294, CWE-295, CWE-306, CWE-307, CWE-521,
  CWE-522, CWE-640, CWE-798, CWE-290, CWE-645, CWE-1390 — i.e. CWE-287 is the parent that both the
  fixation/replay family and the weak-recovery family trace up to.
- **CWE-306 (Missing Authentication for Critical Functionality).** "The product does not perform
  any authentication for functionality that requires a provable user identity."

### RFC 6265 (cookie attributes) and the RFC 6265bis draft (SameSite)

- **Secure (§4.1.2.5, §5.4, §8.3).** Secure "limits the scope of the cookie to 'secure' channels,"
  sent only when "the request-uri's scheme ... denote[s] a 'secure' protocol," and it "protects
  only the cookie's confidentiality," not integrity (an active attacker "can overwrite Secure
  cookies from an insecure channel" regardless). Critically, §8.3's own webmail example shows the
  protection is **not conditional on the server also listening for plain HTTP**: an attacker can
  redirect or induce a victim's browser to make a plain-`http://` request to the same host even
  when "the server is not listening for HTTP connections at all," and *without* `Secure` the
  browser still attaches the cookie to that forced cleartext request, exposing it to a
  network-level attacker; *with* `Secure`, the cookie is withheld from that same request. The RFC
  frames this as "the protection provided by the secure channel will be largely moot" without the
  flag — the risk model is "can a plaintext request to this host ever be induced" (always true for
  any TLS-capable host unless HSTS or similar blocks it outright), not "does the Target itself
  serve a working plain-HTTP site."
- **HttpOnly (§4.1.2.6).** "Limits the scope of the cookie to HTTP requests," specifically
  excluding non-HTTP APIs (e.g. a script-facing `document.cookie`-style accessor) — independent of
  Secure: "a cookie can have both the HttpOnly and the Secure attribute."
- **SameSite is absent from RFC 6265 entirely** — it was never part of that document. It is
  defined only in the still-in-progress RFC 6265bis draft (`draft-ietf-httpbis-rfc6265bis`),
  which defines `Strict`/`Lax`/`None` and — material to any claim pairing the two attributes —
  requires that a cookie asserting `SameSite=None` is rejected outright unless it also carries
  `Secure` ("abort this algorithm and ignore the cookie entirely unless the cookie's
  secure-only-flag is true").

### PortSwigger Web Security Academy

- **"Authentication" category index** has no standalone "session hijacking" page. Its own
  sub-topic enumeration is: brute-force attacks (including account-locking and rate-limiting
  flaws), HTTP Basic auth, **multi-factor authentication vulnerabilities** (a dedicated
  sub-category, not folded into the generic authentication-bypass case), **"Keeping users logged
  in"** (its own term for remember-me/persistent-login), password reset (by email and by URL),
  changing passwords, and OAuth. It frames the category as caused by one of two things: weak
  mechanisms unable to resist brute force, or logic flaws letting an attacker bypass
  authentication outright.
- **Multi-factor authentication page** names, as distinct bypass mechanisms: skipping the second
  factor's server-side check entirely; **flawed verification logic** — logging in with the
  attacker's own credentials, then substituting the victim's identifier (e.g. an `account`
  cookie) before submitting the second-factor code, so the code check runs against the wrong
  account binding; brute-forcing short numeric verification codes absent rate limiting (and
  bypassing logout-after-N-failures protections by automating the whole multi-step flow); SMS
  interception/SIM-swapping; and "same-factor" 2FA (an emailed code verifying only the knowledge
  factor twice).
- **"Keeping users logged in" (remember-me) page.** Predictable persistent-login cookies built
  from "a predictable concatenation of static values," sometimes including the password itself;
  Base64 "offers no protection whatsoever"; unsalted/identifiable hashes are brute-forceable, and
  if cookie-guess attempts aren't rate-limited the same way login attempts are, this bypasses
  login brute-force protection entirely.
- **"Password reset poisoning"** (`portswigger.net/web-security/host-header/exploiting/
  password-reset-poisoning`, filed under the Host-header-attacks section, not under
  Authentication). Defined exactly as: an attacker "manipulates a vulnerable website into
  generating a password reset link pointing to a domain under their control," by controlling the
  host the reset-link-building code reads — named mechanisms are the **Host header** itself and,
  where the literal host can't be swapped outright, **dangling-markup injection via the Host
  header** (an arbitrary non-numeric port value breaking out of an HTML attribute context in the
  email template). A third, separate lab (outside this page, filed under Authentication → "other
  mechanisms" / middleware) poisons the reset link via an **`X-Forwarded-Host`**-style
  forwarding header read by middleware sitting in front of the app, rather than the raw `Host`
  header the backend itself sees — i.e. PortSwigger's own "password reset poisoning" technique
  family is **host-controlling-header poisoning in general**, not literally restricted to the one
  header named `Host`. No parameter-based (non-header) reset-link-poisoning mechanism is
  described on either page.

### Bugcrowd Vulnerability Rating Taxonomy (`vulnerability-rating-taxonomy.json`, `master`)

Under `broken_authentication_and_session_management`:

- **"Failure to Invalidate Session"** carries eight named variants, each independently rated:
  *Concurrent Sessions On Logout* (P5), *Long Timeout* (P5), *On Email Change* (P5), *On Logout
  (Client and Server-Side)* (P4), *On Logout (Server-Side Only)* (P5), *On Password Reset and/or
  Change* (P4), *On 2FA Activation/Change* (P5), *On Permission Change* (unrated). This is a
  taxonomy built from real disclosed reports, and it treats logout, password reset/change, email
  change, 2FA activation/change, and permission change as **five separately-tracked
  invalidation triggers**, not one generic "credential change" bucket.
- **"Session Fixation"** has two variants: *Remote Attack Vector* (P3) and *Local Attack Vector*
  (P5) — the lower-severity "local" variant covers fixation that requires physical/local access
  to set the value (e.g. a shared terminal), distinct from remote/network-settable fixation.
- Other named entries: *Authentication Bypass* (P1), *Cleartext Transmission of Session Token*
  (P4), *Concurrent Logins* (P5, as its own entry separate from the "Concurrent Sessions On
  Logout" invalidation variant), *SAML Replay* (P5), *Second Factor Authentication (2FA) Bypass*
  (P3), *Weak Login Function* (various, HTTP/plaintext-protocol variants), *Weak Registration
  Implementation* (Over HTTP, P4), *Excessive JSON Web Token (JWT) Lifetime* (P5), and *Secret
  Questions Used for Account Verification* (P5). No entry names "remember-me" or
  "persistent-login token" explicitly as its own taxonomy line.

## 2. Audit of `skills/auth-session/SKILL.md`

Ranked most important first.

### Finding 1 — The cookie-attribute sub-case states a conditional claim that RFC 6265 itself contradicts

**Location:** Procedure step 3, "Cookie attribute weaknesses" bullet (lines 85–90): "a missing
`Secure` flag matters only when the Target is also reachable over plain HTTP."

**What's wrong:** This is false against RFC 6265's own stated threat model. §8.3's webmail
example describes exactly the case this clause rules out — a server that "is not listening for
HTTP connections" at all — and shows the `Secure` flag's protection still matters there: an
attacker who can get the victim's browser to *attempt* a plain-`http://` request to the Target's
hostname (a trivial link, a redirect, or a network-level MITM downgrade) will still have that
request carry a non-`Secure` cookie, exposing it in cleartext over the wire regardless of whether
the Target's own server stack answers on port 80. The RFC's framing is explicit: without
`Secure`, "the protection provided by the secure channel will be largely moot." Whether the
Target happens to also run a working plain-HTTP listener is irrelevant to whether this attack is
reachable — what matters is whether *anything* (a DNS/MITM position, a crafted plain-`http://`
link, a forced downgrade) can make the victim's user agent attempt a plaintext request to that
host at all, which is true of essentially any TLS-capable host that isn't additionally protected
by HSTS preloading. PortSwigger's own cookie-security guidance makes the same point generically:
the question is whether the cookie can *ever* be sent in the clear, not whether the server
happens to also accept plaintext traffic today.

**Why it matters:** this is the single highest-value correction in the file — it's a condition an
agent would use to actively suppress a real finding ("Target only serves HTTPS, so I won't flag
the missing `Secure` flag") when the spec it cites would call that finding valid regardless.

**Concrete fix:** replace the clause with: "a missing `Secure` flag is a finding regardless of
whether the Target's own stack currently serves plain HTTP — RFC 6265 §8.3's own threat model is
an attacker inducing a plaintext request to the Target's hostname (a crafted `http://` link, a
network-level downgrade), not the Target's server choosing to listen on port 80. Record it as a
finding whenever the cookie is sent over an HTTPS session without `Secure` set; note in the
Finding whether HSTS (if recorded on the surface) narrows the practical exposure, but do not use
HSTS or an HTTP-less deployment to suppress the finding outright."

### Finding 2 — The password-reset exclusion clause names only "Host header," but PortSwigger's own poisoning technique family also covers forwarded-host headers the backend never sees directly

**Location:** front matter `description` (lines 22–25) and Procedure step 3's reset-token bullet
closing clause (lines 100–103): both say "poisoned via the Host header" / "manipulated via the
request's Host header."

**What's wrong:** PortSwigger's canonical "Password reset poisoning" page frames the technique as
poisoning whatever host-determining input the reset-link-building code reads — its two named
mechanisms are the literal `Host` header and dangling-markup injection carried through the `Host`
header — but a third documented lab (filed under Authentication → "other mechanisms" / middleware)
achieves the identical link-poisoning outcome through an `X-Forwarded-Host`-style header read by
a reverse proxy or middleware layer sitting in front of the application, which never touches the
raw `Host` header the backend receives at all. The file's current wording ("via the Host header")
is narrower than the exclusion it's trying to draw: an agent testing a reset endpoint behind a
proxy that honors `X-Forwarded-Host` could read the current wording as "not the Host header, so
not excluded, so in scope here" and attempt to test it under this vertical, when it's the same
reserved territory.

**Why it matters:** this is exactly the boundary-accuracy question the brief asked about (point
5). The underlying technique is real and does hinge on a host-determining input, not a parameter
or token value this vertical owns — so the routing decision itself (exclude it, point to Host
header attacks) is correct. Only the wording is too narrow.

**Concrete fix:** broaden both the `description` clause and the step-3 clause from "via the Host
header" to "via the Host header or a forwarded-host header (e.g. `X-Forwarded-Host`) that
influences the link's domain" — or, more simply, "via any host-determining request header" — so
the exclusion tracks the actual technique family PortSwigger documents rather than one literal
header name.

### Finding 3 — Missing-invalidation testing covers only logout and the account's own credential change; ASVS and Bugcrowd both name several more invalidation triggers this file is silent on

**Location:** Procedure step 3's two "Missing invalidation" bullets (lines 74–84); `description`
(lines 8–10) names only "logout or credential change."

**What's wrong:** ASVS V7.4.2 (account disable/delete must terminate all sessions), V7.4.3 (an
explicit "terminate all other sessions" control after an auth-factor change — the "log out all
devices" feature named in the brief), and V7.4.5 (admin-initiated termination of a user's or all
users' sessions) are three invalidation triggers distinct from the two this file tests. Bugcrowd's
VRT tracks these as independently-rated findings: `On Email Change`, `On 2FA Activation/Change`,
and `On Permission Change` sit alongside `On Logout` and `On Password Reset and/or Change` as five
separate lines, not variants of one "credential change" bucket. The file's own
"MUST NOT treat one as covering the other" discipline (line 84) is correct as far as it goes, but
it only applies that discipline across two triggers when the primary sources name at least five.
Password reset specifically invalidating *other* sessions (not just the reset flow's own session)
is also unaddressed: V6.4.3 and the reset-flow's interaction with V7.4.1 together imply a
successful password reset should terminate every other session on that account, which is a
distinct, testable claim from "the stale session used to request the reset is now dead."

**Why it matters:** this is the task brief's point 3, and it's the largest procedural gap in the
file — a Target that invalidates on logout and on self-service password change, but not on
account lockout/disable, an explicit "sign out everywhere" button, or email-address change, would
pass every check step 3 currently runs and still have a real, CWE-1464-class finding.

**Concrete fix:** add, after the existing credential-change bullet: "**Missing invalidation on
other triggers**: where the surface records any of the following, replay the baseline session the
same way after each one fires: (a) an explicit 'log out of all devices'/'terminate other sessions'
control; (b) an account-disable, account-lockout, or account-deletion action; (c) a password reset
completing successfully (check both the reset-requester's *other* pre-existing sessions and the
token-redeeming request's own session); (d) an email-address or MFA-factor change. A session-
management system invalidating correctly on logout and on direct credential change can still fail
any of these; MUST NOT generalize a pass on one trigger to any other." Add "account lockout,"
"log out all devices," and "concurrent session termination" to `keywords`.

### Finding 4 — Multi-factor-authentication bypass is a named, non-trivial sub-category the file never mentions

**Location:** entire file — `description`, `keywords`, and Procedure (no MFA bullet anywhere).

**What's wrong:** PortSwigger dedicates a standalone sub-topic to multi-factor bypass, with at
least three mechanically distinct, procedurally testable techniques: (1) the server never
actually re-checks second-factor completion before serving a protected page (skip-the-step); (2)
**flawed verification logic** — authenticate with the attacker's own first factor, then swap the
account-identifying value (a cookie, a hidden field) carried into the second-factor-submission
request to point at the victim, so the second factor is checked against the wrong binding; (3)
unthrottled brute-forcing of a short numeric code. (3) is explicitly out of scope here (the file
already routes brute-forcing to the reserved `rate-limiting / brute-force` vertical, correctly).
But (1) and (2) are not brute-force at all — they're session/identity-binding logic flaws of
exactly the kind this vertical's "What this vertical investigates" paragraph already claims
("whether a session, once established, stays scoped to the identity and the moment that created
it"), and CWE-287/CWE-294 both sit in this file's own reference family. A Target with an MFA step
is current real-world default-adjacent (ASVS treats it as baseline, not exotic), and this file has
no mechanism for it at all.

**Why it matters:** this is the task brief's point 1, flagged as a likely gap, and it's confirmed
— an agent working this vertical against an MFA-protected login flow currently has no procedure
step that would catch (1) or (2) even though both are squarely "does the session/identity binding
hold," not brute-force and not OAuth/JWT structure.

**Concrete fix:** add a sub-case to step 3: "**Multi-factor verification-binding weaknesses**:
where the surface records a second authentication factor, (a) after completing only the first
factor, replay a request to an endpoint that should require the completed second factor, to check
whether the server enforces completion server-side rather than trusting a client-side flag; (b)
authenticate as the testing identity through the first factor, then, before submitting the second
factor, substitute whatever request value (cookie, hidden field, parameter) identifies which
account the second-factor check will run against with a different identity's value, and submit
the testing identity's own correct second-factor code, to check whether the server verifies the
code against the request's claimed identity rather than the identity that actually completed the
first factor." Add "multi-factor authentication bypass," "2FA bypass," and "verification binding"
to `keywords`; add the PortSwigger MFA URL to `References`.

### Finding 5 — Remember-me/persistent-login token weakness is a named PortSwigger sub-topic absent from the file, and it's mechanically closer to the password-reset-token bullet than anything else here

**Location:** entire file.

**What's wrong:** PortSwigger's "Keeping users logged in" page describes persistent-login
("remember me") cookies built from predictable concatenations (sometimes including the password
itself), Base64 mistaken for encryption, and unsalted/identifiable hashes vulnerable to offline
brute-forcing once the cookie's construction is known. This is structurally the same
predictability-testing mechanism the file's password-reset-token bullet already runs (request
multiple samples, compare structure, MUST NOT conclude from one sample) — just applied to a
different artifact (a long-lived persistent cookie instead of a short-lived reset token) that
this vertical's own front matter already claims ownership of ("a session ... once established,"
"weak session-cookie attributes").

**Why it matters:** task brief point 1's explicit example. Without this sub-case, a Target with a
predictable "remember me" cookie has no vertical that would catch it: it's not session fixation,
not missing invalidation, not a cookie *attribute*, and not a password-reset token.

**Concrete fix:** add a sub-case to step 3: "**Persistent-login ('remember me') token
weaknesses**: where the surface records a persistent-login cookie distinct from the primary
session identifier, request at least two (for the same account, via repeated login-with-
remember-me) and compare their structure the same way as the password-reset-token bullet —
MUST NOT conclude predictable or unpredictable from one sample. Where the value is reversible
(Base64 or otherwise trivially decodable), decode and check whether it encodes a static,
guessable concatenation (e.g. username, a fixed salt, a hashed password) rather than a per-issuance
random value." Add "remember me," "persistent login token," to `keywords`; add the PortSwigger
"Keeping users logged in" URL to `References`.

### Finding 6 — Two CWE references are stale against MITRE's own current taxonomy

**Location:** `References` (lines 166–168).

**What's wrong:** CWE-613 (Insufficient Session Expiration), cited at line 167, **is deprecated**
— MITRE's own page states it "has been deprecated because it was insufficiently clear" and
directs readers to CWE-1462 (Improper Session Management) and its two current descendants,
CWE-1463 (Insufficient Session Timeout Value) and CWE-1464 (Improper Session Invalidation). The
file's own missing-invalidation procedure (step 3) maps far more precisely onto CWE-1464 than
onto the deprecated, vaguer CWE-613.

**Why it matters:** a maintainer or future agent following this reference out will land on a page
that explicitly says "don't use this one anymore" — a small but real citation-quality defect, and
an easy one to fix given the replacement is unambiguous.

**Concrete fix:** replace the CWE-613 line with two lines: "MITRE CWE-1463, Insufficient Session
Timeout Value" and "MITRE CWE-1464, Improper Session Invalidation" (both children of CWE-1462),
pointed at from the "Missing invalidation" bullets; optionally also cite CWE-1462 itself as the
umbrella. Leave CWE-384 and CWE-640 as-is — both are current, unflagged entries.

### Finding 7 — `curl.py` claims in the front matter are accurate; no fix needed

**Location:** `description` (lines 13–16): "reading the session identifier and its attributes off
the leading status-line and header block their output carries, and setting a chosen session value
via `headers`."

Read `src/exhaust/rig/wrappers/curl.py` directly. `_invoke` passes `-i` to curl (line 226 of that
file, with the comment explaining it "[p]repends the status line and response headers to the body
in `output`"), so every `ToolResult.output` from `get`/`post_form` genuinely does lead with the
status line and header block, exactly as claimed. `get` and `post_form` both accept a `headers`
mapping (`dict[str, str]`) forwarded verbatim as `-H "<name>: <value>"` argv tokens with no
special-casing of `Cookie` — so "setting a chosen session value via `headers`" is also literally
true: a caller passes `{"Cookie": "sessionid=<chosen value>"}` and it reaches curl unmodified.
Both claims hold up exactly as written; no correction needed.

### Finding 8 — Session-fixation bullet is accurate to CWE-384 but doesn't test the re-authentication case ASVS calls out

**Location:** Procedure step 3, "Session fixation" bullet (lines 67–73).

**What's wrong:** the bullet's mechanism (set a chosen value pre-auth via `headers`, authenticate
while carrying it, check whether the pre-chosen value now grants access) matches CWE-384's own
generic attack description exactly — no more rigorous mechanism is described in any primary
source checked, confirming the task brief's point 2 with no gap on the *initial-login* case. But
ASVS V7.2.4 requires a fresh token "on user authentication, **including re-authentication**" —
i.e. a Target that correctly rotates on first login can still fail to rotate on a step-up/
re-authentication event (the same re-authentication this file's own "Cookie attribute
weaknesses"-adjacent rationalizations and the credential-change bullet already assume exists as a
concept). The current bullet only exercises the initial-login path.

**Why it matters:** smaller gap than Findings 1–5, but concrete and ASVS-backed: a fixation flaw
that survives re-authentication (not initial login) would currently go untested.

**Concrete fix (lower priority):** append to the bullet: "Where the surface records a
re-authentication step (a step-up confirmation, a sensitive-action re-auth), repeat the same
fixation check across it: set a chosen value, trigger re-authentication while carrying it, and
confirm whether a *new* value is issued rather than the pre-chosen one persisting."

### Finding 9 — Session-fixation local-vs-remote distinction (Bugcrowd) is a severity nuance, not a procedural gap; no fix needed

Bugcrowd's VRT splits "Session Fixation" into *Remote Attack Vector* (P3) and *Local Attack
Vector* (P5, lower severity) — i.e. whether the attacker needs physical/local access to plant the
chosen value (a shared terminal) versus being able to set it remotely (the `headers`-based
mechanism this file already uses, which is inherently the remote case). This is a severity/
reporting-time distinction for whoever writes the eventual Finding, not something the testing
procedure itself needs to branch on — the file's one mechanism already produces the
higher-severity remote-vector evidence. No fix needed; worth knowing if a future `references/`
split on fixation wants to say which vector was exercised.
