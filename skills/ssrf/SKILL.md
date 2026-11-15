---
name: ssrf
required: true
description: >
  Probes whether any input controls, in whole or part, the destination
  of a server-initiated outbound request — a URL, hostname, IP, or path
  fragment used by a webhook/callback, a fetch-by-URL feature, an image
  proxy, or a PDF/report generator — letting the Target be made to
  issue a request to an attacker-chosen destination (localhost, an
  internal-only host, a cloud metadata endpoint) instead of, or in
  addition to, its intended one. Dispatches through `curl.get`'s
  `query`/`path_segment` or `curl.post_form`'s `data`, submitting a
  tiered set of destinations and reading the status/header block and
  elapsed-time line their output carries. Use when the Workspace's
  surface records an input whose name or recorded normal value is
  URL/hostname-shaped, or whose baseline response already shows the
  Target fetching content from that value. Do not use for a path or
  filename read directly off local disk — that's `file handling`. Do
  not use for a request forged cross-site using the victim's own
  browser session — that's `CSRF`. Do not use for scanning the Target's
  own listening ports directly — that's `recon`'s job; this vertical is
  about the Target making a request on the attacker's behalf, not the
  attacker reaching the Target itself.
keywords:
  - SSRF
  - server-side request forgery
  - cloud metadata endpoint
  - internal network pivot
  - blind SSRF
  - URL validation bypass
---

## What this vertical investigates

Whether an input that names, in whole or part, where the server should
send an outbound request actually constrains that destination to what
the feature intends, or whether it can be redirected to a destination
only the server itself can reach: localhost, an internal-only service,
or a cloud provider's metadata endpoint.

## Procedure

1. MUST read the Workspace's enumerated surface before touching
   anything — this vertical does not enumerate the Target itself. From
   it, identify every input whose name suggests it names a request
   destination (`url`, `uri`, `link`, `callback`, `webhook`, `src`,
   `path`, `dest`, `target`, `proxy`, `fetch`, `image`, `avatar`,
   `next`, `redirect`-shaped) or whose recorded normal value is itself
   URL- or hostname-shaped, plus any input whose baseline response
   already shows evidence the Target fetched content from that value
   (a reflected title, byte count, or content-type matching the
   supplied URL's own resource).
2. MUST record a baseline for every candidate first: submit the
   input's own recorded normal value (an external, intended
   destination) and record the full response — the leading status/
   header block and the elapsed-time line `curl.get`/`curl.post_form`'s
   output carries. Every later diff in this procedure is measured
   against this baseline, never against an assumed "should have
   failed" response.
3. MUST probe each candidate with an escalating, tiered set of
   destinations, recording each tier's response distinctly:
   - **Localhost / loopback**: submit `http://127.0.0.1`,
     `http://localhost`, and the Target's own observed hostname as the
     input's value. A response that differs from the external
     baseline — a different status, a different body, content that
     looks like an internal admin surface — is evidence the Target
     itself issued the request.
   - **Cloud metadata endpoint**: submit `http://169.254.169.254/latest/meta-data/`
     (and the equivalent GCP `http://metadata.google.internal/` or
     Azure `http://169.254.169.254/metadata/instance` form, if the
     Target's own stack is known from recon). A response containing
     actual metadata content is immediately Oracle-checkable on its
     own — this tier alone can produce a confirmed Finding with no
     further escalation needed.
   - **Internal / RFC 1918 ranges**: submit a small, fixed set of
     common internal addresses (`10.0.0.1`, `192.168.0.1`,
     `172.16.0.1`) and record each response distinctly. A response
     differential against the external baseline (timing, status, error
     shape) is a candidate, not yet confirmed — an address with no
     attacker-visible service behind it can look identical whether the
     Target reached it and got refused, or never reached it at all.
   - **Filter-bypass encodings**: where a raw internal IP/hostname is
     rejected outright (a distinct, filter-shaped error, not a generic
     connection failure) but a URL-shaped input is otherwise accepted,
     MUST retry the identical destination via an alternate encoding
     (a decimal IP form, e.g. `2130706433` for `127.0.0.1`) before
     concluding the filter blocks the destination rather than one
     literal string form of it. Where the surface records a
     Target-hosted open-redirect endpoint, MUST also try submitting
     that endpoint's own URL (pointed at a localhost/internal/metadata
     destination) as the input's value — a filter checking only the
     literal destination string never sees the redirect's real target,
     since this vertical has no attacker-controlled external host of
     its own to redirect through.
