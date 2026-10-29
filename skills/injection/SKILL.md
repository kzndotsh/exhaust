---
name: injection
required: true
description: >
  Probes every discovered input for command, SQL, LDAP, XPath, template
  (SSTI), header/CRLF, and NoSQL injection by submitting a canonical
  boundary-breaking payload per class and diffing the observed response
  against a clean baseline. Use when recon has enumerated at least one
  request-shaped input (form field, query parameter, header, cookie,
  path segment, or uploaded filename) on any Workspace. Do not use for
  deserialization of structured payloads (pickle, YAML,
  XML, Java-object streams) — that's the `deserialization` vertical;
  this one is for payloads interpreted as code or query syntax, never
  payloads reconstructed as a data structure.
keywords:
  - SQLi
  - command injection
  - shell injection
  - OS command injection
  - SSTI
  - server-side template injection
  - LDAP injection
  - XPath injection
  - NoSQL injection
  - CRLF injection
  - header injection
---

## What this vertical investigates

Whether any input the Target accepts crosses from data into an
interpreter's syntax: a shell, a SQL/NoSQL query engine, an LDAP
filter, an XPath expression, a template engine, or an HTTP header
parser reading past the line it should stop at. The shared mechanism
across every sub-case below is the same: find a boundary character or
sequence the target interpreter treats specially, submit it, and check
whether the Target's behavior changes in a way only that interpretation
explains.

## Procedure

1. MUST enumerate every input before touching any of them. Every form
   field, query parameter, header, cookie, path segment, and upload
   filename the Target exposes is a candidate. An input not on this
   list before step 2 starts MUST NOT be probed — do not discover and
   test in the same pass, since an untracked input makes the Exit
   condition below unverifiable.
2. MUST record a baseline for every input first: submit each input's
   own normal, well-formed value and record the response (status code,
   timing, body length, and any error text verbatim). Every later diff
   in this procedure is measured against this baseline, never against
   an assumed "should have succeeded" response.
3. MUST probe each input with one canonical payload per applicable
   class, boundary-breaking rather than exploit-complete (the goal at
   this stage is detecting a behavior diff, not achieving code
   execution or data exfiltration in the same request):
   - **Command injection**: a shell metacharacter sequence that would
     execute a harmless, uniquely-identifiable command if interpreted
     (e.g. a sentinel string echoed back) if the input reaches a shell
     at all. Covers both CWE-78 variants: input appended as an
     argument to a fixed command (the metacharacter sequence above),
     and input that selects the entire command (probe by submitting a
     harmless, identifiable command name as the input's whole value
     and checking whether it runs).
   - **SQL injection**: a single-quote/boolean-logic pair (`' OR '1'='1`
     and `' AND '1'='2`) compared against each other and against
     baseline — a real SQL sink flips behavior between the two; a
     false positive doesn't.
   - **LDAP injection**: an LDAP filter metacharacter (`*`, `)`, `(`)
     that would widen or break a filter if the input reaches an LDAP
     query unescaped.
   - **XPath injection**: a boolean-logic pair shaped like
     `' or ''='` compared against a baseline value, the same
     mechanism as the SQL probe above but against an XPath expression
     (CWE-643) — a real XPath sink returns a different, wider result
     set than the baseline; a false positive returns the same result.
   - **Template injection (SSTI)**: a template-engine expression
     (e.g. `{{7*7}}`-shaped, adapted to whatever templating syntax the
     Target's stack uses once that's known) that evaluates to a
     distinctive value only if the engine actually parses the input.
   - **Header/CRLF injection**: a raw `\r\n` sequence in a header-
     reflected or redirect-target input, checked for a split response
     or an injected header in the Target's reply.
   - **NoSQL injection**: an operator-shaped payload (e.g. a `$ne`/`$gt`
     equivalent for the Target's actual NoSQL engine, once recon has
     identified which one) that would alter query logic if the input
     reaches a NoSQL query unescaped.
4. MUST diff against the recorded baseline, never against expectation.
   A probe is interesting only when its response differs from that
   same input's own baseline in a way the payload's mechanism
   specifically predicts (a timing delay for a sleep-based SQL probe,
   a reflected sentinel for command injection, a distinctive evaluated
   value for SSTI). MUST record every interesting diff as a candidate;
   MUST NOT record a non-diff as "tested clean" without the recorded
   baseline it was compared against.
