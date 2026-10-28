# Playbook proposal (draft) — not locked

This is a draft for discussion, synthesized from three parallel reviews of every file in `docs/research/`, every ADR in `docs/adr/`, and `GLOSSARY.md`, then worked through in a grilling session. It is explicitly **not** the Playbook lock. Per standing instruction, the Playbook stays unlocked until you say the audit campaign is done, and in any case [ADR 0016](../adr/0016-no-hand-maintained-vertical-catalog.md) means this document can never *become* the Playbook's source of truth even once locked — see §1 for why, and §6 for what the real source of truth has to look like instead.

A later cross-check of this draft against primary sources (OWASP WSTG, OWASP ASVS, PortSwigger's own taxonomy) is recorded in [docs/research/2026-10-26-playbook-proposal-cross-check.md](../research/2026-10-26-playbook-proposal-cross-check.md). Its findings are folded into §3, §4, and §7 below as flagged, undecided input — none of them resolve anything on their own. A follow-up pass against three more primary sources (OWASP Top 10:2025, Bugcrowd's VRT, the CWE Top 25) is recorded in [docs/research/2026-10-28-playbook-proposal-additional-sources.md](../research/2026-10-28-playbook-proposal-additional-sources.md) — same status: additional input, not a decision.

## 0. Vocabulary (settled this round)

- **Playbook** — the whole thing: a Workspace's full set of verticals. Was called "Spine" earlier in this project's own documents; renamed because "Playbook" carries the right metaphor on its own (a base set of plays everyone runs, plus situational ones called only when the game calls for them) without needing an explainer.
- **Vertical** — the one and only unit. There is no second noun (Module, Companion, and Appendix were all considered and dropped). Every vertical carries two fields:
  - `required: true | false` — whether it runs on every Workspace regardless of Target, or only when triggered.
  - `gate` — empty when `required: true`; otherwise, a recon-confirmed signal describing the trust boundary that has to actually be observed (never a keyword or dependency-name guess, per [ADR 0011](../adr/0011-playbook-verticals-are-required-or-gated.md)).

`GLOSSARY.md` needs two new formal entries for **Playbook** and **Vertical** (currently "vertical" only appears in passing inside the `Harness` entry, and "Playbook"/"Spine" has no entry at all), plus a light edit to `Harness` to say it loops over the Workspace's **Playbook**.

## 1. Why this document can't be the Playbook's source of truth

[ADR 0016](../adr/0016-no-hand-maintained-vertical-catalog.md) is unambiguous and was sharpened twice (Lynis's silently-stale `db/tests.db`, then the Anthropic-Cybersecurity-Skills audit's "a document that says 'generated' and isn't checked is worse than one that honestly says 'hand-maintained'"). Whatever lists the Playbook's verticals — for the ledger, a status display, anything — has to be **computed by reading the skill files directly**, by a generator that is itself a committed, CI-checked artifact with a check that fails a PR on drift. A markdown table in this document, however complete, would be exactly the second hand-maintained index ADR 0016 exists to prevent.

So this document does three things instead: proposes the per-vertical schema the generator reads (§2), offers the current core plus the newly reserved verticals as an **illustrative, non-canonical** starting point (§3–4), and lays out the generator/CI mechanism ADR 0016 requires (§6). Nothing here is the catalog. The skill files, once written, are.

## 2. Per-vertical schema (what the generator reads)

Synthesizing ADR 0005 (ledger), ADR 0008 (Oracle), ADR 0011 (required/gate), ADR 0014 (eval), ADR 0016 (generation), ADR 0017 (routing contract), and ADR 0019 (`needs-confirmation`), each vertical's skill file front-matter needs at least:

