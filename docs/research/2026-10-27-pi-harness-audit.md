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

## 5. How people actually hack and extend Pi

**The distribution unit is a Pi package** (`packages.md`, fetched directly): "install and
distribute extensions, skills, prompt templates, and themes as one unit," sourced from npm
(`npm:@x/y@1.0.0`), git (`git:host/repo@ref`), or a local path, with versions/refs pinned.
`pi install <source>` records the choice in `~/.pi/agent/settings.json` (global) or
`.pi/settings.json` (project-local, gated behind the same project-trust gate `security.md`
describes). The `pi-package` npm keyword makes a package "eligible for the Pi package gallery" —
a tag-based discovery convention, not a curated or reviewed marketplace. Pi's own docs are blunt
about the resulting trust surface: a package "can execute extension code and include skills that
direct the model to run programs," so review third-party source before installing. That is Pi's
own vendor naming the exact raw-trust problem [ADR 0018](../adr/0018-tool-bridges-expose-a-narrow-enumerated-surface.md)
(a narrow enumerated bridge, never raw shell) exists to design around — convergent evidence, not
a new finding, but worth noting that Pi's own maintainers see the same shape of risk.

**Skills** load the same way exhaust's own catalog does conceptually: a `SKILL.md`-bearing
directory, discovered recursively from project and user locations (including the cross-tool
`~/.agents/skills/`/`.agents/skills/` convention several agent runtimes now share), with only
name/description loaded into the system prompt at startup and full instructions loaded lazily
once the model actually picks the skill — the same just-in-time disclosure principle as
[ADR 0013](../adr/0013-skills-use-progressive-disclosure.md). `disable-model-invocation:
true` restricts a skill to explicit-only use. One sharp edge: name collisions resolve
first-discovered-wins with only a warning, so two packages declaring the same skill name can
silently shadow one another.

## 6. Three independent production codebases confirm the gate — and reveal real integration costs

Beyond pi.dev's own docs, three live, unrelated projects (two serious enough to be a company's
product and a popular third-party GUI) all converge on the same `tool_call`/`beforeToolCall`
mechanism as their actual security boundary. This is materially stronger evidence than a vendor's
own documentation and worked example: it's proof the mechanism survives contact with real
integrators, not just a clean docs page.

**`antinomie-lab/pi-book`** (428 stars, independent of `earendil-works`, a line-cited architecture
deep-dive into the lower-level `@earendil-works/pi-agent-core` package that the `tool_call`
extension API is itself built on) traces the primitive one layer down: `AgentLoopConfig`'s
`beforeToolCall`/`afterToolCall` (`src/types.ts:61`, `src/agent-loop.ts`). Quoted from source via
the book: the loop's prepare phase resolves the tool, validates args against its schema, then
calls `beforeToolCall` — `undefined`/`{}` allows, `{block: true, reason}` denies; the execute
phase wraps the tool's own `execute()` in try/catch, turning a thrown error into `isError: true`;
the finalize phase calls `afterToolCall`, which can rewrite the result or set `terminate`, and
**is independently confirmed fail-closed too** — a thrown error there also becomes `isError:
true`. Two findings worth carrying into any exhaust implementation:

- **Batching is per-turn, not per-call.** Default execution is parallel, but every tool call in
  one assistant turn passes through `beforeToolCall` sequentially, in declared order, *before any
  of them execute* — quoted rationale from the source: "`beforeToolCall` needs to see the
  complete batch — permission systems often need to decide based on what the whole assistant
  message is trying to do, not judge each call in isolation." A turn producing several
  `AgentAction`s would see every one of them cleared by the gate before any dispatches, not one
  call fully round-tripping before the next starts.
- **A documented deadlock hazard.** Quoted directly from Pi's own `docs/agent-harness.md:18`:
  "listeners/hooks currently receive no facade; if they close over the raw harness and call
  settlement APIs such as `waitForIdle()` during the active run, they can deadlock." Concretely: a
  hook that awaits the current run's own completion creates an unbreakable promise cycle with no
  timeout. Any exhaust gate implementation must never have its handler await anything that itself
  waits on the in-flight run finishing.

