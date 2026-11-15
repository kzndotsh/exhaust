---
name: information-disclosure
required: true
description: >
  Probes whether the Target exposes sensitive data to any caller
  regardless of identity: version-control or config files left in the
  webroot (`.git/HEAD`, `.env`), backup-suffixed variants of a known
  file (`.bak`, `.old`, `~`), a verbose error message or stack trace
  revealing file paths or framework internals, an HTML comment or
  inline script left with credentials or developer notes, and
  auto-generated directory listings. Dispatches through `curl.get`
  against a small, fixed checklist of commonly-exposed paths plus every
  path the surface already records, reading the response body for
  recognizable sensitive content. Use when a Workspace's Playbook
  starts; this vertical needs only the Target's base URL and recon's
  enumerated surface, not any particular confirmed input shape. Do not
  use for an authorized identity reading a specific object's own
  properties beyond its entitlement — that's `access-control`'s BOPLA
  sub-case. Do not use for data obtained by making the Target issue a
  request to an internal destination on the attacker's behalf — that's
  `ssrf`. Do not use for correlating a disclosed version or banner
  against a known CVE — that's `known-CVE`. Do not use for reading an
  arbitrary file off local disk via path traversal — that's
  `file handling`.
keywords:
  - information disclosure
  - sensitive data exposure
  - source code disclosure
  - directory listing
  - verbose error message
  - stack trace disclosure
  - backup file exposure
  - config file exposure
---

## What this vertical investigates

Whether the Target hands any caller data it never intended to: a
leftover version-control or config file, a backup copy of a known
file, an error message carrying more than a generic failure, a
developer's own comment or debug note left in a response, or a
directory listing nobody built a page for.

## Procedure

1. MUST read the Workspace's enumerated surface first — this vertical
   does not perform recon's own broad enumeration, but it does run its
   own small, fixed checklist of commonly-exposed paths against the
   Target's base URL directly, independent of what recon's crawl
   happened to link to: `/.git/HEAD`, `/.git/config`, `/.env`,
   `/.svn/entries`, `/.DS_Store`, `/web.config`, `/.htpasswd`. For
   every file-shaped path the surface already records, MUST also try
   the same path with a common backup suffix appended (`.bak`, `.old`,
   `~`, `.orig`, `.swp`).
2. MUST record a baseline for every candidate first: the Target's
   genuine 404/not-found shape (requested from a path that plainly
   doesn't exist) and, separately, each candidate's own actual
   response. Every later judgment about whether a candidate
   "disclosed" anything is made against this recorded not-found shape,
   never an assumed one — a Target that returns 200 for everything
   makes status code alone useless here.
3. MUST probe each applicable mechanism:
   - **Source-control / config file exposure**: a 200 (or any
     status distinct from the recorded not-found shape) from a step 1
     checklist path, carrying content recognizable as that file's real
     format (a git ref line, `KEY=VALUE` env syntax, credentials in a
     `.htpasswd` hash shape), is immediately Oracle-checkable on its
     own.
   - **Backup file exposure**: a backup-suffixed path that returns the
     known file's own source content (not a redirect to the
     non-suffixed version, not the application's normal rendered
     output) confirms the backup copy is being served raw rather than
     processed or blocked.
   - **Verbose error messages**: MUST trigger at least one error
     deliberately (a malformed value on any input the surface
     records — an obviously wrong type, an unterminated quote, an
     out-of-range value) and check whether the response includes a
     stack trace, a local file path, a framework/library version
     string, or a raw database error — not merely a non-200 status.
     MUST NOT conclude "no verbose errors" from a single error trigger;
     try at least two structurally different malformed values before
     closing this candidate.
   - **Comments and inline script in response bodies**: MUST read the
     full body of every response this vertical's own requests already
     captured (not a fresh crawl) for HTML comments or inline
     `<script>` blocks containing credentials, internal hostnames, or
     developer notes (`TODO`, `FIXME`, a real API key shape).
   - **Directory listing**: where the surface records a path shaped
     like a directory (ending in `/`, or the parent of a known file),
     MUST request that directory path directly and check whether the
     response is an auto-generated file listing rather than a 403, a
     404, or the application's own page.
4. MUST diff against the recorded baseline, never against expectation.
   A candidate is interesting only when its content is recognizable,
   format-specific sensitive content distinct from the Target's own
   not-found shape — not a generic non-200 status, which a well-behaved
   Target can return for a candidate that discloses nothing at all.
   MUST record every interesting candidate; MUST NOT record a
   non-match as "tested clean" without the recorded not-found baseline
   it was compared against.
5. MUST escalate only a confirmed candidate far enough to produce
   Oracle-checkable evidence before writing a Finding: the specific
   recognizable content itself (the git ref, the env line, the stack
   trace's own file path, the listing's own directory entries) — not
   this vertical's own interpretation of an ambiguous response.

## Exit condition

- [ ] Every path in step 1's fixed checklist, and every backup-suffixed
      variant of a surface-recorded file, has a recorded response
      (step 1/2).
- [ ] At least two structurally different error-trigger attempts have
      been made per candidate input, per the verbose-errors bullet.
- [ ] Every candidate recorded in step 4 is closed as exactly one of:
      **confirmed** (Oracle-backed, recognizable sensitive content
      actually present, never this vertical's own self-report),
      **ruled out** (the specific, named reason the content isn't
      sensitive — e.g. "response matched the Target's own recorded
      404 shape exactly, same status and same generic body" — not
      just "looked clean"), or **open proof gap**, recorded as
      `needs_confirmation` with its `requirements`. A candidate dropped
      without landing in one of these three is this vertical stopping
      early, not exhausting itself.

## Rationalizations to reject

- "It returned 200, but that's probably just a custom error page." —
  A guess about the body isn't a recorded baseline. MUST actually read
  the body and compare it against the Target's own recorded not-found
  shape before concluding either way.
- "The error page is generic, so there's no verbose-error problem." —
  One malformed input is not an exhaustive trial; MUST try at least two
  structurally different malformed values (step 3's own requirement)
  before ruling this candidate out.
- "It's just a version number in a header, that's normal." — A
  disclosed version is this vertical's own finding regardless of
  whether a matching CVE exists; MUST record it here and let
  `known-CVE` decide separately whether it's exploitable.
- "Nobody would guess this backup filename." — Obscurity isn't a
  control; MUST still try the fixed checklist and backup-suffix set
  against every recorded file, regardless of how likely discovery
  seems.

## Known gaps

No Rig tool exists for wordlist-based guessing of arbitrary backup or
sensitive filenames beyond this vertical's own small, fixed checklist
(the same shape of gap `recon`'s own Known gaps names for hidden-
parameter discovery). A Target using a backup-naming convention
outside that checklist (a non-standard suffix, a renamed `.git`
directory) will not be found by this vertical; treat that as blocked,
not as evidence of safety.

## References

- MITRE CWE-200, Exposure of Sensitive Information to an Unauthorized Actor:
  <https://cwe.mitre.org/data/definitions/200.html>
- MITRE CWE-209, Generation of Error Message Containing Sensitive Information:
  <https://cwe.mitre.org/data/definitions/209.html>
- MITRE CWE-538, Insertion of Sensitive Information into Externally-Accessible File or Directory:
  <https://cwe.mitre.org/data/definitions/538.html>
- MITRE CWE-548, Exposure of Information Through Directory Listing:
  <https://cwe.mitre.org/data/definitions/548.html>
- PortSwigger, Information disclosure vulnerabilities (testing technique):
  <https://portswigger.net/web-security/information-disclosure>
