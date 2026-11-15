# Broken access control: primary-source findings, and an audit of `skills/access-control/SKILL.md`

Researched against primary sources only, fetched live on 2026-11-15. WSTG's own per-test-case
pages (`wstg.owasp.org/.../04-Testing_for_Insecure_Direct_Object_References`, etc.) 404'd on
every URL pattern tried (current site path and the GitHub raw source), so WSTG coverage below
is limited to the chapter index's own enumeration, not full methodology text from each subpage.
Bugcrowd's VRT JSON was reachable and quoted directly; its full BAC taxonomy section matched
without needing severity-ranking interpretation beyond what's noted.

## 1. Primary-source findings on the category

### OWASP WSTG — Authorization Testing chapter (`wstg.owasp.org/latest/`)

The chapter (numbered 4.5.x on the live site; no `WSTG-ATHZ-NN` codes appear on the current
index) enumerates:

- 4.5.1 Directory Traversal and File Include
- 4.5.2 Bypassing Authorization Schema
- 4.5.3 Privilege Escalation
- 4.5.4 Insecure Direct Object References
- 4.5.5 OAuth Weaknesses (4.5.5.1 Authorization Server, 4.5.5.2 Client)

The index gives titles only; full per-subchapter "How to Test" text could not be fetched this
session (every tried URL for the individual subchapters returned 404, both on the live site and
via the GitHub-hosted markdown source). This means WSTG's own methodology text (which may
describe unauthenticated-request testing, parameter removal, or privilege-escalation
horizontal/vertical distinctions in more depth) is not independently confirmed here — note this
as an open gap in this research, not as "WSTG doesn't cover it."

### OWASP API Security Top 10 (2023) — api-security.owasp.org

**API1:2023 Broken Object Level Authorization (BOLA).** "Object level authorization is an
access control mechanism that is usually implemented at the code level." Attackers exploit it
by "changing object IDs in the request," which "can be in the path, query string, headers, or
payload" — not only a path segment. The page states explicitly that comparing the session
user's ID against the ID parameter "isn't a sufficient solution" for BOLA, and separately: if an
attacker reaches an endpoint they shouldn't be allowed at all, "that is Broken Function Level
Authorization (BFLA), not BOLA" — the two are deliberately kept distinct by *what's being
checked* (object ownership vs. endpoint/role eligibility), not by mechanism. The page's own
mitigation list includes writing tests for the authorization mechanism and never deploying a
change that fails them; it does not separately describe testing with zero authentication, and
never mentions "IDOR" at all.

**API3:2023 Broken Object Property Level Authorization (BOPLA).** This category **folds two
former, now-retired OWASP API Top 10 categories into one**: "Excessive Data Exposure" (an
endpoint exposes properties "that are considered sensitive and should not be read by the user")
and "Mass Assignment" (an endpoint "allows a user to change, add/or delete the value of a
sensitive object's property"). It is a distinct axis from BOLA/object-level authorization: BOLA
is about which *object* a caller may touch; BOPLA is about which *properties of an object* a
caller may read or write once they're authorized to touch the object at all. Testing guidance:
fuzzing to discover hidden/undocumented properties, then "crafting an API request and analyzing
the response" to see whether a property can be changed; the worked example replays a legitimate
**PUT** request with an added field (`"blocked": false`) to show the server accepts and applies
a property-level write nothing checked for. The page gives no PATCH-specific example, but PUT
and PATCH share the same mass-assignment mechanism (replaying a write request with extra or
altered body fields).

**API5:2023 Broken Function Level Authorization (BFLA).** "Exploitation requires the attacker
to send legitimate API calls to an API endpoint that they should not have access to." Testing
guidance is explicit on three points directly relevant to a procedure: (1) check whether a
regular/low-privilege account can reach admin endpoints; (2) check whether a sensitive action
can be reached "by simply changing the HTTP method" (e.g. GET → DELETE); (3) check whether a
user in one group/role can reach another group's function "by simply guessing the endpoint URL
and parameters" — i.e., don't trust the URL path shape (`/api/users` can hide both regular and
admin functions side by side); authorization should be modeled against the actual role/group
hierarchy, not inferred from path naming.

