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
actual `AgentAction` validation, then returns `block`/`reason` back into Pi's dispatch.

**Confirmed, not just synthesized: `imrj05/orbit` ships exactly this pattern in production.**
Orbit (130 stars, Apache-2.0, see §8) is a pure Rust/GPUI desktop client with zero Node, JS, or
browser runtime anywhere in its own code, and it still achieves tool-call gating by bundling a
small Pi extension (necessarily JS/TS, loaded by the `pi` CLI child process) that, per its own
README's Safeguards section, "hooks `tool_call` and confirms mutating calls the mode does not
auto-approve." Rust never implements the gate logic itself; it only renders the approval UI and
answers over RPC. `crates/orbit-rpc/src/types.rs:284` confirms the exact wire shape:

```rust
/// Dialog methods (`select`/`confirm`/`input`/`editor`) expect an
/// `extension_ui_response` on stdin with the matching `id`.
ExtensionUiRequest { id: String, method: String, value: Value }
```

with `crates/orbit-pi/src/dialog.rs` documenting the response shape sent back:
`confirm` → `{ "confirmed": bool }`, matched by `id`. This is a complete, shipping, non-JS
client doing exactly what was proposed above as an unverified synthesis — only with Rust standing
in for the role exhaust's Python harness would play. Orbit's own README is also directly honest
about the trust boundary, independently reconfirming `security.md`: "A confirmation guard, not a
sandbox — pi ships no sandbox, and Orbit does not add one."

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

## 7. Eleven more community extensions — a fourth and fifth gate confirmation, and a real bypass

A second research pass covered eleven more community repos the user linked directly. One
housekeeping note first: `pi-rewind`'s README links to `github.com/badlogic/pi-mono` as "the Pi
coding agent" — `gh repo view badlogic/pi-mono` resolves to `earendil-works/pi` (identical star
count and push timestamp), confirming this is a GitHub ownership transfer/rename, not a second,
competing "Pi" project. Worth knowing since older community READMEs still use the `badlogic` URL.

**`Firstp1ck/pi-coding-agent-forge`** (92 stars, MIT, independent of earendil-works) is a large,
unaffiliated collection of community extensions, and two of its sub-packages are directly
load-bearing for this audit:

- **`pi-extension-tools`** is a fourth independent confirmation of the `tool_call` gate, plus a
  *new* enforcement point the earlier passes hadn't found: tool restriction at the declaration
  layer, not just the call layer. Quoted from `index.ts`:
  ```js
  pi.on("tool_call", (event, ctx) => {
    const isAllowed = enforceSelection(ctx);
    if (isAllowed && !isAllowed(event.toolName)) {
      return { block: true, reason: `Tool "${event.toolName}" is disabled by the effective /tools selection.` };
    }
  });
  ```
  It also hooks `context_with_system` to strip disallowed tools from what the model is even shown
  (`toolsRemoved`/`toolsAdded` deltas) and `before_agent_start` to recompute the active selection
  each turn — meaning Pi supports narrowing the agent's visible tool surface declaratively, a
  second, complementary enforcement point alongside the `tool_call` gate that
  [ADR 0018](../adr/0018-tool-bridges-expose-a-narrow-enumerated-surface.md)'s enumerated-bridge
  design could use together with (not instead of) per-call gating.
- **`pi-extension-small-modal-reliability`** independently reimplements almost exactly what
  [ADR 0023](../adr/0023-consequential-real-target-actions-wait-for-a-human.md) specifies, from an
  author with no connection to exhaust. Its approval system is keyed by a deterministic hash of
  tool name plus canonically-serialized input (`hashToolCall`, SHA-256 over `stableStringify`'d
  input), with its own doc comment stating the design intent in almost ADR-0023 language: "the
  approval match is an exact host-normalized operation, never model prose." Approvals are
  `pending`/`approved`/`expired` records that must re-match the exact normalized effect before
  promotion — approving doesn't execute anything; the agent must re-propose the identical call,
  exactly ADR 0023's stance. This is strong, convergent, independent validation of ADR 0023's
  design, not just a passing similarity.

