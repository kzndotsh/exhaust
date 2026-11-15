# Server-side request forgery: primary-source findings, and an audit of `skills/ssrf/SKILL.md`

Researched against primary sources only, fetched live on 2026-11-15. WSTG's own per-test-case
pages 404'd again this session, consistent with prior research in this repo (the access-control
and auth-session audits hit the same wall) — only the chapter index's own title/numbering is
confirmed, not full per-subchapter methodology text. The OWASP Cheat Sheet Series URL named in the
task brief 404'd on first try (`Server-Side_Request_Forgery...`); the index page gave the real,
hyphen-free slug (`Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html`), which was reachable
and quoted directly below. Bugcrowd's VRT JSON was reachable (`master` branch, GitHub raw).

## 1. Primary-source findings on the category

### PortSwigger Web Security Academy — "Server-side request forgery (SSRF)" and its sub-pages

The page's own enumeration (confirmed by direct fetch): **common SSRF attacks** (against the
server itself; against other back-end systems — reaching internal, weakly-secured admin
interfaces by address alone, worked example `stockApi=http://192.168.0.68/admin`); **circumventing
common SSRF defenses** (blacklist-based input filters; whitelist-based input filters; bypassing
filters via open redirection); a dedicated **blind SSRF** sub-page; and **finding hidden attack
surface** (partial URLs in requests; URLs within data formats; **SSRF via the Referer header**).
A separate **URL validation bypass cheat sheet** is linked but, when fetched directly, renders
navigation and a one-line intro only ("This cheat sheet contains payloads for bypassing URL
validation") with no payload table reachable through this session's fetch — its content could not
be independently confirmed.

- **Blacklist bypass**: "Use an alternative IP representation of `127.0.0.1`, such as
  `2130706433`, `017700000001`, or `127.1`." Also: "Try using different redirect codes, as well as
  different protocols for the target URL," and registering an attacker-controlled domain that
  resolves to `127.0.0.1`.
- **Whitelist bypass**: embedding credentials before the hostname via `@` (`https://expected-host@attacker-host`-shaped), using `#` to mark a fragment, and DNS-name tricks that put the
  required substring into a domain the attacker controls.
- **Open-redirect bypass**: "you can construct a URL that satisfies the filter and results in a
  redirected request to the desired back-end target" — this is the exact mechanism the skill
  file's own open-redirect bullet already implements.
- **DNS rebinding and IPv6 address forms are absent from this specific page** — not described
  anywhere in its fetched content.
- **Blind SSRF** (dedicated sub-page): defined as a case where "the response from the back-end
  request is not returned in the application's front-end response." Its own methodology for
  detection: "the most reliable way to detect blind SSRF vulnerabilities" is out-of-band (OAST)
  technique — generate a unique Collaborator domain, place it in the triggering input, and monitor
  for an incoming HTTP request; the page is explicit that "if an incoming HTTP request is observed
  coming from the application, then it is vulnerable to SSRF," and separately warns that a
  DNS-only hit with no follow-up HTTP request "usually means outbound DNS is allowed while
  outbound HTTP is blocked by network filtering" — i.e. DNS-only and HTTP-confirmed are two
  distinct, separately meaningful signals, not interchangeable confirmation. No non-OOB
  (timing-only, side-channel) blind-confirmation methodology is described anywhere on this page.
- **Referer-header SSRF**: named as its own attack-surface item, distinct from body/query
  parameters: "the Referer header is often a useful attack surface for SSRF vulnerabilities,"
  because "analytics software... visits any third-party URLs that appear in the Referer header."
- **URLs within data formats**: the page explicitly routes this to XXE — a parser that accepts a
  URL-bearing structured format (XML named specifically) "may be vulnerable to XXE injection, and
  possibly to SSRF via XXE," which it says is covered elsewhere (its XXE material), not on this
  page.
- **Backend connection reuse / request smuggling**: checked directly — **not connected to SSRF
  anywhere on this page.** "Request smuggling" appears only as an unrelated nav-menu topic; no
  text ties SSRF to connection reuse, keep-alive, or smuggling. The task brief's premise that
  PortSwigger documents this angle is not borne out by the fetched page.

### OWASP Top 10:2021, A10:2021 Server-Side Request Forgery (`top10.owasp.org/2021/...`)

(Reached only after two redirect hops: `owasp.org/Top10/...` → `top10.owasp.org/A10_...` →
`top10.owasp.org/2021/A10_.../index.html`.) Description: "SSRF flaws occur whenever a web
application is fetching a remote resource without validating the user-supplied URL," with rising
incidence/severity tied to cloud services and complex architectures. Four named example scenarios:
**#1 port scanning** (inferring open/closed internal ports from connection results or timing);
**#2 sensitive data exposure** (local files, internal services); **#3 cloud metadata** ("Access
metadata storage of cloud services"); **#4 internal service compromise** (further attacks up to
RCE or DoS). How to Prevent, application layer: "enforce the URL schema, port, and destination
with a positive allow list," don't return raw responses to the client, "disable HTTP redirects,"
and explicitly guard against **"DNS rebinding and TOCTOU race conditions."** It states outright:
**"Do not mitigate SSRF via the use of a deny list or regular expression."** Maps to a single CWE:
CWE-918.

