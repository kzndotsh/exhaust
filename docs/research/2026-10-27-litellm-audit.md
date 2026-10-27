# Research: LiteLLM, as the mechanism behind ADR-0021's credential proxy

LiteLLM has come up repeatedly across the other two research docs (the oss-crs audit's
production credential-isolation pattern, the harness-engineering audit's Task Runners &
Orchestration list, and informally in conversation) without ever getting its own dedicated read.
This closes that gap. Input to ADR-0021's eventual implementation, not a recommendation to adopt
it outright — the question of whether exhaust builds its own minimal proxy or reaches for LiteLLM
is still open, but this document establishes what LiteLLM actually does and doesn't do, so that
question can be answered with facts instead of a vague "it's the standard thing people use."

All sources below were fetched directly from `docs.litellm.ai`, 2026-10-27, via its `llms.txt`
index and the specific pages it links. Nothing here is secondary-sourced.

## 1. What it is — two separable things, not one

LiteLLM is actually two artifacts sharing one name, and conflating them is the most common
source of confusion in casual mentions of "LiteLLM":

- **The `litellm` Python SDK**: a library that translates `litellm.completion(...)` and
  `litellm.embeddings(...)` calls into whatever shape a given provider's API actually wants,
  presenting one OpenAI-compatible call signature over 100+ providers. This is the part that
  would compete with, or complement, an exhaust `AgentSession` adapter — it's a marshaling layer,
  not a service.
- **The LiteLLM Proxy / AI Gateway**: a standalone server (`simple_proxy`) built on top of the
  SDK, run as its own process, that callers talk to over HTTP exactly as if it were the OpenAI
  API. This is the part relevant to ADR-0021: it's the thing that would sit between exhaust's
  `AgentSession` adapter and the real provider, holding the real credentials so the adapter never
  does.

The rest of this document is almost entirely about the Proxy, since that's the artifact ADR-0021
actually needs.

## 2. Virtual keys — the actual mechanism ADR-0021 is describing

**Concrete shape.** A virtual key is an `sk-`-prefixed string the proxy issues, created by
`POST /key/generate` authenticated with the proxy's own master key (`LITELLM_MASTER_KEY`). A
caller then authenticates to the proxy with that virtual key, as a normal `Authorization: Bearer
sk-...` header on an OpenAI-shaped route like `/chat/completions`, and never sees or needs the
real provider credential — the proxy holds that separately and attaches it internally before
forwarding the call upstream.