5. MUST escalate only a confirmed diff, one payload class at a time,
   far enough to produce Oracle-checkable evidence (ADR 0008) before
   writing a Finding. MUST NOT escalate a class that produced no diff
   in step 4 on the theory that a stronger payload might still work —
   that belongs in a later recon-informed pass, not this one.

## Exit condition

- [ ] Every input enumerated in step 1 has a recorded baseline (step 2).
- [ ] Every enumerated input has been probed against every payload
      class applicable to its context (step 3).
- [ ] Every candidate diff recorded in step 4 is closed as exactly one
      of: **confirmed** (Oracle-backed, ADR 0008, never this
      vertical's own self-report), **ruled out** (the specific,
      named reason the diff isn't a real signal — e.g. "timing delta
      within normal response-time variance, confirmed by re-baselining
      three times" — not just "looked clean"), or **open proof gap**,
      recorded as `needs_confirmation` with its `requirements` (ADR
      0019). A candidate dropped without landing in one of these three
      is this vertical stopping early, not exhausting itself.

## Rationalizations to reject

- "The response was 200 OK, so nothing happened." — A 200 is the
  baseline for blind and time-based injection; MUST check timing and
  body-length diffs against the recorded baseline before ruling a
  class out, not just the status code.
- "The error page didn't mention SQL, so it's probably not a SQL
  sink." — Generic/custom error pages are the common case, not the
  exception; a boolean-logic diff (`'1'='1` vs `'1'='2`) still proves
  the sink exists with no error text at all.
- "This input is probably sanitized upstream, I'll skip it." —
  Upstream sanitization is a hypothesis, not a recorded baseline. MUST
  probe every enumerated input per step 3 regardless of where
  sanitization is assumed to live.
- "One payload per class didn't trigger anything, so this class is
  closed." — One canonical payload only rules out the most obvious
  form of that class. Close it as **ruled out** with the specific
  reason (step 4's non-diff plus why), never as a silent non-finding.

## Sub-cases

Command, SQL, LDAP, XPath, SSTI, header/CRLF, and NoSQL injection are
kept inline above rather than split into `references/` files: none of
them yet has enough Target-specific nuance to outgrow a few lines in
this file, and splitting now would cost a lookup for no actual context
savings (ADR 0013's progressive disclosure is a cost tradeoff, not a
default). Split one out into its own `references/<name>.md` the first
time its procedure needs engine-specific detail (e.g. a payload table
keyed on which SQL dialect or templating engine recon identified) long
enough to be worth deferring from every other turn's context.

## Known gaps

`curl.get`/`curl.post_form` (ADR 0027) dispatch steps 2 through 5 for
query-parameter and form-field inputs. Header/cookie inputs,
uploaded-filename inputs, and path-segment inputs have no Rig method
yet: treat those as blocked, name them in the run's own notes, and
don't skip them silently. See ADR 0027 for why.

## References

- MITRE CWE-89, SQL Injection: <https://cwe.mitre.org/data/definitions/89.html>
- MITRE CWE-78, OS Command Injection: <https://cwe.mitre.org/data/definitions/78.html>
- MITRE CWE-90, LDAP Injection: <https://cwe.mitre.org/data/definitions/90.html>
- MITRE CWE-643, XPath Injection: <https://cwe.mitre.org/data/definitions/643.html>
- MITRE CWE-1336, Server-Side Template Injection: <https://cwe.mitre.org/data/definitions/1336.html>
- MITRE CWE-943, NoSQL Injection: <https://cwe.mitre.org/data/definitions/943.html>
- MITRE CWE-93, CRLF Injection: <https://cwe.mitre.org/data/definitions/93.html>
- PortSwigger, SQL injection (testing technique): <https://portswigger.net/web-security/sql-injection>
- PortSwigger, OS command injection (testing technique): <https://portswigger.net/web-security/os-command-injection>
- PortSwigger, Server-side template injection (testing technique): <https://portswigger.net/web-security/server-side-template-injection>
- PortSwigger, NoSQL injection (testing technique): <https://portswigger.net/web-security/nosql-injection>