**`JetBrains/thinkrail`** (3,949 stars, Apache-2.0, a JetBrains-incubated IDE built on
`@earendil-works/pi-coding-agent` via the embedded SDK — `DefaultResourceLoader`,
`ExtensionFactory`, `InlineExtension`, confirming SDK-embedding rather than CLI-subprocess use,
consistent with this audit's §3 framing). The most valuable artifact here is `pi-compatibility.md`,
a maintained engineering doc tracking every place JetBrains compensates for a missing public API
or a Pi defect, each entry carrying an explicit removal gate (what Pi would need to ship before
the workaround can be deleted) and which tests pin it — a serious company formally tracking
technical debt against Pi as a dependency, not ad hoc patching. Concrete gaps named: `AgentSession
.dispose()` "does not emit extension shutdown," so disposing a session without first calling the
public shutdown API leaks the MCP stdio child process; several internals mirrored because Pi
doesn't export them (`defaultModelPerProvider`, `getSessionStats`, the MCP config
loader/validator/writer), with the discipline stated plainly: "Importing a private dist path in
production is not a replacement; such imports remain confined to parity tests." thinkrail also
confirms the gate's real wiring at `packages/server/src/agent/mcp/sessionHost.ts:125`: `pi.on(
"tool_call", (event, ctx) => confirm(pi, event, ctx))`, with allow-once/allow-in-chat/always-
allow/deny semantics and an explicit fail-closed path when no UI is attached: `if (!ctx.hasUI)
return blocked("This MCP call needs the user's confirmation, and no UI is attached.")`. thinkrail
states its own confirmation layer is a boundary it owns, not one Pi could silently change: "a pi
upgrade does not silently remove or weaken" its approvals, overrides, and credential masking.

**`Jaxton07/percho`** (489 stars, MIT, a desktop GUI embedding Pi via `createAgentSession({
customTools, ... })`, advertising "visual tool approvals") is the strongest single piece of
evidence in this pass: a complete, production-grade gate implementation
(`packages/backend/src/permissions/extension.ts`) built, by its own doc comment, "using only Pi's
public extension API (the `tool_call` hook plus the confirm channel)" — effectively a worked
reference for exactly what exhaust would need to write. Its own `docs/extension-ui.md` draws a
design line worth carrying forward directly: Percho deliberately keeps generic extension-UI
primitives (`select`/`input`/`editor`/`confirm`, used for things like notifications and skill
prompts) on a separate code path from the actual tool-authorization gate, quoted: "a generic
confirm does not go through PermissionGate — an extension's question and a high-risk tool's
authorization must not be collapsed into one semantic." The gate itself layers: global deny rules
first, then an OS-temp-directory exemption, then a multi-root path-boundary check with a
read/write asymmetry (a path outside all project roots defaults to allow for reads, ask for
writes), then a per-project "always allow" memory, then an interactive `confirm()` as the final
step. Fail-closed is independently reconfirmed at this layer too: a throwing `confirm()` call is
caught and treated as denial, the same behavior pi-agent-core's own `beforeToolCall`/
`afterToolCall` show for a throwing handler. Two things worth flagging directly to the design
discussion, not just logging as trivia:

- **Percho ships an explicit, audited bypass mode** (`fullAccess`): deny/ask decisions downgrade
  to "log to an audit file, then allow," including for its own self-protection rules. This is the
  opposite of [ADR 0023](../adr/0023-consequential-real-target-actions-wait-for-a-human.md)'s "no
  bypass flag, only pre-approval" stance — a real production counterexample of the exact pattern
  exhaust deliberately rejected, not a reason to reconsider it, but useful to know a popular
  Pi-based tool ships the thing ADR 0023 refused to.
- **An honest, in-code admission of the limits of path-based gating**, quoted: "boundary checks
  only cover path-taking tools; `bash` can't be constrained by path pattern (`cd` can jump
  anywhere), symlink escapes are out of scope." This is a live, production confirmation of exactly
  the weakness [ADR 0018](../adr/0018-tool-bridges-expose-a-narrow-enumerated-surface.md)'s narrow
  enumerated bridge exists to avoid: a team that actually tried to gate a generic shell tool by
  pattern-matching paths hit the exact limitation that ADR predicted.

Percho's `docs/sdk.md` adds tool-registration gotchas anyone wiring `AgentAction` dispatch into
Pi needs to know: `createAgentSession({tools:[...]})` is a silent allowlist that can filter out
extension-registered tools if misused; name collisions resolve via a `replaceable` flag plus
first-registrant-wins, and `customTools` can override an extension's tool of the same name;
`getAllTools()` is available only in the extension factory's closure, not inside the `tool_call`
handler's own context; and a tool's parameter schema must be a single top-level object, since some
providers reject a top-level union/intersection. It also independently reconfirms thinkrail's
`dispose()`/MCP-leak finding, and ships real source patches
(`patches/@earendil-works+pi-coding-agent`, `patches/@earendil-works+pi-agent-core`) against its
pinned SDK version for capabilities the public API doesn't yet expose (retry-last-failed-turn,
bounded summary retry, pre-submit validation) — a second independent data point, after thinkrail's
compatibility doc, that Pi's current public SDK surface has real, acknowledged gaps serious
embedders work around directly rather than wait for.

**Net effect on the gate finding:** three unrelated codebases — a line-cited independent book
reading raw source, a JetBrains product, and a popular third-party GUI — all converge on
`beforeToolCall`/`tool_call` as the real security boundary, with two of them (thinkrail, Percho)
shipping it in front of real users today. That is about as strong as real-world confirmation gets
short of exhaust building the integration itself. It does not change the verdict; it substantially
strengthens it, and adds a second, separate cost to the TypeScript-boundary one already
named: **Pi's current public SDK surface has real gaps that serious integrators are patching or
mirroring around right now**, which is an ongoing maintenance burden of embedding Pi, distinct
from (and additional to) the language-boundary cost.

## 7. What this means for exhaust's shape, concretely

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

**Pi is a live contender, not a dead one — and the strongest-evidenced one surveyed so far.** The
earlier survey's disqualifying claim — no synchronous per-call gate in either mode — is wrong,
confirmed not just by Pi's own docs, worked example, and dispatch source, but by three
independent production codebases (a line-cited third-party book reading the raw agent-loop
source, a JetBrains-incubated IDE, and a popular third-party desktop GUI) all converging on the
same `beforeToolCall`/`tool_call` mechanism as their actual security boundary, two of them
shipping it in front of real users today. Pi's gate is structurally close to Claude Agent SDK's
`canUseTool`: it fires before execution, can block with a reason, fails closed on a throwing
handler at two separate layers, and (via `customTools`) hands the handler a clean `toolName`/
`input` pair per call, batched per-turn so a multi-action turn clears the gate as a whole before
any of it dispatches.

What makes Pi different from the Python-native options is two separable costs, not one. First,
the language boundary: the gate itself must live in a loaded TypeScript extension, with RPC
mode's UI-request channel as the bridge back to exhaust's own Python process for the actual
decision — a real, specific integration cost (one small TypeScript shim to write and keep
auditable), not a blocker. Second, and new in this pass: **Pi's current public SDK surface has
real, acknowledged gaps that two independent serious integrators are actively patching or
mirroring around** (JetBrains' formally tracked `pi-compatibility.md`, Percho's shipped source
patches against its pinned SDK version) — an ongoing maintenance cost of embedding Pi that would
apply to exhaust too, separate from the one-time cost of writing the gate itself. A third,
structural hazard also surfaced: a documented deadlock in Pi's own harness docs if a hook awaits
the current run's own settlement — a constraint any exhaust gate implementation must respect by
design, not something to discover at run time.

Open questions before going further: whether exhaust is comfortable with any TypeScript in the
trust boundary at all (even a thin, reviewable shim); how ADR-0021's credential proxy would sit in
front of a 15-provider `ModelRuntime`; what pi.dev's actual pricing/hosting model is; and whether
the ongoing patch/mirror burden two existing integrators already carry is an acceptable maintenance
cost for exhaust to take on as well.

## What this settled for exhaust

- Corrects [`2026-10-27-agent-backend-abstraction-research.md`](2026-10-27-agent-backend-abstraction-research.md) §2:
  Pi has a real synchronous per-call gate (`pi.on("tool_call", ...)`/`beforeToolCall`), not none.
  Pi moves from "no veto point" to the same tier as Claude Agent SDK's `canUseTool`, now backed by
  three independent production adopters (`antinomie-lab/pi-book`, `JetBrains/thinkrail`,
  `Jaxton07/percho`) confirming the mechanism holds up in real deployments, not just in docs.
  Not a recommendation to adopt it — the backend choice remains open and is the user's call —
  but it is no longer fair to rule Pi out on the "no approval hook" basis the earlier pass used.
- **A new, named cost beyond the TypeScript boundary**: real public-SDK gaps that existing
  integrators formally track (thinkrail) or source-patch around (Percho) — an ongoing maintenance
  burden, not a one-time integration cost, worth weighing against the Python-native options'
  comparative maturity.
- **A real counterexample worth noting against [ADR 0023](../adr/0023-consequential-real-target-actions-wait-for-a-human.md)'s
  "no bypass flag" stance**: Percho ships an audited `fullAccess` bypass mode. Not a reason to
  reconsider ADR 0023 — logged-but-allowed is a materially weaker guarantee than pre-approval-only
  — but evidence a popular Pi-based tool made the opposite call exhaust explicitly rejected.
  Still open before any decision: pi.dev's pricing/hosting model, and how ADR-0021's credential
  proxy would front a 15-provider `ModelRuntime`.
