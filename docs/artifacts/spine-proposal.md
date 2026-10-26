# Spine proposal (draft) — not locked

This is a draft for discussion, synthesized from three parallel reviews of every file in `docs/research/`, every ADR in `docs/adr/`, and `GLOSSARY.md`. It is explicitly **not** the spine lock. Per standing instruction, the spine stays unlocked until you say the audit campaign is done, and in any case [ADR 0016](../adr/0016-no-hand-maintained-vertical-catalog.md) means this document can never *become* the spine's source of truth even once locked — see §1 for why, and §6 for what the real source of truth has to look like instead.

## 0. A glossary gap this proposal exposes

Before anything else: **"Spine" is not a formally defined glossary term**, and "Vertical" only appears once, in passing, inside the `Harness` entry. Worse, three ADRs use three overlapping nouns without stating how they relate: ADR 0005 and ADR 0016 use **vertical** as the general unit; ADR 0011 uses **class** for the always-on core items and **module** for the recon-gated ones, never stating that a module is a kind of vertical. A reader has to infer the hierarchy. This proposal assumes the following resolution, but it's a domain-modeling decision for you to confirm or correct, not something I'm imposing:

> **Spine**: the whole structure — a Workspace's full set of verticals, both always-on and gated.
> **Vertical**: the atomic unit the per-vertical ledger tracks (ADR 0005) — something the Harness can mark pending, in-progress, errored, or terminal.
> **Module**: a *kind* of vertical specifically — one that's recon-gated rather than always-on (ADR 0011). Every module is a vertical; not every vertical is a module (the always-on ones aren't gated, so calling them "modules" would be wrong).

If you agree, I'd add these three as proper `**Term**: ... _Avoid_: ...` entries to `GLOSSARY.md`, and lightly edit the `Harness` entry to say it loops over the Workspace's **spine** rather than its "checklist of verticals," so the glossary's own cross-references hold together. Not done yet — flagging it for your call first, per how `GLOSSARY.md` is supposed to work.

## 1. Why this document can't be the spine's source of truth

[ADR 0016](../adr/0016-no-hand-maintained-vertical-catalog.md) is unambiguous and was sharpened twice (Lynis's silently-stale `db/tests.db`, then the Anthropic-Cybersecurity-Skills audit's "a document that says 'generated' and isn't checked is worse than one that honestly says 'hand-maintained'"). Whatever lists the spine's verticals — for the ledger, a status display, anything — has to be **computed by reading the skill files directly**, by a generator that is itself a committed, CI-checked artifact with a check that fails a PR on drift. A markdown table in this document, however complete, would be exactly the second hand-maintained index ADR 0016 exists to prevent.

So this document does three things instead: proposes the *shape* every vertical's skill file needs to declare (§2), offers the current 11-vertical core as an **illustrative, non-canonical** starting point plus the gaps this round of audits surfaced (§3–4), and lays out the generator/CI mechanism ADR 0016 requires (§6). Nothing here is the catalog. The skill files, once written, are.

## 2. Per-vertical metadata schema (what the generator reads)

Synthesizing ADR 0005 (ledger), ADR 0008 (Oracle), ADR 0011 (core/module split), ADR 0014 (eval), ADR 0016 (generation), ADR 0017 (routing contract), and ADR 0019 (`needs-confirmation`), each vertical's skill file front-matter needs at least:

- `name` — stable identifier; per ADR 0004, this becomes part of a Finding's deterministic key, so renaming one later is a migration, not a free edit.
- `gating` — either `core` (always-on) or a recon-confirmed signal description for a module. Per ADR 0011, a module's gate must name an observed fingerprint ("a confirmed `/graphql` endpoint responding to an introspection probe"), never a keyword or dependency-name guess.
- `oracle_mechanism` — which of ADR 0008's five shapes (out-of-band callback, control-vs-injected differential, observed-execution signal, cross-session access differential, independent-ground-truth differential) a `confirmed` Verdict in this vertical would need, or an explicit `none-identified` flag routing findings here to `needs-confirmation` (ADR 0019) instead of blocking the vertical's own terminal state.
- `exhaustion_criterion` — a machine-checkable description of what "no further avenues" means for this vertical specifically, since ADR 0005 requires the Harness to mechanically validate an exhaustion attestation, not just accept the agent's say-so.
- `description`, `use_when`, `do_not_use_for` — the three-part routing contract ADR 0017 requires, lint-checked, needed precisely because fine-grained near-neighbor verticals (IDOR vs. BOLA vs. BFLA) are exactly where ambiguous routing becomes a real failure mode.
- `eval_fixtures` — pointer to at least one known-vulnerable and one known-clean fixture for this vertical, per ADR 0014's precision requirement.

## 3. The current core (illustrative, not canonical)

Multiple audits (PayloadsAllTheThings, Anthropic-Cybersecurity-Skills, Cloudflare, Shannon) refer to an existing 11-item baseline, confirmed in the committed research files themselves: **injection, access control, business logic, auth/session, SSRF, CSRF, deserialization, known-CVE, information disclosure, file handling, client-side**. No file anywhere declares this list as canonical — it's only ever referenced in prose, which is itself consistent with ADR 0016 already being honored at the research-note level. Offered here as the known starting point, not a decision.

## 4. Gaps and candidates surfaced by this round of audits

