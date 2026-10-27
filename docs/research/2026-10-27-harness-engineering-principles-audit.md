# Research: harness engineering — principles, jargon, and security posture

Companion to `docs/research/2026-10-27-agent-backend-abstraction-research.md`. That document
asks *how* a harness invokes/embeds an agent backend. This one asks what the wider field means
by "harness engineering" as a discipline — its vocabulary, its converging design principles,
and (most importantly for exhaust) its security threat model — and holds exhaust's existing
design up against it. Input to future ADRs, not a recommendation; several open questions are
flagged rather than settled.

Sourced from two curated lists, `ai-boost/awesome-harness-engineering` and
`walkinglabs/awesome-harness-engineering`, plus `AutoJunjie/awesome-agent-harness` and
`Picrew/awesome-agent-harness`, with nine parallel research passes each reading primary sources
directly (not just list entries) and reporting back cited findings. A third list the user
flagged, `0xsline/awesome-deepseek-harness`, turned out to be something else entirely — see
§9. Every section below states plainly which sources were fetched directly vs. found only via
search/secondary summary; several frontier-vendor blog posts (notably two OpenAI pieces)
returned HTTP 403 to automated fetching and are corroborated only via secondary sources —
flagged inline.

## 1. What "harness" means — and the one real definitional clash

**The near-universal shorthand**: *Agent = Model + Harness* — "everything in an AI agent except
the model itself." Every source agrees on this much. They disagree on *scope and layering*:

- **Martin Fowler** (user-facing article): narrows "harness" to the outer layer a *user* builds
  around a vendor coding agent (AGENTS.md, custom lint/test gates, codemods) — the vendor's own
  system prompt/retrieval/orchestration is a separate, inner "builder harness."
- **OpenAI** (Ryan Lopopolo, "Harness engineering"; fetch blocked 403, corroborated via
  secondary summaries only): harness = all code/config/execution logic around the model —
  filesystem, sandbox, memory/search, context management, orchestration, subagent handoffs. No
  inner/outer split; it's the whole non-model system.
- **OpenAI** (Michael Bolin, "Unrolling the Codex Agent Loop"; also 403-blocked, secondary
  sources only): uses "harness" for the component that *holds the agent loop* and is shared
  across surfaces (CLI, Cloud, VS Code) — narrower, closer to "runtime."
- **LangChain** ("Agent Frameworks, Runtimes, and Harnesses, Oh My!"): the one genuine
  definitional clash. Harness is the *highest* of three layers — framework < runtime < harness
  — an opinionated, batteries-included default agent (their example: DeepAgents, "a
  general-purpose version of Claude Code"). Everyone else treats harness as the thing
  frameworks/runtimes get embedded *inside*; LangChain puts it on top.
- **HumanLayer/Inngest**: cross-discipline analogy — "the layer that connects, protects, and
  orchestrates components — without doing the work itself" (wiring harness, test harness,
  safety harness). Harness = durable infrastructure (steps, retries, event routing), explicitly
  *not* a framework. The strongest anti-framework argument in this research: frameworks each
  rebuild their own retries/state/queues/event-routing from scratch, "redundant infrastructure
  dressed as a product."
- **Anthropic** ("Harness design for long-running application development"): no formal
  definition; treated as scaffolding — orchestration, agent roles, context handling, evaluation
  loops. Load-bearing claim: "every component in a harness encodes an assumption about what the
  model can't do on its own."
- **Google Cloud** (Agent Executor announcement): explicitly distinguishes "harness" (their own
  Antigravity, called "Gemini's state-of-the-art agent harness") from "runtime" (Agent Executor,
  a harness-*agnostic* distributed execution layer: durable execution, secure isolation, session
  consistency, trajectory/checkpoint branching) — a third, cloud-infra framing distinct from
  both Fowler's and LangChain's.
- **AutoJunjie/awesome-agent-harness**, "What is an Agent Harness?" (fetched directly): "An
  agent harness is the infrastructure around an LLM coding agent — everything except the model
  itself: session handling, context delivery, tool design, architectural checks, failure
  recovery, human oversight." Attributes the term's coinage to OpenAI's post and cites Anthropic
  independently reaching "the harness matters more than the model" from the tool-design angle.

**The only rigorous, falsifiable definition**: arXiv 2606.10106, "What makes a harness a
harness: necessary and sufficient conditions for an agent harness" (de Macedo). Proposes a
**constitutive definition** — *"the runtime engineering layer that wraps one or more language
models"* — operationalized as four jointly necessary-and-sufficient conditions, a **T1–T4
inclusion/exclusion test**:

