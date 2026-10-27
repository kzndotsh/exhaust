# Audit: Pi (`pi.dev`, `earendil-works/pi`), as an `AgentSession` backend candidate

Pi came up in the earlier survey ([`2026-10-27-agent-backend-abstraction-research.md`](2026-10-27-agent-backend-abstraction-research.md),
section 2) and was marked down hard: "Pi has no synchronous per-call approval hook at all, in
either mode" — the one agent runtime in that survey with no host-side veto point an exhaust
adapter could hang `ActionRejected` on. The user asked to confirm, with a dedicated deep pass,
whether that disqualifies Pi or whether the earlier pass missed something. It missed something.
This document corrects the record and gives Pi the same depth of treatment as the LiteLLM audit.

All primary sources below were fetched directly from `pi.dev`'s docs and from a shallow clone of
`github.com/earendil-works/pi`, 2026-10-27. Repo metadata came from `gh api`, not a web search.

## 1. What it is

A provider-agnostic coding-agent toolkit: one `ModelRuntime` abstraction over 15+ model
providers, an embeddable SDK (`createAgentSession()`, npm package
`@earendil-works/pi-coding-agent`), a CLI, and an RPC subprocess mode
(`pi --mode rpc --no-session`, newline-delimited JSON over stdin/stdout). `session.prompt(text)`
runs one turn; `session.subscribe(listener)` delivers an observability event stream
(`message_update`, `tool_execution_start/update/end`, `agent_end`, `agent_settled`, compaction/
retry events). Sessions persist as JSONL trees on disk, supporting continue/fork/clone and
compaction (a summary entry replacing older ones, originals retained).

**It is not a niche project.** `github.com/earendil-works/pi`: MIT license, not a fork, created
2025-08-09, last pushed 2026-10-27 (the same day as this research — actively maintained),
**118,284 stars, 15,149 forks, 380 open issues, 343 subscribers**. Confirmed directly via `gh
api`, not a secondary report. For comparison, this puts it in the same tier of visibility as
Strix (72k stars, [audited earlier](2026-10-26-strix-audit.md)) — a prominent, fast-growing
open-source project, not an obscure one.

## 2. The earlier pass's gap, and what was actually missed

The earlier research fetched `latest.md`, `how-pi-works.md`, `sdk.md`, `rpc.md`, and
`security.md` — but never fetched `extensions.md`, which is where Pi's actual tool-call gate
lives. `security.md` is accurate as far as it goes, and worth quoting exactly, since it's the
page that produced the earlier wrong conclusion:

> "it does not ask for approval before every tool call."
> "Extensions, package installers, language servers, and other child processes run with those
> same permissions"
> "Watching the transcript, using project trust, and reviewing changes do not create a security
> boundary."
> "Project trust does not limit what tool calls can access or affect."
> "Extensions execute inside the Pi process."

Every one of those statements is true, and none of them is about whether a gate *can* exist —
they're about whether Pi defends itself *against a malicious extension*. It doesn't, and says so
plainly. But exhaust is not a hostile third party trying to escape Pi's sandbox; exhaust would
*author* the extension. `security.md`'s silence on that distinction is exactly the blind spot
that produced the earlier "no hook at all" conclusion.

## 3. The actual gate: `pi.on("tool_call", ...)`

`extensions.md`, fetched directly, documents a synchronous, blocking extension hook:

> "Fired after `tool_execution_start`, before the tool executes. **Can block.**"