### OWASP Top 10 (2021) — A01 Broken Access Control (`top10.owasp.org/2021/...`)

34 CWEs are mapped to A01:2021, the most relevant being CWE-22/23/35 (path traversal), CWE-284
(Improper Access Control), CWE-285 (Improper Authorization), CWE-352 (CSRF), CWE-425 (Forced
Browsing), CWE-566 and CWE-639 (authorization bypass through a user-controlled [SQL primary]
key), CWE-862 (Missing Authorization), CWE-863 (Incorrect Authorization), CWE-601 (Open
Redirect). The description's example list explicitly names: violation of least
privilege/deny-by-default; bypassing access checks by modifying the URL, internal state, HTML,
or API request; **insecure direct object references** allowing viewing/editing another user's
account via its identifier; missing access control on POST/PUT/DELETE; privilege escalation
(acting as unauthenticated, or as admin while logged in as a regular user); metadata
manipulation — "replaying or tampering with a JWT access token, or altering cookies or hidden
fields" to escalate privilege, or abusing JWT invalidation; CORS misconfiguration allowing
"API access from unauthorized/untrusted origins"; and forced browsing, both unauthenticated
users reaching authenticated pages *and* standard users reaching privileged pages.

### PortSwigger Web Security Academy — "Access control vulnerabilities"

The page's own sub-type enumeration (confirmed by direct fetch): **vertical privilege
escalation** (with four named sub-forms — unprotected functionality, parameter-based access
control, platform misconfiguration, URL-matching discrepancies), **horizontal privilege
escalation**, **horizontal-to-vertical escalation** (compromising a higher-privileged user's
account via a horizontal flaw), **insecure direct object references (IDOR)** (direct references
to both database objects and static files), **access control in multi-step processes** (a later
step skips a check an earlier step enforced), **referer-based access control**,
**location-based access control**, and **context-dependent access controls** (restrictions tied
to application state or action ordering). The page never uses the term "BOLA" at all — it is
purely a "IDOR" / "privilege escalation" framing, and its IDOR illustration is a bare parameter
substitution ("modifies the `id` parameter value to that of another user"), not a worked testing
methodology.

### MITRE CWE

- **CWE-639** (Authorization Bypass Through User-Controlled Key): "The system's authorization
  functionality does not prevent one user from gaining access to another user's data or record"
  by modifying the key value. Extended description: "It is likely that an attacker would have
  to be an authenticated user in the system." `ChildOf` CWE-863 (Incorrect Authorization);
  `ParentOf` CWE-566. Its Alternate Terms note says OWASP's "Insecure Direct Object Reference"
  term is **broader** than this CWE, because IDOR as OWASP uses it also covers path traversal
  (CWE-22) — i.e., the classic web-era "IDOR" label spans both the authorization-bypass case
  this CWE models and a file/path-traversal case this CWE does not.
- **CWE-862** (Missing Authorization): "does not perform an authorization check when an actor
  attempts to access a resource or perform an action." `ChildOf` CWE-285 (Improper
  Authorization) and CWE-284 (Improper Access Control, a Pillar). `ParentOf` CWE-425 (Direct
  Request/forced browsing), CWE-638, CWE-939, CWE-1314.
- **CWE-863** (Incorrect Authorization): "performs an authorization check... but it does not
  correctly perform the check" — i.e., a check exists and runs, but its logic is wrong. This is
  the structural distinction from CWE-862: *missing* (no check ran) vs. *incorrect* (a check ran
  but failed to enforce the right boundary). `ChildOf` CWE-285. `ParentOf` CWE-639 itself, plus
  CWE-551, CWE-647, CWE-804, CWE-942, CWE-1244.
- **CWE-284** (Improper Access Control, the pillar both 862 and 863 ultimately trace to via
  CWE-285): "does not restrict or incorrectly restricts access to a resource from an
  unauthorized actor." Direct children include CWE-269 (Improper Privilege Management), CWE-285
  (Improper Authorization), CWE-287 (Improper Authentication), CWE-346 (Origin Validation
  Error — the CORS-misconfiguration case A01:2021 names).

### Bugcrowd VRT (1.19, fetched as JSON)