### MITRE CWE

- **CWE-918 (SSRF)**: "The web server receives a URL or similar request from an upstream
  component and retrieves the contents of this URL, but it does not sufficiently ensure that the
  request is being sent to the expected destination." `ChildOf` CWE-441 (Unintended Proxy or
  Intermediary) and CWE-610 (Externally Controlled Reference to a Resource in Another Sphere);
  `MemberOf` CWE-417 (Communication Channel Errors). The page's own notes mark **CWE-611 (XXE)**
  as "closely related" — "both involve web technologies and outbound requests," distinguished by
  XXE's ability to also occur client-side — matching PortSwigger's own XXE-routing statement above
  almost exactly. **CWE-184 (Incomplete Denylist)** is cited directly in CWE-918's own mitigation
  notes as the reason denylists are commonly bypassable, the same point A10:2021 makes as a flat
  prohibition. One demonstrative example (PHP, 2025): bad code calls `file_get_contents()` on an
  unvalidated `$_GET['url']`, reaching "internal resources such as admin panels, cloud metadata
  endpoints, and localhost services"; good code checks the URL against a predefined allowlist via
  `in_array()`.
- **CWE-441 (Unintended Proxy or Intermediary)**, CWE-918's direct parent: `ChildOf` CWE-610;
  `ParentOf` CWE-918 and CWE-1021; `PeerOf` CWE-611 (XXE) — the same XXE-adjacency CWE-918's own
  page notes, confirmed from the parent's side too.