**`AgwaB/pi-workflow`** (369 stars, MIT) is multi-step workflow orchestration — named, resumable,
stoppable workflows fanning work across Pi subagent sessions, tracked to disk under `.pi/workflows`
and surviving session reload. Structurally, this is close to what exhaust's own Harness does
(drive an agent through a fixed sequence, persist state, survive restarts) — real evidence a
Harness-equivalent *can* be expressed as a Pi extension rather than a separate Python process, if
exhaust ever wanted to run entirely inside Pi. The cost is the same language boundary already
named in §7, now concrete at the orchestration layer too: the ledger, scope checks, and approval
logic would all end up as TypeScript workflow-state code, not exhaust's own Python domain modules.

**`garnetlyx/pi-goal-kit`** (5 stars, MIT) implements a real five-phase state machine
(`idle → select-reviewer → plan → act → review → verify → exit`) with an adversarial review phase
gating "done" — richer than exhaust's own ledger states in that one respect. But its own README
admits the same weakness Percho's audit entry already surfaced: "the reviewer's tool whitelist
includes `bash`, which is not sandboxed. Withholding write/edit tools plus an explicit instruction
is a strong default, not an enforced boundary." A third independent confirmation that a raw shell
tool defeats text-pattern/instruction-based restriction, the exact risk ADR 0018's enumerated
bridge exists to avoid.

**`tintinweb/pi-tasks`** (236 stars, MIT) is a Claude-Code-style task tracker — and its task
status transitions are **purely agent-self-reported with no host-side verification**: `TaskUpdate`
writes whatever status the model calls it with, with no oracle-style check that a task marked
`completed` actually produced anything. A fourth, unrelated confirmation of the gap
[ADR 0008](../adr/0008-confirmed-requires-a-host-run-oracle.md) already names as "the one gap found,
in some form, in nearly every comparable tool audited so far." Its own stated design choice —
"there is deliberately no executable config file, so nothing in a cloned repository's `.pi/` can
run on your machine" — is a small, sound security pattern (config as data, never code) worth
noting in passing.

**`tintinweb/pi-schedule-prompt`** (121 stars, MIT) surfaces the single most concrete new risk in
this batch: **a real, default-open gate-bypass path, confirmed in source.** A scheduled job that
sets `model` spawns a fresh, separate `AgentSession` via `src/subagent.ts`, whose own doc comment
states plainly: "spawn a fresh AgentSession with the chosen model, run the prompt to completion,
return the assistant's text. No subprocess, no extension recursion (`noExtensions: true`), no
persistence." Extensions — including any `tool_call` gate extension — are **not loaded by default**
in that spawned session; the README documents `extensions: boolean | string[]` as an explicit
opt-in an operator must set, defaulting to none. This means a background or scheduled subagent
session, by default, runs with zero gates unless whoever configured that job explicitly re-enables
extensions for it. Sharper and more concrete than the RPC-mode question in §4: a real path where
the gate genuinely is bypassed by default, not merely a theoretical one. Directly actionable for
any exhaust-on-Pi design: every `createAgentSession()` call site — main session and any
subagent/background session spawned by any extension — needs its own explicit gate-loading check,
since Pi does not propagate it automatically.

**`arpagon/pi-rewind`** (116 stars, MIT) checkpoints via git commits under a dedicated ref
namespace, entirely separate from Pi's own session JSONL-tree/fork/clone mechanism (§1) — "a
two-layer split: `core.ts` is pure git operations with zero Pi dependency." One checkpoint per
turn, offering `/rewind` to roll back after the fact. Useful as a contrast, not a convergent
finding: this is a reactive, filesystem-only undo mechanism with no answer to (and no way to
extend to) a crash mid-`RealTargetCall` — you cannot git-rewind a real network scan or an
already-sent exploit attempt the way you can a local file edit. It confirms, by contrast, that
[ADR 0015](../adr/0015-crash-mid-real-target-action-blocks-not-retries.md)'s "block and surface
state explicitly, never silently roll back or retry" stance addresses a problem class the Pi
community's own tooling has no answer for, because that tooling is scoped to local-filesystem
coding work where "undo" is coherent.

## 8. Credential isolation: two real, opposite answers already built

Two of the linked repos tackle the exact question [ADR 0021](../adr/0021-agent-never-holds-the-real-llm-credential.md)
settled for exhaust — never let the agent process hold the real, usable LLM credential — and land
on opposite answers, both pushed the same day.