**Scoping fields**, all settable at creation time: `models` (an explicit allowlist of which
models this key may call — `all-team-models` and `no-default-models` are special values),
`aliases` (remaps a requested model name to a model group, so traffic can be redirected without
changing caller code), `max_budget` / `budget_duration` (a USD spend cap with a reset period —
exactly the "budget-capped" half of ADR-0021's own phrasing), `duration` (a relative TTL like
`"30d"`, stored as an absolute `expires` timestamp — the other half, since a key that expires is
functionally a per-run credential if `duration` is set to the run's expected lifetime), `tpm_limit`
/ `rpm_limit` / `max_parallel_requests` (rate limits), `team_id` / `user_id` (ownership for spend
rollup), `allowed_routes` (restricts which proxy endpoints the key can hit at all, not just which
models), and a free-form `metadata` object. A full example:

```bash
curl http://0.0.0.0:4000/key/generate \
  -H "Authorization: Bearer <master-key>" \
  -H "Content-Type: application/json" \
  -d '{"models": ["gpt-6-luna"], "team_id": "<team-id>", "duration": "30d",
       "max_budget": 10, "budget_duration": "30d", "rpm_limit": 60,
       "metadata": {"user": "dev@example.com"}}'
```

**Lifecycle operations**: `POST /key/block` / `/key/unblock` to suspend or restore a key without
deleting it, `POST /key/update` to change scoping on an existing key, `POST
/key/<key>/regenerate` to rotate the key string itself (Enterprise-only, with an optional
`grace_period` so the old string keeps working during cutover), and `auto_rotate: true` with a
`rotation_interval` for scheduled rotation without a manual call. `GET /key/info?key=<key>`
returns current spend and settings for auditing.

**This is, almost field-for-field, what ADR-0021 describes wanting**: a budget-capped virtual
key issued per run, with the real credential never reaching the agent process. The one gap: the
delivery mechanism ADR-0021 specifies — "mounted as a file rather than an environment variable" —
is an exhaust-side decision about how the harness hands the issued key string to whatever spawns
the agent process, not something LiteLLM itself prescribes. LiteLLM's job ends at issuing the
key string via its API; where exhaust puts that string afterward is still exhaust's own design
question.

## 3. Life of a request — the proxy's actual request pipeline

Fetched from the architecture page directly, the documented sequence is:

1. A caller sends a request to the proxy with a virtual key.
2. **Auth and budget check**: the Bearer token is validated and checked against its budget,
   reading from a Redis or in-memory cache first, falling back to Postgres on a cache miss. This
   is the only synchronous database read in the whole request path.
3. **Rate limiting**: checked at four nested scopes simultaneously — global server, virtual key,
   user, team.
4. **Endpoint handling**: `proxy_server.py` serves the OpenAI-shaped routes and hands off to the
   **Router**.
5. **Router**: load balancing, fallbacks, and retries, internally as `function_with_fallbacks`
   wrapping `function_with_retries` wrapping a base `litellm.completion`/`litellm.embeddings`
   call. Retries stay within the same model group (same `model_name`); a *fallback* is what
   crosses to a different model group.
6. **Provider call via the SDK**: the actual translation to the upstream provider's wire format,
   including downloading and re-encoding image URLs as base64 for providers that don't accept
   URLs directly (capped at 50MB per download, up to 10 cached in memory).
7. **Asynchronous post-processing**: logging to external observability sinks (Lunary, MLflow,
   Langfuse are named), rate-limiter bookkeeping across all four scopes, and spend/usage writes
   to Postgres via `_ProxyDBLogger`.

The one architectural fact worth internalizing for anyone designing something similar: **nearly
every database write happens after the response has already gone back to the caller.** Budget
enforcement on the way in is cache-first and synchronous; spend recording on the way out is
async. That's a deliberate latency/consistency tradeoff — a caller could in principle burst past
a budget cap within one cache-refresh window before the next request sees the updated spend — not
a flaw the docs hide, just a design decision worth knowing about if exhaust's own instinct is "a
budget cap should be exact."

## 4. Routing, model groups, and fallbacks — the multi-backend-adapter overlap

This is the section most directly relevant to the open "what AI powers the harness, how dynamic
can it be" question from the architecture discussion elsewhere in this research.

**A model group is just every deployment sharing one `model_name`.** Nothing requires those
deployments to be the same provider — the documented example groups an Azure OpenAI deployment
and a plain OpenAI deployment under one alias, and a cost-based-routing example groups an OpenAI
model with a Groq model. A caller requests the alias; the Router picks which actual deployment
serves it. This means LiteLLM already *is* a generic "one logical model, many interchangeable
backends" abstraction — conceptually adjacent to, though a layer below, an `AgentSession` backend
adapter. It doesn't know anything about agent loops, tool calls, or turn semantics; it only
abstracts the model-call layer underneath wherever exhaust's own backend adapter lives. If
exhaust ever wants "same AgentSession adapter, swap the underlying model/provider without code
changes," routing that adapter's HTTP calls through a LiteLLM-fronted model group is a way to get
provider-swapping almost for free, one level below exhaust's own abstraction rather than instead
of it.

**Load-balancing strategies** (selectable per router or per named routing group): `simple-shuffle`
(the documented default and recommendation for production — rpm/tpm-weighted or random, with an
optional `weight` field to skew traffic), `usage-based-routing` (routes to whichever deployment
has the lowest current-minute TPM usage; the docs explicitly say this "is not recommended for
production due to performance impacts"), `latency-based-routing` (tracks recent response times
per deployment), `least-busy` (fewest in-flight calls), `cost-based-routing` (cheapest healthy
deployment by the model cost map, defaulting unknown models to $1), and a custom-strategy
extension point via subclassing.

**Fallbacks are a distinct concept from retries and from routing.** A retry (`num_retries`) tries
the *same* model name again; a fallback (`fallbacks: [{"gpt-6-luna": ["gpt-6.1-sol"]}]`) only
fires after retries are exhausted, and crosses to a *different* model group entirely. Three
fallback types exist for three different failure classes: `fallbacks` (the catch-all, including
rate limits and server errors), `content_policy_fallbacks` (specifically
`ContentPolicyViolationError`), and `context_window_fallbacks` (specifically
`ContextWindowExceededError`, requiring `enable_pre_call_checks: true` to catch it before the call
rather than after). `allowed_fails` and `cooldown_time` put a repeatedly-failing deployment into a
cooldown window rather than retrying it immediately. The proxy re-checks the fallback target
against the *caller's own* model access and budget before using it (`enforce_fallback_model_access`
/ `enforce_fallback_budget` can disable this), so a fallback can't be used to route around a
key's own scoping.

