---
name: recon
required: true
description: >
  Enumerates every request-shaped input the Target exposes (form fields,
  query parameters, headers, cookies, path segments, upload filenames) and
  attempts to confirm or refute every gate signal a gated vertical
  declares, recording both to the Workspace's shared surface. Use when a
  Workspace's Playbook starts, before any other vertical's own
  investigation begins. Do not use for judging what a discovered input
  means for a specific weakness class, or for probing it — that's every
  offensive vertical's own job; this one only maps what the Target
  exposes and never claims a weakness of its own.
keywords:
  - enumeration
  - surface mapping
  - fingerprinting
  - attack surface discovery
---

## What this vertical investigates

What inputs the Target actually exposes, and which declared trust
boundaries (a reverse proxy, a GraphQL endpoint, a WebSocket upgrade, and
the like) are actually present, so every other vertical reads one shared
answer instead of each re-discovering it alone.

## Procedure

1. MUST enumerate every form field, query parameter, header, cookie, path
   segment, and upload filename the Target exposes, using whatever Rig
   tools are available: `curl.get` against discovered routes and against
   `/robots.txt` and `/sitemap.xml` (a `Disallow` entry or a listed URL is
   often the cheapest way to surface a path nothing else links to),
   `nmap`'s `service_version_scan`, a crawl of observed links, and an
   OpenAPI/Swagger spec if the Target serves one. For each input found,
   MUST record it: its kind, the endpoint it lives on, its name, which
   Rig method and parameter a later vertical uses to reach it, and a
   well-formed sample value.
2. MUST attempt to actually observe the trust boundary named by every
   signal this turn's request lists as needing confirmation. For each
   one, MUST record a confirmed or refuted signal, backed by something
   actually seen (a response header, a status-code pattern, a redirect,
   an introspection probe). MUST NOT record a signal from an inference —
   "this response looks like Node, there's probably an nginx reverse
   proxy in front of it" is a guess, not an observation, and recording it
   as confirmed would let a gated vertical start on a boundary nobody
   actually saw.
3. MUST NOT probe for or claim a weakness of any kind. This vertical maps
   the Target's shape; it opens no Finding and makes no claim about what
   any input or boundary means.

## Exit condition

- [ ] Every route discoverable with the Rig tools available to this
      vertical has had its inputs enumerated and recorded.
- [ ] Every signal this turn's request listed as needing confirmation has
      a recorded confirmed or refuted signal — none left unaddressed.

## Rationalizations to reject

- "This input looks like every other one on this form, recording it is
  redundant." — A later vertical can only probe what is recorded here;
  an input skipped at this stage is invisible to every vertical that
  reads the shared surface, not merely unprobed by this one.
- "The tech stack suggests a proxy is probably in front of this." — A
  suggestion is not an observation. MUST record refuted, not confirmed,
  until the boundary is actually seen.

## Known gaps

Hidden-parameter discovery (wordlist-based fuzzing against every
discovered endpoint, the way a dedicated parameter-fuzzing tool would)
and mining a Target's own JavaScript for endpoints and parameter names
it never renders into a form have no Rig tool to dispatch through yet.
Treat both as blocked for now: name them in the run's own notes rather
than skipping silently, and enumerate only what `curl`, `nmap`, a crawl
of observed links, and metafiles actually surface.