**`joaomj/pi-claude-directsdk`** (36 stars, MIT) gets this right, in ADR 0021's own spirit, by a
different mechanism than a virtual-key proxy. It spawns a **request-scoped `claude` child process
per model call**, replays Pi's transcript into it via stdin (`stream-json`, `--max-turns 1`,
`--permission-mode dontAsk`, `--no-session-persistence`), and routes the CLI's outbound
`POST /v1/messages` through a local loopback "admission relay" that forwards only the first
upstream request and locally denies any retry the CLI attempts on its own. Quoted from its own
architecture doc: "Pi owns the transcript, tools, approvals, and retries. The CLI supplies
subscription authentication as a model transport... The provider never manages login or reads
credentials." The real credential never enters the Pi/extension process at all — it stays inside
the official `claude` binary's own auth storage, which this extension never touches.

**`leohenon/pi-anthropic-oauth`** (109 stars, MIT) does the opposite: it performs its own direct
OAuth client registration against Anthropic's endpoints using the well-known public Claude Code
client ID, then talks to the real Messages API directly with the resulting bearer token — the raw
OAuth credential lives inside the Pi extension process itself, exactly the anti-pattern ADR 0021
forbids. It also actively impersonates the Claude Code client to keep OAuth working: "prepends the
Claude Code billing-header and identity system blocks and rewrites standalone `Pi`/`pi` references
in Pi's system prompt to `Claude Code`," with its own README warning "disabling or weakening the
rewrite may affect OAuth compatibility." Its README quotes a live, dated enforcement signal worth
noting directly: the actual Anthropic API error this extension exists to route around, `400
invalid_request_error`: "Third-party apps now draw from your extra usage, not your plan limits" —
confirmation Anthropic has already begun enforcing a distinction between a user's own CLI usage and
third-party-app usage of the same subscription, a live fact rather than a policy-page inference.

**Updates the earlier subscription-auth caveat, doesn't resolve it.** `pi-claude-directsdk`'s own
`docs/comparison.md` cites a more specific, more recent primary source than the earlier
agent-backend-abstraction research reached: Anthropic's subscription-guidance support article
(`support.claude.com/en/articles/15036540`), which states Agent SDK, `claude -p`, and third-party
app usage "can still draw from subscription limits" — read by this repo's own author as leaving
the question open rather than settling it either way, quoted directly: "these statements address
different conditions; neither establishes project-specific approval." That is the repo author's
own hedge, not a verified legal conclusion, but it is a materially more specific and more recent
source than what the earlier pass found, and worth checking directly before treating ADR 0021's
"unresolved, don't build toward subscription auth" stance as fully settled.

## 9. Two more real-world data points: branch-scoped gate state, and a richer extension lifecycle

**`huang-sh/PiX`** (215 stars, MPL-2.0) is a non-linear workbench built directly on Pi's documented
session-tree model, confirming it works for a real third-party UI: "Sessions are real Pi sessions
— no new format — so they remain usable outside PiX." It also answers a question the core audit
hadn't asked: does `tool_call`-hook state (e.g. an "always allow this tool" memory) carry across a
session fork? No — quoted from its own docs: "each branch has its own independent Pi runtime,
SessionManager and services." Gating state is runtime-scoped like everything else about a branch,
and branch content never merges back into the main session automatically, by design. Relevant if
exhaust ever used Pi's branching for parallel investigation of a vertical: any approval state the
gate accumulates would need its own explicit propagation, since Pi won't do it.

**`green-dalii/pi-shift-router`** (13 stars, MIT, heavily SEO-marketed README treated as
promotional, not factual, text) confirms Pi's extension lifecycle is considerably richer than
"gate plus custom tools": source confirms `pi.on(...)` registrations across `model_select`,
`session_start`, `before_agent_start`, `tool_call`, `tool_result`, `agent_end`, `agent_settled`,
`turn_end`, `after_provider_response`, `message_start`, and `message_end`. Its actual per-turn
model-routing mechanism hooks `before_agent_start` and calls `pi.setModel(model)` — a documented,
public mutation point, not a `ModelRuntime`-layer hack. Not directly relevant to the gate question,
but worth knowing the full hook surface exists, since a future exhaust-on-Pi design might want more
than just `tool_call` (e.g. `session_start` for Workspace setup, `agent_end` for ledger bookkeeping).

