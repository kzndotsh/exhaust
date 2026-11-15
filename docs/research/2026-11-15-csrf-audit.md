# Cross-site request forgery: primary-source findings, and an audit of `skills/csrf/SKILL.md`

Researched against primary sources only, fetched live on 2026-11-15. The OWASP Cheat Sheet
Series URL the task brief and the skill file's own `References` both already use resolved
cleanly (no hyphen/slug trap this time, unlike the SSRF and auth-session audits' cheat-sheet
URLs). Bugcrowd's VRT JSON was reachable (`master` branch, GitHub raw). RFC 6265bis was read
from its IETF IDs datatracker rendering (`draft-ietf-httpbis-rfc6265bis`, the current
in-progress draft — there is still no final RFC number for SameSite, consistent with what the
auth-session audit already found). Chromium's own `chromium.org/updates/same-site/` page (dated
2019-11-01, Chromium's own operational announcement, not a secondary write-up) was fetched
directly to pin the one concrete figure (the Lax+POST grace window) neither the draft RFC nor
web.dev's own explainer state as a number.

## 1. Primary-source findings on the category

### PortSwigger Web Security Academy — "Cross-site request forgery (CSRF)" and its sub-pages

The top-level page's own enumeration (confirmed by direct fetch), each with a dedicated
sub-page:

- **Bypassing SameSite restrictions** (`csrf/bypassing-samesite-restrictions`):
  - **Lax bypass via GET, through a top-level navigation**: "As long as the request involves a
    top-level navigation, the browser will still include the victim's session cookie." This is
    the mechanism behind the file's existing state-changing-GET bullet, but the page's own
    framing is specifically about a **top-level navigation** — not an arbitrary background
    request.
  - **Method overriding**: "some frameworks provide ways of overriding the method specified in
    the request line," naming Symfony's `_method` form parameter specifically ("takes
    precedence over the normal method for routing purposes") and noting "other frameworks
    support a variety of similar parameters." This is a **request-body parameter**, not a header
    like `X-HTTP-Method-Override` — the task brief's own framing of this technique as a header is
    not what PortSwigger's page actually documents; the mechanism it names is a framework-level
    form-field convention.
  - **On-site gadgets (bypassing Strict)**: a client-side redirect hosted on the Target's own
    site is itself "a same-site request and, as such, will include all cookies related to the
    site," letting an attacker bounce the victim through the Target's own gadget into the real
    cross-site-looking request while it still reads as same-site to the browser; "this can enable
    you to bypass any SameSite cookie restrictions completely." A server-side redirect does not
    have this property ("the equivalent attack is not possible with server-side redirects").
  - **Vulnerable sibling domains**: "a request can still be same-site even if it's issued
    cross-origin" — an XSS or CSWSH-vulnerable sibling subdomain shares the same registrable
    domain and so shares SameSite-cookie eligibility with the Target.