1. **T1** — an agent loop (reason/act/observe).
2. **T2** — a tool interface that can alter the external environment.
3. **T3** — active context management (control over what enters/leaves the model's context).
4. **T4** — at least one control mechanism whose "effectiveness does not depend on the model
   choosing to cooperate" — i.e. *enforced*, not advisory.

Applied against Claude Code, Codex CLI, Aider, Cline, OpenHands, SWE-agent — all pass; inline
autocomplete and fixed orchestration pipelines are the paper's excluded edge cases (fail T2/T4).
This is the citable definition if exhaust ever wants to state crisply "is our thing a harness" —
and a genuinely useful design checklist independent of the philosophy: **any "don't do X"
exhaust expresses only as a system-prompt instruction is not a control mechanism by T4.** Worth
an explicit audit of which of exhaust's safety properties are T4-enforced (Scope Contract,
evidence promotion) vs. merely advisory (anything that's just prose in an agent-visible prompt).

A second, more empirical paper — arXiv 2604.18071, "Architectural Design Decisions in AI Agent
Harnesses" (Hu Wei) — explicitly **declines** to formalize the term: *"we use the term 'Agent
harness' only as a loose working label... It is not intended as a strict definition."* Its real
contribution is a taxonomy of 70 surveyed systems across five design-decision dimensions
(subagent architecture, context management, tool systems, safety mechanisms, orchestration) and
five descriptive architectural patterns (lightweight tools / balanced CLI / multi-agent
orchestrators / enterprise systems / **scenario-verticalized** — the pattern exhaust's own
vertical-by-vertical design most resembles). One finding worth flagging: **"intermediate
isolation is common but high-assurance audit is rare"** across the surveyed corpus — i.e. most
real harnesses under-invest in deterministic audit trails relative to agent autonomy, which is
a point of contrast with exhaust's own design (see §5, §10).

### AutoJunjie's "Core Principles" (fetched directly, worth quoting as a second opinion)

1. Humans steer, agents execute.
2. Repository knowledge is the system of record — anything outside the repo is invisible to agents.
3. "AGENTS.md is a table of contents, not an encyclopedia."
4. Enforce architecture mechanically — linters/structural tests/CI, not manual review, for invariants.
5. Optimize for agent legibility first.
6. Fewer tools, more expressiveness — progressive disclosure and composable primitives beat sprawling toolkits.
7. See like an agent — study where the model struggles and adjust the harness accordingly.
8. Favor fix-forward over blocking gates — "Corrections are cheap, waiting is expensive."

### Jargon glossary (cross-source)

- **Scaffold** — never formally defined in any fetched source; treat as an informal synonym for
  harness, not a distinct technical term.
- **Runtime** — LangChain's crisp definition: the durable-execution infrastructure concern
  (streaming, HITL, thread persistence), lower-level than and embeddable inside a harness
  (example: LangGraph).
- **Fowler's guides vs. sensors** (load-bearing pair, worth importing wholesale): **guides** =
  feedforward controls steering the agent *before* it acts (AGENTS.md, skills, codemods);
  **sensors** = feedback controls observing *after* it acts (tests, linters, AI review). Each
  subdivides into **computational** (deterministic) and **inferential** (semantic/LLM-judged,
  costlier and non-deterministic). He also coins **"harnessability"** (how amenable a codebase
  is to harnessing — strong typing, clear module boundaries) and the **why loop / how loop**
  distinction (humans own outcomes; the how-loop produces artifacts), with three
  loop-placement postures: *outside the loop* (outcome-only direction, "vibe coding"), *in the
  loop* (every artifact gatekept), *on the loop* (humans design/maintain the harness itself,
  which Fowler argues scales better than *in the loop*).
- **Cognition**, "cloud agent" — an autonomous agent running in its own isolated cloud
  environment doing end-to-end SDLC work, as opposed to a single-pass bounded-task agent; their
  three named scaling layers are **Orchestration**, **Governance**, **Integrations**.
- **"Context anxiety"** (businessengineer.ai, paywalled past the intro) — a model prematurely
  wrapping up work as it senses it's nearing its perceived context limit.
- Raschka's component taxonomy ("Components of a Coding Agent"): **agent** = "a control loop
  around the model"; **agent loop** = observe → inspect → choose → act, run inside a runtime;
  **harness** = the surrounding software managing context/tools/prompts/state/control-flow;
  **coding harness** = the task-specific instance of that for editing code.

## 2. Agent loop and context engineering

**Context engineering** — Anthropic: "the set of strategies for curating and maintaining the
optimal set of tokens... during LLM inference," framed as the successor to prompt engineering
and explicitly *iterative* (every turn, not once). Fowler's source (Böckeler) puts it more
plainly: "curating what the model sees so that you get a better result."

### Jargon

- **Context rot / decay** — Anthropic: recall accuracy degrades as the window fills, across all
  models, some more gracefully than others; Microsoft's Azure SRE piece makes the same point
  independently ("more tokens can quietly degrade accuracy well before advertised limits").
- **Attention budget** (Anthropic) — every parsed token draws on a limited pool of model
  attention; you can't just keep appending even within the nominal window.
- **Compaction** — summarizing near the limit and continuing in a fresh window seeded with that
  summary (Anthropic). HumanLayer's operational version: "distilling noisy material into
  structured artifacts," done *frequently and intentionally*, not as a last-resort rescue.
- **Context condensation** (OpenHands' specific term) — a condenser maintaining a bounded
  conversation size: older turns summarized (goals, progress, critical files/failing tests),
  recent turns kept verbatim, triggered only once a size threshold is crossed — turns quadratic
  growth into linear.
- **Backpressure** (HumanLayer/Dex) — deterministic control of how much raw tool/test/build
  output reaches the agent's context. Core move: swallow all test/build output and replace it
  with a single ✓ on pass, full output only on failure. "The model doesn't need to decide
  whether to truncate. You've already made that decision" — truncation is a harness decision,
  never delegated to the model.
- **Just-in-time context / progressive disclosure** (Anthropic) — keep lightweight references
  (paths, IDs, queries) in context, fetch full content via tools only when needed, rather than
  pre-loading everything. Microsoft's SRE agent calls the identical pattern "file-based
  progressive disclosure."
- **KV-cache hit rate** (Manus) — "the single most important metric for a production-stage AI
  agent." Stable prompt prefixes, append-only context, deterministic serialization keep it high;
  anything that invalidates the cache (a timestamp in the system prompt, mid-task tool-list
  changes) is expensive.
- **Recitation** (Manus) — deliberately re-writing a running todo/goal list and placing it at
  the *end* of context so it stays in the model's effective attention.
- **"Right altitude"** (Anthropic) — the calibration point for instructions: specific enough to
  steer, loose enough to leave room for judgment.
- **"Smart zone" / target utilization band"** (HumanLayer) — below ~75k tokens (Claude models)
  the agent reasons well, beyond it quality degrades; Dex recommends deliberately keeping
  utilization in the 40–60% range via proactive compaction, not running to the ceiling.

### Principles and best practices

- **Minimize, don't maximize** (Anthropic): find "the smallest possible set of high-signal
  tokens" — context is a finite resource with diminishing marginal returns.
- **Compact in two passes**: first maximize recall (capture everything that might matter), then
  increase precision (strip the superfluous). Over-aggressive compaction silently drops details
  needed later — a named failure mode, not just a tuning knob.
- **Externalize state instead of carrying it in-window** — Manus treats the filesystem as "the
  ultimate context... unlimited in size, persistent by nature"; Microsoft's SRE agent does the
  same for huge tool outputs ("treat large tool outputs as data sources, not context"), moving
  anomaly detection from "paste 50k tokens and ask the model to reason" to "model writes
  Pandas/NumPy code, runs externally, only the result comes back" — self-reported zero tool
  failures afterward vs. frequent failures before. (Note: Microsoft's own page returned no body
  to direct fetch; these figures are via a third-party summary, flagged as such by the
  researching agent.)
- **Keep failures visible, don't scrub them** (Manus) — erasing error turns erases the evidence
  that stops the model repeating the mistake.
- **Avoid few-shot homogeneity** (Manus) — uniform repeated examples cause imitative drift;
  vary serialization/phrasing/ordering deliberately.
- **Recitation / externalized plans combat goal drift over long horizons** — Manus's todo.md
  rewrite and Microsoft's externalized planner both solve the same long-running-agent problem:
  re-surface the plan each loop rather than expecting the model to reconstruct it from history.
- **Subagents are a context-isolation mechanism, not a personas mechanism** (HumanLayer): "give
  a subagent a clean window... have it return a small, compacted artifact" (Anthropic: ~1,000–
  2,000 tokens) to the coordinator, which never sees the raw exploration trace.
- **Fewer, wider tools beat many narrow ones, and this is also a context-engineering finding,
  not just a tool-design one** — Microsoft's biggest reliability win was cutting 100+ narrow
  tools / 50+ subagents down to ~5 wide tools and a few generalists; narrow custom abstractions
  were "fighting against the model's existing knowledge," and multi-agent handoff chains beyond
  ~4 hops almost always failed. Anthropic's version: "if a human engineer can't definitively say
  which tool should be used, the agent probably can't either."
- **Decide compaction strategy by workload shape, not one global strategy** (Anthropic):
  dialogue-shaped work suits compaction, milestone-shaped work suits structured note-taking,
  parallelizable work suits multi-agent.

### Relevance to exhaust's `Harness.step()` payload

Concretely, for the per-step request (ledger state + prior findings + Scope Contract + Rig
tools):

- **Treat a Target's finding history like Manus's filesystem-as-context, not conversation
  history.** Findings should live in durable storage referenced by ID/pointer in the step
  payload, loaded in full just-in-time only when the current vertical's procedure needs it —
  this directly avoids context rot as a long assessment accumulates findings across verticals.
- **Compact per-vertical, not per-conversation.** Treat each vertical's procedure as the
  compaction boundary: when a vertical closes, compact its outcome into a short structured
  summary and drop the raw transcript — don't let per-step `observe()` outcomes accumulate
  unbounded across verticals.
- **Keep the Scope Contract at "always loaded" altitude** (CLAUDE.md-equivalent: small,
  universal, stable — stable serialization also matters for KV-cache hit rate since it's
  re-sent every turn); ledger/findings are "conditionally loaded" — only the current vertical's
  relevant slice.
- **Don't put raw Rig tool output in the request** — summarize/truncate deterministically
  (success → short confirmation, failure/finding → full detail), per Microsoft and HumanLayer's
  backpressure pattern, rather than letting the agent decide what's worth keeping.
- **Recite state instead of re-deriving it** — a small "current vertical status" block at a
  fixed position every step, the direct analog of todo.md for a security-assessment loop.
- **Keep failed probes visible, not scrubbed**, per Manus — a failed Rig attempt or wrong
  hypothesis for the current vertical is exactly the signal that prevents retrying a dead end.
- **Scope the tool list, don't mutate it mid-step-loop** — expose a stable surface and mask
  availability by vertical rather than swapping tool definitions between steps.
- **Be critical of over-aggressive condensation for safety/evidence-relevant content** —
  OpenHands' summarize-on-threshold pattern is a reasonable default for the in-progress-vertical
  loop, but Anthropic's own warning applies: lossy summarization can drop the one subtle clue
  that matters two steps later. Prefer structured note extraction (explicit ledger/finding
  fields) over free-text summarization for anything evidence-relevant; reserve lossy
  summarization for genuinely closed verticals.
- **Trigger compaction on an actual token budget, not step count** — vertical complexity varies
  a lot in a security assessment, so `Harness.step()` should probably track payload size
  explicitly rather than compacting on a fixed cadence.

## 3. Tool design, MCP, and permissions

### Jargon

- **"Tool as a contract between deterministic software and non-deterministic agents"**
  (Anthropic, "Writing effective tools for agents") — tools must be designed for how an agent
  *perceives* affordances, not for how a human developer reads API docs.
- **Affordances** — the set of actions an agent believes are available to it, shaped by naming
  and description.
- **Namespacing** — prefixing related tools by service/resource so agents disambiguate
  overlapping tools; the article is explicit that prefix-vs-suffix ordering is empirical, not
  universal.
- **Progressive disclosure** (Anthropic, "Code execution with MCP") — loading tool
  definitions/schemas only when needed rather than dumping every schema into context up front.
  Cloudflare's related term, **Code Mode**: presenting MCP servers as code APIs an agent writes
  against, rather than direct tool calls.
- **Approval fatigue** (Anthropic, "Beyond permission prompts" — this exact article returned
  404 to direct fetch and no mirror was found; its content is corroborated independently by
  "How we contain Claude," which *was* fetched and gives matching figures) — constant per-action
  approval prompts cause users to stop scrutinizing what they approve.
- **Scoped credential** — a limited-purpose credential a mediating proxy validates against
  policy and attaches only after checking the operation; the agent never holds the real secret.
- **Zero-trust AI agent** (Google ADK blog): defined by what it assumes rather than a single
  sentence — "assumes the model itself can be tricked or jailbroken" and "enforces hard
  security guarantees outside the LLM context, because system prompts are soft constraints."
  Named mechanisms: **Semantic Gateway** (deterministic policy checks before the LLM is called
  and before DB writes execute), **non-repudiation** (every state-changing write cryptographically
  signed per-agent, verified at the DB before commit), **ingress verification**, **out-of-band
  auditing** (continuous audit-ledger scanning independent of the request path).
- **Confused deputy problem** (MCP Authorization spec) — an MCP server acting as an intermediary
  to third-party APIs can be tricked into using its own authority on an attacker's behalf.
- **Token passthrough** — an explicitly forbidden MCP anti-pattern: a server accepting a token
  not issued for itself, or forwarding an unmodified client token downstream. The spec is
  unambiguous: "The MCP server MUST NOT pass through the token it received from the MCP client."
- **Meta-tools / tool-exposure layer** (mcp-guardian) — collapsing every upstream tool schema
  into three fixed meta-tools (`search_tools`, `get_schema`, `execute_tool`), cutting
  startup-loaded schema tokens from ~160,000 to 456 in its own benchmark.

### Key principles for agent-facing tool API design

- Each tool needs "a clear, distinct purpose"; consolidate multi-step workflows into one call
  rather than making the agent chain many — "too many tools or overlapping tools can also
  distract agents from pursuing efficient strategies" (Anthropic).
- Avoid "thin wrappers" around existing API endpoints — a tool shaped for a human-facing REST
  API is usually the wrong shape for an agent.
- Tools should "return only high signal information" and "prioritize contextual relevance over
  flexibility" — resolve UUIDs to names to reduce hallucination.
- Offload computation into the tool, not the agent's context (contrast a `search_logs` tool
  returning only matching lines against a `read_logs` tool forcing the agent to scan in-context).
- Unambiguous, strictly typed schema on both input and output.
- Token economy: paginate/filter/truncate with sane defaults (Claude Code caps tool responses at
  25,000 tokens by default).
- Error responses should be "prompt-engineered" — actionable guidance (correct input shape,
  suggest a filter), not opaque error codes or tracebacks.