**This is directly relevant to the earlier, unresolved "route to a different backend when one
declines" question** (raised in the DeepSeek research): `content_policy_fallbacks` is
*structurally* the closest existing mechanism found anywhere across all three research docs to
that exact idea — a documented, first-class config option that reroutes specifically on a content
policy violation, not just on outages or rate limits. It's worth being precise about what it
actually catches, though: `ContentPolicyViolationError` is the error a *provider's own API*
returns when it refuses a request, not a heuristic exhaust would invent. Whether a given model's
hedging/declining behavior on a security-research task actually raises that specific exception
type, versus just answering reluctantly in prose, is unverified and would need direct testing
against whichever provider exhaust is routing through — this doesn't settle the open question,
but it gives it a concrete mechanism to test against instead of nothing.

## 5. Credential and secret management

**External secret manager integration** (confirmed Enterprise-licensed feature, not community):
the proxy can read provider credentials from AWS Secret Manager, Azure Key Vault, Google Secret
Manager, HashiCorp Vault, or CyberArk Conjur, configured via a required
`general_settings.key_management_system` value, with `access_mode` controlling whether the proxy
reads, writes, or both (default read-only), and `store_virtual_keys` controlling whether
LiteLLM-issued virtual keys themselves get written back into the secret manager. The documented
example configs contain no literal credential values, only settings and names, which is
consistent with — though the fetched page doesn't state outright — real provider keys living
only in the secret manager and being referenced by name rather than embedded in `config.yaml` or
the proxy's own environment.

**Per-team/per-project credential routing** (a separate, non-Enterprise-gated feature, off by
default behind `enable_model_config_credential_overrides: true`): the same model name can resolve
to *different* provider credentials depending on which team or project's key made the call —
the documented use case is "separate Azure OpenAI instances per business unit for cost isolation,
data residency, or rate limit separation." Precedence, most specific first: clientside credentials
in the request body, project-level model override, project default, team-level model override,
team default, then the deployment default from `config.yaml`. This is a second, independent
multi-tenancy mechanism from virtual keys' own scoping — virtual keys answer "what can this caller
do," credential routing answers "which actual upstream account does this caller's traffic
actually bill against," and the two compose.

**Rotation guidance**: the security-best-practices page is explicit that `LITELLM_SALT_KEY`
should never be rotated after credentials have been stored (it's used to encrypt them at rest, so
rotating it without a migration step breaks decryption), and that the master key should never be
handed to applications or end users — "Applications and users should use scoped Virtual Keys, not
the LiteLLM master key," with a separate service-account key per production workload so one
compromised/misbehaving workload's key can be revoked without affecting the others.

## 6. Guardrails — a pre/during/post-call gate, directly comparable to exhaust's own gates