- **CWE-610 (Externally Controlled Reference to a Resource in Another Sphere)**: `ChildOf` Pillar
  664; `ParentOf` a wide family including CWE-15 (config setting), CWE-73 (file name/path), CWE-384
  (session fixation), CWE-441 (the SSRF parent above), CWE-601 (open redirect — the exact mechanism
  the skill file's open-redirect bullet exploits), and CWE-611 (XXE). This confirms open-redirect
  reuse and SSRF are literal CWE siblings under the same parent, not an ad hoc connection the skill
  file invented.

### AWS — EC2 Instance Metadata Service documentation (`docs.aws.amazon.com`)

Directly fetched, current page. **"By default, you can use either IMDSv1 or IMDSv2, or both"** —
IMDSv1 is not disabled by default; an operator must explicitly configure the instance to
"only accept IMDSv2 calls, which will cause IMDSv1 calls to fail." IMDSv2's own mechanism: **"Use a
`PUT` request to initiate a session... The `PUT` request returns a token that must be included in
subsequent `GET` requests... When token usage is set to `required`, requests without a valid token
or with an expired token receive a `401 - Unauthorized`."** Also stated: **"`PUT` requests are
rejected if they contain an `X-Forwarded-For` header,"** and the `PUT` request's own response has a
"response hop limit (time to live) of `1` at the IP protocol level" by default — both aimed at
making the token-issuing `PUT` request specifically hard to trigger through a proxying/forwarding
hop, which is exactly the shape a generic reflected-URL SSRF primitive has. AWS's own blog, linked
from this page, is titled "Add defense in depth against **open firewalls, reverse proxies, and SSRF
vulnerabilities**" — i.e. AWS's own stated purpose for IMDSv2 is specifically to blunt the class of
attack this skill file's metadata bullet performs.

### GCP and Azure metadata endpoints

- **Azure** (`learn.microsoft.com/.../instance-metadata-service`, fetched directly): every worked
  example request carries `-H Metadata:true` / `@{"Metadata"="true"}`; the page also instructs
  clients to **bypass any local proxy** when querying IMDS (`--noproxy "*"` / `-NoProxy`). The page
  text available in this session does not include an explicit "rejected without this header"
  statement, but every documented request shape requires the header — a request lacking it is not
  one of Azure's own documented access patterns.
- **GCP**: the primary `cloud.google.com/compute/docs/metadata/overview` page (redirected to
  `docs.cloud.google.com/...`) states plainly: **"You must sandbox any process that shouldn't be
  able to access the metadata server"** — metadata access is unauthenticated query-scoped, not
  identity-scoped, so anything able to reach the metadata IP at all can read it. This session could
  not independently reach GCP's specific `querying-metadata` page to confirm the `Metadata-Flavor:
  Google` header requirement directly (404 on the attempted URL); that requirement is widely known
  but is **not independently confirmed as a primary-source quote in this research session** and
  should be treated as a probable but unverified claim if cited in the skill file.

### OWASP Cheat Sheet Series — Server-Side Request Forgery Prevention Cheat Sheet

(Correct slug has no hyphen in "Server Side": `Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html`; the hyphenated URL the task brief suggested 404s.) This is the most procedurally
detailed primary source fetched:

- **DNS rebinding, named explicitly and distinctly from IP-encoding bypasses**: "Domain
  allowlisting alone does not prevent DNS rebinding." "A second, unchecked DNS lookup between
  validation and connection can bypass these checks." Its own fix is to "connect to the validated
  IP while keeping the original hostname for the Host header, SNI, and certificate verification,"
  and to "apply the destination policy to retries and fallback connections as well."
- **IP-address encoding bypasses, tested per-library, not as one flat technique**: the sheet tests
  Hex, Octal, Dword, URL, and Mixed encodings against real parsing libraries. Java's
  `InetAddressValidator.isValid`, JavaScript's `ip-address`, and Ruby's `IPAddr` are called out as
  **not** vulnerable to any of the five forms; .NET's `IPAddress.TryParse` **is** "exposed to
  bypass using Hex, Octal, Dword and Mixed encoding" (not URL encoding). Its own fix: "unmap or
  canonicalize an address to its native IPv4 form before checking it against these ranges" — a
  direct reference to IPv4-mapped-IPv6 forms (`::ffff:127.0.0.1`-shaped) as a real normalization
  gap, even though the sheet's fetched text does not spell out that literal payload string.
- **A dedicated "IMDSv2 in AWS" section** exists (confirming the task brief's premise that primary
  sources tie cloud-metadata testing to the IMDSv2 distinction as its own point): "IMDSv2 is an
  additional defense-in-depth mechanism for AWS that mitigates some of the instances of SSRF," with
  the sheet recommending migrating to IMDSv2 and disabling IMDSv1 outright.
  **It frames IMDSv2 explicitly as a partial, not complete, mitigation** — consistent with AWS's
  own "default allows both" admission above.
  - "Deny-lists are bypass-prone. Prefer allow-lists," matching A10:2021's flat prohibition.
  - Disabling HTTP redirects and restricting schemes to `HTTP`/`HTTPS` only (the sheet separately
    names `file://`, `gopher://`, `data://` as other schemes an unrestricted fetch could abuse) are
    both named as application-layer controls — i.e. the skill file's current scheme-restriction
    rationalization-to-reject ("only accepts http/https, so it's safe") matches the cheat sheet's
    own framing of scheme restriction as necessary-but-insufficient, not irrelevant.

### MITRE/OWASP WSTG

WSTG's live table of contents lists **"4.7.19 Server-Side Request Forgery"** under 4.7 Injection
(chapter 4, Web Application Security Testing) — confirmed present, by title only. Every attempted
fetch of the actual subchapter page (`.../19-Testing_for_Server-Side_Request_Forgery` and
variants) returned 404, the same failure mode the auth-session and access-control audits already
recorded for other WSTG subchapters. This is noted as an open research gap, not as "WSTG has no
real methodology" — only that it could not be independently read this session.

### Bugcrowd Vulnerability Rating Taxonomy (`master`, fetched as JSON)

Under **Server Security Misconfiguration → Server-Side Request Forgery (SSRF)**, seven
independently-rated variants: *External - DNS Query Only* (P5), *External - Low impact* (P5),
*Internal Secrets Exposure* (P2), *Internal Data Exposure* (P3), *Internal Port Service Scan* (P3),
*Internal Exposure of the Presence of Data/Secrets* (P4), *Internal Port Scan Only* (P4). The
SSRF subcategory itself carries no blanket priority. Two things worth noting: (1) *External - DNS
Query Only* (P5) is Bugcrowd's own severity line for exactly the "DNS resolved, no HTTP follow-up"
signal PortSwigger's blind-SSRF page calls an ambiguous, lower-value result — independent
confirmation that a DNS-only hit is real but low-value, not non-evidence. (2) *Internal Port Scan
Only* (P4) vs. *Internal Port Service Scan* (P3) is Bugcrowd's own severity split between "we know
a port responded differently" (a timing/status differential — candidate-tier evidence) and "we got
actual service content back" (Oracle-tier evidence) — the same confirmed/candidate distinction the
skill file's own step 3/step 5 escalation discipline already encodes structurally.

## 2. Audit of `skills/ssrf/SKILL.md`

Ranked most important first.

### Finding 1 — The cloud-metadata tier's plain-GET mechanism does not reach a correctly-configured modern instance on any of the three cloud providers, and the file gives no instruction for what a probe should do differently

**Location:** Procedure step 3, "Cloud metadata endpoint" bullet (lines 68–74): "submit
`http://169.254.169.254/latest/meta-data/`... A response containing actual metadata content is
immediately Oracle-checkable on its own — this tier alone can produce a confirmed Finding with no
further escalation needed."

**What's wrong:** This is only true against a legacy or misconfigured instance. Per AWS's own
documentation (quoted above), IMDSv2-only mode makes every `GET` without a prior `PUT`-issued
token return a bare `401 - Unauthorized` — and that `PUT`-token exchange is a **different HTTP
method, to a different path, requiring a response header read back and replayed on a second
request**, which is not a thing a reflected-destination SSRF primitive (an attacker controlling
one URL/hostname value that the Target's own code fetches) can generally do at all: the attacker
picks the destination, not the Target's own method or its ability to chain two requests together.
A `401` here is not evidence the Target is unreachable from this vertical's own candidate — it's
evidence a stronger-than-plain-GET protection is active, which is itself worth recording, not
silently absorbed into "no diff, move on." Azure's own documented access pattern requires a
`Metadata: true` header on every request (every worked example on its docs page carries it); GCP's
metadata server is unauthenticated-by-reachability but conventionally gated behind a
`Metadata-Flavor: Google` header this session could not independently verify from a primary source
(noted above as unconfirmed). The file's GCP/Azure variant bullet ("the equivalent GCP
`http://metadata.google.internal/` or Azure `http://169.254.169.254/metadata/instance` form")
sends neither provider's required header at all, and nothing in `curl.get`'s dispatch instructions
here tells the probe to set one — despite `headers` being exactly the parameter already available
for it (confirmed directly against `curl.py`: `get`'s `headers` mapping is forwarded verbatim as
`-H` tokens with no special-casing).

**Why it matters:** this is the task brief's point 2, and it's a real, high-value gap: an agent
following this bullet exactly as written against a hardened AWS instance gets a `401` and, per the
file's own step 4 diff discipline ("a generic error shared by every destination tried" is not
interesting), has no instruction telling it this specific `401` is itself worth recording as a
distinct finding-adjacent signal (IMDSv2 enforced) rather than a dead end; against Azure or GCP, it
never gets real content at all because it never sends the one header that would let it, and
nothing in the file says so.

**Concrete fix:** rewrite the bullet as: "submit `http://169.254.169.254/latest/meta-data/` (AWS),
`http://metadata.google.internal/computeMetadata/v1/` with a `Metadata-Flavor: Google` header set
via `curl.get`'s `headers` parameter (GCP), and `http://169.254.169.254/metadata/instance` with a
`Metadata: true` header via the same mechanism (Azure, requires `?api-version=<date>` on the query
string too). A response containing actual metadata content on any of these is immediately
Oracle-checkable on its own. A `401`/`403` specifically from the AWS form is not a dead end — AWS's
own IMDSv2 requires a `PUT`-issued session token before any `GET` succeeds, a two-step,
cross-method exchange this vertical's single-destination dispatch generally cannot perform through
a reflected-URL SSRF primitive; record this as `needs_confirmation` with the requirement 'Target
enforces IMDSv2; confirming a bypass needs an SSRF primitive that lets the attacker also control
HTTP method and a prior request, not only the destination' rather than ruling the tier out." Add
the AWS IMDSv2 defense-in-depth blog and the OWASP Cheat Sheet's "IMDSv2 in AWS" section to
`References`.

### Finding 2 — DNS rebinding is a primary-source-named SSRF filter-bypass technique, distinct from alternate IP encoding, and the file has no mechanism for it and doesn't flag it as blocked either

**Location:** Procedure step 3's "Filter-bypass encodings" bullet (lines 82–94); `Known gaps`
(lines 155–164) — absent from both.

**What's wrong:** The OWASP Cheat Sheet names DNS rebinding as its own distinct bypass category
("Domain allowlisting alone does not prevent DNS rebinding... a second, unchecked DNS lookup
between validation and connection can bypass these checks"), and A10:2021 lists "DNS rebinding and
TOCTOU race conditions" as its own named thing to guard against, separate from the IP-encoding
bypass family the file currently names. The mechanism needs an attacker-controlled DNS record
that resolves to one address during the Target's validation check and a different (loopback/
internal) address at actual-connection time — which requires owning and flipping a real DNS zone.
Neither `curl` nor `nmap` (the Rig's only two registered bridges, confirmed directly against
`default_bridges()`) provisions DNS-record control at all. This is the same shape of gap the file's
own `Known gaps` section already names for out-of-band blind-SSRF confirmation (no Rig tool for
standing up a listener this vertical controls) — but DNS rebinding isn't mentioned anywhere, so an
agent reading this file has no way to know the technique exists, let alone that it's blocked.

**Why it matters:** task brief point 1's explicit example. Silently omitting a named technique
reads differently from naming it and marking it blocked — the latter is honest about this
vertical's own exhaustion boundary (what the Exit condition's "genuinely exhausted its angles"
claim depends on being accurate about); the former risks a future agent, or a maintainer who adds a
DNS-capable tool later, never knowing this vertical was supposed to pick it up.