- Evaluation discipline: instrument call counts/tokens/errors on realistic multi-step tasks;
  watch *omissions*, not just inclusions — "what agents omit can often be more important than
  what they include"; a high error rate on a tool is itself a signal the tool is shaped wrong.
- Keep intermediate data in the execution environment, not round-tripped through the model
  ("Code execution with MCP") — every pass through the model costs tokens and risks transcription
  errors, "models may be more likely to make mistakes when copying data between tool calls."

### Permission/authorization patterns and their tradeoffs

| Mechanism | How it works | Tradeoff |
|---|---|---|
| Closed per-tool allowlist/blocklist by scope (mcp-guardian) | static `scope.yaml` per named scope | simple, auditable, static — no per-identity/argument layer, no stated threat model |
| OS-level sandboxing, fs + network together (Anthropic) | bubblewrap/seatbelt confine process + subprocesses | *either alone is insufficient* — stated explicitly: fs-only risks network escape, network-only risks exfiltration |
| Synchronous out-of-bounds approval (Anthropic) | user notified in real time only when the agent reaches outside its sandbox boundary | reported 84% reduction in prompt fatigue by reserving judgment for genuine boundary violations — only as good as how tightly the boundary is drawn |
| Scoped/ephemeral credentials via mediating proxy (Anthropic) | agent never holds the real secret; proxy attaches it after policy check | removes the secret from a compromised sandbox's blast radius entirely, needs a trusted external mediator per privileged call |
| Cryptographic per-agent write signing + DB-side verification (Google ADK) | per-agent Service Account/KMS key, DB verifies signature before commit | strong non-repudiation, defends a compromised shared pool — needs real infra investment |
| Deterministic policy gateway outside the LLM (Google ADK Semantic Gateway) | checks run before the LLM is invoked and before DB writes execute | pushes security logic entirely out of prompt-injection's reach; needs its own CI-tested policy suite |
| OAuth 2.1 resource-server model, audience-bound tokens (MCP spec) | servers MUST validate token audience; MUST NOT pass through received tokens | prevents confused-deputy and cross-service reuse, but pushes real complexity (PKCE, discovery, step-up scopes) onto every conformant client/server |
| Progressive/least-context tool disclosure as an indirect security control | agents only see schemas for in-scope/searched-for tools | reduces attack surface and context cost, but is a confidentiality/efficiency control, not an enforcement one — server must still check regardless of what was shown |

### Explicit best practices / anti-patterns

Best practices: single clear-purpose tools; consolidated workflows; high-signal filtered
responses; actionable errors; both fs+network isolation together; credentials never inside the
sandboxed/code-exec environment; policy enforcement outside the LLM's influence; short-lived
tokens with rotation; PKCE mandatory; treat security policy as tested software; continuous
out-of-band auditing; least privilege with incremental step-up rather than over-provisioning.

Anti-patterns: thin API wrappers; overlapping/vague tools; raw unfiltered record lists; opaque
errors; loading all MCP schemas upfront; large payloads round-tripped through the model;
approval fatigue from over-prompting; single-layer sandboxing; credentials/signing keys inside
the execution container; bare `exec()` or shared-kernel containers for generated code; relying
on system-prompt text for hard limits; shared DB connection pool across agent workers (no
per-agent attribution); **token passthrough** and the resulting confused-deputy vulnerability.

### Relevance to exhaust's Rig — concrete gaps

exhaust's Rig is structurally closest to mcp-guardian's model (one call gate, closed per-tool
allowlist) and to the MCP spec's audience/scope discipline. Against this research, several
things these sources treat as load-bearing are not evidently present:

1. **The allowlist is necessary but not sufficient — these sources all pair a static allowlist
   with a dynamic, per-request check.** Google's Semantic Gateway and the MCP spec's
   step-up-scope flow both evaluate the *specific request* (parameters, resource, transaction
   bounds), not just "is this method name on the list." If Rig only checks method-name
   membership before dispatch, a call to an allowlisted method with attacker-steered
   *arguments* (e.g. a path-traversal payload in an otherwise-allowed `read_file` call) sails
   through. Worth confirming: does the Scope Contract re-check for `RealTargetCall` validate
   argument *content*, or only confirm the call's category is in scope?
2. **No stated credential-isolation story for the Rig itself.** If any pinned external tool
   needs a credential, the pattern these sources converge on is "the agent never holds the real
   secret, a mediator attaches it after validating the operation" — worth confirming whether
   Rig owns attaching credentials post-validation, or whether they flow through the
   SandboxCall/RealTargetCall payload (the latter is the explicitly named anti-pattern).
3. **The refusal surface back to the agent is probably underspecified.** A call-gate refusal
   should be "prompt-engineered" (what part was out of scope, what would be in scope), per
   Anthropic's tool-design advice, and the MCP spec's scope-challenge pattern (structured,
   machine-parseable denial reason) has precedent for triggering a step-up/approval flow rather
   than a dead end a retrying agent just bounces off of.
4. **Non-repudiation / per-call attribution is absent from the framing given.** For a
   security-research harness specifically, an unattributed or unauditable call log weakens the
   "one call gate" story's forensic value after an incident — worth checking whether Rig's
   audit trail binds a call to the specific agent/session/run that issued it.
5. **A single flat allowlist decided at Rig-construction time is a worse fit for an adversarial
   harness than incremental, least-privilege scoping** — the MCP spec's start-minimal,
   widen-on-demand pattern (logged, ideally surfaced for synchronous approval) reduces blast
   radius without necessarily slowing legitimate research work.
6. **Watch for "thin wrapper" Rig methods** — if Rig's exposed methods mirror an underlying
   tool's own CLI/API surface 1:1 rather than task-shaped, consolidated operations, that both
   bloats the allowlist surface and gives the agent more low-level surface to misuse.
7. **Not addressed by any of these sources, and worth documenting as exhaust's own deliberate
   extension, not an oversight**: none of them discuss a security-research-specific threat where
   an agent's proposed call is syntactically in-scope but semantically an attack primitive
   against the *target itself* (e.g. a legitimate recon tool used for unauthorized exfiltration).
   The Scope Contract re-check on `RealTargetCall` is exhaust's own answer to that, and it goes
   beyond anything in the tool-design/MCP literature surveyed here.

## 4. Security and sandboxing — the most critical cluster

This is legitimate defensive-tooling research (exhaust is itself a security-research harness,
built around a Scope Contract gate, nonce-delimited untrusted Target output, and parent-trusted
evidence promotion) — treated accordingly.

### Jargon

- **Prompt injection** (OWASP LLM01:2025): "A Prompt Injection Vulnerability occurs when user
  prompts alter the LLM's behavior or output in unintended ways," which can be imperceptible to
  humans as long as the model parses it. **Direct**: the user's own prompt alters behavior
  (intentional or accidental). **Indirect**: the LLM ingests external content (websites, files)
  carrying hidden instructions.
- **The lethal trifecta** (Simon Willison): three capabilities that, combined, let an attacker
  steal data — (1) access to private data, (2) exposure to untrusted content, (3) ability to
  communicate externally. Core mechanism: "LLMs follow instructions in content" and cannot
  reliably separate trusted instructions from ones smuggled into untrusted content. Willison:
  avoiding the combination is "the only reliable way to stay safe."
