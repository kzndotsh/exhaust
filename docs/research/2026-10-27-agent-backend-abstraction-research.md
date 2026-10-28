# Research: how a harness actually invokes an agent/LLM

**Superseded for the decision itself**: [ADR 0025](../adr/0025-agentsession-is-backed-by-pi-gated-by-a-thin-relay-extension.md)
settled `AgentSession`'s first implementation on the vendor-agent-SDK row of this
document's own comparison table (Pi, specifically) — see
[`2026-10-27-pi-harness-audit.md`](2026-10-27-pi-harness-audit.md) for the dedicated research
that led there. This document's comparative survey of the other approaches remains accurate and
useful if that decision is ever revisited, which is why it's kept rather than deleted.

Input to a future ADR on `AgentSession` (src/exhaust/harness/agent.py), not a recommendation.
exhaust's `Harness` drives one `AgentSession` through typed `step(request) -> AgentAction` /
`observe(outcome)` calls; `AgentAction` is a closed union (`SandboxCall`, `RealTargetCall`,
`RecordFinding`, `ProposeVerdict`, `SelfReport`, `SetVerticalState`,
src/exhaust/harness/actions.py). Every approach below is evaluated against that specific
shape: can a concrete adapter extract exactly one `AgentAction` per `step()` call and feed
back exactly one validated `ActionOutcome`, without the agent itself ever holding the real
provider credential (ADR 0021) or supplying its own Oracle result.

## 1. Raw provider API / tool-use loop (Anthropic Messages API)

**What it is.** A single stateless HTTP endpoint (`POST /v1/messages`). The caller owns the
entire loop: send messages, read `tool_use` blocks, run the tool, append a `tool_result`,
send again. No agent runtime exists outside the caller's own process.

**Concrete shape.** A request carries `model`, `max_tokens`, `messages`, and a `tools` array
of `{name, description, input_schema}` (JSON Schema). Claude's response is a `Message` whose
`content` is a list of typed blocks; when it wants to call a tool, `stop_reason` is
`"tool_use"` and one or more blocks have `{"type": "tool_use", "id": ..., "name": ...,
"input": {...}}`. The caller runs the named tool and appends a new `user` message containing
`{"type": "tool_result", "tool_use_id": <id>, "content": ...}`, then calls `/v1/messages`
again with the full accumulated `messages` list (the API is stateless; history is sent on
every call). Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview

**Cost/benefits for exhaust's shape.** This is the closest fit to `AgentSession.step`/
`observe` conceptually — one `tool_use` block maps naturally to one `AgentAction`, and
`observe()` maps naturally to appending one `tool_result`. Every byte of state (procedure,
transcript, available tools) is explicit and harness-owned, which fits ADR-0021's "agent
never holds the real LLM credential" cleanly: the harness process is the only thing that ever
calls the provider. The cost is that the harness must hand-write everything an agent SDK gives
for free: context/window management, retry/backoff, prompt caching, parallel-tool-call
handling, and any notion of "subagent." Dependencies: just an HTTP client or the thin
`anthropic` SDK (which only wraps request/response marshaling, not a loop).

**Known adopter.** Any hand-rolled tool-use loop built directly against the Messages API;
this is the substrate every vendor SDK below is built on top of. exhaust's own prior audits
describe several bespoke loops built this way (e.g. the cyber-harness and defending-code
reference harness both run their own model-call loop against a provider API directly, see
`docs/research/2026-10-26-cyber-harness-audit.md` and
`docs/research/2026-10-26-defending-code-reference-harness-audit.md`).

## 2. Vendor agent SDKs (Claude Agent SDK, OpenAI Agents SDK, Cursor SDK, Google ADK, Pi, fx)

**What it is.** A library that owns the tool-use loop, session/context management, and (for
Claude's SDK) the same built-in toolset Claude Code ships with, callable as a Python/TS
library rather than a CLI subprocess.

**Claude Agent SDK.** `query(prompt, options)` runs a full agent loop; a custom tool is
defined with `@tool(name, description, input_schema)` (Python) / `tool()` (TS), then wrapped
in `create_sdk_mcp_server(name, version, tools=[...])` and registered via
`ClaudeAgentOptions(mcp_servers={...}, allowed_tools=[...])`. This in-process MCP server runs
inside the same process — no subprocess or network hop — and the tool is addressed as
`mcp__{server}__{tool}`. A handler returns `{"content": [...], "structuredContent": ...,
"isError": ...}`, the same `CallToolResult` shape MCP defines. Subagents are separate agent
instances the main agent can spawn via the `agents` option, markdown files in
`.claude/agents/`, or the built-in general-purpose subagent — a layer exhaust's one-harness-
one-agent relationship has no use for. Sources:
https://code.claude.com/docs/en/agent-sdk/custom-tools ,
https://code.claude.com/docs/en/agent-sdk/subagents

**OpenAI Agents SDK.** Agents, tools (`@function_tool`), and *handoffs* — a handoff is
literally a specialized tool call (the model sees a synthesized `transfer_to_<agent_name>`
tool) that transfers the whole conversation to another agent instance. A separate pattern,
"agents as tools," keeps one manager agent in control and calls other agents as ordinary
tools instead of transferring control. Sources: https://pypi.org/p/openai-agents-python and
the OpenAI Agents SDK docs (official site not reached directly in this pass; corroborated by
multiple third-party summaries of the same PyPI/GitHub material).

**Cursor SDK (Python `cursor-sdk`, TypeScript `@cursor/sdk`).** "The same agent that runs in
the Cursor IDE, CLI, and web app is scriptable from Python with sync and async clients" — and
the equivalent is true of the TypeScript package. `Agent.create(...)` returns a durable agent
handle; passing `local=LocalAgentOptions(cwd=...)` runs the agent loop in your own process
against files on disk, while `cloud=CloudAgentOptions(...)` runs it in a Cursor-hosted VM
instead. Each `agent.send(prompt)` call returns a `Run`; `run.stream()`/`run.messages()`
yields typed events discriminated on `type` (`assistant`, `thinking`, `tool_call`, `status`,
`usage`, ...). A custom tool is a plain function registered via `LocalAgentOptions.custom_tools`
/ `local.customTools` with `{description, input_schema/inputSchema, execute}` — the SDK exposes
the whole set to the agent as a single MCP server named `custom-user-tools`, and `execute` runs
synchronously in the caller's own process. `tool_call` events fire once at start carrying
`args`, and again on completion carrying `result`, correlated by call id — directly analogous
to MCP's `tools/call` request/response pair but surfaced as a stream the harness can watch
without being the dispatch target itself (unless using custom tools, where the harness *is*
the dispatch target). `run.cancel()` stops an in-flight run, and the TS SDK additionally
exposes `run.steer(text)`, which injects a message into a running *local* turn mid-flight.
Agents are resumable (`Agent.resume(agent_id)`, with `bc-`-prefixed ids routing to the cloud
runtime), with local conversation state persisted through a bundled local server called the
**Bridge** (`cursor-sdk-bridge`) — a small loopback-bound process, speaking protobuf-over-
Connect (explicitly not classic gRPC: "Classic gRPC over HTTP/2 will not connect"), that the
Python SDK already bundles and the TypeScript SDK embeds directly; it exists so a third
language with no first-party SDK could still script the same agent against the identical
`sdk.v1` wire contract. Both SDKs' docs are explicit that hooks are file-based only
(`.cursor/hooks.json`) with "no programmatic hook callback," and that `tool_call` payload
shapes ("`args` and `result` ... are not stable") should be parsed defensively. Sources:
https://cursor.com/docs/sdk/python, https://cursor.com/docs/sdk/typescript,
https://cursor.com/docs/sdk/bridge (all fetched directly, 2026-10-27; the TypeScript page is
125k characters and only the first 100k were read in this pass).