**Concrete fix:** add to `Known gaps`: "DNS rebinding (an attacker-controlled hostname that
resolves to a benign address during the Target's own validation check and to a loopback/internal
address at actual connection time) is a named SSRF filter-bypass technique this vertical cannot
exercise at all today: neither `curl` nor `nmap` provisions registering or flipping a DNS record
under this vertical's control. Record any candidate whose only remaining open question is a
rebinding bypass as `needs_confirmation` with that requirement named explicitly, never as ruled
out." Add the OWASP Cheat Sheet URL to `References` if not already present via Finding 1's fix.

### Finding 3 — SSRF via the Referer header is a primary-source-named, cheaply-dispatchable attack surface this vertical's input enumeration never looks for

**Location:** Procedure step 1 (lines 43–52): enumerates only named parameters ("`url`, `uri`,
`link`, `callback`, `webhook`, `src`, `path`, `dest`, `target`, `proxy`, `fetch`, `image`,
`avatar`, `next`, `redirect`-shaped") and URL/hostname-shaped recorded values — no mention of a
request header as a candidate input shape anywhere in the file.

**What's wrong:** PortSwigger names this as its own, separate finding-hidden-attack-surface
sub-case: "the Referer header is often a useful attack surface for SSRF vulnerabilities," because
server-side analytics software commonly "visits any third-party URLs that appear in the Referer
header." This is not a body or query parameter at all — it's a header the Target's own server-side
code reads and may itself fetch, which the file's current step 1 enumeration has no instruction to
even look for. Dispatching it needs nothing new: `curl.get`/`curl.post_form`'s shared `headers`
parameter (already this vertical's own identity/credential-carrying mechanism in sibling verticals
like `auth-session`) can set `Referer` to any tiered destination value exactly the way it sets
`Cookie` elsewhere in this repo.

**Why it matters:** this is a real, named technique with a concrete, already-available dispatch
path and zero current coverage — the kind of gap that's cheap to close and currently silently
unexercised rather than deliberately excluded.

**Concrete fix:** add to step 1's enumeration: "a `Referer` header the Target's own back-end
analytics or link-preview feature might dereference, even when no URL-shaped parameter exists on
the same request." Add to step 3: "**Referer-header SSRF**: where the surface records
server-side processing of the `Referer` header (an analytics hit, a referral log, a link-preview
feature), submit the same tiered destination set as the candidate's own baseline via `curl.get`'s
`headers` parameter (`{\"Referer\": \"<tiered destination>\"}`) rather than a body or query value."
Add the PortSwigger SSRF page's own URL (already present) covers this; no new `References` entry
needed.

### Finding 4 — Filter-bypass-encoding bullet is narrower than the Cheat Sheet's own tested encoding family, and conflates a distinct address form (IPv6) with an encoding of the same literal

**Location:** step 3, "Filter-bypass encodings" bullet (lines 82–94): "retry the identical
destination via an alternate encoding (a decimal IP form, e.g. `2130706433` for `127.0.0.1`)."

**What's wrong:** the Cheat Sheet tests real parsing libraries against five encoding families —
Hex, Octal, Dword, URL, and Mixed — and shows the vulnerability is library-specific (.NET's
`IPAddress.TryParse` fails on Hex/Octal/Dword/Mixed but not URL-encoding; Java/JS/Ruby's equivalents
fail none of them in the sheet's own testing). PortSwigger separately names decimal (`2130706433`),
octal (`017700000001`), and short-form dotted (`127.1`) as concrete payloads. The file's current
bullet only ever tries one encoding (decimal) before its own step 4/5 discipline would let an agent
conclude the filter survived the whole "filter-bypass encodings" tier — which doesn't match the
library-specific reality either primary source actually documents: one encoding failing says
nothing about another. Separately, IPv6 loopback forms (`::1`, `::ffff:127.0.0.1`) are not an
*encoding* of the decimal/octal/hex family at all — they're a different address-literal form the
Cheat Sheet gestures at only indirectly (its own fix text says to "unmap or canonicalize an address
to its native IPv4 form," which only makes sense as a response to IPv4-mapped IPv6 forms actually
being submitted) — so folding it into the same bullet as "another encoding" would mischaracterize
what it actually is.

**Why it matters:** task brief point 3's framing (decimal encoding is this file's current full
scope) is otherwise correct. The underlying mechanism is as cheap as what's already there — each of
these is a plain string substitution curl already dispatches — so the gap is pure missed coverage,
not a capability problem.

**Concrete fix:** broaden the bullet to: "MUST retry the identical destination via each of: a
decimal IP form (`2130706433` for `127.0.0.1`), an octal form (`017700000001`), and a short/dotted
form (`127.1`) before concluding an IP-literal filter survives this tier — MUST NOT conclude from
one alternate encoding failing that the filter handles the whole family, since real-world parsers
are documented as encoding-specific (a filter blocking decimal does not imply it blocks octal)."
Add a separate clause to the localhost/loopback tier (lines 62–67, not the encoding-bypass tier,
since this is a distinct address form rather than an encoding of the same one): "also submit
`http://[::1]` and `http://[::ffff:127.0.0.1]` (IPv6 loopback and IPv4-mapped-IPv6 forms) — some
validators normalize only dotted-decimal IPv4 input and never canonicalize an IPv6-literal form
before comparing it against a blocklist." Add the OWASP Cheat Sheet URL to `References`.

### Finding 5 — "Known gaps" claim about blind SSRF confirmation is accurate; no non-OOB citable methodology exists in the fetched sources, and the Rig genuinely has no tool for it

**Location:** `Known gaps` (lines 155–164).

Checked directly against `src/exhaust/rig/wrappers/__init__.py`'s `default_bridges()`: only
`curl` and `nmap` are registered — no DNS, no listener, no callback-receiving tool of any kind.
PortSwigger's own blind-SSRF page is explicit that OOB/Collaborator technique is "the most reliable
way to detect blind SSRF vulnerabilities," and describes no alternative timing-only or
side-channel-only methodology with a defined, citable procedure. The task brief's point 4 asked
whether such a technique exists that this vertical could adopt instead of flagging the gap — it
does not, in what was fetched this session. The file's own existing tiered-probe design (timing/
error-shape differential against an external baseline, confirmed by re-baselining) is already the
closest thing to a non-OOB signal any source describes, and the file already uses it for the
RFC 1918 tier. No fix needed on this specific claim; see Finding 2 for the adjacent DNS-rebinding
gap this section should also name.