- **Bypassing Referer-based defenses** (`csrf/bypassing-referer-based-defenses`):
  - **Validation skipped when the header is absent**: "skip the validation if the header is
    omitted," bypassed by suppressing the header entirely via `<meta name="referrer"
    content="never">` on the attacker's hosting page.
  - **Weak-match bypasses, two distinct shapes**: a **prefix check** bypassed by an
    attacker-controlled subdomain of the attacker's own domain shaped so the Target's domain
    appears as a leading substring (`vulnerable-website.com.attacker-website.com`), versus a
    **substring/contains check** bypassed by placing the Target's domain anywhere later in the
    URL, including the query string (`attacker-website.com/csrf-attack?vulnerable-website.com`).
    These are two different weak-check shapes, not one.
  - **Query-string stripping in real browsers**: "many browsers now strip the query string from
    the `Referer` header by default" — a Burp-replayed proof-of-concept carrying a full Referer
    may not reproduce in a real browser unless the exploit page itself sets
    `Referrer-Policy: unsafe-url`.

- **Bypassing token validation** (`csrf/bypassing-token-validation`), five named flaws:
  1. **Validation depends on request method**: "skip the validation when the GET method is
     used" — a token check wired to run only for non-GET methods, bypassable by switching the
     *same* endpoint to GET even when its primary, documented interface is POST.
  2. **Validation depends on the token being present**: "correctly validate the token when it is
     present but skip the validation if the token is omitted."
  3. **Token not tied to the user session**: "do not validate that the token belongs to the same
     session as the user who is making the request" — any valid-shaped token from any session is
     accepted.
  4. **Token tied to a non-session cookie**: "tie the CSRF token to a cookie, but not to the same
     cookie that is used to track sessions," commonly from two uncoordinated frameworks (one for
     sessions, one for CSRF).
  5. **Token duplicated in a cookie ("double submit")**: the server checks only that the request
     parameter matches the cookie value, with no session-bound server-side state at all — an
     attacker can set *both* values themselves (an invented token as the parameter, the same
     value as the cookie, via any mechanism that can plant a cookie, e.g. a vulnerable sibling
     application).
  - **Not covered on this page**: no mention of `X-HTTP-Method-Override`, JSON-based CSRF as its
    own named technique, or multi-step/wizard-flow CSRF.

- **State-changing GET**: covered only in the top-level page's delivery-mechanism section —
  "some simple CSRF exploits employ the GET method," framed as the exploit's own delivery
  simplicity (a self-contained URL), not as a dedicated bypass sub-page.

- **Multi-step/wizard-flow CSRF and JSON-specific CSRF**: checked directly — **neither is named
  as its own technique anywhere on PortSwigger's CSRF page or its three linked sub-pages.** The
  task brief's premise that PortSwigger documents these as enumerated techniques does not hold
  up against the fetched pages; they may exist as informal testing knowledge but are not
  citable to this primary source.

### MITRE CWE

- **CWE-352 (Cross-Site Request Forgery)**. Description: "The web application does not, or
  cannot, sufficiently verify whether a request was intentionally provided by the user who sent
  the request, which could have originated from an unauthorized actor." `ChildOf` CWE-345
  (Insufficient Verification of Data Authenticity); `PeerOf` CWE-79 (XSS) — the mitigation notes
  say XSS can bypass most CSRF defenses and CSRF can itself deliver an XSS payload (citing the
  Samy worm); `CanFollow` **CWE-1275 (Sensitive Cookie with Improper SameSite Attribute)**; and
  its own "Composite Components (requires)" list names **CWE-346 (Origin Validation Error)**,
  CWE-441 (Unintended Proxy or Intermediary), **CWE-613 (deprecated: Insufficient Session
  Expiration)**, and CWE-642 (External Control of Critical State Data). Its one demonstrative
  example is a PHP profile-update endpoint that checks for a valid session but never verifies
  the request's own intentionality, paired with an auto-submitting hidden-form attack page.
- **CWE-1275 (Sensitive Cookie with Improper SameSite Attribute)**. Description: "The SameSite
  attribute for sensitive cookies is not set, or an insecure value is used." `ChildOf` CWE-923
  (Improper Restriction of Communication Channel to Intended Endpoints); `CanPrecede` CWE-352
  directly — i.e. MITRE's own graph states the SameSite-attribute weakness as a named precursor
  to CSRF, not a generic cookie-hygiene nit.
- **CWE-346 (Origin Validation Error)**, named in CWE-352's own composite-components list as one
  of the mechanisms CSRF "requires" the absence of — directly the Origin/Referer-checking
  mechanism the skill file's own bullet already tests.

### OWASP Top 10:2021

CSRF (CWE-352) is not a standalone Top 10 category in the 2021 edition; it is folded into
**A01:2021 Broken Access Control**'s own mapped-CWE list, confirmed by direct fetch of
`top10.owasp.org/2021/A01_2021-Broken_Access_Control/index.html`: "CWE-352 Cross-Site Request
Forgery (CSRF)" appears both in the category's prose overview and its 34-entry mapped-CWE list
— and **CWE-1275 (Sensitive Cookie with Improper SameSite Attribute) is mapped to the same
category**, alongside it. This is independent, current (2021) confirmation that the
SameSite-attribute weakness and CSRF itself are treated as the same family of finding by OWASP's
own current taxonomy, not merely by the older MITRE graph.

### OWASP Cheat Sheet Series — Cross-Site Request Forgery Prevention Cheat Sheet

The most procedurally detailed primary source fetched, read in full:

- **Synchronizer token pattern**: "CSRF tokens should be generated on the server-side" and
  stored per-session ("the value is stored in the session"); validation compares the submitted
  token against that session-bound stored value. This is inherently **stateful**: the server
  must hold something per session to compare against.
- **Naive double-submit cookie — explicitly discouraged**: "Cookie validation is INSECURE" on
  its own; the sheet's stated attack is that "an attacker-controlled subdomain (e.g., via DNS
  takeover) could inject a matching cookie" and then also supply the matching parameter value
  itself — the server holds **no server-side state at all**, so the only thing it checks is
  "does the submitted value equal the cookie value," which an attacker who can plant any cookie
  on the victim (not just read one) can satisfy unilaterally, with no legitimate token ever
  involved.
- **Signed double-submit cookie — the sheet's recommended pattern**: the token is
  session-bound via HMAC ("should never leave the server or be in plain text"), validated by
  recomputing the HMAC and using "a constant-time comparison function." The sheet is explicit
  that "simply signing tokens without session binding provides minimal protection" — i.e. the
  binding is what matters, not merely the presence of a signature.
- **No per-strategy test procedure is given**: the sheet is a prevention guide, not a testing
  guide, and defers testing methodology to "the OWASP WSTG for CSRF testing" rather than
  describing one itself.
- **SameSite framing — defense-in-depth, not a primary defense**: "SameSite is useful as a
  defense-in-depth control but it does not replace a proper CSRF defense in most deployments,"
  and, directly on point: **"If any state-changing operation in the application is reachable via
  a GET request, SameSite=Lax will not stop it."** The sheet's own remediation advice for a
  SameSite-reliant deployment is to "review every GET endpoint and ensure that none of them
  mutate server-side state" — i.e. the cheat sheet treats the skill file's own "state-changing
  GET" sub-case as the single biggest hole SameSite=Lax itself leaves open, not a redundant or
  obsolete check.
- **Content-Type / `text/plain` bypass — real and explicitly named**: "may accept `text/plain`
  which would be vulnerable to CSRF" is stated directly about JSON APIs, with the sheet's fix
  being to "disallow these simple content types" server-side. This confirms the task brief's
  point 4 cleanly: the technique is real and directly documented by this primary source, not an
  invented or overstated case.
- **Custom header defense**: described as "particularly well suited for AJAX or API endpoints,"
  relying on the CORS preflight mechanism — and warned that a loose CORS configuration
  ("CORS from all subdomains of your site using a regular expression") is itself "a less secure
  configuration" if a subdomain can be taken over, tying back to the same sibling-domain risk
  PortSwigger's SameSite-bypass page names.
- **GET and state changes**: "Do not use GET requests for state changing operations," with the
  fallback instruction that if GET is used anyway, "protect those resources against CSRF" the
  same as any other method.

### RFC 6265bis (`draft-ietf-httpbis-rfc6265bis`) — SameSite semantics

SameSite is **not defined in the final RFC 6265** (confirmed independently already by the
auth-session audit); it exists only in this still-in-progress draft.

- **§4.1.2.7 (attribute definitions)**: `Strict` — "the cookie will only be sent along with
  'same-site' requests." `Lax` — "the cookie will be sent with same-site requests, and with
  'cross-site' top-level navigations" (the Lax↔top-level-navigation pairing is stated directly
  in the attribute's own defining section, not merely implied elsewhere). `None` — "the cookie
  will be sent with same-site and cross-site requests."
- **§5.6.7.1 (enforcement algorithm)**: the top-level-navigation carve-out for Lax is stated as
  conditioned on the request being "top-level navigations which use a 'safe'" method — i.e. the
  exception is scoped to safe (GET-class) methods specifically, matching the skill file's own
  framing that a bare GET is the relevant case, not an arbitrary method.
- **Default SameSite value**: §5.7 step 17 — a cookie with no valid SameSite attribute at all
  has its "same-site-flag" set to `"Default"`; §4.1.2.7 states an unrecognized/default value
  gets "a default enforcement mode that is equivalent to 'Lax'." Read together, this is the
  draft's own normative basis for "no SameSite attribute ⇒ treated as Lax" — the behavior every
  modern browser now ships as a matter of course.
- **"Lax-allowing-unsafe" compatibility mode (§8.8.6)**: an explicitly **temporary, transitional**
  relaxation — "a temporary, transitional measure to ease adoption of 'Lax' enforcement by
  default" — that allows "recently created cookies to be sent cross-site with unsafe top-level
  requests," while still retaining "some of the protections of 'Lax' enforcement (as compared to
  'None')." The draft itself does not state the exact age cutoff.

### Chromium's own operational documentation (`chromium.org/updates/same-site/`, dated 2019-11-01)

This is the primary source that actually pins the number RFC 6265bis leaves undefined:

- **"Lax + POST" grace window, exact figure**: "allows these cookies to be sent on top-level
  cross-site POST requests if they are at most **2 minutes old**." This is Chromium's own stated
  mitigation specifically for legacy POST-based redirect flows (e.g. some SSO/payment handoffs)
  that would otherwise break the moment Lax became the default.
- **Scope of the exception**: covers only **top-level cross-site POST** requests for cookies
  carrying no explicit `SameSite` attribute; Chromium's own text contrasts this with the ordinary
  Lax rule, which blocks "any other cross-site requests with a non-idempotent HTTP method such
  as `PUT`" outright, with no grace window at all.
- **Phase-out, stated plainly**: Chromium calls the 2-minute window "a temporary intervention"
  that "will be removed at some point in the future," after which the affected cookies "need
  `SameSite=None` and `Secure` even when they are under 2 minutes old."
- **Cross-site subresource requests (`<img>`/`<script>`) are not named as carrying Lax cookies
  anywhere in any source fetched this session.** RFC 6265bis's own Lax definition (§4.1.2.7)
  names only same-site requests and cross-site **top-level navigations** as the two cases a Lax
  cookie is sent on; nothing in the draft, in web.dev's explainer, or in Chromium's own page
  states that a cross-site subresource request (an `<img>` or `<script>` load, which is not a
  top-level navigation) carries a Lax cookie under any circumstance, grace window included — the
  2-minute exception is scoped to POST specifically, which an `<img>`/`<script>` tag cannot issue
  in the first place.

### Bugcrowd Vulnerability Rating Taxonomy (`master`, fetched as JSON)

Under `Cross-Site Request Forgery (CSRF)`: **Action-Specific → Authenticated Action**
(unrated), **Action-Specific → Logout** (P5), **Action-Specific → Unauthenticated Action**
(unrated), **Application-Wide** (P2), **CSRF Token Not Unique Per Request** (P5), and
**Flash-Based** (P5). A separate, unrelated entry, **"CSRF/URL-Based"** (P3), sits under the
*Cross-Site Scripting → Stored* category rather than under CSRF itself (a reflected/stored-XSS
variant whose payload happens to be CSRF-shaped, not a CSRF taxonomy line). The taxonomy does
**not** split state-changing-GET, JSON-CSRF, or classic form-based CSRF into distinct lines —
its own axis is request-authentication-state (authenticated/unauthenticated/logout) and token
freshness (**"CSRF Token Not Unique Per Request"**, its own named, independently-rated line —
a token that validates correctly but is reused across multiple requests rather than minted fresh
each time, a distinct flaw from "not bound to the session" the task brief's point 3 doesn't
separately name but a real sub-case Bugcrowd tracks on its own).

## 2. Audit of `skills/csrf/SKILL.md`

Ranked most important first.

### Finding 1 — The state-changing-GET bullet's "cheapest-to-forge... a plain `<img>`-shaped request" framing is backwards against modern SameSite=Lax-by-default behavior

**Location:** Procedure step 3, "State-changing GET" bullet (lines 85–91): "this is the
cheapest-to-forge case (a plain `<img>`-shaped request)."

**What's wrong:** Every primary source checked agrees that a Lax cookie (including the modern
default for a cookie that sets no `SameSite` attribute at all, per RFC 6265bis §4.1.2.7/§5.7 and
Chromium's own shipped behavior) is carried on a cross-site **top-level navigation**, and
nothing fetched this session — not the draft RFC, not web.dev's explainer, not Chromium's own
page — states that a Lax cookie is carried on a cross-site **subresource** request such as an
`<img>` or `<script>` load. PortSwigger's own SameSite-bypass page frames the exact same
mechanism the same way: "As long as the request involves a **top-level navigation**, the browser
will still include the victim's session cookie." An `<img>` tag is specifically *not* a top-level
navigation — it is the canonical example of the subresource-request case Lax is designed to
block. Describing the bare-GET case as "a plain `<img>`-shaped request" names the one delivery
mechanism that modern SameSite=Lax defaults actually stop, for the one sub-case (GET) that is
otherwise the single biggest real gap SameSite=Lax leaves open per the OWASP Cheat Sheet's own
wording ("If any state-changing operation... is reachable via a GET request, SameSite=Lax will
not stop it"). The real delivery mechanism that survives Lax is a top-level navigation: a
plain `<a href>` link, a `window.location` redirect, or a GET-method `<form>` submission that
replaces the whole page — mechanically cheap to construct, but a materially different (and
slightly less silent/invisible) primitive than a background `<img>` tag a victim never has to
act on at all.

**Why it matters:** this is the task brief's point 2, and it's a real accuracy problem rather
than a stale-but-harmless detail: an agent reading this file verbatim could reasonably conclude
the state-changing-GET finding's severity or delivery feasibility is the same as a silent
background image load, when the actual delivery requires getting the victim to follow a link or
land on a page that redirects them there — still realistic and still worth testing (hence
"MUST check," correctly kept), but not the invisible, zero-interaction primitive the current
wording implies, and the implied mechanism is specifically the one case modern Lax defaults do
block.

**Concrete fix:** replace the parenthetical with something like: "this is the cheapest-to-forge
case once delivered via a top-level navigation (a plain link, a `window.location` redirect, or a
GET-method form submission that replaces the page) — not a background request such as an `<img>`
tag, which a cookie defaulting to `SameSite=Lax` (the behavior of any cookie that sets no
explicit `SameSite` attribute in a modern browser) will not carry cross-site at all. A Target
relying on SameSite=Lax to cover this case is still exposed: the Cheat Sheet's own guidance is
that Lax does not stop a state-changing GET reachable via a top-level navigation." Add the RFC
6265bis citation is unnecessary per house style (a named RFC doesn't need a URL entry), but
consider adding one sentence pointing at `auth-session`'s own recorded `SameSite` value, since
this vertical already reads that value per its own exclusion clause.

### Finding 2 — "Token not bound to the session" tests only the synchronizer-token-pattern flaw; the double-submit-cookie flaw needs a differently-shaped test this file never states

**Location:** Procedure step 3, "Token not bound to the session" bullet (lines 70–75): "obtain a
token from a second, independent session or an unauthenticated page load, and submit it
alongside the first session's own cookie."

**What's wrong:** per the OWASP Cheat Sheet, these are two mechanically distinct real-world
patterns with two distinct server-side failure shapes:

- **Synchronizer token pattern** (stateful: "the value is stored in the session"). The file's
  current test — obtain a token minted for a *different* session, submit it with the victim's
  own cookie — is exactly the right shape for this pattern: it's testing whether the server
  checks "does this exact session own this exact token" or merely "does a valid-shaped token
  exist somewhere." PortSwigger's own page 3 of this family ("token not tied to the user
  session") names precisely this test.
- **Double-submit cookie** (stateless: no server-side state at all — "Cookie validation is
  INSECURE" per the sheet's own framing, and "the server checks only that the request parameter
  matches the cookie"). The file's current test doesn't cover this shape at all: there is no
  legitimate "second session's token" to obtain, because there is no session-bound secret on the
  server side to begin with — the actual flaw-detecting test is whether the server accepts an
  **attacker-invented value used as both the cookie and the submitted parameter/header**, with
  no legitimate token ever read from anywhere. This is also the exact mechanism behind
  PortSwigger's own fifth named flaw ("token simply duplicated in a cookie") and the one the
  Cheat Sheet calls out as the reason a naive double-submit scheme is "INSECURE" — an attacker
  who can plant any cookie on the victim (a sibling-domain cookie-fixation vector, which this
  same file's Known-gaps-adjacent territory already touches via `auth-session`'s session-fixation
  bullet) can satisfy the whole check unilaterally.

**Why it matters:** this is the task brief's point 3 exactly. The current bullet is not wrong —
it correctly tests the synchronizer-token case — but it silently assumes that's the only
token-binding architecture in play. A Target using a double-submit (or signed double-submit)
pattern would pass the file's current test trivially (there's no "other session's token" to even
obtain in a meaningful sense) while still being vulnerable to the cookie-and-parameter-both-
attacker-chosen variant the current bullet never attempts.

**Concrete fix:** split the bullet into two sub-tests: "**Synchronizer-token flaw**: obtain a
token from a second, independent session or an unauthenticated page load, and submit it
alongside the first session's own cookie — tests whether the server validates the token against
the specific session that owns it, the shape a server-side-stateful token-store implies.
**Double-submit-cookie flaw**: independent of any legitimate token, submit an attacker-invented
value as both the request's token parameter/header and (via `headers`, the same `Cookie`-setting
mechanism `auth-session` already uses for fixation) the cookie value itself, with the victim's
real session cookie otherwise left intact if the implementation uses a cookie distinct from the
session cookie for this purpose — tests whether the server does anything beyond comparing the
submitted value against whatever cookie value arrived with the request, the shape a stateless
double-submit scheme implies. MUST NOT treat a pass on one shape as covering the other: a
Target's token-binding architecture determines which test is the meaningful one, and this
vertical cannot assume which architecture is in play without trying both." Add "double submit
cookie" and "synchronizer token" to `keywords`.

### Finding 3 — No sub-case for method confusion: switching a token-protected endpoint's own method to GET, or using a framework's method-override parameter, both documented PortSwigger bypasses this file never tests

**Location:** entire file — no bullet in step 3 addresses either mechanism; the existing
"Missing or invalid token" bullet (lines 66–69) and "State-changing GET" bullet (lines 85–91)
are both endpoint-shape-preserving (they vary the token or read an endpoint already known to be
GET-reachable) rather than method-switching.

**What's wrong:** PortSwigger names two distinct method-related bypasses this file has no
procedure step for:

1. **Validation depends on request method** — a server that validates the CSRF token for POST
   but "skip[s] the validation when the GET method is used," on the *same* endpoint whose
   primary, documented interface is POST. This is different from the file's existing
   state-changing-GET bullet, which only fires "where a state-changing action is reachable via
   `curl.get` rather than `curl.post_form`" as already recorded by recon — i.e. it tests an
   endpoint already known to accept GET, not whether a POST-shaped endpoint's token check can be
   sidestepped by resubmitting the identical mutation as a GET that recon never recorded as
   working.
2. **Method overriding via a framework convention** (Symfony's `_method` form field named
   specifically, with "other frameworks support[ing] a variety of similar parameters") — a
   request that is delivered as a plain GET or POST at the HTTP layer (and so satisfies
   SameSite=Lax's top-level-navigation carve-out, or a Content-Type-based CORS-preflight
   avoidance) but is routed and processed by the Target's own framework as if it were a
   different method (PUT/DELETE) entirely, potentially skipping whatever method-scoped CSRF
   check only runs for the literal HTTP verb.

**Why it matters:** this is the task brief's point 1's own named example, confirmed as a real,
primary-source-documented gap. Both mechanisms are cheap to dispatch with the Rig tools already
in play: method 1 is just another `curl.get` call against the endpoint's own URL with the
baseline's real token/body carried over; method 2 is a `curl.post_form`/`curl.get` call adding a
`_method`-shaped field to `data`/`query` with no new Rig capability needed.

**Concrete fix:** add a sub-case to step 3: "**Method confusion**: resubmit the identical
baseline mutation to the same endpoint URL via `curl.get` even when the endpoint's own recorded,
primary interface is `curl.post_form` (and vice versa) — a server that validates the token only
for its documented method can skip that check entirely for the other one. Separately, where the
Target's own stack is known to use a method-override convention (a `_method`-shaped form field,
or an equivalent the Target's own framework documents), resubmit the baseline mutation as a
plain GET or simple-Content-Type POST carrying that field set to the real method, to check
whether the token/Origin check that gated the real method also gates the overridden one." Add
"method override" and "method confusion" to `keywords`; add the PortSwigger
`bypassing-samesite-restrictions` URL (already implicitly covered by the existing PortSwigger
`csrf` URL in `References`, which links to it) — no new `References` entry strictly required
since it's the same canonical PortSwigger CSRF page tree.

### Finding 4 — The "Content-Type-based bypass" bullet assumes a raw-body dispatch `curl.post_form` cannot actually perform

**Location:** Procedure step 3, "Content-Type-based bypass" bullet (lines 92–100): "where the
endpoint's own baseline request used a non-simple `Content-Type` (e.g. `application/json`)...
resubmit the identical body with the `Content-Type` header changed to a simple type."

**What's wrong:** read `curl.py` directly. The Rig's only two state-mutating dispatch methods
are `get` (query string / path segment, no body) and `post_form` (a flat `dict[str, str]` sent
field-by-field via repeated `--data-urlencode key=value` tokens — i.e. it can only ever produce
an `application/x-www-form-urlencoded` body shape) — plus `post_multipart`, irrelevant here. **No
method on this bridge can submit a raw JSON body at all.** If the endpoint's own true baseline is
a JSON-encoded body (`{"amount":100}`-shaped, not flat key=value pairs), there is no Rig call in
this vertical's own toolkit that reproduces "the identical body" in the first place — the vertical
can change the `Content-Type` header via `headers` (confirmed real and unproblematic: `headers`
forwards verbatim as `-H` tokens with no special-casing, and curl's own automatic
`Content-Type: application/x-www-form-urlencoded` header is only added when the caller hasn't
already set one, so an explicit override genuinely takes effect), but it cannot independently
send the *body* the real endpoint expects unless that JSON object happens to be flat enough that
its fields coincide with form fields the server's lenient parser would also accept read as
`key=value` pairs — which is a real, narrower case than "the identical body" implies, not a
general one.

**Why it matters:** this is the task brief's point 4's second half (is the bullet's own
dispatch claim accurate, not merely whether the underlying technique is real). The technique
itself is real and squarely documented by the OWASP Cheat Sheet ("may accept `text/plain` which
would be vulnerable to CSRF"); the gap is that the file's wording ("resubmit the identical body")
overstates what `curl.post_form` can actually reproduce for a true JSON-bodied baseline, and the
file gives no guidance for the narrower, real case (a flat, form-shaped JSON object) versus the
general one it implies.

**Concrete fix:** reword to: "where the endpoint's own baseline request used a non-simple
`Content-Type` (e.g. `application/json`) and the body is a flat set of key/value pairs `curl.
post_form`'s `data` can reproduce field-by-field, resubmit those same fields with the
`Content-Type` header changed to a simple type (`text/plain` or
`application/x-www-form-urlencoded`) via `headers`. Where the real body is not flat (nested
JSON, an array), this vertical's own dispatch tools cannot reproduce it faithfully at all — MUST
record it as `needs_confirmation` with the requirement 'baseline body is not flat-key/value
shaped; confirming this bypass needs a raw-body POST capability this Rig doesn't currently
pin,' not silently skip or assume the bypass works." Add a line to `Known gaps` (currently
absent from this file) naming the same constraint: "`curl.post_form` can only submit a flat,
form-urlencoded body; a Target whose real endpoint requires a raw JSON (or other non-flat)
request body cannot have its exact shape reproduced by this vertical's own dispatch, narrowing
the Content-Type-bypass sub-case to flat-bodied JSON endpoints only."

### Finding 5 — The Origin/Referer weak-match bullet names only the subdomain-prefix bypass; PortSwigger documents a second, distinct substring/query-string shape it omits

**Location:** Procedure step 3, "Origin/Referer not enforced" bullet (lines 76–84): "Where the
surface shows the server does check but matches loosely (a substring/prefix check against the
Target's own domain), MUST try a value a weak check could still satisfy (e.g.
`https://target.example.attacker.com`)."