**Google Agent Development Kit (ADK).** A code-first agent framework, officially shipped in
four languages: Python (the reference implementation, broadest model-adapter coverage —
Gemini, Anthropic, OpenAI, and LiteLLM — and the most Google Cloud integrations), Java, Go,
and TypeScript (`npm install @google/adk`, from `github.com/google/adk-js`; the TS package's
own README states "API Stability: Mostly stable, but expect potential breaking changes before
1.0" and "Production Use: Not recommended yet" — so it is officially shipped but explicitly
pre-1.0). Agent logic, tools, and orchestration are defined directly in the host language, the
same "decorated function + schema" shape as the other two SDKs here; Google recommends either
its own Vertex AI Agent Engine Runtime or a self-hosted container (e.g. Cloud Run) for
deployment. Sources: https://developers.googleblog.com/introducing-agent-development-kit-for-typescript-build-ai-agents-with-the-power-of-a-code-first-approach/
and the `google/adk-js` repository (both via WebSearch summaries in this pass, not fetched
directly — treat version/stability claims as needing a direct-source check before relying on
them further). Do not confuse this with `adk-typescript` (`njraladdin/adk-typescript`), an
unrelated, unofficial third-party port with its own package name.

**Cost/benefits for exhaust's shape.** The pluggable-tool extension point in all three SDKs is
exactly a typed function/schema/handler triple — structurally compatible with wrapping
`AgentAction` dispatch as a single tool (or one tool per `AgentAction` variant) the SDK calls
and whose return value is `observe()`'s input. Of the three, **Claude Agent SDK's `canUseTool`
callback is the actual per-action blocking rendezvous exhaust's shape wants**, not just an
observability hook as earlier drafts of this research hedged: it fires synchronously before a
tool neither an allow rule nor the active permission mode has already resolved, the call
"pauses execution until your callback returns" (the callback "can stay pending indefinitely"),
and the callback returns either `PermissionResultAllow(updated_input=...)` — which can modify
the tool's arguments before they run — or `PermissionResultDeny(message=...)`, which blocks
the tool and feeds Claude a rejection message it sees as the tool result, directly
analogous to `ActionRejected` carrying a reason the model must retry against. This is
materially better evidence than the earlier hedge in this document, which treated `canUseTool`
as a weaker, partial-visibility hook; it is not. Permission modes (`default`, `plan`,
`dontAsk`, `auto`, `bypassPermissions`) decide which calls reach `canUseTool` at all — e.g.
`dontAsk` and `bypassPermissions` skip the callback for most or all calls, which matters for an
exhaust adapter choosing a mode deliberately (`default` to guarantee every `AgentAction` is
routed through the callback, never `dontAsk`/`bypassPermissions`, which would let calls through
unchecked). Cursor's `tool_call` event pair (`args` at start, `result` at completion,
correlated by call id, delivered as a typed stream event) is, by contrast, genuinely only an
*observability* stream unless the call targets a registered custom tool, where the harness's
own `execute` function is the handler — same shape as Claude's `@tool`, but Cursor's own docs
are explicit that hooks are file-based only with "no programmatic hook callback," so there is
no Cursor-SDK equivalent of `canUseTool` for built-in tools. Cursor's `run.cancel()`/
`run.steer()` add a mid-turn control surface none of the other SDKs documented here expose.
What you gain over raw API, across all three: built-in context window management
(Claude's SDK auto-compacts and emits a `compact_boundary` event when it does), retry handling,
and (for Claude's and Cursor's SDKs) direct access to the same first-party toolset their own
CLI ships with. What you give up: the SDK's own agent loop still decides tool-call
batching/parallelism (Claude's SDK runs read-only tools concurrently, state-mutating ones
sequentially, by a `readOnlyHint` annotation) and retry timing; and credential handling wants
care — the SDK process is the one making model calls, so ADR-0021's proxy would sit between
the SDK's HTTP client and the real provider (via a custom base URL, an `apiKeyHelper`, or
Cursor's `CURSOR_API_KEY`/`options.api_key`), which all three support but none is designed
around. Dependency weight: a full package (`@anthropic-ai/claude-agent-sdk`, `openai-agents`,
`cursor-sdk`/`@cursor/sdk`, or `@google/adk`) plus, for Claude's and Cursor's SDKs, a bundled
native binary under the hood (the `claude` CLI binary and the `cursor-sdk-bridge` binary
respectively) rather than a pure-library footprint. Sources (this pass, fetched directly,
2026-10-27): https://code.claude.com/docs/en/agent-sdk/agent-loop.md,
https://code.claude.com/docs/en/agent-sdk/user-input.md.

**Known adopter.** The oss-crs audit documents wrapping Claude Code and Codex as backends in
a CRS framework (see section 6); the Claude Agent SDK's own docs describe it as "the same
engine as Claude Code... as a library" for embedding (secondary-source corroboration from a
WebSearch result, flagged as such in the search summary above and not independently verified
against the official architecture page). No exhaust prior audit documents a Cursor SDK or ADK
adopter; both are new findings in this research pass, not corroborated against exhaust's own
audited tools.