### Finding 6 — `curl.py` and tool-dispatch claims in the front matter and Procedure are accurate; `nmap` correctly has no role here

**Location:** front matter `description` (lines 11–14): "Dispatches through `curl.get`'s
`query`/`path_segment` or `curl.post_form`'s `data`, submitting a tiered set of destinations and
reading the status/header block and elapsed-time line their output carries."

Read `curl.py` directly. `get` accepts both `query` (a flat string-to-string mapping appended as a
query string) and `path_segment` (a string appended to the URL path) — both real, validated
parameters. `post_form` accepts `data` (a flat string-to-string mapping sent via
`--data-urlencode`) — also real. `_invoke` passes `-i` (prepending status line and headers to the
body) and `-w` with `_TIMING_WRITEOUT`, which appends an `X-Exhaust-Elapsed-Seconds: <total>` line
after the body — so "the status/header block and elapsed-time line their output carries" is
literally true of every dispatch this vertical makes. Read `nmap.py` directly too: its two methods
(`tcp_connect_scan`, `service_version_scan`) only accept a `host` the caller already controls
directly and scan from the caller's own vantage point — they cannot make the Target itself issue a
request anywhere, which is this vertical's whole subject. The file's existing routing boundary
("Do not use for scanning the Target's own listening ports directly — that's `recon`'s job... this
vertical is about the Target making a request on the attacker's behalf") is accurate against what
`nmap.py` actually does; there is no plausible use for `nmap` inside this vertical's own procedure.
No fix needed.

### Finding 7 — "URLs within data formats" and "backend connection reuse" are both out of scope, but for different, unstated reasons; routing boundary is correct in substance but doesn't say so

**Location:** `description` (lines 17–23): only two exclusions are named today (file/path read
directly off disk → `file handling`; a cross-site-forged request using the victim's own browser
session → `CSRF`).

**What's wrong:** PortSwigger's own "finding hidden attack surface" material routes a third case —
a URL embedded inside a parsed data format (XML named specifically) — to XXE, explicitly: a parser
that accepts such a payload "may be vulnerable to XXE injection, and possibly to SSRF via XXE." The
skill file never says this boundary exists at all; `skills/injection/SKILL.md`'s own exclusion
clause (deserialization of "pickle, YAML, XML... that's the `deserialization` vertical") implies
the natural home for this case already exists elsewhere in the catalog, but neither file's
exclusion clause names the other's territory for this specific overlap. Checked separately: the
"backend connection reuse / request smuggling" angle the task brief asked about is simply not a
documented SSRF technique on PortSwigger's own page at all (confirmed by direct fetch) — so there
is no real boundary question here to resolve, only a premise that didn't hold up.

**Why it matters:** smaller than Findings 1–4, but a real, source-backed gap in the routing
contract itself (the thing `exhaust skill lint`'s description-shape check and ADR 0017's four-part
contract are both built to make reliable): an agent that finds a URL embedded in an XML body being
parsed server-side currently has nothing in this file telling it that's someone else's territory.

**Concrete fix:** add to `description`'s exclusion list: "Do not use for a URL embedded inside a
parsed structured payload (XML, YAML, or similar) that a parser dereferences as part of handling
the format itself — that's the `deserialization` vertical's XXE-adjacent territory, not a
destination-naming input this vertical enumerates directly." No change needed for the backend-
connection-reuse point; it was checked and isn't a real technique in the fetched source.

### Finding 8 — Two CWE relationships worth adding to `References` for context; not urgent

**Location:** `References` (lines 166–172): cites only CWE-918.

CWE-918 is `ChildOf` CWE-441 (Unintended Proxy or Intermediary) and CWE-610 (Externally Controlled
Reference to a Resource in Another Sphere) — both confirmed by direct fetch, and both already cited
as parents in this repo's own `access-control` and `auth-session` SKILL.md files for their own
CWEs' lineage, so this would match house style. Lower priority than Findings 1–7 since CWE-918
alone is unambiguous and sufficient for an agent's own purposes; adding the parents is a citation-
completeness nicety, not a procedural fix.

**Concrete fix (optional):** add "MITRE CWE-441, Unintended Proxy or Intermediary" and "MITRE
CWE-610, Externally Controlled Reference to a Resource in Another Sphere" to `References`.