## 10. What this means for exhaust's shape, concretely

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
- **The real new cost is the language boundary — but it's a confirmed-working one, not a
  guess.** Pi is TypeScript end to end — the embedded SDK, the extension API, the RPC subprocess's
  internals. exhaust's Harness is Python. Every other backend surveyed so far (Claude Agent SDK,
  Cursor SDK, Codex) either ships a Python SDK or is driven as a subprocess with a wire protocol
  exhaust's own Python process fully owns. `imrj05/orbit` (§7) proves the bridge pattern actually
  works in production: a pure Rust client with zero Node/JS anywhere in its own code still achieves
  gating by bundling a thin TypeScript extension that defers every decision over RPC to the
  external process. The same shape would work for a Python harness. It is a real integration cost
  (one small, auditable TypeScript shim to write and trust) — now a de-risked one, not speculative.
- **A second, concrete cost: the gate is not inherited by default.** `tintinweb/pi-schedule-prompt`
  (§7) shows a scheduled subagent session spawned with a `model` override loads **zero extensions**
  by default (`noExtensions: true`), meaning zero gates, unless the operator explicitly re-enables
  them for that session. Any exhaust-on-Pi design would need to treat "is the gate extension loaded"
  as a per-`createAgentSession()`-call-site check, never an inherited property — a concrete
  implementation discipline, not a disqualifier, but a real way to get this quietly wrong.
- **A third cost, independent of the gate question: real, acknowledged public-SDK gaps.** Two
  separate serious integrators (JetBrains' `pi-compatibility.md`, Percho's shipped source patches,
  §6) are actively patching or mirroring around missing public API surface in Pi's current SDK —
  an ongoing maintenance burden anyone embedding Pi inherits, distinct from the one-time cost of
  writing the gate extension itself.
- **Credential isolation ([ADR 0021](../adr/0021-agent-never-holds-the-real-llm-credential.md))
  now has two sharply contrasting real-world answers** (§8): `pi-claude-directsdk` gets it right —
  the agent process never touches the real credential, which stays inside an opaque `claude`
  subprocess — while `pi-anthropic-oauth` does the opposite, holding a raw OAuth bearer token
  in-process. Neither resolves how a virtual-key proxy would front Pi's own 15-provider
  `ModelRuntime` for providers other than Claude, which remains unverified, but the credential
  question is no longer purely theoretical for Pi specifically.
- **Pricing/business model is still unverified.** Not reached in any pass so far. Before treating
  Pi as a real candidate, confirm whether `pi.dev` is purely the open-source CLI/SDK (consistent
  with the MIT-licensed GitHub repo found) or whether there's a hosted/paid tier with its own terms
  that would matter the way the Claude Agent SDK's subscription-billing ambiguity did in the
  earlier survey.

## Verdict

**Pi is a live contender, not a dead one — and by a wide margin the most thoroughly evidenced one
surveyed so far.** The earlier survey's disqualifying claim — no synchronous per-call gate in
either mode — is wrong, now confirmed not just by Pi's own docs, worked example, and dispatch
source, but by **six** independent, unrelated third-party production codebases converging on the
same `beforeToolCall`/`tool_call` mechanism as their actual security boundary: a line-cited
third-party book reading the raw agent-loop source (`pi-book`), a JetBrains-incubated IDE
(`thinkrail`), a popular third-party desktop GUI (`percho`), a Pi-ecosystem extension library's own
enforcement tooling (`pi-extension-tools`), an independently-reinvented near-copy of ADR 0023's own
approval design (`pi-extension-small-modal-reliability`), and a pure-Rust client proving the gate
survives a non-JS language boundary in production (`orbit`). Four of these ship the gate in front
of real users today, not just in a docs example. Pi's gate is structurally close to Claude Agent SDK's `canUseTool`: it
fires before execution, can block with a reason, fails closed on a throwing handler at two
separate layers, hands the handler a clean `toolName`/`input` pair per call, and batches per-turn
so a multi-action turn clears the gate as a whole before any of it dispatches.