Under "Broken Access Control (BAC)": **Insecure Direct Object References (IDOR)** is its own
subcategory with five priority-ranked variants — P1 Modify/View Sensitive Information (Iterable
Object Identifiers), P2 Modify Sensitive Information (Iterable), P3 View Sensitive Information
(Iterable), P4 Modify/View Sensitive Information (Complex/GUID-UUID), P5 View Non-Sensitive
Information. **Privilege Escalation** is listed as its own BAC subcategory but carries no own
priority value in the taxonomy (severity is assessed case-by-case). No VRT entry is explicitly
labeled "BFLA," "BOLA," or "horizontal/vertical" — Bugcrowd's taxonomy uses the older
IDOR/privilege-escalation vocabulary throughout, not the 2023 API-Security terms.

### Synthesis: is IDOR/BOLA a real distinction?

The primary sources converge on this picture: **IDOR is the older, broader, web-era term**
(used by WSTG, PortSwigger, Bugcrowd, and CWE-639's own alternate-terms note) that covers both
the authorization-bypass case and, in some usages, path-traversal-flavored object access.
**BOLA is OWASP API Security's 2023 term for the identical core mechanism** (swap an
object-identifying value, see if the authorization check holds), scoped specifically to API
object-level access and deliberately kept distinct from BFLA by *what's being checked*
(object ownership, not endpoint/role eligibility) — not by a different test mechanism. No
primary source treats IDOR and BOLA as describing two different vulnerabilities; they are the
same bypass under two different vocabularies from two different eras/documents.

## 2. Audit of `skills/access-control/SKILL.md`

Ranked most important first.

### Finding 1 — BOPLA (API3:2023) is entirely absent: no description mention, no keyword, no procedure step, no reference

**Location:** front matter `description` (lines 4–19), `keywords` (20–28), `Procedure` step 3
(61–80), `References` (146–157) — absent from all four.

**What's wrong:** API3:2023 Broken Object Property Level Authorization folds together what used
to be "Excessive Data Exposure" and "Mass Assignment" — a caller authorized to touch an object
at all can still read sensitive properties never meant to be returned, or write properties never
meant to be settable, via the same PUT/PATCH/POST body the baseline request uses. This is a
real, OWASP-enumerated sub-category of the "who may do what to which object/property" umbrella
this skill file claims to own ("object-level bypass... and function-level bypass," line 7),
and it is not claimed by any other vertical in this repo (`skills/injection`,
`skills/recon` — neither mentions mass assignment or property-level authorization). It is
currently nowhere: not in scope, and not explicitly routed elsewhere either.

**Why it matters:** per the skills-system spec, a vertical's `description` is the routing
contract an agent (or a human) uses to decide whether a surface finding belongs here. A
surface that enumerates a PATCH/PUT endpoint accepting a JSON body currently has nothing in this
file's "use when" trigger (line 12–15, object-id-shaped input or role-gated endpoint only) that
would make an agent try submitting extra/sensitive fields in that body, even though the
underlying mechanism (replay a legitimate write with a tampered body) is a small variant of the
IDOR/BOLA swap-and-diff mechanism this file already describes in full.

**Concrete fix:** add a fourth bullet to Procedure step 3 — object-property-level (BOPLA):
authenticated as the identity that owns the object, replay its own legitimate PUT/PATCH/POST
body with (a) one undisclosed/sensitive property added or changed to a value only a
higher-privileged identity or the server itself should set (e.g. a `role`, `is_admin`,
`balance`, or `price` field not present in the normal form/UI), and (b) the same request with a
property the baseline response includes but that identity shouldn't be able to read, removed
from the request to see whether the response still (over-)returns it. Diff against the same
identity's own baseline per step 4. Add "BOPLA" / "mass assignment" / "excessive data exposure"
to `keywords`, and add a one-line clause to `description` making clear whether this is in scope
(recommended: yes, since it's the same identity-swap/diff mechanism family and no other vertical
claims it) or an explicit "do not use for X, use `<vertical>`" pointer if the maintainer decides
it belongs elsewhere. Add the OWASP API3:2023 URL to `References`.

### Finding 2 — No Rig tool/method is named anywhere in the procedure; this looks like an oversight, not a deliberate omission