`event.input` is mutable in place to patch tool arguments before execution — "No re-validation
is performed after your mutation," which is a real sharp edge, not a gap: a gate that mutates
`input` has to re-derive its own safety judgment from the mutated value itself, since Pi won't
check it again. The handler's return shape is `{ block?: boolean; reason?: string; terminate?:
bool }`. Error handling is fail-closed: "`tool_call` errors block the tool," confirmed directly
in source — a throwing handler is caught and rethrown as
`` `Extension failed, blocking execution: ${err}` ``, so a buggy or crashing gate denies rather
than silently lets the call through.

Pi's own maintainers ship a worked example of exactly this pattern:
`packages/coding-agent/examples/extensions/permission-gate.ts`, which gates `bash` calls
matching `rm -rf`/`sudo`/`chmod 777` and returns `{ block: true, reason: "Blocked by user" }`.
This is not a hypothetical capability inferred from a type signature — it's the pattern Pi
itself demonstrates as the intended use of the hook.

**Confirmed against the runtime source, not just the docs** (`packages/coding-agent/src/core/
extensions/runner.ts`, `agent-session.ts`): `emitToolCall()` is `async`, iterates every
registered `tool_call` handler in sequence, `await`s each, and returns immediately once any
handler sets `result.block`. It is wired into the live `Agent` instance via
`this.agent.beforeToolCall = (context) => this._beforeToolCall(context)` inside
`_installAgentToolHooks()`, with a comment directly above it reading "Tool call and tool result
interception now happens here instead of in wrappers" — i.e. this is the current, intentional
dispatch path, not a legacy or deprecated one.

**It attaches to embedded SDK sessions, not just the CLI.** `sdk.md`: `resourceLoader` supplies
extensions (among skills, prompt templates, themes, context files), and `extensionFactories` on
`DefaultResourceLoader` is the documented way to register inline extensions on a
`createAgentSession()` call. The earlier pass's "in either mode" framing — treating the CLI and
the SDK as both lacking a hook — doesn't hold; the embedded path exhaust would actually use has
the same gate the CLI's worked example demonstrates.

**Custom tools carry exactly the shape exhaust needs.** A tool registered via `customTools`
surfaces to the `tool_call` hook as a `CustomToolCallEvent` with `source: "sdk"`,
`toolName: string`, `input: Record<string, unknown>`
(`packages/coding-agent/src/core/extensions/types.ts`). That's a clean `toolName`/`input` pair
per call, arguably a better fit for `AgentAction`'s closed union than Claude's Messages-API
`tool_use` block, which arrives nested inside a larger content array exhaust would have to parse
apart itself.

## 4. RPC mode doesn't bypass the gate — it relocates where the decision is made

`security.md` confirms extensions "execute inside the Pi process" even under
`pi --mode rpc --no-session`, so the `tool_call` hook still runs in-process there too; RPC mode
doesn't add a second, separate gate. What it adds, per `rpc-types.ts`, is an
`extension_ui_request`/`extension_ui_response` channel (`method: "confirm" | "select" |
"editor" | ...`) letting an extension's `tool_call` handler defer its allow/deny decision to
whatever's on the other end of the RPC pipe, instead of prompting a local terminal UI.

That channel makes a specific integration shape possible: a thin gate extension, written in
TypeScript, loaded into the Pi subprocess, whose `tool_call` handler calls `ctx.ui.confirm(...)`
— which round-trips over the RPC JSON stream to exhaust's own Python harness process for the
actual `AgentAction` validation, then returns `block`/`reason` back into Pi's dispatch. This is
my own synthesis from the documented primitives, not a pattern pi.dev's docs name explicitly,
and no third-party writeup of exactly this use (a gated, Python-driven embedder) turned up in
this pass — flagged as unverified-by-example, though directly supported by what the RPC types
and the extension API each separately document.

## 5. What this means for exhaust's shape, concretely

Compared against `AgentAction`'s closed union (`SandboxCall`, `RealTargetCall`, `RecordFinding`,
`ProposeVerdict`, `SelfReport`, `SetVerticalState`) and the synchronous-gate requirement the
earlier survey used to judge every backend:

- **The gate exists and is the right shape.** `tool_call` fires before execution, can block with
  a reason, and fails closed on an exception — the same three properties that made Claude Agent
  SDK's `canUseTool` the strongest fit in the earlier survey. Pi now belongs in that tier, not at
  the bottom of it.
- **It does not do exhaust's job for it.** Like every SDK surveyed, Pi's hook is a place to put a
  gate, not a gate itself — exhaust would still write the actual `AgentAction` validation,
  the Scope Contract re-check for `RealTargetCall`, and the [ADR 0023](../adr/0023-consequential-real-target-actions-wait-for-a-human.md)
  pending-approval logic inside the handler, exactly as it would inside `canUseTool`.
- **The real new cost is the language boundary.** Pi is TypeScript end to end — the embedded SDK,
  the extension API, the RPC subprocess's internals. exhaust's Harness is Python. Every other
  backend surveyed so far (Claude Agent SDK, Cursor SDK, Codex) either ships a Python SDK or is
  driven as a subprocess with a wire protocol exhaust's own Python process fully owns. Pi's RPC
  mode gets exhaust most of the way there (a Python process can drive the subprocess over
  stdin/stdout JSON without writing TypeScript), but the gate itself — the `tool_call` extension
  — has to be a loaded TypeScript module running inside the Pi process, not something exhaust's
  Python harness can author directly. The `extension_ui_request`/`response` bridge narrows this
  to "write one small, auditable TypeScript shim that forwards every decision to Python," not
  "port the harness to TypeScript," but it is a real integration cost none of the Python-native
  or wire-protocol-first options carry.
- **Credential isolation ([ADR 0021](../adr/0021-agent-never-holds-the-real-llm-credential.md))
  is unresolved in this pass**, same gap as every other backend surveyed except LiteLLM
  specifically: Pi's `ModelRuntime` abstraction would be the thing making the actual provider
  call, so a virtual-key proxy would sit between Pi and the real provider via whatever base-URL/
  API-key configuration each of its 15+ provider adapters accepts — not verified in this pass,
  and provider-adapter-specific, so it would need its own check before relying on it.
- **Pricing/business model is unverified.** Not reached in this pass. Before treating Pi as a
  real candidate, confirm whether `pi.dev` is purely the open-source CLI/SDK (consistent with
  the MIT-licensed GitHub repo found) or whether there's a hosted/paid tier with its own terms
  that would matter the way the Claude Agent SDK's subscription-billing ambiguity did in the
  earlier survey.

## Verdict

**Pi is a live contender, not a dead one.** The earlier survey's disqualifying claim — no
synchronous per-call gate in either mode — is wrong, confirmed by the docs, a maintainer-shipped
example, and the dispatch source itself, not just a more charitable reading of the same pages.
Pi's `tool_call` extension hook is structurally close to Claude Agent SDK's `canUseTool`: it
fires before execution, can block with a reason, fails closed, and (via `customTools`) hands the
handler a clean `toolName`/`input` pair per call. What makes Pi different from the Python-native
options is the language boundary: the gate itself must live in a loaded TypeScript extension,
with RPC mode's UI-request channel as the bridge back to exhaust's own Python process for the
actual decision. That is a real, specific integration cost — one small TypeScript shim to write
and keep auditable — not a blocker on its own. Open questions before going further: whether
exhaust is comfortable with any TypeScript in the trust boundary at all (even a thin, reviewable
shim), how ADR-0021's credential proxy would sit in front of a 15-provider `ModelRuntime`, and
what pi.dev's actual pricing/hosting model is.

## What this settled for exhaust

- Corrects [`2026-10-27-agent-backend-abstraction-research.md`](2026-10-27-agent-backend-abstraction-research.md) §2:
  Pi has a real synchronous per-call gate (`pi.on("tool_call", ...)`), not none. Pi moves from
  "no veto point" to the same tier as Claude Agent SDK's `canUseTool`, with an added
  TypeScript-boundary cost neither Claude Agent SDK nor a Python-native option carries.
  Not a recommendation to adopt it — the backend choice remains open and is the user's call —
  but it is no longer fair to rule Pi out on the "no approval hook" basis the earlier pass used.
  Still open before any decision: pi.dev's pricing/hosting model, and how ADR-0021's credential
  proxy would front a 15-provider `ModelRuntime`.