**Concrete shape.** A guardrail is configured in `config.yaml` with a `guardrail_name`, a
provider (Presidio, Lakera, Aporia, Bedrock, Azure content moderation, OpenAI Moderation, Cato
Networks, Guardrails AI, or LiteLLM's own built-in content filter are all named integrations, plus
a generic custom-code extension point), and a `mode` that places it in the request pipeline:
`pre_call` (before the model ever sees the input), `during_call` (concurrent with the model call,
withholding the response until the check completes), `post_call` (after the response, checking
both input and output), or `logging_only` (observes and records a verdict without altering
anything the caller sees). Modes can combine (`mode: [pre_call, post_call]`). A blocked request
returns a 400 with a message like "Violated guardrail policy"; a guardrail like Presidio can also
*modify* rather than block, masking specific PII entity types (`CREDIT_CARD: "MASK"`) in place
rather than refusing the whole call.

**Why this is worth comparing to exhaust directly, not just noting as a feature list.** LiteLLM's
guardrails are a gate on the *model-call* layer — they see the prompt text and the model's raw
output, nothing about what tool call or action that output will eventually trigger inside
whatever harness is consuming it. exhaust's own gates (the Scope Contract re-check, the Rig's
call-gate allowlist, evidence promotion) sit one layer up, on the *action* a harness has already
decided to attempt, with full knowledge of structured fields (`target`, `tool`, `method`,
`params`) that a guardrail operating on raw text never sees. The two are complementary, not
competing: a LiteLLM guardrail could catch something at the token-stream level (PII leaking into
a prompt, a jailbreak-shaped completion) that never becomes a structured `AgentAction` at all, and
exhaust's own gate catches something a text-level guardrail structurally cannot, because it
requires knowing that *this specific call* is a `RealTargetCall` whose `target` field needs
re-checking against a Scope Contract that doesn't exist at the model-call layer at all. If exhaust
ever puts a LiteLLM proxy between its backend adapter and a real provider, a guardrail there
would be one more layer, not a substitute for anything exhaust's Harness already does.

## 7. Security best practices — a direct checklist against exhaust's own posture

Fetched from the dedicated security page; grouped as that page groups them:

- **Secrets**: store provider credentials, the master key, and the salt key in a secret store,
  never in `config.yaml` or source control; one service-account key per production workload.
- **Versioning**: pin an exact version or image digest, never `latest`; verify the Docker image
  signature before deploying.
- **Network**: run the gateway on a private network where possible; expose only the routes
  clients actually need; TLS on both client-to-gateway and gateway-to-provider legs with
  certificate verification kept on; suppress identifying headers (`Server`); disable the
  auto-generated API docs in production (`NO_DOCS`, `NO_REDOC`, `NO_OPENAPI`), since unauthenticated
  docs expose every route to anyone who finds the gateway.