**Location:** entire `Procedure` section (37–97); compare `skills/injection/SKILL.md` step 1,
which names `curl.get`'s `path_segment` parameter, `curl.post_form`, and "either method's
`headers` parameter for header and cookie inputs," wiring each input shape to its actual Rig
dispatch method.

**What's wrong:** this file's mechanism — swap an object-id value in a path segment or query
parameter, and swap which identity (i.e. which `Authorization`/cookie header) sends the request
— is already exactly what `CurlBridge` supports today: `curl.get`'s `path_segment` and `query`
parameters are the id-swap mechanism, and `curl.get`/`curl.post_form`'s shared `headers`
parameter is the identity-swap mechanism (send the same request with the second identity's
captured session header instead of the baseline's). `curl.post_form`'s `data` parameter is
exactly the BFLA/BOPLA body-tampering mechanism too (Finding 1's fix). None of this requires a
new Rig capability — it's the same `curl` bridge `injection` already dispatches through, just
for a different purpose (identity substitution instead of payload substitution).

**Why it matters:** the task brief flagged this as worth auditing explicitly — is naming no Rig
tool a gap, or correctly out of scope for a vertical whose mechanism is identity-swapping rather
than payload-submission? Having read `curl.py` directly: it's a gap. Identity-swapping *is*
payload submission here — a different `Authorization` header value is just another flat string
in the same `headers: dict[str, str]` parameter `injection` already dispatches header-shaped
inputs through. There is no mechanism this vertical needs that the Rig doesn't already expose;
the file simply never says so, which leaves an agent re-deriving the same
shape-to-method mapping `injection`'s step 1 explicitly warns against re-deriving ("Each input
already carries which Rig method and parameter reaches it, so dispatch through that rather than
re-deriving a shape-to-method mapping").

**Concrete fix:** in step 1 or step 2, add: "Dispatch every probe through `curl.get` (object-id
in a path segment via `path_segment`, or a query parameter via `query`) or `curl.post_form`
(object-id or property values in `data`), carrying the probing identity's credential in
`headers` rather than the baseline identity's." This also makes `exhaust skill lint`'s tool-drift
check (`_tool_drift_findings`) actually apply to this file, which today has nothing for it to
check.

### Finding 3 — The unauthenticated-swap test case is excluded by the routing boundary, but the boundary as written may excise a legitimate access-control test, not just a different vulnerability class

**Location:** `description`, lines 16–19: "Do not use for a resource reachable with no
authentication at all — that's the `information disclosure` vertical."

**What's wrong:** A01:2021's own example list explicitly includes, as a single failure mode,
"force browsing... unauthenticated users reaching pages that require authentication, or...
standard users reaching privileged pages" — i.e. it treats *zero-auth access to a thing that
should require auth* as a Broken Access Control instance alongside the swapped-identity case,
not as a separate category. The file's current boundary reads as categorical: any resource
reachable with no authentication belongs to `information disclosure`, full stop. That's correct
for a resource that was *never* meant to require auth (e.g. a misconfigured public S3 bucket).
It's a different and narrower case when the object-id input under test is one this very
vertical's own step 2 already recorded a baseline for *as an authenticated request* — testing
the identical swapped-id request with the `Authorization`/cookie header stripped entirely is the
same CWE-862 "Missing Authorization" mechanism (no check ran at all) sitting right next to the
CWE-863 "Incorrect Authorization" mechanism (a check ran but picked the wrong boundary) step 3
already covers, and OWASP's BOLA page frames both as the same underlying question: "does the
authorization mechanism check specifically against this caller." As currently scoped, step 3's
object-level bullet only ever swaps to a second identity's owned id — it never tries the
no-identity-at-all variant against the same already-enumerated input.

**Why it matters:** this is the sub-case the task brief specifically asked about (point 3) and
it's a real gap: a Target that never checks for *any* session token on `GET /orders/{id}` and a
Target that checks for a session token but not for the right owner are both Broken Access
Control, exercised with the same baseline and nearly the same probe, and the current procedure
would only ever catch the second.

**Concrete fix:** either (a) narrow the `description`'s exclusion clause to resources that
were never gated behind auth at all (distinguishing "genuinely public" from "auth-gated
endpoint, tested with auth stripped"), and add a bullet to step 3's object-level case: "also
replay the same swapped-id request with no identity's credentials at all (no `Authorization`
header, no session cookie) to test whether the authorization check runs at all versus runs
incorrectly" — or (b) if the maintainer wants to keep that case in `information disclosure`
instead, say so explicitly and name the handoff ("an already-enumerated auth-gated input that
also responds with no credentials at all is an `information disclosure` candidate; record it
there, not here") so the boundary is a deliberate routing decision visible in the file, not an
implicit side effect of the current wording.

### Finding 4 — IDOR/BOLA conflation matches the literature; no fix needed, but note for future reference-splitting

Lines 7 and 34 treat "IDOR" and "BOLA" as naming the same mechanism. This is consistent with
every primary source checked: none describes IDOR and BOLA as different vulnerabilities, only
as the same bypass named by two different documents/eras (§1 Synthesis above). No change
needed. One nuance worth flagging if the file ever grows a `references/` split (the
skills-system spec's own illustrative layout names `references/idor.md`, `references/bola.md`,
`references/bfla.md` as an example, though this file currently has no `references/` directory at
all): CWE-639's alternate-terms note says OWASP's own "IDOR" label is *broader* than the
authorization-bypass mechanism, because it has historically also covered path-traversal-style
object access (CWE-22) — which this file's own routing boundary already correctly excludes via
`skills/injection`'s territory and the "no auth at all" carve-out. No action needed now; worth
knowing if a future split tries to write a standalone `idor.md` that re-expands scope back into
path traversal.

### Finding 5 — BFLA sub-case already matches API5:2023 guidance closely; no fix needed

Step 3's BFLA bullet (lines 69–74, "MUST try every HTTP method and every equivalent route the
surface records for that action... not only the one path the normal-privilege baseline used")
directly mirrors API5:2023's three testing points (admin-as-regular-user, HTTP-method
substitution, alternate-route guessing) and its explicit warning not to trust URL-path shape.
No gap found here.

### Finding 6 — "Known gaps" claim checked against `scope_contract.py` and `workspace.py`: accurate

**Location:** lines 136–144.

Read both files directly. `src/exhaust/scope_contract.py`'s `ScopeContract` dataclass carries
exactly three fields — `target`, `basis`, `extent` — with no concept of multiple identities, nor
any credential material at all; `is_in_scope` gates only on target name and extent tier.
`src/exhaust/workspace.py`'s `scaffold_workspace` creates `AGENTS.md`, `BRIEF.md`,
`sandbox/docker-compose.yml`, and empty `poc/`, `findings/`, `surface/` directories — `BRIEF.md`'s
own template has an "Auth model" section for prose description of how the Target authenticates,
but nothing structured, and no identity-provisioning mechanism at all. The file's claim —
"Nothing in the Workspace or Scope Contract today provisions or declares a second Target
identity" — holds up exactly as written. No fix needed.

### Finding 7 — minor wording: step 3's parameter-manipulation mechanism is narrower than WSTG/PortSwigger's "modify, remove, or substitute" framing

**Location:** step 3, object-level bullet (62–68): "replace the object-id input's value with an
id that same identity does not own."

**What's wrong:** this only covers value substitution. A01:2021's description bullet and
PortSwigger's general access-control framing both describe tampering more broadly as modifying
"the URL, internal state of the application, or the HTML page" — which includes removing a
parameter outright (does the endpoint then default to "no object," "all objects," or crash in a
way that leaks data?) and, for an array-shaped id parameter, submitting multiple values or a
wildcard. This is a smaller gap than Findings 1–3 — the value-substitution case is the dominant
real-world IDOR mechanism and the one every fetched source leads with — but it's worth a
one-clause addition given the file already goes to the trouble of a "MUST try every HTTP method"
bullet for BFLA's equivalent broadening.

**Concrete fix (optional, lower priority):** append to the object-level bullet: "and, where the
surface records it as removable without the request failing outright (an optional query
parameter, a field absent from some but not all client variants), MUST also try the request with
that input omitted entirely."