**Flagged as homeless by independent sources, worth a core or module slot:**
- **Proxy/transport parsing discrepancies** (request smuggling, cache poisoning, part of the WebSocket surface) — PayloadsAllTheThings and Anthropic-Cybersecurity-Skills both independently flag this as having no home, and PayloadsAllTheThings proposes exactly this grouping since all three share one root cause (a proxy or cache disagreeing with the origin about how to parse a message). Gating signal: a confirmed intermediary observed in front of the Target (header/behavior differential), not an assumption from hosting provider.
- **GraphQL-specific testing** — currently scattered across injection/info-disclosure/access-control in PayloadsAllTheThings; absent entirely from Anthropic-Cybersecurity-Skills. Gating signal: confirmed `/graphql`-equivalent endpoint responding to an introspection probe.
- **WebSocket-specific testing** — same situation. Gating signal: confirmed WebSocket upgrade handshake observed in traffic.
- **Rate-limiting / brute-force** as its own control, not just a side effect of auth testing (PayloadsAllTheThings gap).
- **Denial of service / ReDoS** — no current home (PayloadsAllTheThings gap).
- **Supply chain** (dependency confusion, exposed keys, insecure SCM config) — PayloadsAllTheThings gap; nuclei-templates' `exposures`/`misconfiguration` taxonomy is the closest machine-checkable analog.
- **AI/LLM agent abuse** — for a Target that itself embeds an LLM. Cloudflare's skill carries this as a domain module; PayloadsAllTheThings calls it the clearest novel gap; SecLists already has a sourced jailbreak dataset (Shen et al., CCS 2024) sitting in the Rig unused for this. Gating signal: a confirmed LLM-backed endpoint (observed structured prompt/response behavior), not a config-file mention of a provider name.

**Confirmed thin on both our side and the best comparable library (not an oversight unique to us):**
- File-upload-specific coverage.
- Web-application-specific known-CVE coverage (nuclei-templates' `classification` block — CVSS, CWE, EPSS, CPE — is the concrete mechanism to eventually drive this, keyed by detected product+version against a maintained feed, never a hand-curated narrative list).

**A genuine disagreement to resolve, not just a gap:** race conditions. PayloadsAllTheThings folds them into business logic; Anthropic-Cybersecurity-Skills treats them as a distinct class. Recommendation surfaced by the research: a named sub-class within business logic/injection, not a full top-level vertical — reserve top-level slots for genuinely cross-cutting, target-neutral concerns per ADR 0011.

**Cloudflare's remaining domain companions** (memory-safety/kernel, desktop/IPC, cloud/IaC, protocols/RPC, resource exhaustion, data lifecycle) go well past exhaust's actual hunting targets to date (Roundcube, Webmin, ispmanager, Mail-in-a-Box — server-side web apps). Not a conflict given the gated-module shape: adopt the gating mechanism, ship a narrower initial module set, and only add these as recon on a real Target actually surfaces the trust boundary they cover.

## 5. Ledger-state shape (feeds the Harness loop, ADR 0005 + ADR 0015)

The ledger's state enum is larger than ADR 0005's headline sentence implies once ADR 0015 is folded in:

- `pending`
- `in_progress`
- `errored` — itself needs to distinguish a known, resumable failure from a real-Target action with an ambiguous outcome, which ADR 0015 says must **block**, never silently retry.
- `terminal` — reached only via (a) a gate-exclusion logged with a reason, or (b) a Harness-validated, typed self-report attestation (ADR 0007) that the vertical's declared `exhaustion_criterion` (§2) is met. Findings parked at `needs-confirmation` (ADR 0019) don't block a vertical from going terminal; the vertical's *investigation* can be done even if a specific finding's Oracle confirmation is still pending.

Whether "errored" needs to be one state with a sub-flag or two sibling states is flagged by the ADR review as a genuine open design gap, not resolved here.

## 6. The generator (what ADR 0016 actually requires)

Not a nice-to-have: a generator script, committed to the repo, that reads each vertical skill file's front-matter (§2) and emits the derived catalog/ledger-schema; a CI check that fails a pull request if the generated artifact is out of sync with the skill files; ideally a self-healing commit on merge, the pattern ADR 0016 cites as the one that actually worked elsewhere. Nothing that reads from a cached or hand-edited catalog file — the Lynis lesson specifically was that the engine never even read its own stale index, only a display helper did, which is exactly how staleness goes unnoticed.

## 7. Open questions only you can settle

1. **The concrete module catalog.** ADR 0011 explicitly leaves this open. §3–4 above are candidates, not a decision.
2. **Per-vertical Oracle mechanism assignment**, especially for verticals where no mechanism is evident yet (certain business-logic or purely analytical checks) — these should be flagged `none-identified` rather than forced into a Verdict they can't earn.
3. **Where the generator actually lives and what writes it** — ADR 0002 suggests Python, but the schema/directory layout is a real implementation decision.
4. **The exact shape of the "forced self-report turn" tool contract** (ADR 0005 + ADR 0007) — established that it must be a typed, Harness-validated call, not what it mechanically checks per vertical.
5. **How the ledger's `errored` state subdivides** (§5).
6. **How deep sub-vertical decomposition goes** beyond the IDOR/BOLA/BFLA example ADR 0017 already names.
7. **Whether/when the spine accepts community-contributed modules at all** — this decides whether the §2 schema needs a signature/provenance field (ADR 0022) from day one or can add it later.

## What this settled

Nothing locked. This document exists to put a concrete shape in front of you — schema, not catalog; gaps, not decisions — so the actual spine-lock conversation has something specific to react to rather than starting from twenty-plus scattered audit files.