**Caveat: subscription (Pro/Max) auth is not a credential source exhaust should plug into the
Claude Agent SDK.** The SDK does no authentication of its own — it spawns the `claude` binary,
which "reads whatever credentials it's already configured with," so a machine logged into Claude
Code via a Pro/Max subscription (no `ANTHROPIC_API_KEY` set) would have the SDK ride on that
subscription session rather than metered API billing. Mechanically possible; not something to
build on. Anthropic's usage policy (fetched directly, 2026-10-27,
https://www.anthropic.com/legal/aup) prohibits, under "Do Not Abuse Our Platform," "services that
route requests through consumer subscriptions" — aimed at reselling, but exhaust as a built tool
reads closer to that category than to "ordinary individual use of Claude Code." Secondary
reporting (not independently verified against Anthropic's current legal/compliance page, which
returned 404 on direct fetch) describes Anthropic's developer guidance as API-key billing for
anything built on the Agent SDK, and notes that an earlier line permitting OAuth tokens with the
Agent SDK has reportedly been removed; a May 2026 plan to give Agent SDK usage its own
subscription-linked credit tier was announced and then paused days before taking effect, which is
itself a signal this isn't settled policy. Independent of the policy question: ADR-0021's
credential-isolation design (a budget-capped virtual key per run, issued through a local proxy)
has no equivalent for an OAuth subscription session — there's no key to scope or cap the same way
— so subscription auth doesn't fit exhaust's existing credential model even if the policy
question resolved favorably. Treat this as unresolved, not as a cost-saving option to build
toward.

**Pi (`pi.dev`, package `@earendil-works/pi-coding-agent`).** A deliberately minimal,
provider-agnostic agent toolkit — explicitly *not* a single vendor's SDK, since it runs over
15+ model providers through one `ModelRuntime` abstraction. `createAgentSession()` returns an
`AgentSession` owning one conversation, its model, tools, and queue; `session.prompt(text)`
runs a turn, `session.subscribe(listener)` delivers typed events (`message_update`,
`message_end`, `agent_end`, `agent_settled`, tool/queue/compaction/retry events) before or
during a run. A turn is: build a request from the system prompt, active conversation branch,
and tool definitions → the provider streams an assistant response with text and/or tool calls
→ Pi executes each tool call and records the result → repeat if more work is queued, otherwise
the run ends. `customTools` is a constructor option on session creation, though the exact
schema/handler shape wasn't reached in this pass (deferred to an example file not fetched).
Sessions are JSONL trees on disk — `SessionManager.inMemory()` opts out — where each entry
has an id and parent, supporting continue (new branch from an existing entry), fork, clone, and
compaction (a summary entry replacing older ones, originals retained in the tree). Pi also has
a non-embedded mode: `pi --mode rpc --no-session` runs it as a long-lived subprocess speaking
newline-delimited JSON (one JSON object per line, strict LF framing) over stdin/stdout —
Command records in, Response/session-event records out, correlated by an optional `id` the
caller supplies. **The decisive gap for exhaust's shape: Pi has no synchronous per-call
approval hook at all**, in either mode. Its own security docs say plainly that "it doesn't ask
for approval before each tool call" and tools "run with the operating-system permissions of the
Pi process" — "project trust" gates whether `.pi` config, MCP config (so MCP *is* supported,
contrary to some third-party "no MCP" characterizations), extensions, and skills load at
startup, but explicitly "does not limit what tool calls can access or change after startup."
Of every pattern surveyed in this document, Pi sits at the opposite end from Claude Managed
Agents' server-enforced block/ask/deny (section 8): it's the one agent runtime here with *no*
host-side veto point an exhaust adapter could hang `ActionRejected` on — an adapter would have
to layer its own gate entirely outside Pi (e.g. wrapping each tool it registers via
`customTools` so the gate lives in the handler, not in the framework), rather than relying on
anything Pi itself enforces. Sources (fetched directly, 2026-10-27):
https://pi.dev/docs/latest.md, https://pi.dev/docs/latest/how-pi-works.md,
https://pi.dev/docs/latest/sdk.md, https://pi.dev/docs/latest/rpc.md,
https://pi.dev/docs/latest/security.md.

**Correction (2026-10-27, dedicated follow-up pass):** the "no synchronous per-call approval
hook at all" claim above is wrong. This pass never fetched `extensions.md`, where Pi's actual
gate lives: `pi.on("tool_call", ...)` fires before a tool executes, can block with a reason, and
fails closed on a throwing handler — confirmed against both the docs and the dispatch source
itself, and attachable to an embedded SDK session via `resourceLoader`/`extensionFactories`, not
just the CLI. Pi belongs in the same tier as Claude Agent SDK's `canUseTool`, not at the bottom
of this survey. See [`2026-10-27-pi-harness-audit.md`](2026-10-27-pi-harness-audit.md) for the
full corrected treatment.