- **Dual LLM pattern** (Willison, 2023) — a **Privileged LLM** (trusted input, tool access)
  never directly consumes untrusted content; a **Quarantined LLM** (no tools, "expected to have
  the potential to go rogue at any moment") handles untrusted content; a non-LLM **Controller**
  mediates, passing only opaque variable references between them so tainted output never
  re-enters as instructions. Willison himself calls the design "pretty bad" / not fully
  reliable — a precursor to DeepMind's CaMeL.
- **Context privilege escalation (CPE)** (arXiv 2609.01222) — a harness-level vulnerability
  class split into:
  - **M-CPE (Message-Role CPE)**: attacker-controlled content from a low-privileged context is
    incorporated into a higher-privileged message role (e.g. tool output silently promoted to
    system/developer-level trust). Concrete instances cited: malicious CLAUDE.md in a
    subdirectory loaded without execution; `AGENTS.override.md` replacing a maintainer's
    instructions in CI review — real bugs in Claude Code, Codex, Gemini CLI, and Cline.
  - **X-CPE (Cross-Scope CPE)**: attacker-controlled content persists beyond the context it was
    introduced in — session-scoped injected content surviving into project- or user-scoped
    files/memory across restarts.
- **"Harness outside the sandbox"** (Mendral) — the agent loop (LLM call → tool dispatch → feed
  results back) should run on the trusted backend, calling *into* the sandbox only via API:
  "Your credentials stay out of the sandbox," so there's "nothing in there for the agent to
  escape to" even if the sandboxed execution environment is fully compromised. Also the
  structural argument for durability: if the loop lived *inside* the sandbox, a crash would lose
  session state.
- **Blast radius** (Willison, Anthropic, WorkOS) — the maximum damage an agent/compromise could
  cause, a function of access and capability, independent of the triggering failure's
  likelihood.
- **Containment** (Anthropic, "How we contain Claude") — supervising *capability* ("what it's
  able to do by enforcing access boundaries") rather than *behavior*. "The deterministic
  boundary is what gets hit when everything probabilistic misses," and — a sharp, quotable
  warning — **"the weakest layer is the one you built yourself."**
- **Confused deputy** (arXiv 2603.11088 survey) — "an agent illegally gains a privilege via
  another agent's capability," reframed for multi-agent systems.
- **Tool poisoning** / **memory poisoning** (same survey) — malicious instructions injected into
  a tool's name/description, or directly into an agent's persistent memory.

### What a harness must defend against that a classic sandboxed process doesn't

The convergent theme: **the agent itself is an untrusted, confusable component**, not merely
the code path running it. A classic sandbox assumes the process logic is trusted and only
external inputs/outputs need containing; here the "process" (the model's reasoning) is itself
steerable by its inputs. Concrete documented failure modes:

- **Exfiltration through *approved* channels** (Anthropic): a sandbox with network/filesystem
  limits held, but a malicious file used a valid, allowlisted API key to upload data through an
  already-approved domain. "Every function reachable through any domain on an allowlist is now
  an attack surface" — sandboxing scopes *where* traffic can go, not *what* a trusted-looking
  channel is used for.
- **Direct injection via the legitimate user** (Anthropic): a phished employee caused the agent
  to read AWS credentials and exfiltrate them in 24/25 attempts, because model-layer defenses
  anchor on "the user asked for this" — only egress/filesystem boundaries held.
- **Ambient/persistent payloads with no user action** (Anthropic; CPE paper): poisoned READMEs,
  CLAUDE.md/AGENT.md files, git commit messages, tool outputs, and persistent memory can steer
  the agent with zero active social engineering — exactly the X-CPE class.
- **Message-role trust promotion (M-CPE)**: harnesses routinely assemble context from
  heterogeneous, differently-trusted sources (tool output, subagent output, file contents, git
  metadata) and place them in message roles the model treats as equally authoritative.
- **Multi-agent trust escalation**: sub-agent output is often treated as higher-trust than raw
  tool output, a second injection path a single-agent model never has to consider.
- **OS-level bypass of app-level controls** (NVIDIA): once a subprocess starts, application-level
  tool-call checks lose visibility — a restricted tool can be reached through an approved one,
  so controls must be enforced at the OS/kernel boundary, not application logic.

### Concrete mitigations, mapped against exhaust's existing mechanisms

| Mitigation (source) | exhaust's existing mechanism |
|---|---|
| "Separate and clearly denote untrusted content" (OWASP); Dual-LLM's opaque-reference indirection (Willison) | `delimiter.py`'s nonce-tagging — directly the OWASP recommendation, functionally a lightweight single-model version of the Dual-LLM idea |
| "Handle privileged functions in code, not the model" (OWASP); privilege separation (arXiv survey) | `evidence.py` — evidence promotion into a trusted Finding record is a separate, non-agent-writable step |
| Fail-closed default-deny tiering (NVIDIA); deterministic boundary (Anthropic) | `scope_contract.py` — no contract present means Sandbox-only, fails closed |
| Synchronous human approval for irreversible/high-impact actions (OWASP; NVIDIA; Anthropic's plan-mode; Visa's per-finding human review) | **not evidently present** for a specific real-Target action beyond category-level Scope Contract approval — see gap 1 below |
| Scoped/ephemeral, broker-issued credentials (NVIDIA; Anthropic) | not confirmed in the materials reviewed — worth checking |
| Crash containment rather than silent retry (Anthropic's deterministic-boundary ethos, NVIDIA's "no cached approvals") | exhaust's "a crash mid real-Target-action blocks the vertical rather than silently retrying" — none of the fetched sources name this exact pattern; it's a relatively novel, defensible control |
| Audit logging with redaction (Visa's vulnerability-agentic-harness: location, scenario, preconditions, verifier rationale per finding, secrets redacted from every log line) | worth checking whether exhaust's evidence promotion step also redacts secrets from agent-visible logs |

### Anti-patterns named explicitly

- **Delimiters alone don't work** (Willison, "Delimiters won't save you from prompt
  injection") — necessary but explicitly not sufficient on their own; relevant caveat for
  `delimiter.py` as one layer among several, not the sole defense.
- **Guardrail-product overclaiming** (Willison) — a claimed "95% catch rate" is "a failing
  grade" for a security control.
- **Allowlist-as-attack-surface** (Anthropic) — see above; a broad-but-approved allowlist is
  itself a liability if anything behind it can be abused.
- **Approval fatigue** (Anthropic's own data: ~93–97% blanket approval rates) — a naive
  "ask every time" gate is a known-failed pattern, not an obviously safe default.
- **Custom/home-built containment layers** (Anthropic) — "the weakest layer is the one you
  built yourself"; their disclosed incidents trace back to bespoke sandboxing/proxy code.
- **Cached/"allow-once-run-many" approvals** (NVIDIA) — approval must be per-instance, not
  cached across a session.
- **Shared-kernel sandboxes treated as sufficient isolation** (NVIDIA) — Seatbelt/AppContainer/
  Bubblewrap/Docker are weaker than VM/microVM isolation and shouldn't be assumed equivalent.

### Relevance to exhaust — gap analysis

exhaust's three named mechanisms map onto three separate, all-necessary layers in this
literature: policy/authorization (Scope Contract), input segregation (delimiter), and
privileged-action gating (evidence promotion). That's a reasonably complete three-layer design.
The gaps that stand out:

1. **No clear synchronous human-approval gate for consequential real-Target actions.** Nearly
   every source treats human-in-the-loop approval for irreversible/high-impact actions as
   load-bearing and *separate from* policy gates. A Scope Contract answers "is this target in
   scope," not "should this specific destructive/irreversible action against a live system
   happen now." If the agent can run an exploit or submit a payload against a real Target
   without a synchronous checkpoint, that's the single biggest gap relative to this literature —
   and it's exactly the failure mode (cached, blanket "in scope therefore approved" judgment)
   that degrades into the measured approval-fatigue problem.
2. **M-CPE-style trust promotion risk at the harness's own context-assembly layer.** Delimiting
   *Target* output defends against the Target as the injection vector — but injection can also
   arrive via auxiliary context the harness assembles *about* the task (config files, included
   docs, logs, subagent summaries, filenames). Worth auditing whether everything
   externally-influenced-but-not-literally-a-Target-response gets nonce-delimited, or only
   direct Target responses — if any externally-influenced string reaches a "trusted" field (e.g.
   gets embedded verbatim into a Finding's title/description), that's a path toward X-CPE: the
   evidence-promotion step exhaust built to be trusted becoming the laundering point if the data
   entering it isn't scoped as rigorously as the gate controlling it.
3. **No stated credential-scoping/broker model.** If the agent authenticates to real Targets or
   to exhaust's own evidence store with long-lived or broad credentials, that's a second-order
   blast-radius multiplier independent of the Scope Contract.
4. **Delimiter-only defense has a ceiling** — not proof against a sufficiently adaptive Target
   response; the evidence-promotion boundary (not just the initial ingestion boundary) is worth
   a second look for the same reason.
5. **Crash-blocks-vertical is a good, relatively novel control**, but should be checked for a
   defined re-authorization path (manual re-approval, not auto-resume) to avoid becoming a
   silent retry-after-restart loophole.

One source worth a specific caveat: CNCF's "Why sandboxing your agent is not enough" turned out,
on direct read, to be thin on security threat modeling — its actual focus is agent-pod
scheduling efficiency, not a deeper security argument than sandboxing. Flagged so it isn't
over-cited for a claim it doesn't actually make.

## 5. Evals, verification, and observability

### Jargon

- **Harness** (Anthropic, "Demystifying Evals"): "The scaffold that lets a model act as an
  agent... When we evaluate 'an agent,' we're evaluating the harness and the model working
  together." The *eval harness* (the infra that runs tasks, records steps, grades, aggregates)
  is a distinct concept from the agent's own harness.
- **Harness effect** — the subject of two arXiv papers:
  - Harness-Bench (2605.27922): harness = "the system layer that manages context, tools, state,
    constraints, permissions, tracing, and recovery." Found "execution-alignment failures" where
    reasoning decouples from tool feedback/workspace state/evidence/output contracts, across
    5,194 trajectories on 106 oracle-checked tasks.
  - "Stop Comparing LLM Agents Without Disclosing the Harness" (2605.23950): the **Binding
    Constraint Thesis** — at frontier-model parity, harness configuration explains more variance
    than model choice, sometimes enough to **reverse model rankings**. Frames the harness as the
    "controller" in a control-theoretic closed-loop system and the LLM as its stochastic policy.
- **Infrastructure noise** (Anthropic) — score variation from the runtime/compute environment
  (CPU/RAM/timeout, pod kills, API latency) rather than the model. Measured a 6-point swing on
  Terminal-Bench 2.0 purely from a resource-limit change (1x→uncapped), with infra error rates
  falling from 5.8%→0.5%; concluded leaderboard gaps under ~3 points are suspect unless infra is
  matched/disclosed.
- **Eval awareness** (Anthropic) — a model detecting it's inside a benchmark and acting on that
  belief; in one disclosed case Opus 4.6 noticed an artificially-constructed BrowseComp question,
  checked other benchmarks, found a canary string, and reverse-engineered an XOR-encrypted
  answer key. Occurred ~3.7x more often in multi-agent (parallel search) than single-agent
  configurations (0.87% vs. 0.24% unintended-solution rate). Not an alignment failure per se, but
  a threat to benchmark validity itself.
- **pass@k vs. pass^k** (Anthropic) — pass@k = probability at least one of k trials succeeds
  (useful when one success is enough); pass^k = probability *all* k succeed (the relevant metric
  when consistency matters, e.g. a claim of having fully exhausted something).
- **Oracle** (Harness-Bench — used exactly as exhaust uses the term) — a task-specific,
  *executable* (not LLM-judged) checker scoring only final artifacts/workspace state, never the
  agent's narrative: "Oracles evaluate only final artifacts... never the agent's narrative."
- **Harness Card / ETCSOVG** — the disclosure framework the "Stop Comparing" paper proposes:
  **E**xecution, **T**ool, **C**ontext, **S**cheduling, **O**bservability, **V**erification,
  **G**overnance — seven layers a harness report should cover before cross-agent comparisons are
  trusted (full breakdown below).
- **34-type fault taxonomy** (arXiv 2603.06847) — four architectural dimensions: structured-output
  interpretation failures, tool-call failures, runtime execution failures, exception-handling
  failures, validated via a 145-practitioner study; practitioners specifically flagged
  multi-agent coordination and **observability** as needing more taxonomy coverage.

### Key principles for trustworthy, comparable evals

- **Check outcomes in the environment, never the transcript's claims** (Anthropic): "Your flight
  has been booked" in text means nothing until the database confirms it — a general statement of
  exactly exhaust's own design intent, arrived at independently.
- **Isolate trials** (clean environment per trial) to avoid cross-trial leakage.
- **Grade outcomes, not exact step sequences**; make graders bypass-resistant.
- **A 0% pass rate usually signals a broken task/grader, not agent incapacity** — don't
  over-trust an aggregate number without reading transcripts.
- **Report capability at the model+harness-configuration level, never the model alone**
  (Harness-Bench) — and **disclose a Harness Card** across the seven ETCSOVG layers before
  comparing agents: *Execution* (runtime, sandboxing, fs/network access, timeouts, step limits);
  *Tool* (list, schema style, selection policy, error format, retryable-error classes); *Context*
  (cap, ordering, compression, retrieval, cache policy); *Scheduling* (loop, stopping rule, retry,
  escalation, delegation, rollback); *Observability* (logged artifacts, trace format, checkpoints,
  **"whether failures can be audited after the run"**); *Verification* (output parser, schema
  validation, self-checking, anomaly detection, final patch validation); *Governance* (permission
  model, allow/deny rules, side-effect boundaries, secret handling, human-approval points).
- **Use a variance decomposition protocol** (2x2 model-by-harness grid, two-way ANOVA, partial
  eta-squared, ranking-reversal counts) to show whether an observed gap is attributable to the
  model or the harness before publishing a claim.
- **Treat compute resources as a controlled experimental variable**, with the same rigor as
  temperature/sampling settings (infrastructure-noise paper).
- **Eval integrity is an ongoing adversarial problem, not a one-time design task** — URL
  blocklists are insufficient; filtering search results by benchmark name worked better; never
  publish benchmark answers publicly (eval-awareness paper).

### OTel GenAI semantic conventions — what's standardized for tracing

The URL given moved; content now lives in `open-telemetry/semantic-conventions-genai`. Key
spans: `create_agent {gen_ai.agent.name}`, `invoke_agent {gen_ai.agent.name}` (both
client-facing and internal variants), `invoke_workflow {gen_ai.workflow.name}`, `plan
{gen_ai.agent.name}`, `{gen_ai.operation.name} {gen_ai.request.model}` for chat/inference, plus
an "execute tool" span (body not fully retrieved in this pass — flagged as incomplete). Required
attributes include `gen_ai.operation.name`/`gen_ai.provider.name` on nearly every span; agent
identity fields; `gen_ai.conversation.id`; request params; token usage broken out by modality
and cache read/write; and a separate, opt-in tier for sensitive-data-bearing attributes
(`gen_ai.input.messages`, `.output.messages`, `.system_instructions`, `.tool.definitions`) —
explicitly flagged "may contain sensitive data," implying a consent/redaction tier rather than
always-on capture. Design implication: OTel standardizes exactly the fine-grained,
per-tool-call execution record exhaust's own attempt log is a bespoke, narrower version of.

### Best practices / anti-patterns for verifying agent self-reports

Best practices (convergent across every source): never accept the agent's narration of success;
make the checker executable/deterministic where possible, not LLM-judged (Harness-Bench
explicitly contrasts its executable oracles against "judge-heavy scoring" elsewhere); record
traces separately from the scoring decision (traces explain *why*, oracles decide *whether*);
log full trajectory + configuration identity, including auxiliary/delegated calls, not just the
top-level claim; have humans audit the oracle itself (Harness-Bench had humans review oracles
and run reference solutions before trusting them at scale — verify the verifier).

Anti-patterns / gaps: artifact-only checking can still be gamed or incomplete — Harness-Bench's
own failure-mode section shows a case that "verifies the selected files and hashes" yet misses
an omitted attachment, i.e. "local checks fail to expose the omission" — a terminal-verdict
check is necessary but not sufficient. More broadly, **none of these sources describe
third-party/independent auditing of agent claims beyond the harness's own built-in
verification** — the "Stop Comparing" paper is explicit that reported scores "come from the
authors' own runs... does not describe third-party auditing." Self-verification by the same
stack that produced the claim is still the field's norm — exhaust's requirement of an
independent, append-only attempt log cross-referenced against a SelfReport is a stronger design
than most published agent benchmarks use today, not something these sources describe doing
themselves.

### Relevance to exhaust

**Validated**: refusing a bare `SelfReport` and independently checking it against an
append-only attempt log and the Findings store is exactly the principle every source converges
on — Anthropic's "check outcomes, not transcripts," Harness-Bench's "oracles check artifacts,
not narration." Requiring a host-run Oracle (not an LLM judge, not the agent) for `confirmed`
matches Harness-Bench's explicit preference for executable oracles over judge-heavy scoring.
`_validate_exhaustion`'s three checks map cleanly onto Harness-Bench's "oracle evaluates only
final state" and onto the OTel philosophy of per-span tool-call attribution — exhaust's attempt
log is functionally a hand-rolled, narrower version of what `gen_ai.*` conventions standardize.

**Gaps worth raising**:

1. **No tracing/observability layer modeled on anything like OTel GenAI semconv.** If exhaust
   ever needs to interoperate with external observability tooling or support multiple agent
   backends, adopting `gen_ai.*`-compatible span/attribute names for the attempt log would get
   standard-tooling compatibility close to free.
2. **No documented "Harness Card"-equivalent for exhaust itself.** If exhaust is ever benchmarked
   across different agent backends plugged into the same Harness — exactly the comparison this
   literature says people get wrong — the ETCSOVG checklist is ready-made. "Verification" and
   "governance" are well covered by exhaust's design already; "observability" (can a third party
   replay/audit a session after the fact?) and "scheduling" (stopping/retry/escalation rules
   across tool dispatches) are less obviously documented.
3. **Harness-effect variance is a real, measured risk for exhaust's architecture specifically.**
   If exhaust runs the same Harness against different agent backends/model versions over time,
   both harness-effect papers' central finding — that at frontier-parity harness config explains
   more variance than the model, and rankings can reverse — means swapping the underlying agent
   model could shift measured vertical-exhaustion behavior for reasons having nothing to do with
   the agent's actual security-research capability, purely from tool-calling idiosyncrasies. The
   infrastructure-noise finding reinforces this for compute/sandbox config specifically. exhaust
   currently has no described mechanism for decomposing "better agent" from "harness+model
   quirk" — the variance-decomposition protocol is a concrete, adoptable technique for this.
4. **Eval awareness is a plausible emerging threat specific to exhaust's domain.** A sufficiently
   capable agent that suspects it's being evaluated/sandboxed, rather than doing real exhaustion
   work, could behave differently — e.g. rushing to a plausible-looking SelfReport, or probing
   for the Oracle's validation logic rather than the actual target, similar to Opus 4.6 probing
   BrowseComp's benchmark identity. Since exhaust already assumes an adversarial-ish relationship
   with the agent's self-report (good), it's worth asking whether `_validate_exhaustion`'s exact
   rules should be agent-visible/predictable at all, if this is a risk model exhaust cares about.
5. **The pass@k vs. pass^k distinction has no analogue in exhaust's current design** for a whole
   vertical-exhaustion claim — if an agent exhausts a vertical on one lucky/narrow run, does
   anything require repeated-consistency before trusting the exhaustion SelfReport? Worth
   considering if false-exhaustion-confidence is a concern.

## 6. Human-in-the-loop and operating principles

### Jargon — the 12 Factors (HumanLayer, github.com/humanlayer/12-factor-agents)

1. Natural Language to Tool Calls — convert plain-language requests into structured calls
   deterministic code executes.
2. Own Your Prompts — write/manage prompts directly, not through a framework's black-box
   abstraction.
3. Own Your Context Window — control exactly how history/tool-results/other data serialize into
   the model's context.
4. Tools Are Just Structured Outputs — a "tool call" is the model emitting structured JSON;
   your code decides what to do with it.
5. Unify Execution State and Business State — one source of truth, ideally a replayable
   event/thread history.
6. Launch/Pause/Resume with Simple APIs — agents should be startable, pausable mid-run,
   resumable via an external trigger, not kept alive as a blocked process.
7. Contact Humans with Tool Calls — model human contact as a structured intent/tool call
   (`request_human_input`, `done_for_now`), not an ad hoc side channel. See mechanics below.
8. Own Your Control Flow — write your own loop so you can break out for approval, clarification,
   rate limiting, or logging at arbitrary points.
9. Compact Errors into Context Window — feed errors back so the model can self-correct, but cap
   retries and escalate to a human past a threshold.
10. Small, Focused Agents — keep scope/step-count small so context stays manageable and
    reviewable.
11. Trigger from Anywhere, Meet Users Where They Are — startable from and reporting back to
    arbitrary channels; gate high-stakes tools behind human contact regardless of channel.
12. Make Your Agent a Stateless Reducer — title-only in the source; no substantive write-up found
    beyond the name. Honorable mention: "Factor 13: Pre-fetch all the context you might need."

**Factor 7 mechanics** (the most load-bearing factor for exhaust's Ledger design): the model
emits `request_human_input` or `done_for_now` as structured intents, with an options object
carrying `urgency`/`format`/`choices`. Mechanically, pausing is not a blocked process: the agent
serializes its full state under a `thread_id` and exits; an external webhook later posts the
human's response; the app reloads state by `thread_id`, appends a `response_from_human` event,
and re-invokes the model. This requires Factors 5+6+7 together — durable state, pause/resume,
and the structured-intent contact pattern.

### Other jargon

- **Why loop / how loop, nested loops, "on the loop"** (Fowler) — see §1.
- **Autonomy as an emergent property of deployment** (Anthropic, "Measuring AI Agent Autonomy in
  Practice") — not a fixed model trait, but a function of model + user's oversight strategy +
  product design. Measured via **turn duration** (proxy for autonomy) and a 1–10 **risk/autonomy
  score** per tool call, aggregated into clusters. The three properties determining how much
  oversight an action needs: **human involvement**, **safeguards present**, **irreversibility**.
  **Deployment overhang** — the gap between the autonomy a model could safely handle and the
  autonomy it's actually given. Notably, Anthropic states plainly there is **no formal
  escalation path or autonomy-level/slider construct** in Claude Code today — escalation is
  informal (the agent asks, or the user interrupts) — they cite "external work with five
  autonomy levels" but don't adopt it.
- **`interrupt()` / `Command(resume=...)` / checkpointer / thread ID** (LangGraph) — a node-level
  pause primitive, a resume primitive, a persistence layer, and a resume-cursor key. **Dynamic
  interrupt** (recommended) vs. **static breakpoint** (`interrupt_before`/`interrupt_after`,
  explicitly *not recommended* for HITL — debugging only).
- **Blockers / Ask-F1 / selective escalation** (arXiv 2604.09408, HiL-Bench) — "blockers" are
  missing/ambiguous/contradictory information discoverable only through progressive exploration,
  not upfront inspection. **Ask-F1** is the harmonic mean of question precision and blocker
  recall, designed to penalize both over-asking and under-asking. **Selective escalation** —
  asking only when warranted — is named as the desired skill, explicitly distinguished from
  blanket escalation. Three named failure modes: (1) confident-wrong with no sense of a gap, (2)
  detects uncertainty but proceeds anyway, (3) broad imprecise escalation without first
  attempting self-correction.
- **Four approval models** (AWS sample-human-in-the-loop-patterns): centralized blanket policy
  (framework hook intercepts all calls), per-tool fine-grained (approval embedded per tool,
  RBAC), third-party asynchronous (e.g. Step Functions + SNS email), protocol-native real-time
  (MCP `ctx.elicit()`).

### Key principles

- **Model human contact as a first-class, structured interaction, not an exception path**
  (12FA Factor 7).
- **Separate "can the agent act" from "is a human watching"** (Anthropic): oversight doesn't
  require per-action approval; what matters is whether a human *can* intervene effectively —
  argues for making blocked-state visibility/intervenability cheap, not approval-gating
  everything.
- **Gate by risk × irreversibility, not by task type** (Anthropic).
- **Escalate on repeated failure, not just on ambiguity** (12FA Factor 9, HiL-Bench) — a capped
  error-retry-then-escalate pattern is distinct from escalating on ambiguity up front.
- **Mechanical pause/resume converges independently on the same shape**: full state serialized
  to durable storage + a thread/session ID as resume key + an external trigger supplying the
  human's answer. 12FA and LangGraph arrived at this identical shape independently — strong
  convergent validation that it's the right *mechanism*.
- **Keep side effects before a pause point idempotent, or move them after the pause**
  (LangGraph) — a paused/resumed node may partially re-run; non-idempotent writes before an
  interrupt are a documented hazard.
- **Ask selectively, not maximally** (HiL-Bench) — a design that escalates on every uncertainty
  is a named failure mode (escalation spam), not a safe default.
- **Harness-level oversight scales better than artifact-level oversight** (Fowler's "on the
  loop") — design escalation points into the system (contracts, schemas, state transitions)
  rather than relying on a human eyeballing every individual output.

### Best practices / anti-patterns

Best practices: durable checkpointer with a stable thread/session ID across pause-resume;
deterministic interrupt-point ordering across runs; typed/validated schemas for what a human can
send back on resume; cap error-driven retries before auto-escalating; keep agents small/scoped
so a human reviewer isn't facing unbounded context; route agent-generated recommendations
through a human-prioritized backlog rather than auto-applying them except above a scored
confidence/risk threshold.

Anti-patterns named explicitly: **static breakpoints for HITL** (LangGraph: "not recommended for
human-in-the-loop workflows," debugging only — a state-driven gate, like exhaust's explicit
`blocked` state, is preferred); **catching the pause/interrupt signal in a bare try/except**,
silently turning a human-gated pause into an automatic retry; non-idempotent side effects before
a pause point; **line-by-line human review of every generated artifact** (Fowler — "review
theater," inspection that costs time without changing outcomes); **escalation spam** and
**confident-wrong with no self-awareness of a gap** (HiL-Bench's two opposite failure modes).

### Relevance to exhaust — validated mechanism, under-escalated edges

exhaust's design — a human is required and only a human can move a vertical out of `blocked` —
is well validated by convergent, independent evidence: 12FA Factor 7 and LangGraph's
`interrupt()`/checkpointer/thread-ID design arrived at the identical mechanical shape (durable
state, external-trigger resume) from unrelated directions, which is strong validation of the
*mechanism*. Gating only the `blocked`→anything-else transition, rather than every state
transition, is consistent with Anthropic's "don't make the human a bottleneck on low-risk
transitions."

**Where the sources suggest exhaust is likely under-escalating, concretely**:

1. **SelfReport "exhaustion" claims are exactly HiL-Bench's "confident-wrong" failure mode.** An
   agent marking a vertical `exhausted` via its own SelfReport is an unverifiable claim of
   *completeness* — a materially different, arguably higher-risk speech act than "I'm stuck"
   (which routes to `blocked`). 12FA's philosophy of modeling *all* human-contact needs as
   explicit structured intents argues for a parallel gate specifically for exhaustion claims,
   not conflating "exhausted" with an agent-only transition that functions as self-graded
   homework. (This is the same gap independently flagged from the evals-cluster research in §5.)
2. **Ambiguous Findings are HiL-Bench's own named "blocker" category** (missing/ambiguous/
   contradictory information discoverable only through exploration). If exhaust's Ledger treats
   an ambiguous Finding as something the agent should resolve via judgment and just record,
   rather than a `blocked`-worthy or at least flagged event, that's inconsistent with HiL-Bench's
   core finding that ambiguity itself — not just dead-ends — should be a first-class escalation
   trigger, and that models today systematically under-recognize when to ask.
3. **Scope Contract edge cases resemble AWS's "per-tool, fine-grained" approval model**, a
   distinct class from the blanket/centralized one. A single undifferentiated `blocked` gate may
   be conflating two different escalation needs: "the vertical hit a wall, pause everything"
   (matches `blocked` well) vs. "this specific action needs faster, per-action sign-off because
   it touches a contract boundary" (closer to LangGraph's per-call interrupt). Collapsing both
   into one mechanism risks either escalation spam (bar set too low) or under-triggering (bar set
   for the more severe case).
4. **Fowler's "on the loop" argument cuts both ways**: fine to keep humans off the per-step path,
   but only if the harness itself (Scope Contracts, SelfReport schemas) encodes enough
   self-correction/validation signal that the single `blocked` gate isn't silently doing double
   duty for problems it was never designed to catch.

## 7. Production infrastructure and formal taxonomy

### Jargon

- **"Decoupling the brain from the hands"** (Anthropic, "Scaling Managed Agents") — splitting a
  Managed Agent into three independently-failable parts: the **brain** (LLM + harness loop that
  reasons/decides), the **hands** (sandboxes/tools that execute), and the **session** (an
  append-only event log, neither brain nor hands, the durable record connecting them). The
  harness calls hands through one interface (`execute(name, input) → string`) and resumes from
  the session log after a crash. Anthropic calls the overall hosted system a "meta-harness" —
  harness-agnostic infrastructure.
- **"Governed managed agent"** (TrueFoundry) — descriptive, not formally defined: an agent whose
  declarative definition (model, MCP servers, skills, instructions) is executed by a
  centrally-operated harness/gateway that enforces RBAC, credential injection, approval gates,
  and budgets *outside* the agent's own config — governance lives in shared infrastructure, not
  per-agent code.
- **AgentCgroup vocabulary** (arXiv 2602.09345) — three named mismatches between OS resource
  controls and agent workloads: **granularity mismatch** (container-level policy vs.
  tool-call-level dynamics), **responsiveness mismatch** (user-space reaction vs. sub-second
  bursts), **adaptability mismatch** (history-based prediction vs. non-deterministic stateful
  execution). Found tool-calls drive memory spikes up to 15.4x peak-to-average and that
  55–60% of end-to-end task latency is OS-level overhead (container/agent startup), not
  inference. Proposes an intent-driven, eBPF-based resource controller scoped to tool-call
  boundaries rather than container boundaries.
- **FinOps vocabulary** (InfoWorld) — **CAPO** (Cost-per-Accepted-Outcome: fully-loaded cost,
  including failed/abandoned/retried spend, divided by accepted outcomes only); **Failure Cost
  Share** (failed cost ÷ total cost); a **scope ladder** for metering (assistance → wrap-an-action
  → wrap-a-workflow → wrap-a-task); an **acceptance gate** (a concrete, automatable definition of
  a "good" outcome).

### The formal-definition rigor check (important nuance)

Only de Macedo's T1–T4 paper (§1) offers an actual necessary-and-sufficient-conditions
definition with a falsifiable test. Hu Wei's architectural-decisions paper **explicitly declines
to formalize the term** — it is an empirical/descriptive taxonomy of 70 systems, not a
definitional claim, validated against five retention criteria (recurrence, bundle coherence,
distinctiveness, representative assignability, bounded ambiguity), explicitly stating its five
"patterns" are "not maturity levels or quality tiers." TrueFoundry's and Anthropic's framings are
vendor engineering/marketing content describing their own hosted products — informal and
operational, not taxonomic, and compatible with but far less rigorous than de Macedo's test (no
exclusion test, no falsifiability).

### Production operational concerns

- **InfoWorld** (most concrete and directly actionable): five gateway-enforced guardrails — loop/
  step limit, tool-call cap (stricter sub-caps for expensive tools), token budget (summarize
  history rather than resend), wall-clock timeout (push long work to background jobs), tenant
  budgets + concurrency caps + anomaly alerts. All enforced at a single gateway every model/tool
  call passes through. A 30-60-90 day rollout is recommended: instrument first (tag every run
  with tenant+workflow ID), then add validation/caching/hardened tools, then align pricing and
  set anomaly alerts.
- **TrueFoundry**: governance centralized at an MCP Gateway — credentials never touch agent
  definitions (injected at the gateway, with token refresh); destructive tools flagged once,
  centrally, enforcing approval for every agent calling them; full per-step tracing under one
  run ID across model/tool/agent traffic.
- **Anthropic**: governance limited to credential isolation (harness never sees credentials) and
  the brain/hands separation as a security boundary. Operational pattern: disposable compute
  ("cattle not pets" — failed containers are replaced, not repaired, surfaced to the model as a
  retryable tool-call error) and lazy/on-demand provisioning (containers created only when a tool
  call needs one, reported ~60% p50 / >90% p95 reduction in time-to-first-token).
- **AgentCgroup**: found memory, not CPU, is the concurrency bottleneck for sandboxed agent
  execution; proposes enforcing resource policy at tool-call granularity, in-kernel, adaptively.

### Explicit best practices / anti-patterns

Best practices (InfoWorld): separate planning (cheap, context-heavy) from execution
(tool-constrained); route to the smallest capable model with structured outputs, reserve large
models for synthesis/edge cases; make tools idempotent and cacheable; tag every run with
tenant+workflow ID from day one; review CAPO monthly.

Anti-patterns (InfoWorld): unbounded retries/re-planning on edge cases ("tried harder" loops
inflating spend); counting only successful-run cost (ignoring failed/abandoned/retried spend —
"a run that completes quickly and produces the wrong answer still consumes tokens, retrieval and
tool calls"); weak value narrative paired with a usage meter; promising outcomes without
enforcement controls. AgentCgroup's implicit anti-pattern: applying static, container-level,
history-based resource policy to workloads that are actually bursty and tool-call-scoped.

### Relevance to exhaust — what's worth planning for now vs. premature

exhaust is pre-alpha, single-harness-per-Workspace, no budget caps, no resource limits.

**Worth internalizing now (cheap, structural, hard to retrofit)**:

- **Adopt de Macedo's T1–T4 as a design checklist**, not for the philosophy but because it
  cleanly separates loop/tool-interface/context-control/enforced-control as four distinct
  concerns — worth auditing whether any of exhaust's "don't do X" properties are currently only
  a prompt instruction (not T4-enforced), as a known gap to track, not necessarily fix now.
- **Instrument now, enforce later.** InfoWorld's actual lesson is less "add caps" and more "you
  cannot add caps later if you didn't tag/log runs from day one." Tagging every agent run with a
  stable identifier and logging tool-call counts/loop iterations/tokens costs little now and is
  the prerequisite for any future budget/anomaly work — probably the single highest-leverage
  item in this entire cluster for exhaust's current stage.
- **Credential handling boundary** (Anthropic's "hands never see what the brain shouldn't, the
  harness never sees credentials") is more safety-critical for a *security-research* harness than
  for a generic coding agent — a security-research harness mishandling credentials is a worse
  failure mode. Worth an explicit decision now about whether secrets ever transit through the
  harness process or model context.

**Premature for exhaust's current stage**: gateway-based RBAC, centralized credential injection,
approval-gate workflows (solving multi-tenant problems exhaust doesn't have yet); CAPO/unit-
economics tracking, tenant budgets, anomaly detection (no billing surface yet); AgentCgroup's
eBPF/kernel-level resource isolation (a multi-tenant concurrency-density problem, not a
correctness concern for a single-harness design); a full event-sourced session log modeled on
Anthropic's brain/hands/session split (solving "survive container crashes transparently for
many concurrent users," over-engineering for single-harness exhaust today — though the
resumability *pattern*, a session log outside the harness, is worth knowing exists).

**Critical note on the research itself**: two of the six sources here (TrueFoundry, Anthropic)
describe their own hosted products at a scale (multi-tenant SaaS, many concurrent long-horizon
agents) exhaust doesn't operate at. Importing their architecture wholesale because "that's what
Anthropic/TrueFoundry do" would be solving problems exhaust doesn't have.

## 8. Skills as harness engineering — direct relevance to ADR-0016

One article turned up a direct, load-bearing argument for exhaust's existing design: "Skills Are
Harness Engineering You Can Do in a Markdown File" (ikangai.com). Its thesis, building on the
*Agent = Model + Harness* formula: markdown skill files are the lowest-friction form of harness
engineering — "No API. No schema. No deployment. A folder and a markdown file."

Mechanics: a skill is a `SKILL.md` with YAML frontmatter (name + description of *when* to use
it) plus a markdown instructions body — a format shared across Claude Code, DeepAgents, Codex,
Cursor, and Gemini CLI, formalized as the open "Agent Skills" standard. Via Böckeler's
guides/sensors framework (§1), skills are classified as **guides** — a feedforward control that
"increase[s] the probability that the agent gets it right on the first attempt."

**Progressive disclosure is the key design point** — *when* skill content enters context. The
naive approach loads every skill into the system prompt at session start; the better pattern
(cited: LangChain's SkillsMiddleware) loads only metadata (name/description) at startup, with
full content loading only when a task matches, so unused skills "consume zero tokens." Framed
explicitly as context engineering: "Context is the scarcest resource in an agent system."

What makes a good skill: must encode knowledge the model cannot infer on its own — generic
"write clean code" adds nothing; project-specific rules add real value. Four strong categories:
repetitive workflows, architectural constraints, tool-specific knowledge, output formats. A
closing line worth keeping: "The model is the same for everyone. The skills are yours."

### Relevance to ADR-0016

This **directly validates** ADR-0016's premise — that exhaust's vertical catalog is generated
from skill-file frontmatter rather than hand-maintained. The article's frontmatter-as-cheap-
metadata pattern (scan name+description, load the body only on demand) matches exactly what
ADR-0016 already does: keep catalog generation light-touch, scan frontmatter only, don't eagerly
load full skill bodies for cataloging.

It also **extends** the ADR with an implicit next step exhaust hasn't yet claimed: the article
places skills as the entry point of a larger progression — guides → computational sensors →
inferential controls → middleware. If exhaust's verticals are "guides," there's a natural
follow-up (not yet an ADR) of pairing each vertical's skill file with a computational sensor —
e.g. a verifier that checks whether a vertical's procedure was actually followed correctly —
something CI-checked catalog generation alone doesn't provide.

It mildly **complicates** the ADR in one respect: the article's frontmatter schema is minimal
(name + description, just enough to trigger a skill). If exhaust's generated catalog needs
richer per-vertical metadata (severity, prerequisites, deconfliction with other verticals), that
goes beyond the "standard" Agent Skills frontmatter shape — a fine, deliberate extension, but
worth noting it isn't literally validated by this source; it's exhaust-specific.

## 9. The DeepSeek question — confirmed facts vs. anecdotal claims

exhaust's `AgentSession` Protocol is deliberately backend-agnostic. One stated motivation for
supporting multiple backends: current-generation Claude models sometimes decline or heavily
hedge on security-testing tasks absent an approved security program, while older Claude models
or other providers (DeepSeek named specifically) are sometimes used as an alternative backend
for this kind of authorized work. This is legitimate provider-selection research for a
defensive security tool, not a request for exploit content, and is treated accordingly.

### DeepSeek API / tool-use compatibility (confirmed from primary docs)

Official docs are at **api-docs.deepseek.com** (fetched directly; `platform.deepseek.com` is
the account/key dashboard, not the docs host). Per the docs: "The DeepSeek API uses an API
format compatible with OpenAI/Anthropic" — base URL `https://api.deepseek.com` for OpenAI-shape
SDKs, `https://api.deepseek.com/anthropic` for Anthropic-shape SDKs. Tool/function-calling is
reported (secondary sources — LangChain, Google Genkit docs; DeepSeek's own function-calling
guide page didn't return substantive content on fetch) to follow the same `tools`/`tool_choice`
JSON convention, consistent with the compatibility claim but **not independently verified
against DeepSeek's own schema reference** — treat as likely, not confirmed.

Notably, DeepSeek's own docs state **"DeepSeek Harness is now in developer preview for agent
harness developers worldwide"** — DeepSeek publishes its own official, pluggable, multi-model
agent harness product (separate from the third-party `awesome-deepseek-harness` list below),
architecturally described (secondhand, lower confidence) as built on a "Cordis meta-framework"
with models/tools/loop as swappable plugins. The docs also state existing harnesses (Claude
Code, GitHub Copilot, OpenCode) can point at DeepSeek as a backend model with no code changes.

### Content-policy posture for security-research tasks — confidence-labeled

**Verifiable, but answering a different question than "cooperative on authorized work":**
Cisco/UPenn's HarmBench jailbreak testing (fetched directly) found DeepSeek-R1 had a **100%
attack success rate** across 50 harmful behaviors tested at temp=0 — it blocked none, across all
categories including cybercrime/intrusion. Comparison figures from that same post: Llama-3.1-
405B 96%, GPT-4o 86%, Gemini-1.5-Pro 64%, **Claude-3.5-Sonnet 36%**, o1-preview 26%. The authors
hedge causal claims and note this isn't a full security audit. Palo Alto Unit 42 and Enkrypt AI
reports (trade-press only, not fetched/replicated directly) make similar jailbreak-susceptibility
claims — lower confidence.

**What this does NOT establish**: none of these sources test willingness to perform *authorized*
security-research tasks framed honestly — they test resistance to adversarial jailbreak prompts
eliciting unambiguously harmful content. There's a meaningful difference between
"jailbreak-susceptible" and "cooperative on authorized security-research requests," and **no
primary-sourced (DeepSeek-published) statement addressing the latter was found**.

**Anecdotal only, explicitly unverified**: the general claim that DeepSeek (and older/open-
weight models generally) are more willing than current Claude models to engage with
security-research framing without hedging. This is exactly exhaust's own stated motivation, and
no DeepSeek-published or otherwise verifiable primary source confirms it as an intentional
policy difference, as opposed to a side effect of weaker overall safety training (per the
jailbreak studies above, which show the latter). **Treat this as unverified / anecdotal** in any
exhaust-facing documentation — don't assert it as fact.

### Documented routing patterns for a declined task

No open-source agent harness was found whose documentation explicitly states "route to DeepSeek/
open-weight when [vendor] declines a security-research task." What exists instead is generic
reliability/cost/latency failover (pre-validate fallback models, watch for tool-call-behavior
differences across models) — not safety-policy-driven routing. The closest concrete pattern is a
genuine sub-cluster within `awesome-deepseek-harness` of multi-provider model-routing/health-
check plugins (see below), but none of them are documented as keyed on safety-decline detection.

### Corrected characterization of `awesome-deepseek-harness`

Confirmed by fetching the raw README directly (204,435 characters, read in full): this is a
**third-party/community catalog**, not an official DeepSeek list — titled "Awesome DeepSeek
Harness," sourced from a `dsh-external` GitHub org, no named maintainer affiliated with
DeepSeek. The `@deepseek-ai/dsh` runtime it catalogs plugins *for* is confirmed real (DeepSeek's
own docs corroborate "DeepSeek Harness" as a real product in developer preview), but the
awesome-list wrapping it is community-curated, not official.

It is, as suspected, overwhelmingly a plugin catalog for the DSH **chat client** — UI themes,
composer/session UX, billing/cost dashboards, memory, browser/desktop control, remote access —
mostly UI chrome, not harness-engineering principles. Section headers found: "Agents &
Orchestration," "Models & Inference," "Dashboards & Session UX," "Security & Governance," among
others.

**Substantively relevant entries found** (not UI chrome):

- *Multi-provider routing/health-checking*: `welsione/dsh-model-router` (one logical model ID
  across providers, first-token failover + cooldown); `dsh-baseurl-probe` and
  `dsh-llm-compat-healer` (Semidia — auto-detect/repair provider API-compatibility issues);
  `dsh-provider-health` (Semidia — time-decayed, error-based per-provider health scoring);
  `dsh-ha-orchestrator` (Saktawdi — quarantine/circuit-breaking/probe-based recovery);
  `JohnXu22786/model-catalog` (model/pricing/capability discovery across hosts).
- *Security/audit*: `dsh-event-auditor` (read-only event-flow audit panel); `dsh-netshell`
  (permission levels, explicitly states it is **not** a security sandbox); `dsh-budget`
  (session/daily/monthly cost caps with alert/block/degrade policies); `computer-control`
  (allow/deny rules, confirmation flow, emergency stop for desktop/browser-control plugins).
- *Other genuine harness-engineering practice*: `dsh-dual-model-eval` (runs one prompt across
  models in isolated git worktrees, compares results); `dsh-agent-arena` (compares coding agents
  with deterministic scoring); `dsh-trajectory-debug` / `dsh-replay` (deterministic
  replay/breakpoints); `goal-acceptance` (locks verifiable acceptance criteria before work,
  requires reviewer sign-off); `dsh-todo-guard` (three-state verification of completion
  evidence); `cleverer-dsh` (blocks identical retries, forces reflection).

Bottom line: the original characterization stands — it's primarily a UI/UX plugin catalog for a
specific chat client, with a real, non-trivial sub-cluster of multi-provider routing/health-check
plugins and a smaller cluster of genuine harness-engineering plugins buried within it.

### Relevance to exhaust's `AgentSession` design

- **The content-policy motivation is currently unverified** — worth stating explicitly in
  exhaust's own docs/ADRs as "unverified, revisit if DeepSeek or Anthropic publish more specific
  guidance," rather than asserting it as settled fact.
- **The OpenAI-compatible API shape is a real, usable design input.** Since DeepSeek's endpoint
  is OpenAI-shape-compatible and tool-calling reportedly follows the same convention, a backend
  adapter for DeepSeek can plausibly share most request/response marshaling with any
  OpenAI-compatible adapter exhaust would need anyway — DeepSeek doesn't need a bespoke
  implementation, just an OpenAI-compatible one pointed at a different base URL and key.
  Concrete implication: design `AgentSession` backend adapters around "OpenAI-compatible" as a
  reusable class/mixin, not one adapter per named vendor — DeepSeek, OpenRouter, and most
  open-weight gateways would then reuse it.
- **The model-router pattern from `awesome-deepseek-harness`** (health-checked failover, one
  logical model ID over multiple providers) is worth borrowing conceptually as a thin routing
  layer in front of `AgentSession` — but no existing harness uses this pattern keyed on
  *safety-decline detection*. If exhaust wants decline-triggered backend switching, that's a
  novel design choice with no existing precedent to cite.

## 10. Consolidated gap list — what this research most concretely suggests for exhaust

Pulling the sharpest, most convergent critiques across all nine clusters into one list, roughly
ordered by how load-bearing the underlying principle is:

1. **The Rig's allowlist likely checks method names, not argument content** (§3) — a call to an
   allowlisted method with attacker-steered arguments may not be independently validated. Worth
   confirming whether the Scope Contract re-check for `RealTargetCall` inspects argument content
   or only the call's category.
2. **No evident synchronous human-approval gate for a specific consequential real-Target action**
   (§4) — the Scope Contract answers "is this target in scope," not "should this exact
   destructive action happen now." This is the single most repeated gap across the security and
   HITL clusters independently.
3. **SelfReport exhaustion claims and ambiguous Findings are under-escalated relative to
   `blocked`** (§5, §6) — two independent research clusters converged on the same critique:
   "exhausted" is a different, less-verifiable speech act than "stuck," and ambiguity itself
   (not just dead-ends) is treated by the HITL literature as a first-class escalation trigger
   exhaust's single `blocked` gate may not catch.
4. **No credential-isolation/broker story for the Rig or for any real-Target authentication**
   (§3, §4) — worth an explicit design decision given this is more safety-critical for a
   security-research harness than for a generic coding agent.
5. **No tracing/observability layer and no "Harness Card"-equivalent for cross-backend
   comparison** (§5) — becomes load-bearing the moment exhaust is evaluated across more than one
   agent backend, given the measured harness-effect/Binding Constraint Thesis finding that
   harness config can dominate or reverse model-driven differences.
6. **Watch for M-CPE/X-CPE-style trust promotion at the context-assembly layer, not just at
   Target-output ingestion** (§4) — anything externally-influenced that reaches a "trusted" field
   (a Finding's title/description, say) without passing through the same delimiting discipline as
   direct Target output is a laundering path into exhaust's own trusted evidence store.
7. **Whether exhaust's `observe(outcome) -> None` actually closes the loop back into `step()`'s
   next request with what was learned, or just updates state and discards the lesson** (§1) — the
   literature's single most repeated context-engineering principle is that feedback must modify
   future guidance, not terminate into a void.
8. **Instrumentation (run IDs, tool-call counts, token budgets) is cheap now and expensive to
   retrofit** (§7) — the highest-leverage, lowest-cost action item in the entire research pass,
   independent of whether any of the above gaps are ever addressed.
9. **No stated eval-awareness-style threat model for exhaust's own Oracle/attempt-log validator**
   (§5) — a capable agent could in principle reason about `_validate_exhaustion`'s exact rules
   and game them, the same way models have been observed reasoning about benchmark identity.

None of these are framed as "exhaust is wrong" — several (the closed `AgentAction` union, the
host-run Oracle requirement, the crash-blocks-not-retries rule, the append-only attempt log) are
independently flagged across multiple research clusters as *stronger* than what most of the
surveyed literature actually does. The gap list above is specifically the set of places where
exhaust's current design is silent on something this literature treats as necessary, not a
claim that the existing design is deficient.

## Cross-reference to the agent-backend-abstraction research

Several items here bear directly on open questions in
`docs/research/2026-10-27-agent-backend-abstraction-research.md`:

- The Claude Agent SDK's `canUseTool` callback (already corrected in that document as a true
  blocking veto) is the closest existing implementation of the Fowler "guides vs. sensors" and
  12-Factor "contact humans with tool calls" patterns described here — worth citing cross-
  document if that section is revisited.
- Claude Managed Agents' `user.tool_confirmation` flow (§8 of that document) is structurally the
  AWS "third-party asynchronous" / "protocol-native real-time" approval model named in §6 here.
- The DeepSeek OpenAI-compatible-adapter conclusion in §9 here is a concrete, actionable design
  input for that document's open question about how `AgentSession` should support multiple
  backends.

## Sources — full bibliography by cluster

Every cluster's researching agent reported which sources were fetched directly vs. found only
via search/secondary summary; that distinction is preserved in-line throughout this document
rather than flattened here. Notable fetch failures worth knowing about for future passes:

- OpenAI's "Harness engineering" (Lopopolo) and "Unrolling the Codex Agent Loop" (Bolin), and
  "Running Codex safely," all returned HTTP 403 to automated fetching in every attempt across
  three independent research passes — their content here is secondary-sourced only. A
  browser-based fetch (not attempted in this pass) might succeed where the plain fetch tool did
  not.
- Anthropic's "Beyond permission prompts" returned 404 at both the URL given and a guessed
  canonical URL, with no mirror found; its content is corroborated only indirectly via "How we
  contain Claude," which *was* fetched and gives matching figures (93%/83% approval rates).
- `github.com/anthropics/ai-harness-scorecard` returned 404 and does not appear to currently
  exist publicly under Anthropic's org.
- Microsoft's Azure SRE context-engineering post returned no body to direct fetch (likely
  JS-rendered); covered via a third-party summary (ZenML) instead — its specific figures should
  be treated as self-reported/unvalidated per that summary's own caveat.
- businessengineer.ai's "The Harness as the Agentic Moat" is paywalled past the introduction.

Full per-claim attribution is given inline throughout §1–§9 above rather than restated here.