- `name` — stable identifier; per ADR 0004, this becomes part of a Finding's deterministic key, so renaming one later is a migration, not a free edit.
- `required` (bool) + `gate` (string, set only when `required: false`) — see §0.
- `oracle_mechanism` — which of ADR 0008's five shapes (out-of-band callback, control-vs-injected differential, observed-execution signal, cross-session access differential, independent-ground-truth differential) a `confirmed` Verdict in this vertical would need, or an explicit `none-identified` flag routing findings here to `needs-confirmation` (ADR 0019) instead of blocking the vertical's own terminal state.
- `exhaustion_criterion` — a machine-checkable description of what "no further avenues" means for this vertical specifically, since ADR 0005 requires the Harness to mechanically validate an exhaustion attestation, not just accept the agent's say-so.
- `description`, `use_when`, `do_not_use_for` — the three-part routing contract ADR 0017 requires, lint-checked, needed precisely because fine-grained near-neighbor verticals (IDOR vs. BOLA vs. BFLA) are exactly where ambiguous routing becomes a real failure mode.
- `eval_fixtures` — pointer to at least one known-vulnerable and one known-clean fixture for this vertical, per ADR 0014's precision requirement.

No `signature` field for now — community-contributed verticals are out of scope until that changes (ADR 0022 only applies once they're accepted).

## 3. The current required set (illustrative, not canonical)

Multiple audits (PayloadsAllTheThings, Anthropic-Cybersecurity-Skills, Cloudflare, Shannon) refer to an existing 11-item baseline, confirmed in the committed research files themselves: **injection, access control, business logic, auth/session, SSRF, CSRF, deserialization, known-CVE, information disclosure, file handling, client-side**. This round added a twelfth: **race conditions**, given its own top-level, always-required slot rather than being folded into business logic — it's a technique that can hit any stateful operation (auth, access control, payments), not a business-logic-specific concern, so it clears the same "genuinely universal" bar the other required verticals do. No file anywhere declares this list canonical — it's only ever referenced in prose, which is itself consistent with ADR 0016 already being honored at the research-note level.

**Added via §8 (two cross-check rounds):** **configuration/deployment-management** (default creds, exposed admin panels, backup/old files, HTTP methods, directory listing) and **cryptography/TLS-weakness** (weak ciphers, padding oracle, cert validation, weak hashing, insecure randomness) — top-level and universal in every source checked across both rounds, including OWASP Top 10:2025 ranking them #2 and #4. That makes 13.

**Still unresolved, not decided either way:** **deserialization**'s required-vs-gated classification. PortSwigger's own taxonomy places it under "Advanced," not universal server-side, and its real trigger (observing a serialized-object format on the wire) looks structurally like a `gate` condition rather than a `required` one, by ADR 0011's own bar. But the CWE Top 25's real-world frequency×severity ranking puts it at #16, ahead of SSRF (#19) — a real-impact argument pointing the other way. SSRF itself is settled as required: PortSwigger's own grouping supports it, and nothing since has challenged that.

## 4. Reserved (gated) verticals — names and gates only, detail on first real use

Per this round's decision: these get a name and a `gate` now; the actual how-to-check-it procedure is written the first time a real Target actually needs it, not before.

| Vertical | `gate` (recon-confirmed signal) |
|---|---|
| Request smuggling (front-end/back-end parsing discrepancy) | A confirmed intermediary (reverse proxy, CDN, LB) observed in front of the Target via a header/framing differential |
| Cache poisoning | A confirmed caching layer observed in front of the Target (cache-control/vary behavior, cache-hit headers) |
| GraphQL | A confirmed `/graphql`-equivalent endpoint responding to an introspection probe |
| WebSocket | A confirmed WebSocket upgrade handshake observed in traffic |
| Rate-limiting / brute-force | A confirmed unauthenticated or low-friction repeatable action (login, OTP, coupon) |
| Denial of service / ReDoS | A confirmed algorithmically-expensive endpoint behavior observed during recon |
| Supply chain (dependency confusion, exposed keys, SCM misconfig) | A confirmed CI/build pipeline or package-registry surface reachable/observable |
| AI/LLM agent abuse | A confirmed LLM-backed endpoint (observed structured prompt/response behavior) |
| Host header attacks *(added via §8)* | The Target builds a URL/link (password reset, absolute link) from the request's Host header rather than a fixed value, confirmed by reflection |
| OAuth / JWT handling *(added via §8)* | A confirmed OAuth authorization/token endpoint or a JWT-shaped token (`eyJ...` structure or `Authorization: Bearer`) in use |

The original "proxy/transport parsing discrepancies" row above has been split in two per the cross-check: request smuggling and cache poisoning are triggered by different observable signals (an intermediary's parsing behavior vs. a caching layer's own behavior), so one gate was conflating two distinct trust boundaries. **DoS/ReDoS stays reserved, but its gate is still unwritten, not just weak**: the category itself is real and industry-recognized (Bugcrowd rates "Application-Level DoS" as first-class), but across five sources checked (WSTG, ASVS, PortSwigger, Bugcrowd, CWE) none describes a safe, confirmable pre-test trigger for it the way the other nine have one. Supply chain's gate stays as-is: OWASP Top 10:2025 ranks supply-chain failures #3, but its own page says real detection needs SBOM/dependency-scanning tooling, not a live recon signal, so a reachable CI/build-pipeline surface remains the right-shaped gate for what exhaust can actually test for live.

Cloudflare's further domain companions (memory-safety/kernel, desktop/IPC, cloud/IaC, protocols/RPC, resource exhaustion, data lifecycle) go past exhaust's actual hunting targets to date (Roundcube, Webmin, ispmanager, Mail-in-a-Box — server-side web apps). Not reserved yet; add only once recon on a real Target actually surfaces that trust boundary.

HTTP Host header attacks (a PortSwigger "Advanced" topic, distinct from request smuggling since it needs no intermediary) and OAuth/JWT handling (ASVS gives each its own top-level chapter, V9 and V10) were flagged by the first cross-check as absent, then added to the table above via §8 — both sit closer to exhaust's actual past targets than the Cloudflare companions above.

File-upload-specific coverage and web-application-specific known-CVE coverage are confirmed thin everywhere, including in the best comparable library — not unique to us, but worth strengthening under the existing `file handling` and `known-CVE` required verticals rather than splitting out new ones.

## 5. Ledger states (ADR 0005 + ADR 0015, formalized this round)

`pending` → `in_progress` → one of:
- `retryable` — a known, resumable failure (crashed, rate-limited); safe to pick back up automatically.
- `blocked` — a real-Target action left with an ambiguous outcome; needs a person before this vertical moves again (never silently retried, per ADR 0015).
- `terminal` (`exhausted` or `skipped`) — reached only via a logged gate-exclusion, or a Harness-validated, typed self-report attestation (ADR 0007) that the vertical's `exhaustion_criterion` (§2) is met. A finding parked at `needs-confirmation` (ADR 0019) doesn't block its vertical from going terminal.

## 6. The generator (what ADR 0016 actually requires)

A generator script, committed to the repo, written in Python (matching ADR 0002), that reads each vertical skill file's front-matter (§2) and emits the derived catalog/ledger-schema. It runs two ways: as a local command (regenerate after adding or editing a vertical) and as a CI check that fails a pull request if the generated artifact is out of sync with the skill files — both required, not either/or. Nothing reads from a cached or hand-edited catalog file; the Lynis lesson was specifically that the engine never even read its own stale index, only a display helper did, which is exactly how staleness goes unnoticed.

## 7. Open questions only you can settle

1. **The concrete module — now vertical — catalog beyond §3–4.** ADR 0011 explicitly leaves this open.
2. **Per-vertical Oracle mechanism assignment**, especially for verticals where no mechanism is evident yet (certain business-logic or purely analytical checks) — these should be flagged `none-identified` rather than forced into a Verdict they can't earn.
3. **Where the generator actually lives and what writes it** — Python is settled; the schema/directory layout is still a real implementation decision.
4. **The exact shape of the "forced self-report turn" tool contract** (ADR 0005 + ADR 0007) — established that it must be a typed, Harness-validated call, not what it mechanically checks per vertical.
5. **How deep sub-vertical decomposition goes** beyond the IDOR/BOLA/BFLA example ADR 0017 already names.
6. **Whether/when the Playbook accepts community-contributed verticals at all** — settled as "not now" this round; revisit if that changes, since it decides whether the §2 schema needs a `signature` field.
7. **Whether deserialization should move from required to gated** — still genuinely unresolved, not just unwritten: PortSwigger's "Advanced" grouping argues gated, but the CWE Top 25's real-world frequency×severity ranking puts it at #16, ahead of SSRF (#19) — two primary sources pointing opposite ways. See §8.
8. **Whether the DoS/ReDoS gate signal is salvageable at all.** Settled that the category itself is real and industry-recognized (Bugcrowd rates it as first-class) — the open part is narrower now: nobody checked across five sources (WSTG, ASVS, PortSwigger, Bugcrowd, CWE) describes a safe, confirmable *pre-test* trigger for it. See §8.
9. **Where open redirect (Bugcrowd's "Unvalidated Redirects and Forwards") goes** — a clean gap with no record anywhere in this document: its own small required vertical, or folded into `access control`'s or `client-side`'s procedure. See §8.
10. **Writing a procedure note into `information disclosure`, `access control`, and `business logic`** instructing the agent to specifically probe error paths and exception handling — OWASP's 2025 "Mishandling of Exceptional Conditions" category's substance already falls inside those three verticals' scope; this isn't a new vertical, just unwritten instruction. See §8.

## 8. Second round: resolved via two cross-checks (OWASP WSTG/ASVS/PortSwigger, then OWASP Top 10:2025/Bugcrowd VRT/CWE Top 25)

Resolved, not just flagged this time:

- **Configuration/deployment-management and cryptography/TLS-weakness join the required set**, bringing it to 13 (soon 14, pending §7.7-9). Confirmed by two independent rounds: WSTG/ASVS first, then OWASP Top 10:2025 ranking them #2 and #4 respectively — not a marginal case either time.
- **Host header attacks and OAuth/JWT handling join the reserved (gated) set**, bringing it to 9: Host header attacks gated on "the Target builds a URL/link from the request's Host header rather than a fixed value, confirmed by reflection"; OAuth/JWT gated on "a confirmed OAuth endpoint or JWT-shaped token in use." Both closer to exhaust's actual target history than the Cloudflare companions already declined, and both have clean confirmable gates the way the original seven do.
- **Supply chain stays reserved, not promoted**, despite OWASP Top 10:2025 ranking it #3: fetched that category's own page directly, and OWASP's own description says it's genuinely hard to test for live — detection relies on SBOM/dependency-scanning tooling, a different mechanism than a confirmable recon signal against a running Target. Its existing gate (a reachable CI/build pipeline or package-registry surface) stays as the right shape for what exhaust can actually test for.
- **Insecure Design and Security Logging/Alerting Failures (OWASP 2025) are declined, not silently absent**: both checked directly and found genuinely inapplicable to exhaust's external black-box model — Insecure Design is a secure-development-process concern with no externally-confirmable trust boundary to gate on; Security Logging/Alerting needs visibility into the Target's own logs, which an external agent doesn't have.

Not resolved, narrowed instead (see §7): deserialization's required-vs-gated classification, the DoS/ReDoS gate signal, open redirect's placement, and the error-handling procedure note for three existing verticals.

## What this settled

Vocabulary (Playbook, Vertical, `required`/`gate`), the ledger's `retryable`/`blocked` split, race conditions as a required vertical, nine reserved gated verticals (name + gate only), no community contributions for now, and a Python generator that runs both locally and in CI. The required set is now 13 (config/deployment-management and crypto/TLS added via §8), pending deserialization's still-open classification. Not locked: the full catalog, Oracle-mechanism mapping, and the self-report tool schema — all deliberately deferred to real implementation and real targets, not silently assumed.