**fx (`fx.sh`, Vercel Labs, a sibling project to `deepsec` covered in the harness-engineering
audit's §4).** A coding agent written in Zig, shipped as a single native binary with no runtime
dependency, explicitly positioned to "run the same way on a laptop, in CI, or in an agent
sandbox" rather than only inside an IDE — labeled experimental. Its embeddable core, **libfx**, is
a separate artifact from the `fx` CLI: a JavaScript-facing agent core shipped as both a native
Node.js addon and (experimentally) WebAssembly, with its own API surface (prompts/streaming,
tools, images, steering, save/restore, durability) independent of the CLI's terminal UX — making
it the only project surveyed in this document, alongside Cursor's SDK/Bridge split, that
deliberately separates "the agent as an embeddable library" from "the agent as a CLI" as two
first-party artifacts rather than treating the CLI as the only front end. Tools in libfx are
"JavaScript functions the agent can call," the same plain-function-plus-schema shape as every
other SDK surveyed here; the exact custom-tool registration call wasn't named in the pages
reached in this pass (only `llms.txt`'s page index, not the full API reference, was fetched).

**Provider flexibility is the most notable thing about fx's design.** Per its own docs, both the
CLI and libfx can run against "AI Gateway, a ChatGPT or Grok plan, or an OpenAI-compatible
server" — i.e. a first-party agent tool that treats a **consumer subscription login** (ChatGPT
Plus/Pro, presumably OAuth-based like Claude Code's) as one of three equally first-class backend
options, alongside a metered gateway and any OpenAI-compatible endpoint (Ollama, vLLM,
OpenRouter named explicitly). This is directly relevant to the subscription-vs-API-billing
question already raised for the Claude Agent SDK in this document: fx's own vendor treats
subscription-backed agent use as a supported, documented path rather than a gray area, which is
a useful data point that this pattern exists elsewhere in the field — but it says nothing about
whether *OpenAI's or xAI's own usage policies* permit it any more cleanly than Anthropic's does;
that would need the same kind of direct policy check given to Anthropic's AUP earlier, not fetched
in this pass, so don't read "fx supports it" as "it's unambiguously allowed."

**CLI and protocol surface.** `fx ask` runs a non-interactive request and can emit JSON
(`fx ask --json "<prompt>"`), continuing a saved session the same way Claude Code's `--continue`/
`--resume` does, though the exact output schema wasn't reached in this pass (the summarized page
didn't enumerate fields; `llms-full.txt` would have them). `fx acp` serves the **Agent Client
Protocol** over stdio — the same ACP that osmedeus (section 6) uses to drive *external* CLIs
generically, except here fx is the thing being driven, i.e. fx is a concrete instance of "the
external CLI an ACP-speaking orchestrator like osmedeus could plug in," not a new abstraction of
its own. Skills load from `.fx/skills`, `~/.fx/skills`, and, notably, also from `.claude/skills`
and `.agents/skills` — direct, first-party interoperability with Claude Code's and the open
AGENTS.md ecosystem's skill directories, reinforcing the harness-engineering audit's §8 finding
that the Agent Skills markdown-plus-frontmatter shape is becoming a de facto cross-vendor
standard, not a Claude-specific convention. Default permission mode (`auto`) routes "other
actions" through a model-based check for prompt injection or malicious behavior before holding
them — structurally similar to Claude Code's auto-mode classifier (already covered in this
document's §2 and the harness-engineering audit's supplementary findings), another independent
confirmation that a separate-model-reviews-the-action pattern is converging across vendors rather
than being one company's idiosyncratic design. Source: https://fx.sh/llms.txt and the raw GitHub
README, both fetched directly, 2026-10-27; the full page content behind each `llms.txt` summary
line (output schemas, the libfx API reference, ACP server setup detail) was not fetched in this
pass and would need a follow-up read before citing exact field names.

## 3. MCP (Model Context Protocol) — exposing exhaust's own tools to an arbitrary agent

**What it is.** A JSON-RPC-based protocol for a *server* (exhaust's own process) to expose
tools, resources, and prompts to an arbitrary *client* (whatever agent runtime the client
side chooses), over stdio or HTTP. exhaust would be the server; the agent/its SDK would be
the client. This use is the inverse of section 2 (section 2 is exhaust *consuming* an agent
SDK; this section is exhaust *exposing its own* Rig bridges, ledger ops, and finding/verdict
recording as MCP tools so any MCP-capable agent can be swapped in without a bespoke adapter
per framework).

**Concrete shape.** A three-phase lifecycle — initialization (capability negotiation +
protocol version), operation, shutdown
(https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle). A server that
exposes tools declares `{"capabilities": {"tools": {"listChanged": true}}}` during
initialization. The client lists tools with `tools/list` (returns `{name, title, description,
inputSchema, outputSchema?, annotations?}` per tool, paginated via `cursor`/`nextCursor`) and
invokes one with `tools/call` → `{"name": ..., "arguments": {...}}`, getting back
`{"content": [...], "structuredContent"?, "isError"?}`. Protocol-level failures (unknown
tool, bad arguments) are JSON-RPC errors; tool-level failures are results with `isError:
true`. Source: https://modelcontextprotocol.io/specification/2025-06-18/server/tools

**Cost/benefits for exhaust's shape.** MCP is model-controlled by design: "the language
model can discover and invoke tools automatically based on its contextual understanding,"
and the spec explicitly says implementations are free to choose any interaction pattern — it
does not mandate a single-action-at-a-time rendezvous. Exposing exhaust's six `AgentAction`
variants as six (or fewer, parameterized) MCP tools would let *any* MCP-capable agent runtime
drive the harness without exhaust writing a bespoke adapter per framework — a real win for
the "support multiple ways of running the agent" goal, and it reuses a spec every major
vendor SDK already speaks (both Claude Agent SDK and OpenAI's support MCP natively). The
cost: MCP's `tools/call` is a stateless, fire-and-forget RPC from the server's point of view
— the spec's own security guidance assumes a human-in-the-loop UI layer on the *client* side
deciding whether to approve a call, not a strongly-typed host-side validator that can refuse
and hand back a structured rejection the model must retry against, which is what
`ActionRejected` is. `isError: true` is the closest primitive and it is weaker than exhaust's
own validated-outcome model: it is prose in a content block, not a typed `ActionOutcome`.
MCP also doesn't itself express ADR-0021's credential isolation; the agent-side MCP *client*
still needs its own LLM credential from somewhere, MCP only concerns exhaust's own
tool-exposure surface, not how the agent gets to the model at all.

**Known adopter.** Both vendor SDKs in section 2 use MCP as their own tool-plumbing
substrate (the Claude Agent SDK's in-process custom tools literally return the MCP
`CallToolResult` shape). Strix (per `docs/research/2026-10-26-strix-audit.md`) exposes its
own internal tool surface — coverage, reporting, multi-agent coordination — through MCP with
a narrow, five-tool dispatch surface, which ADR-0018 already cites approvingly as a model for
a narrow enumerated bridge.

## 4. A2A (Agent2Agent protocol)

**What it is.** A protocol for independent, potentially opaque agent systems — built on
different frameworks, by different vendors, in different organizations — to discover each
other and delegate tasks, originally released by Google in April 2025 and now developed
under the Linux Foundation / Agentic AI Foundation via the `a2aproject` GitHub organization.
Source: https://a2a-protocol.org/latest/specification/

**Concrete shape.** Each participating agent publishes an **Agent Card** — a JSON document
(name, capabilities, skills, service endpoint, auth requirements, optionally a JWS
signature) conventionally served at `/.well-known/agent.json`. Work is delegated as a
**Task**, which has an id, optional `contextId`, a status (`state` + optional message +
timestamp), optional artifacts and history. Task states split into interrupted
(`INPUT_REQUIRED`, `AUTH_REQUIRED`), terminal (`COMPLETED`, `FAILED`, `CANCELED`,
`REJECTED`), and in-flight (`SUBMITTED`, `WORKING`). A **Message** carries a `messageId`,
optional `contextId`/`taskId`, a `role` (`ROLE_USER`/`ROLE_AGENT`), and one or more `Part`s
(text, file, or structured data); results belong in **Artifacts**, not Messages. v1.0
(current stable) defines three transport bindings: JSON-RPC 2.0, gRPC, and HTTP+JSON.
Source: https://a2a-protocol.org/latest/specification/ (fetched directly, first 100k
characters).

**Fit assessment — honest, not spun positive.** A2A is designed for peer delegation across
organizational/vendor boundaries where the two sides don't share internal state, memory, or
tools, and may not trust each other's internals at all — the spec's own framing is
"independent, potentially opaque AI agent systems." That is a materially different
relationship from exhaust's: one `Harness` process driving one `AgentSession` it instantiated
itself, where every action must be individually typed, validated, and gated by host-side
checks (Scope Contract, Oracle, evidence promotion) that assume full visibility into the
single agent's intent at the granularity of one tool call. A2A's task lifecycle is built
around coarse, potentially long-running, asynchronously-polled units of work ("submitted" →
"working" → terminal), not a tight step/observe rendezvous per atomic action; nothing in the
Task/Artifact model maps naturally onto "propose exactly one `AgentAction`, get back exactly
one validated `ActionOutcome`." The Agent Card discovery/auth model solves a problem exhaust
doesn't have (exhaust always knows exactly which agent it's driving — it started the
process). A2A would be a plausible fit if exhaust ever needed to delegate a whole vertical to
an external, untrusted agent service it doesn't control the internals of; it is a poor fit
for the Harness-to-single-agent seam this research is about, and should not be adopted on
"it's newer" grounds alone.

## 5. CLI-invocation (driving a coding/agent CLI as a subprocess)

**What it is.** Treating a mature agent CLI (Claude Code, Codex CLI, etc.) as an opaque
subprocess: write a prompt to argv/stdin, read structured output from stdout, check the exit
code.

**Concrete shape (Claude Code).** `claude -p "<prompt>" --allowedTools "..."` runs
non-interactively; exit code 0 on success, non-zero on failure, 143 on SIGTERM.
`--output-format json` returns one JSON object with `result`, `session_id`,
`total_cost_usd`, and per-model cost breakdown; `--output-format stream-json` emits
newline-delimited events, including `assistant`/`user` messages carrying `tool_use`/
`tool_result` blocks, a `system/init` event reporting loaded tools/MCP servers/plugins, and a
final `result` event. `--json-schema` plus `--output-format json` constrains the final answer
to a given JSON Schema, surfaced in a `structured_output` field — but this only shapes the
CLI's final textual answer, not individual tool calls as they happen. `--continue`/`--resume
<session_id>` thread multi-turn state across separate subprocess invocations; `--bare` skips
auto-discovery of hooks/skills/MCP servers/CLAUDE.md for reproducible CI-style runs — the docs now
call `--bare` "the recommended mode for scripted and SDK calls, and will become the default for
`-p` in a future release," and are explicit that bare mode never reads OAuth/subscription
credentials, only `ANTHROPIC_API_KEY` or an `apiKeyHelper`. `--permission-prompts none` is the
flag for a genuinely unattended run: it stops the process from waiting on a permission host at
all (an Agent SDK `canUseTool` callback or a `--permission-prompt-tool`), denying anything nothing
else resolves rather than blocking on it. The `stream-json` event vocabulary is richer than a bare
transcript: `system/api_retry` carries a typed `error` category (`rate_limit`, `overloaded`,
`authentication_failed`, etc.) plus `attempt`/`max_retries`/`retry_delay_ms`, and `system/init`
carries a `capabilities` array of protocol-behavior strings for feature-detection instead of
version-string comparison. Sources: https://code.claude.com/docs/en/headless (original pass),
re-fetched directly 2026-10-27 for the detail above.

**A variant worth distinguishing: a local headless HTTP server instead of a subprocess
transcript (opencode).** `opencode serve` doesn't print a transcript to stdout at all — it
starts a long-lived HTTP server (default `127.0.0.1:4096`, OpenAPI 3.1 spec at `/doc`) that the
opencode TUI itself connects to as an ordinary client, and that opencode's own SDK
(`@opencode-ai/sdk`, generated from that same OpenAPI spec) wraps. A caller creates a session
(`POST /session`), sends a prompt (`POST /session/:id/message`, blocking until the response, or
`/prompt_async` for fire-and-forget), and reads results either by polling
(`GET /session/:id/message`) or subscribing to `GET /session/:id/event`, a server-sent-events
stream beginning with a `server.connected` event. Most relevantly, opencode exposes a real
per-call permission endpoint — `POST /session/:id/permissions/:permissionID` with body
`{response, remember?}` — which exists specifically to answer a pending tool-approval request
(opencode's permission config separately resolves each action to `allow`/`ask`/`deny`, with
`--auto` approving everything not explicitly denied). This is structurally the same shape as
Claude Managed Agents' `user.tool_confirmation` (section 8) — a synchronous, per-call,
host-answerable gate — but reachable over a local HTTP API rather than a cloud session, and
without needing a subprocess-transcript-parsing adapter at all. The official server-docs page
reached in this pass names the endpoint but doesn't document the event that announces a
pending request or confirm the call blocks, so the full synchronous contract needs the OpenAPI
spec itself to verify, not just the docs page. Source (fetched directly, 2026-10-27):
https://opencode.ai/docs/server/; permission semantics corroborated via WebSearch against
https://opencode.ai/docs/permissions, not fetched directly.

**What you gain:** reuse of a mature, battle-tested agent loop (context management, its own
tool implementations, retry logic, cost tracking) with zero SDK integration work — just
process plumbing. **What you lose, concretely for exhaust's shape:** the CLI's internal tool
calls happen entirely inside its own process; the only host-side visibility into *individual*
tool calls is the `stream-json` transcript (readable, but after-the-fact and coarser than a
blocking "propose/validate/respond" rendezvous) or native hook points (`PermissionRequest`,
`canUseTool`-style callbacks in the Agent SDK wrapping the CLI) that can approve/deny but
don't let the harness substitute its own `ActionOutcome` cleanly into the loop's state the
way `AgentSession.observe()` implies. This exactly matches what exhaust's own osmedeus audit
already found independently (see section 6) — ACP-driven external CLIs give you only a
coarse permission callback, with neither the call's arguments nor result reliably reaching
the orchestrator; Claude Code's own native hook system is a materially richer version of the
same subprocess-CLI approach, not a different category, and needs checking on its own terms
rather than assumed to solve the granularity problem. ("ACP" here is Zed's Agent Client
Protocol, unrelated to the separate Agent Communication Protocol covered in §7.)

**Known adopter.** The oss-crs audit (section 6) documents OSS-Fuzz's CRS orchestration
framework running Claude Code and Codex headlessly, in production, today — proving the
operational pattern works, while also showing it gives up mid-run per-action control in favor
of a network-level budget + wall-clock timeout (`docs/research/2026-10-26-oss-crs-audit.md`).

## 6. How other harnesses solved this (from exhaust's own prior audits)

- **osmedeus** (`docs/research/2026-10-26-osmedeus-audit.md`) is the most directly relevant
  finding: it supports *three* distinct backend modes simultaneously — an embedded agent loop
  it fully owns, an external coding-agent CLI (Claude Code, Codex, OpenCode, Gemini) driven
  over the generic Agent Client Protocol (ACP — Zed's protocol, see the disambiguation in §7,
  not the Agent Communication Protocol also covered there), and a dedicated vendor SDK. Only the embedded
  loop allows per-action interception; over ACP, individual tool calls happen entirely inside
  the external CLI's process, with only a coarse permission callback (auto-approved wholesale
  in this implementation) as a hook — neither a call's arguments nor its result reach the
  orchestrating code. This is independent confirmation, from a real shipping tool, of exactly
  the granularity gap described in section 5 above.
- **oss-crs** (`docs/research/2026-10-26-oss-crs-audit.md`) wraps Claude Code and Codex
  headlessly as working production backends, settling that half of the open question
  (headless CLI invocation is operationally proven) while confirming the other half against
  exhaust's needs: it gives up all mid-run per-action control, relying entirely on a
  network-level LLM-call budget and a wall-clock timeout rather than any per-call gate. This
  audit also documents the credential pattern ADR-0021 already adopted: every CRS instance
  talks to a local LiteLLM proxy, never holding the real provider key directly, with the
  budget-capped virtual key mounted as a file rather than an environment variable.
- **Strix** (`docs/research/2026-10-26-strix-audit.md`) does not hard-code one SDK call
  shape for its own internal tools: it exposes a narrow, enumerated five-tool MCP dispatch
  surface for coverage/reporting/coordination, rather than giving the agent each remote MCP
  tool directly. But its actual pentest tools (nmap, sqlmap, ffuf) get raw shell access via a
  generic `exec_command`, i.e. the model-facing abstraction boundary is inconsistent within
  the same tool — tight for its own control-plane operations, loose for the actual offensive
  tool invocations.
- **Shannon** (`docs/research/2026-10-26-shannon-audit.md`) and **cyber-harness**
  (`docs/research/2026-10-26-cyber-harness-audit.md`) were audited primarily for their
  (absent) scope/authorization enforcement, not their agent-backend abstraction specifically;
  neither audit records them abstracting over multiple agent backends the way osmedeus does.
  cyber-harness's `core/decision` module (protobuf wire types for decisions) exists but
  nothing in the audited slice imports it, so it isn't evidence of a working abstraction
  either.
- **T3mp3st**, **REA**, and the **defending-code-reference-harness** audits
  (`docs/research/2026-10-26-t3mp3st-audit.md`, `2026-10-26-rea-audit.md`,
  `2026-10-26-defending-code-reference-harness-audit.md`) focus on verification/Oracle gaps
  and finding-lifecycle design, not on how each tool invokes its own LLM backend; no
  multi-backend abstraction was recorded in those audits.
- **The AIxCC-descended CRS framework** referenced in ADR 0021 is the same project audited
  as oss-crs above; see that bullet.

## 7. ACP (Agent Communication Protocol, agentcommunicationprotocol.dev)

**Disambiguation first.** This is a *different* protocol from the "ACP" named in §5–6 above
(Zed's Agent Client Protocol, which osmedeus uses to drive external coding-agent CLIs). The
two are unrelated specs that happen to share an acronym.

**What it is.** An open standard developed under IBM's BeeAI project, with the project's own
site describing it as "an open standard under the Linux Foundation." It frames its purpose as
fixing agent-ecosystem fragmentation — agents built in isolation across frameworks, teams, and
infrastructure, causing integration barriers and duplicated effort. Source:
https://agentcommunicationprotocol.dev/introduction/welcome (fetched directly, 2026-10-27).

**Concrete shape.** A RESTful API over standard HTTP, explicitly positioned against protocols
that need "specialized methods such as JSON-RPC" (a direct contrast with MCP's and A2A's
JSON-RPC-based transports). Billed as "async-first, sync supported," with streaming,
long-running tasks, and both stateful and stateless patterns; payloads are typed by MIME
content type (`input_content_types`/`output_content_types` on an agent's manifest, defaulting
to `["*/*"]`), so arbitrary formats pass through unchanged. An agent manifest otherwise
declares `name` and `description` (defaulting to the wrapped function's name/docstring in the
Python SDK) plus unspecified "capabilities," "metadata," and "runtime status" fields the
fetched pages describe as existing but don't define. Discovery can be online or offline, with
metadata embeddable directly in an agent's distribution package for disconnected or
scale-to-zero environments. Official Python and TypeScript SDKs exist; BeeAI, LangChain,
CrewAI, or custom-built agents can all implement the protocol. Sources:
https://agentcommunicationprotocol.dev/introduction/welcome,
https://agentcommunicationprotocol.dev/core-concepts/agent-manifest (both fetched directly,
2026-10-27). Neither page defines the actual run/task request-response wire shape (no
equivalent of A2A's Task/Message/Artifact schema was found in the fetched content); that detail
would need the linked OpenAPI spec, not reached in this pass.

**Status — the decisive fact for exhaust's purposes.** The project's own site currently carries
a banner stating "ACP is now part of A2A under the Linux Foundation" and links to a migration
guide (the guide URL itself 404s as of this research, but the banner's claim is on the live
welcome page). ACP has been folded into A2A rather than continuing as an independent,
competing spec. That makes it, here, not a seventh live alternative but a lineage that has
already collapsed into §4's A2A — inheriting the same fit assessment made there (built for
cross-org, potentially opaque agent delegation with coarse task lifecycles, not a tight
single-process step/observe rendezvous over one atomic action), with the added irony that
ACP's own stated anti-JSON-RPC, REST-first design choice did not survive the merge: A2A
itself specifies JSON-RPC, gRPC, and HTTP+JSON transport bindings.

**Known adopter.** The BeeAI platform (ACP's reference implementation). The fetched pages name
no production adopter outside the BeeAI/IBM ecosystem, and no exhaust-relevant prior audit in
docs/research/ mentions it.

## 8. Hosted/managed agent execution as a service (Claude Managed Agents, Cursor Cloud Agents)

**What it is.** A pattern distinct from all seven above: instead of a library you embed or a
CLI you spawn, the vendor runs the entire agent loop, sandbox, and tool execution on its own
infrastructure, and your application is a thin client that creates a session, streams events,
and answers the events that need a decision. Both Anthropic and Cursor now ship this as an
official, separate product line from their respective SDKs — not a hypothetical, a confirmed
pattern from two different vendors found by sweeping `llms.txt` indexes neither prior pass in
this document had read closely.

**Claude Managed Agents** (beta, `managed-agents-2026-04-01`). Positioned explicitly against
the raw Messages API in Anthropic's own comparison table: "Direct model prompting access" vs.
"Pre-built, configurable agent harness that runs in managed infrastructure," the latter "best
for long-running tasks and asynchronous work." Four concepts: an **Agent** (model, system
prompt, tools, MCP servers, skills, created once and referenced by id), an **Environment**
(an Anthropic-managed cloud sandbox or a self-hosted one on your own infrastructure), a
**Session** (one running instance), and **Events** (the message traffic in both directions,
persisted server-side and fetchable in full). Tool execution is governed by **permission
policies** per toolset: `always_allow` (default for the built-in agent toolset), `always_ask`
(default for MCP toolsets — "This ensures that new tools added to an MCP server do not run in
your application without approval"), or `auto`, where the server itself evaluates each call
and returns one of three outcomes — runs it, denies it outright (the agent gets a synthetic
tool-error result and "your client cannot override the denial"), or pauses for your approval
exactly as `always_ask` would. An `always_ask`/paused-`auto` call blocks the session
(`session.status_idle` with `stop_reason.type: "requires_action"`, naming the blocking event
ids) until you send a `user.tool_confirmation` event with `result: "allow"|"deny"` and an
optional `deny_message` the agent receives as the rejection reason — a true synchronous,
per-call, blocking veto with a structured, agent-visible rejection reason, the same shape as
`ActionRejected`, and (unlike Claude Agent SDK's `canUseTool`, which is one callback the
embedding application implements itself) enforced server-side, outside the agent's own
process, which is a stronger trust boundary for a harness that must not rely on the agent's
cooperation. Every `agent.tool_use`/`agent.mcp_tool_use` event also carries
`evaluated_permission` (`"allow"|"ask"|"deny"`) and, under `auto`, a `reason_code` — an audit
trail exhaust's own Finding/Verdict append-only design would recognize the shape of. Custom
tools are explicitly carved out of this policy system ("Permission policies do not apply to
custom tools... your application receives an `agent.custom_tool_use` event and is responsible
for determining whether to run it"), which is exactly where an exhaust adapter would hang
`AgentAction` dispatch, same pattern as the other vendor SDKs in section 2. Sources (fetched
directly, 2026-10-27): https://platform.claude.com/docs/en/managed-agents/overview.md,
https://platform.claude.com/docs/en/managed-agents/permission-policies.md.

**Cursor Cloud Agents** (public API, `/v0/agents` and a newer v1 in beta per forum/community
sources — not independently confirmed against an official reference page in this pass, so
treat the version detail as needing a direct check). Launch, list, get-status, follow-up, and
stop operations over a REST API authenticated with a bearer API key; this is the same `cloud`
runtime the Cursor SDK's `Agent.create({cloud: ...})` wraps (section 2), so for a caller using
the SDK this pattern is already subsumed — the raw REST surface mainly matters for languages
with neither the Python nor TypeScript SDK nor the Bridge. Unlike Claude Managed Agents, no
primary source reached in this pass documents a synchronous per-call permission-pause/approval
flow on the raw API; the richer approval semantics (if any) live in the SDK layer already
covered in section 2, not in the bare REST surface.

**Cost/benefits for exhaust's shape.** This pattern inverts exhaust's current assumption that
the harness process is also the one running the agent: here, the agent's entire execution —
sandbox, tool calls, model calls — happens in infrastructure exhaust does not control, and
exhaust's `Harness` would be a client reacting to a remote event stream rather than a process
driving a loop. The Claude Managed Agents `always_ask`/`auto`-deny flow is, on paper, the
*strongest* synchronous per-call veto of every pattern surveyed in this document, stronger than
`canUseTool` because it's enforced outside the agent's own process — but adopting it means
ADR-0021's "agent never holds the real LLM credential" problem disappears by construction (the
vendor's own infrastructure holds it, not the harness or the agent), while a new one appears:
exhaust's Scope Contract, Oracle, and evidence-promotion checks would all need to run against
a remote session's event stream rather than a local in-process call, and `RealTargetCall`
dispatch to a real Target would require the vendor's sandboxed cloud environment to actually
reach that Target's network, which is a materially different operational assumption than a
locally spawned agent process exhaust fully controls.

**Known adopter.** No exhaust prior audit documents either of these as an adopted pattern; both
are new findings from this `llms.txt`-driven pass, not corroborated against exhaust's own
audited tools, and both are explicitly in beta per their own vendor documentation.

Net pattern across the audited tools: **none of them abstract over multiple agent-invocation
mechanisms behind one clean interface except osmedeus**, and even osmedeus's three modes
trade away per-action granularity for every mode except its own fully-owned embedded loop.
The field's default is to pick one mechanism (usually a provider API loop or a CLI subprocess)
and accept whatever granularity that choice gives you, rather than building an
abstraction boundary exhaust's `AgentSession` Protocol already demands by construction.

## Further leads found by sweeping `llms.txt` indexes (not yet read into this document)

A pass over the `llms.txt` link indexes for cursor.com, code.claude.com, platform.claude.com,
developers.openai.com, modelcontextprotocol.io, and a2a-protocol.org (2026-10-27) surfaced
pages worth a dedicated read before this research is treated as settled, beyond what's already
folded in above:

- **Google ADK primary source.** Section 2's ADK paragraph is sourced from WebSearch summaries
  only, not a direct fetch of `github.com/google/adk-js`, `google.github.io/adk-docs`, or the
  Python ADK's own docs — unlike every other SDK in this document. Its tool-definition shape,
  permission/approval model (if any), and credential-isolation story are all unconfirmed
  firsthand.
- **OpenAI Codex CLI and Gemini CLI headless modes.** Found via WebSearch, not fetched directly:
  Codex's `exec --json`/`--output-schema`/`--output-last-message` (developers.openai.com/codex)
  and Gemini CLI's `--output-format json|stream-json` (geminicli.com/docs/cli/headless) both
  converge on the same text/json/stream-json triad as Claude Code's and Cursor's CLIs — a
  fourth and fifth confirmation of the pattern in section 5 — but neither was read from its
  official page directly, so exact field names are secondhand here.
- **OpenAI Workspace Agents API** (`developers.openai.com/workspace-agents`). Not investigated
  at all in this pass; its `llms.txt` entry ("Trigger workspace agent runs") suggests it may be
  OpenAI's own entry in the hosted/managed agent execution category (section 8), parallel to
  Claude Managed Agents and Cursor Cloud Agents — worth checking before concluding only two
  vendors ship that pattern.
- **MCP's `Tasks` extension** (`modelcontextprotocol.io/specification/2026-07-28/basic/patterns`
  plus SEP-1686/2663). The 2026-07-28 spec draft adds asynchronous, long-running task support
  to MCP, which section 3's analysis (MCP's `tools/call` as "stateless, fire-and-forget") may
  no longer fully describe once this extension is adopted — worth re-checking section 3 against
  it specifically, since it could narrow the gap this document identified between MCP and a
  blocking per-action rendezvous.
- **Cursor's own `/docs/agent-sdk/*` tree** (distinct from `/docs/sdk/*`, which section 2
  covers). A direct fetch of `cursor.com/docs/agent-sdk` 404s as of this pass; the `llms.txt`
  listing names `reference/http-api.md`, `reference/sessions.md`, `guides/agent-to-agent.md`,
  `reference/channels.md`, and `reference/schedules.md` alongside GitHub/Slack/Linear/PagerDuty
  integration guides, which reads more like configuring Cursor's own hosted agent product
  (triggers, schedules, cross-agent handoffs) than a second client SDK — but this is a guess
  from URL names alone, not a confirmed finding, and should not be treated as established until
  read directly.

## Comparison table

| Approach | Coupling to one vendor | Granularity of control over individual tool calls | Implementation effort | Auth / credential model |
|---|---|---|---|---|
| Raw provider API tool-use loop | High (one provider's wire format) | Full — harness sees and gates every `tool_use`/`tool_result` pair itself | High (hand-roll the whole loop) | Harness process holds the only credential; trivially fits ADR-0021's proxy-in-front pattern |
| Vendor agent SDK (Claude Agent SDK / OpenAI Agents SDK) | High (SDK's own abstractions, subagents/handoffs) | Partial — custom-tool handlers see each call, but the SDK's own loop controls batching/retry/parallelism | Medium (SDK does the loop; harness writes tool handlers) | SDK process makes the model calls; proxy must sit between SDK's HTTP client and provider (supported, not SDK-native) |
| MCP (harness exposes tools to an agent) | Low — any MCP-capable client can drive it | Per-call at the RPC level, but `isError`-as-prose is weaker than a typed `ActionOutcome`; no built-in structured-rejection/retry contract | Medium (define `tools/list`/`tools/call` server over exhaust's own actions) | Orthogonal — MCP doesn't address how the *agent* gets to its own LLM at all |
| A2A (agent-to-agent delegation) | Low in principle, but solves a different problem (cross-org opaque agents) | Coarse — task-level lifecycle (submitted/working/terminal), not single-action rendezvous | High, and largely wasted effort for a single in-process agent | Out of scope — built for authenticated cross-boundary agents, not a locally spawned one |
| CLI-invocation (subprocess) | Medium (one CLI's flags/output format) | Weak by default — only after-the-fact `stream-json` transcript or coarse permission hooks; args/results don't reliably reach the orchestrator | Low (process plumbing only) | Proven pattern (oss-crs): local credential proxy, key never touches the agent's own env |
| ACP (Agent Communication Protocol) | Low in principle, but now merged into A2A rather than independent | Inherits A2A's coarse task-level lifecycle, not single-action rendezvous | High, and now the same effort as A2A since it's no longer a separate spec | Unspecified in the fetched docs; no credential-isolation story found |
| Hosted agent execution (Claude Managed Agents, Cursor Cloud Agents) | High (vendor's own managed infrastructure and event schema) | Strongest of all patterns surveyed for Claude Managed Agents — a server-enforced, synchronous, per-call block with a structured agent-visible rejection (`user.tool_confirmation`/`deny_message`); weak/unconfirmed for Cursor's raw Cloud Agents API | Low integration effort, but inverts control: the harness reacts to a remote session rather than driving a local process | ADR-0021's problem disappears (vendor holds the credential) but Scope Contract / Oracle / evidence-promotion would need to operate against a remote event stream, and `RealTargetCall` needs the vendor's sandbox to reach the real Target's network |