**What's wrong:** the file's own parenthetical already says "substring/prefix," but its one
example (`target.example.attacker.com`) only demonstrates the **prefix** case (the Target's
domain name appears as a subdomain label at the start of the attacker's own domain). PortSwigger
names the **substring/contains** case as mechanically distinct: a check that merely looks for
the Target's domain *anywhere* in the Referer string is bypassed by placing it in the query
string instead (`attacker-website.com/csrf-attack?vulnerable-website.com`) — no subdomain
registration needed at all, a cheaper and differently-shaped probe than the prefix case.

**Why it matters:** smaller than Findings 1–4, but a concrete, primary-source-backed gap: an
agent following the current wording's one example might try only the prefix shape and conclude
the weak-check tier is exhausted, when a substring-only check (which the prefix-shaped value
would also happen to satisfy, masking that it's actually the weaker of the two checks) is a
separate, independently-testable case.

**Concrete fix:** reword the parenthetical and example to: "a substring/prefix check against the
Target's own domain, two distinct shapes: a **prefix check**, satisfied by a subdomain naming
the Target first (`https://target.example.attacker.com`), and a **substring/contains check**,
satisfied by placing the Target's domain anywhere in the URL including the query string
(`https://attacker.example/csrf-attack?target.example`) — MUST try both, since a value
satisfying the prefix shape can pass a substring check too without proving which (if either) the
Target actually implements." Add to `Known gaps` or a closing note: "a Referer-based
proof-of-concept replayed through this vertical's own direct request manipulation does not
reproduce a real browser's query-string-stripping behavior on the `Referer` header; this
vertical confirms the missing/weak server-side check directly rather than via an actual browser
delivery, consistent with this file's existing `Known gaps` framing for the rest of the CSRF
surface."

### Finding 6 — `References` cites only CWE-352; two directly-related CWEs the primary sources name are missing, and CWE-613 should not be added despite appearing in CWE-352's own relationship list

**Location:** `References` (lines 169–173): cites only MITRE CWE-352.

**What's wrong:** CWE-352's own fetched relationship data names **CWE-1275 (Sensitive Cookie
with Improper SameSite Attribute)** as a direct `CanFollow` precursor, and OWASP Top 10:2021 maps
both CWE-352 and CWE-1275 to the same category (A01:2021), independent confirmation this is a
real, current pairing and not just an older MITRE-graph artifact. CWE-352 also lists **CWE-346
(Origin Validation Error)** among its own "Composite Components (requires)" — the exact
mechanism the file's own Origin/Referer bullet already tests. Neither is currently cited. CWE-352
*also* lists **CWE-613 (deprecated: Insufficient Session Expiration)** in that same
composite-components list — this is the identical stale CWE the auth-session audit already
flagged as deprecated by MITRE in favor of CWE-1462/1463/1464; it should not be added here either
despite appearing in CWE-352's own page, for the same reason.

**Why it matters:** smaller than Findings 1–5 — CWE-352 alone is unambiguous and sufficient on
its own — but a citation-completeness gap in exactly the direction this project's own house
style already favors (the SSRF and access-control files both cite a CWE's immediate parents/
peers once confirmed, not just the single most specific entry).

**Concrete fix (optional):** add "MITRE CWE-1275, Sensitive Cookie with Improper SameSite
Attribute" and "MITRE CWE-346, Origin Validation Error" to `References`, pointed at the
SameSite-exclusion clause in `description` and the Origin/Referer bullet respectively. Do not add
CWE-613.

### Finding 7 — `curl.py` and routing-boundary claims the file makes are otherwise accurate; no fix needed beyond Finding 4's narrower carve-out

**Location:** front matter `description` (lines 10–11): "Dispatches through
`curl.get`/`curl.post_form`, varying only the token/header shape of an otherwise-legitimate
request."

Read `curl.py` directly, as Finding 4 above already did in detail. Every other claim this file
makes about the bridge holds: `headers` on both `get` and `post_form` is a real,
validated `dict[str, str]` forwarded verbatim as `-H "<name>: <value>"` tokens with no
special-casing of `Origin`, `Referer`, or `Content-Type` — so setting any of the three to an
arbitrary attacker-chosen value, or omitting the default ones entirely (the bridge adds its own
browser-shaped `User-Agent`/`Accept`/`Accept-Language` defaults but nothing for `Origin` or
`Referer`, so simply not passing them in `headers` already reproduces "the shape a plain HTML
form submission produces, with no script able to set them," exactly as the "Origin/Referer not
enforced" bullet's omission case assumes), reaches curl unmodified. `_invoke` passes `-i`, so
every dispatch's output genuinely leads with the status line and header block this vertical's
own baseline-recording and diffing steps depend on. The routing boundary against `auth-session`
(SameSite/cookie-attribute testing excluded, reading its recorded value instead) and against
`access-control` (a second identity's own valid credentials excluded) both match those two files'
own stated scope exactly, confirmed by reading both directly. No fix needed beyond Finding 4's
own narrower wording for the one claim ("resubmit the identical body") that doesn't hold in
general.