What makes Pi different from the Python-native options is three separable, now-concrete costs,
not an abstract one. First, the language boundary: the gate itself must live in a loaded
TypeScript extension, with RPC mode's UI-request channel as the bridge back to exhaust's own
Python process — a real cost, but **de-risked, not speculative**: `imrj05/orbit` ships exactly
this bridge pattern in production from a pure-Rust client. Second: the gate is **not inherited by
default** — `tintinweb/pi-schedule-prompt` shows a model-overridden subagent session spawns with
zero extensions loaded unless an operator explicitly re-enables them, a real default-open bypass
path any exhaust-on-Pi design must check at every session-creation site, not assume. Third: **Pi's
current public SDK surface has real, acknowledged gaps** that two independent serious integrators
are actively patching or mirroring around (JetBrains' formally tracked `pi-compatibility.md`,
Percho's shipped source patches) — an ongoing maintenance cost distinct from the one-time cost of
writing the gate extension. A structural hazard also surfaced and must be designed around from the
start: a documented deadlock in Pi's own harness docs if a hook awaits the current run's own
settlement.

Credential isolation (ADR 0021) is no longer a purely theoretical gap for Pi specifically: one
linked repo (`pi-claude-directsdk`) gets it right by routing through an opaque `claude` subprocess
the agent process never touches; another (`pi-anthropic-oauth`) does the opposite, holding a raw
OAuth token in-process — real evidence both the right and wrong answers already exist in Pi's own
ecosystem, though neither settles how a proxy would front Pi's 15-provider `ModelRuntime` for
non-Claude providers. Open questions before going further: whether exhaust is comfortable with any
TypeScript in the trust boundary at all (even a thin, reviewable, now-precedented shim); how
ADR-0021's credential proxy would sit in front of a 15-provider `ModelRuntime`; what pi.dev's
actual pricing/hosting model is; and whether the ongoing patch/mirror burden two existing
integrators already carry is an acceptable maintenance cost for exhaust to take on as well.

## What this settled for exhaust

- Corrects [`2026-10-27-agent-backend-abstraction-research.md`](2026-10-27-agent-backend-abstraction-research.md) §2:
  Pi has a real synchronous per-call gate (`pi.on("tool_call", ...)`/`beforeToolCall`), not none.
  Pi moves from "no veto point" to the same tier as Claude Agent SDK's `canUseTool`, now backed by
  six independent production adopters (`antinomie-lab/pi-book`, `JetBrains/thinkrail`,
  `Jaxton07/percho`, `pi-extension-tools`, `pi-extension-small-modal-reliability`, `imrj05/orbit`)
  confirming the mechanism holds up in real deployments, not just in docs. Not a recommendation to
  adopt it — the backend choice remains open and is the user's call — but it is no longer fair to
  rule Pi out on the "no approval hook" basis the earlier pass used.
- **`imrj05/orbit` de-risks the RPC-bridge integration pattern specifically**: what the first Pi
  pass flagged as its own unverified synthesis (a thin TypeScript gate extension deferring to an
  external, non-JS process over RPC) is now a confirmed, shipping pattern from a pure-Rust client.
  The language-boundary cost is real but no longer speculative.
- **`tintinweb/pi-schedule-prompt` names a concrete, previously-unknown risk**: a model-overridden
  subagent session loads zero extensions by default (`noExtensions: true`), meaning zero gates,
  unless an operator explicitly re-enables them. Any exhaust-on-Pi design needs an explicit
  gate-loaded check at every session-creation site, since Pi does not propagate it automatically.
- **`pi-extension-small-modal-reliability` independently reinvented something very close to ADR
  0023's own design** (hash-keyed approvals, host-normalized matching, re-propose-after-approval,
  never execute on approval alone) — convergent validation from an author with no connection to
  exhaust, not just an internally-consistent design.
- **A new, named cost beyond the TypeScript boundary**: real public-SDK gaps that existing
  integrators formally track (thinkrail's `pi-compatibility.md`) or source-patch around (Percho's
  shipped patches) — an ongoing maintenance burden, not a one-time integration cost, worth weighing
  against the Python-native options' comparative maturity.
- **Credential isolation (ADR 0021) now has two contrasting real-world examples specific to Pi**:
  `pi-claude-directsdk` never lets the agent process touch the real credential (an opaque `claude`
  subprocess holds it); `pi-anthropic-oauth` does the opposite, holding a raw OAuth token in-process
  and spoofing client identity to keep it working. Neither resolves how a proxy would front Pi's
  15-provider `ModelRuntime` for non-Claude providers.
- **A real counterexample worth noting against [ADR 0023](../adr/0023-consequential-real-target-actions-wait-for-a-human.md)'s
  "no bypass flag" stance**: both Percho and `imrj05/orbit` ship an audited `fullAccess`/"Full
  access" bypass mode. Not a reason to reconsider ADR 0023 — logged-but-allowed is a materially
  weaker guarantee than pre-approval-only — but evidence that two separate popular Pi-based tools
  independently made the opposite call exhaust explicitly rejected.
  Still open before any decision: pi.dev's pricing/hosting model, and how ADR-0021's credential
  proxy would front a 15-provider `ModelRuntime`.