- **Auth**: least-privilege RBAC roles, a small admin population, disabling the shared
  environment-variable admin login once real accounts/SSO exist (the docs call it bluntly "a
  permanent, shared, cleartext admin credential... a bootstrap mechanism only"), rate-limiting
  failed admin sign-ins, and preferring short-lived JWTs over long-lived keys for API traffic
  where an identity provider is available.
- **Audit**: enable and review audit logs for administrative changes specifically — key
  creation/deletion, role changes, team changes — not just request-level logging.
- **Input/output controls**: guardrails for sensitive workloads, file-upload extension allowlists
  and size caps.

**What the page doesn't cover, worth flagging rather than assuming it's handled**: there's no
dedicated database-security section (the proxy's state — keys, spend, budgets — lives in
Postgres, and nothing in this page discusses hardening that store specifically), and the page
doesn't explicitly state the "real provider keys are isolated from every caller, including the
proxy operator" property in so many words — it's implied by the secret-manager and
virtual-key-vs-master-key guidance, not asserted as a standalone security property with its own
threat model, the way exhaust's own Scope Contract or evidence-promotion docstrings state their
threat model explicitly.

## 8. Relevance to exhaust and ADR-0021

**What this confirms**: ADR-0021's shape — a local proxy issuing a budget-capped virtual key per
run, the agent process never holding the real credential — is not a novel design exhaust invented
for itself; it's close to a direct description of LiteLLM's own flagship feature, built,
documented, and production-hardened by a project with its own security team and CVE process. If
exhaust implements ADR-0021 by standing up a LiteLLM proxy rather than hand-rolling an equivalent,
it inherits: budget/TTL-scoped keys for free, the fallback/routing layer as a bonus (not required
by ADR-0021, but available), guardrails as an optional additional gate, and a documented,
externally-reviewed security posture instead of a bespoke one — directly relevant given the
security audit's own repeated warning that "the weakest layer is the one you built yourself."

**What's still exhaust's own decision, not something LiteLLM settles**:

1. **Where the issued key string goes.** LiteLLM issues an `sk-...` string via its API; ADR-0021's
   "mounted as a file, not an environment variable" delivery mechanism is exhaust's own harness
   logic, wiring the key from LiteLLM's `/key/generate` response into whatever process spawns the
   agent backend.
2. **Whether to run LiteLLM at all versus a minimal bespoke proxy.** LiteLLM is a large,
   general-purpose gateway (100+ providers, enterprise RBAC, multi-region deployment, a whole
   secret-manager integration layer) built for multi-tenant SaaS operation. A huge fraction of
   that is irrelevant to exhaust's current single-harness-per-Workspace stage — this is the same
   "don't import a hosted product's architecture because that's what the hosted product does"
   caution the production-infrastructure research already raised about TrueFoundry and Claude
   Managed Agents. Standing up Postgres, a master key, and an RBAC model to get "one capped key
   per run" is a heavier dependency than the problem obviously requires at exhaust's current
   scale, even though the feature itself is exactly right.
3. **The budget-enforcement timing gap.** Spend recording is asynchronous (§3); a budget cap is
   therefore a soft, eventually-consistent limit, not an instantaneous hard stop. Whether that's
   acceptable for exhaust's own ADR-0021 budget intent — presumably meant to bound how much a
   single compromised or runaway agent run could spend — is worth a deliberate check rather than
   an assumption, since "budget-capped" in the ADR's own language could be read as stricter than
   what the mechanism underneath it actually guarantees.
4. **Credential routing's `content_policy_fallbacks` is a concrete thing to test**, not a settled
   answer, for the "route to a different backend on a decline" question raised elsewhere — it
   exists, it's documented, and it's scoped to a real provider-returned exception type rather than
   a heuristic exhaust would have to invent; whether that exception type actually fires for the
   specific declining behavior exhaust cares about is an empirical question, not something this
   research settles by reading docs.
5. **Guardrails are additive, not a replacement for the Harness's own gates** (§6) — worth stating
   explicitly in any future ADR that references LiteLLM, so nobody later assumes "we have
   guardrails at the proxy" covers what the Scope Contract and Rig call-gate are actually for.

## Sources

All fetched directly from `docs.litellm.ai`, 2026-10-27:

- `llms.txt` (index)
- `docs/proxy/virtual_keys.md`
- `docs/proxy/architecture.md`
- `docs/proxy/security_best_practices.md`
- `docs/proxy/reliability.md`
- `docs/secret_managers/overview.md`
- `docs/proxy/guardrails/quick_start.md`
- `docs/routing.md`
- `docs/proxy/credential_routing.md`

Not fetched, named in `llms.txt` but out of scope for this pass: the full API reference for every
`/key/*`, `/team/*`, `/user/*` endpoint; the Enterprise RBAC/SSO/SCIM pages beyond what the
security-best-practices page summarizes; the Rust AI Gateway (beta); and the individual
provider-specific pages (Bedrock, Azure, etc.) beyond what the routing and model-group examples
already covered. A follow-up pass would need those only if exhaust actually moves to implement
ADR-0021 against LiteLLM specifically, not before.