4. MUST diff against the recorded baseline, never against expectation.
   A probe is interesting only when the response differs from that
   same input's own baseline in a way the tier's own mechanism
   specifically predicts (metadata content, internal-surface content,
   a timing or error-shape differential against the external baseline)
   — not a generic error shared by every destination tried. MUST
   record every interesting diff as a candidate; MUST NOT record a
   non-diff as "tested clean" without the recorded baseline it was
   compared against.
5. MUST escalate only a confirmed diff far enough to produce
   Oracle-checkable evidence before writing a Finding: actual metadata
   content, actual internal-surface content, or a reproducible timing/
   error-shape differential confirmed by re-baselining at least once —
   not this vertical's own interpretation of an ambiguous response.
   MUST NOT escalate a tier that produced a generic, baseline-matching
   failure on the theory that a different internal address might still
   work — that belongs in a later recon-informed pass, not this one.

## Exit condition

- [ ] Every candidate input identified in step 1 has a recorded
      baseline (step 2).
- [ ] Every candidate has been probed against every tier in step 3
      applicable to it (the filter-bypass tier only applies once the
      localhost/internal tiers show a distinct, filter-shaped
      rejection).
- [ ] Every candidate diff recorded in step 4 is closed as exactly one
      of: **confirmed** (Oracle-backed, never this vertical's own
      self-report), **ruled out** (the specific, named reason the diff
      isn't a real signal — e.g. "internal-range timing matched the
      external baseline's own connection-failure shape exactly,
      confirmed by re-baselining twice" — not just "looked clean"), or
      **open proof gap**, recorded as `needs_confirmation` with its
      `requirements`. A candidate dropped without landing in one of
      these three is this vertical stopping early, not exhausting
      itself.

## Rationalizations to reject

- "It only accepts `http`/`https` schemes, so it's safe." — A scheme
  restriction constrains the protocol, not the host; `169.254.169.254`
  and `127.0.0.1` are both valid `http://` hosts.
- "It returned a connection error for the internal IP, so it's
  blocked." — A connection error, a timeout, and an immediate
  filter-rejection are three different signals. MUST compare against
  what an equally-unreachable *external* address produces before
  concluding the internal address was specifically blocked rather than
  generically unreachable the same way any dead host would be.
- "This input only offers a dropdown of fixed hostnames, so it can't
  be redirected." — A UI constraint isn't a server-side one; MUST still
  submit the underlying parameter directly with an out-of-list value,
  and MUST check whether an allow-listed hostname is matched by exact
  string or by a weaker check (prefix, substring, suffix) that a
  crafted value could still satisfy.
- "The response didn't contain anything, so nothing happened." — A
  non-reflected response doesn't prove no outbound request fired; MUST
  check for a timing or error-shape differential against the baseline
  before ruling a candidate out, and record it as an open proof gap
  rather than ruled out when no such differential is available either.

## Known gaps

No Rig tool exists for standing up an out-of-band listener the agent
controls: a destination this vertical doesn't already have a response
channel for — the canonical real-world case of blind SSRF — cannot be
confirmed by this vertical at all today, only recorded as
`needs_confirmation`. Treat this as blocked, not as evidence of safety:
a candidate whose only available signal is "no reflected content and
no measurable differential" is an open proof gap, never a ruled-out
result.

## References

- MITRE CWE-918, Server-Side Request Forgery (SSRF): <https://cwe.mitre.org/data/definitions/918.html>
- OWASP Top 10:2021, A10:2021 Server-Side Request Forgery:
  <https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/>
- PortSwigger, Server-side request forgery (SSRF) (testing technique):
  <https://portswigger.net/web-security/ssrf>
