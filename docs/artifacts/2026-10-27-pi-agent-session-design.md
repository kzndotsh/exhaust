# Design: `PiAgentSession`, the first `AgentSession` implementation

Produced via the architect workflow (Ground → two independent Sketch candidates → Synthesis), per
ADR 0025. A design sketch, not a decision document: ADR 0025 already settled that Pi backs
`AgentSession`; this settles *how*, down to types and signatures, with `not implemented` bodies.
Nothing has been written to `src/` yet. This is the Phase C checkpoint artifact — implementation
starts only after sign-off.

## Problem

`AgentSession` (`src/exhaust/harness/agent.py`) is a two-method Protocol — `step(request) ->
AgentAction`, `observe(outcome) -> None` — deliberately not a `take_turn(transcript)` call, so a
stateful SDK session can keep its own history instead of the Harness reconstructing it every turn.
`Harness._run_one_turn` (`core.py`) calls these strictly alternately, once each, synchronous,
one action at a time. Pi is the opposite shape: an asynchronous subprocess running its own agent
loop that decides on its own when to call a tool. The adapter inverts one into the other without
either side knowing.

Three constraints the design must honor, not paper over:

- `AgentAction` and `ActionOutcome` are closed, fixed unions (`actions.py`). The adapter produces
  instances; it never adds a variant, and `Harness._dispatch` is untouchable.
- `AgentTurnRequest.available_tools` is `tuple[ToolInfo, ...]` — tool-level `name`/`usage`/`doc`
  only, confirmed by `tests/test_harness.py:625`'s `request.available_tools ==
  (FakeScanner.info,)`. No method list, no parameter schema, ever reaches the agent seam. This is
  deliberate: ADR 0013 has the agent read a tool's `doc` to learn its methods, as prose.
- Pi does not load extensions into spawned sessions by default
  (`tintinweb/pi-schedule-prompt`'s `noExtensions: true` finding, in
  `docs/research/2026-10-27-pi-harness-audit.md` §7). A gate that isn't verified loaded is a gate
  that isn't there.

## Usage (caller's view)

```python
# src/exhaust/cli/run.py — the only place that knows Pi exists
from exhaust.harness.core import Harness
from exhaust.harness.budget import RunBudget
from exhaust.harness.pi_adapter import PiAgentSession, PiLaunchConfig, GateNotLoadedError

cfg = PiLaunchConfig(
    pi_executable=Path("/usr/local/bin/pi"),
    model="anthropic/claude-sonnet",
    provider_base_url="https://proxy.local:8899/v1",  # ADR 0021's proxy; issued elsewhere
    gate_extension_dir=PI_ADAPTER_GATE_DIR,
)

try:
    with PiAgentSession.launch(cfg, scratch_dir=workspace_dir / "pi") as agent:
        harness = Harness.open(workspace_dir, skills_dir, target, agent=agent, bridges=bridges)
        outcome = harness.run(budget=RunBudget(max_turns=200))
except GateNotLoadedError as exc:
    sys.exit(f"refusing to run ungated: {exc}")
```

`Harness`, `core.py`, and `actions.py` import nothing from `pi_adapter` — per ADR 0025, no other
exhaust module is aware Pi exists. `PiLaunchConfig.provider_base_url` is the one seam ADR 0021's
credential proxy plugs into; minting the virtual key is a separate module's job, not this one's.

## Shape

### Module map

```
src/exhaust/harness/pi_adapter/
    __init__.py       # exports PiAgentSession, PiLaunchConfig, the error types
    session.py        # PiAgentSession: the AgentSession implementation, process/session lifecycle
    rpc.py             # PiRpc: newline-delimited JSON transport over the subprocess's stdio
    translate.py       # pure: RelayCall -> AgentAction, ActionOutcome -> the wire reply value
    schema.py          # the six customTool JSON schemas, derived from actions.py; written to a file
    errors.py          # GateNotLoadedError, PiProtocolError, AgentWentSilentError
    gate/
        extension.ts    # the one piece of TypeScript; relays, decides nothing
        package.json
```

`translate.py` and `schema.py` are pure functions over domain types, no I/O, independently
testable against `actions.py` with zero subprocess dependency. `rpc.py` is a thin transport shell.
`session.py` is the only stateful object.

### The central fork, resolved: Pi sees exactly six tools, never the Rig catalog

The decisive synthesis call. One candidate registered a generic relay `customTool` per Rig
`ToolInfo` (N tools, one per pinned tool, plus four fixed meta-action tools) — rejected. Every one
of those N tool schemas would carry the identical generic shape `{method, params, target?}`, since
`ToolInfo` has no method-level detail to make them structurally different; registering N
identical-shaped tools buys no model-call correctness exhaust doesn't already get from two, and it
grows the model's visible tool list with the size of the Rig catalog, in tension with ADR 0013's
progressive-disclosure intent.

The adopted design instead registers exactly the six `AgentAction` variants as Pi `customTools` —
`SandboxCall` and `RealTargetCall`'s schemas carry a generic `{tool, method, params, target?}`
shape (for `RealTargetCall`, `target` is required), and the Rig's actual tool catalog is rendered
as prose inside the prompt built from `AgentTurnRequest.available_tools`, exactly mirroring how
`ToolInfo` already works today for every other hypothetical backend. This never touches
`ToolInfo`/`AgentTurnRequest` — the shared seam every future `AgentSession` backend depends on —
and it is the more faithful reading of ADR 0013 in the first place: a tool's methods are supposed
to be learned from its `doc`, as prose, not from a structured schema that doesn't exist yet.
Correctness on `tool`/`method`/`params` is not schema-enforced; an unknown tool or method raises
inside `rig.call`, the Harness turns it into `ActionRejected`, and that already-tested retry loop
(ADR 0007) is where a bad call gets corrected, not a new validation layer this adapter would have
to keep in sync with the Rig's own.

```python
# schema.py
def action_tool_schemas() -> list[dict[str, object]]:
    """The six customTool definitions, one per AgentAction variant, derived from actions.py's
    own dataclass fields. Written to a file at launch (schema.py's output, not hardcoded in the
    extension) and read by the gate extension via an env var it's launched with, so the extension
    carries zero exhaust vocabulary and actions.py stays the one source of truth. A test asserts
    these schemas' fields match the dataclass fields in actions.py, so a field added to
    RecordFinding and forgotten here fails loudly instead of silently drifting.
    """
    raise NotImplementedError
```

### Subprocess and session lifecycle: one subprocess per run, verified per vertical

One Pi subprocess for the whole `Harness.run()` call, reused across every turn and every vertical.
A fresh Pi *session* is opened within that subprocess on each vertical's first visit
(`PiRpc.new_session()`), giving each vertical a clean context — the structural form of ADR 0013's
"an inactive vertical's procedure never enters context," not a prompting discipline relying on the
model not mentioning an old one. The gate is re-verified on every new session, never assumed from
an earlier one, directly answering the `pi-schedule-prompt` default-off finding at every
session-creation point rather than only the first.

```python
@dataclass(frozen=True)
class PiLaunchConfig:
    """Everything needed to spawn and gate one Pi subprocess.

    Attributes
    ----------
    pi_executable : Path
        The `pi` binary, started as `pi --mode rpc --no-session --extensions <gate_extension_dir>`.
    model : str
        Pi's provider/model id, e.g. "anthropic/claude-sonnet".
    provider_base_url : str | None
        Written into Pi's provider config as the `baseUrl` ADR 0021's proxy fronts. None is only
        valid outside a real run.
    gate_extension_dir : Path
        This package's own `gate/`, passed to `--extensions` explicitly — Pi loads none by
        default into RPC sessions (ADR 0025, the `pi-schedule-prompt` finding).
    handshake_timeout_s : float = 10.0
        How long to wait for the gate's own announced handshake before refusing to run.
    settle_reprompts : int = 2
        How many times `step()` nudges Pi to act when a turn settles with no tool call, before
        raising `AgentWentSilentError`.
    """

    pi_executable: Path
    model: str
    provider_base_url: str | None
    gate_extension_dir: Path
    handshake_timeout_s: float = 10.0
    settle_reprompts: int = 2


class PiAgentSession:
    """A live Pi subprocess, presented to the Harness as one AgentSession.

    `step`/`observe` strictly alternate, enforced by `Harness._run_one_turn`'s own ordering: one
    relay call is ever parked between a `step` return and the next `observe`, so a single
    `_pending` id suffices. No queue, no shared write state — one producer (Pi), one consumer
    (the Harness), per `separate-before-serializing-shared-state`.
    """

    def __init__(self, rpc: "PiRpc", cfg: PiLaunchConfig) -> None:
        self._rpc = rpc
        self._cfg = cfg
        self._active_vertical: str | None = None
        self._pending: str | None = None

    @classmethod
    def launch(cls, cfg: PiLaunchConfig, *, scratch_dir: Path) -> "_PiSessionCtx":
        """Spawn the subprocess, perform the gate handshake, and only then yield a session.

        A failed handshake raises `GateNotLoadedError` before yielding, so a caller can never
        hold a session whose gate isn't confirmed live. On exit, SIGTERMs the subprocess.
        """
        raise NotImplementedError

    def step(self, request: AgentTurnRequest) -> AgentAction:
        """Drive Pi until it proposes one relayable action; translate and return it.

        A new `request.vertical`: open a fresh Pi session, re-verify the gate, send the prompt
        built from the procedure and `available_tools`. Then block on RPC for the next relay
        call. If the turn instead settles idle (the model answered in plain text, no tool call),
        re-prompt up to `settle_reprompts` times, then raise `AgentWentSilentError` — the
        synchronous protocol must always yield an action, so a model that won't act is a loud
        failure, never a hang.
        """
        raise NotImplementedError

    def observe(self, outcome: ActionOutcome) -> None:
        """Answer the parked relay call so Pi's handler returns `outcome` as that tool's result.

        `ToolResult` and `ActionRejected` both arrive at the model as a normal tool *result* it
        reads and reacts to — `ActionRejected` is ADR 0007's retry feedback, never a Pi-level
        `block`. Pi's own `block` is reserved for the gate's defense-in-depth refusal of a
        non-relay tool, a decision this adapter never asks it to make about a real dispatch
        outcome.
        """
        raise NotImplementedError

    def _begin_vertical(self, request: AgentTurnRequest) -> None: ...
    def _await_next_relay_call(self) -> "RelayCall": ...
    def _answer_relay(self, request_id: str, value: dict[str, object]) -> None: ...
    def _verify_gate(self) -> None: ...
    def _compose_prompt(self, request: AgentTurnRequest) -> str: ...
```

### The relay: event in, `AgentAction` out; outcome in, wire reply out

```python
# translate.py
@dataclass(frozen=True)
class RelayCall:
    """One parked tool call, already deserialized off the RPC wire."""

    id: str
    tool_name: str  # one of the six AgentAction variant names, or the handshake's own name
    input: dict[str, object]


def action_from_relay(call: RelayCall, *, vertical: str) -> AgentAction:
    """Build one AgentAction from a relay call's name and input.

    `vertical` is injected from the Harness's own currently active vertical, never read from
    Pi's payload — nothing in the model's input can forge which vertical an action is attributed
    to; this is encoded by construction, not checked at runtime.
    """
    raise NotImplementedError


def outcome_to_wire(outcome: ActionOutcome) -> dict[str, object]:
    """ToolResult -> {"ok": ..., "output": ...}. ActionRejected -> {"ok": False, "output": reason}
    (still a readable result, not a block). None -> {"ok": True, "output": ""}.
    """
    raise NotImplementedError
```

### The gate extension — one job: relay, never decide

```typescript
// gate/extension.ts — the one piece of TypeScript this adapter introduces.
export default function gate(ctx: ExtensionFactoryCtx): Extension {
  const schemas = readActionSchemas(process.env.EXHAUST_ACTION_SCHEMA); // written by schema.py

  return {
    customTools: schemas.map((s) => ({
      name: s.name,
      inputSchema: s.inputSchema,
      handler: async (input) => {
        // One RPC round trip, ever: awaits only the Harness's reply, never this run's own
        // settlement (waitForIdle/agent_settled) — the documented deadlock hazard, avoided by
        // construction rather than by care.
        const { ok, output } = await ctx.ui.request({ method: "exhaust.relay", value: { tool: s.name, input } });
        return { content: output, isError: !ok };
      },
    })),

    // Proves the gate is live by making an outbound call itself, rather than relying on Pi's
    // own wire protocol to happen to enumerate loaded extensions somewhere.
    onSessionStart: async () => {
      await ctx.ui.request({ method: "exhaust.handshake", value: {} });
    },

    // Defense in depth, checked in TypeScript before any RPC round trip: a tool that isn't one
    // of our six relay tools — Pi's own built-in bash/edit, or anything a subsession leaks in —
    // is blocked immediately, never forwarded. Fail-closed is Pi's own default for a throwing
    // hook, so even a bug here denies rather than allows.
    onToolCall: (event) => {
      if (!schemas.some((s) => s.name === event.toolName)) {
        return { block: true, reason: "exhaust: only relayed AgentActions may execute" };
      }
      return {};
    },
  };
}
```

### Interface depth

The public surface is three symbols: `PiAgentSession`, `PiLaunchConfig`, and the error types.
`PiAgentSession` exposes exactly the two methods `AgentSession` already demands. Behind that:
subprocess lifecycle, RPC framing, the async-to-sync inversion, per-vertical session management,
the self-proving gate handshake, idle-settle recovery, and wire translation. No Pi or RPC type
appears on any public signature; the Harness and the CLI that wires this in see only
`AgentSession`.

### What it deliberately does not do

- No validation of `tool`/`method`/`params` beyond what `Harness._dispatch` already does — a
  second validation layer here would drift from the one the Rig itself owns.
- No `AgentAction` variant invented, filtered, or special-cased.
- No tool execution. Pi never runs a Rig tool directly; every relay handler round-trips to the
  Harness, which remains the sole dispatch chokepoint.

## Synthesis decision

Two independent candidates (Opus, Sonnet) sketched this design in parallel from the same
grounding. Opus's candidate is the base: its resolution of the tool-schema fork (six
`AgentAction`-shaped tools, Rig catalog as prose) has strictly better interface depth than
Sonnet's N-tools-plus-four approach for no correctness loss, its `onToolCall` whitelist adds a
real defense-in-depth layer Sonnet's design left to Python alone, its self-proving `onSessionStart`
handshake doesn't depend on an unconfirmed assumption about Pi's wire protocol the way Sonnet's
"read it off the init message" approach does, its `ActionRejected`-as-tool-result argument against
Sonnet's `ActionRejected`-as-Pi-`block` is the more carefully reasoned of the two and the one that
actually preserves ADR 0007's retry semantics, and its explicit `AgentWentSilentError` names an
async-to-sync edge case (the model settles a turn with no tool call at all) that Sonnet's design
addressed less directly.

Grafted from Sonnet's candidate: its `_VerticalSession`-shaped "one subprocess per vertical, kept
alive across the run" design is adopted wholesale as this design's **named fallback**, not
discarded. Opus's single-subprocess, multiple-sessions-via-`new_session()` approach depends on an
unverified capability of Pi's actual RPC wire (see Open questions); Sonnet's design never needed
that capability at all, since a fresh subprocess is guaranteed to start with a fresh Pi session by
construction. If the spike below shows `new_session()` doesn't cleanly reset context, Sonnet's
fully-specified per-vertical-subprocess shape is what this design falls back to, not a redesign
from scratch.

Rejected from Sonnet's candidate, with reasons: the N-tools-plus-four schema registration (strictly
worse interface depth, no correctness gain, see §Shape); mapping `ActionRejected` to Pi's `block`
(breaks the retry loop a model needs to read as corrective feedback); inferring gate-loaded state
from a wire-protocol enumeration rather than an active, self-proving handshake call.

## Tradeoffs accepted

- We accept a maintained Python-to-JSON-to-TypeScript schema pipeline (`schema.py` plus an env
  var the extension reads) in exchange for an extension with zero exhaust vocabulary and
  `actions.py` as the single source of truth, with drift caught by a test, not by a production
  surprise.
- We accept that `tool`/`method`/`params` correctness is unenforced at the schema level, in
  exchange for never widening `ToolInfo`/`AgentTurnRequest`, a seam every current and future
  backend shares, and for staying faithful to ADR 0013's prose-driven tool discovery.
- We accept one Pi session reset per vertical visit (reusing one subprocess) as the primary
  design, contingent on a capability this design has not yet verified against the real `pi`
  binary — with a fully-specified, no-redesign-needed fallback already written down if that
  verification fails.
- We accept `AgentWentSilentError` as a real, user-visible failure mode rather than a silent hang,
  since the synchronous `step`/`observe` contract has no way to represent "the agent didn't do
  anything this turn."
- We accept that Pi's own subagent/background-session spawning is disabled outright for this
  adapter — not threaded through the gate at all — rather than designing a second relay path for
  it before any vertical's procedure has asked for one.

## Alternatives considered

- **One generic `exhaust_action` mega-tool** with a free-form discriminator field, instead of six
  typed `customTools`. Rejected: identical interface depth, but it gives the model a looser
  surface to fill, which empirically means more malformed calls and more `ActionRejected`
  round-trips than a schema that matches the real six-variant closed vocabulary.
- **Widen `ToolInfo`/`AgentTurnRequest` to carry `MethodInfo` and real per-method parameter
  schemas**, so every Rig tool could get its own richly-typed Pi tool. Rejected: this taxes every
  current and future `AgentSession` backend to solve one backend's wire-format preference, breaks
  the existing `tests/test_harness.py:625` contract, and isn't actually needed once Rig tools are
  understood as parameters *inside* an action, not as Pi tools in their own right.
- **A subprocess per turn** (spawn, one action, kill, repeat). Throws away Pi's own context,
  caching, and compaction on every single action, which is the entire reason to use Pi instead of
  a raw API loop. Rejected outright.
- **Two-phase RPC**: the gate decides allow/deny first, a second follow-up call fetches the
  execution result for the handler to return. Rejected: reopens the exact deadlock shape the
  research flagged (a hook awaiting more of the run it's already blocking), for no benefit — the
  Harness already has the real outcome synchronously by the time the gate's reply is due.

## Implementation reconciliation

Before writing any code, a verification spike installed the real published package
(`@earendil-works/pi-coding-agent@1.4.0`) and read its actual shipped type definitions and docs,
rather than implementing against the sketch's assumptions on faith. Two of those assumptions were
wrong, caught before they became bugs:

- **There is no `customTools` constructor option on `createAgentSession()`.** Custom tools are
  registered inside an extension via `pi.registerTool({name, label, description, parameters,
  execute})`, confirmed directly from `examples/sdk/06-extensions.ts` in the installed package.
  This doesn't change the design's conclusion (six relay tools, Rig catalog as prose) — it changes
  *where* those six tools are declared: inside `gate/extension.ts` itself, hand-authored with
  `typebox`'s `Type.Object(...)`, not generated from a Python-written schema file an env var
  pointed at. `schema.py` is now the parity anchor a test pins (`RELAY_TOOL_FIELDS`), not a
  generator; `gate/extension.ts` is the implementation, kept in sync by hand, per its own README.
- **`ctx.ui` is not a general-purpose arbitrary-payload channel.** Its dialog methods
  (`select`/`confirm`/`input`/`editor`) are real and do round-trip over RPC, confirmed from
  `docs/rpc-extension-ui.md` and `examples/extensions/rpc-demo.ts` in the installed package, but
  each has a fixed, narrow response shape, and — decisively — **a dialog auto-resolves with a
  default value if the client doesn't answer in time.** That is the one property this design
  cannot accept anywhere near an authorization decision: a hung decision-channel silently defaulting
  to "allow" is exactly the failure ADR 0023 exists to rule out. The relay instead runs over a
  dedicated Unix domain socket (`relay.py`, `UnixSocketRelayChannel`) that this adapter owns
  outright, never auto-allowing on timeout — but a code-review pass after the first implementation
  found the first cut of this only half-delivered that: `accept_once`'s `timeout` bounded waiting
  for a new connection, not reading the call off one already accepted, so a peer that connected
  and then stalled hung indefinitely despite the configured timeout. Fixed by applying the same
  `timeout` to the accepted connection's own read (`connection.settimeout(timeout)`), proven by
  `tests/test_pi_adapter_relay.py::test_a_connection_accepted_but_never_sending_data_times_out`,
  which connects and deliberately sends nothing. The RPC command channel (`rpc.py`) had the
  identical gap — no timeout at all on the subprocess's stdout read — fixed the same way via
  `select.select` with a configurable `response_timeout_s`. The gate handshake is now a seventh
  registered tool (`exhaust_handshake`) the opening prompt explicitly instructs the model to call
  first, rather than an `onSessionStart` hook calling `ctx.ui.request(...)` (which also doesn't
  exist) — proven, not assumed, by `PiAgentSession._begin_vertical`'s unit tests. Those same tests
  caught a second real bug: `_active_vertical` was being set before the handshake was confirmed,
  so a retried `step()` after a failed handshake silently skipped re-verification; fixed by only
  setting it once the handshake actually succeeds, proven by
  `test_retrying_step_after_a_failed_handshake_re_runs_begin_vertical`. A relayed call arriving
  before the handshake tool is now also diagnosed as its own `HandshakeSkippedError`, distinct from
  `GateNotLoadedError`: the call only reaches this adapter by actually traveling through the loaded
  extension, which is proof the gate loaded, so the two causes (infra failure vs. a model skipping
  an instruction) no longer collapse into one indistinguishable error.

  The same pass also found `UnixSocketRelayChannel.close()` only closed the listening socket, never
  a connection that was accepted but never answered (e.g. if an exception elsewhere left it
  unanswered) — now `close()` tracks and closes every such connection, proven by
  `test_close_cleans_up_a_connection_accepted_but_never_answered`. What that fix doesn't reach: an
  exception escaping `Harness._dispatch`'s own narrow `except` clauses during normal operation still
  leaves one connection unanswered until the next `close()`, since that dispatch code lives outside
  this package. Left as a known limitation, not fixed here.

  Finally, `_propose_verdict` validated every field except `note` and `requirements`, which went
  straight from the wire into a `Verdict` with no type check, unlike every sibling field. Fixed with
  the same `_str`-shaped helpers the rest of the module already uses
  (`_str_with_default`/`_optional_str`), proven by
  `test_propose_verdict_rejects_a_non_string_note`/`_requirements`.

One assumption was independently confirmed correct: **`new_session` is a real, documented
top-level RPC command** (`{"type": "new_session"}`, `docs/rpc-commands.md`), so the primary
single-subprocess, multi-session-via-`new_session()` design needed no fallback after all; the
fully-specified per-vertical-subprocess alternative in this doc's history was never required.

Implemented: `src/exhaust/harness/pi_adapter/` (`errors.py`, `translate.py`, `schema.py`, `rpc.py`,
`relay.py`, `session.py`, `gate/extension.ts`), with full test coverage for every pure-Python path
and the real Unix-socket implementation (`tests/test_pi_adapter_*.py`, 48 tests), and the gate
extension's TypeScript independently checked clean (`tsc --noEmit`, zero errors) against the real
installed package and `typebox` type definitions. **Not yet verified: an actual end-to-end run
against a live `pi` subprocess with real model credentials** — everything above is proven against
real, installed types and documentation, and against this adapter's own logic through fakes and a
real local socket, but no live model has ever actually called one of these tools. That remains the
next real risk before trusting this in production.

A follow-up no-credential smoke test — installing `@earendil-works/pi-coding-agent@1.4.0` in
isolation and actually spawning `pi --mode rpc` with `session.py`'s real `launch()` argv — found two
more wrong assumptions, both in argv construction rather than in the TypeScript or the Python
domain logic, and both now fixed and regression-tested:

- **The flag is singular: `--extension <file>`, not `--extensions <dir>`.** `pi --help` on the real
  CLI confirms it; `--extensions` doesn't exist, and `--no-extensions`/`-ne` (a different flag) is
  only for disabling discovery. It also only loads a directory if that directory holds an
  `index.ts`/`index.js` entry point — `gate/` holds `extension.ts`, so the config now names the file
  directly (`PiLaunchConfig.gate_extension_file`, renamed from `gate_extension_dir`). Loading the
  real `gate/extension.ts` this way against the real `pi` binary registered all seven tools and its
  `tool_call` hook with no runtime error, confirming the TypeScript is correct under Pi's own `jiti`
  transform, not just under `tsc --noEmit`.
- **`--provider` alone is rejected by the real CLI**: `Error: --provider requires --model (for
  example: --provider anthropic --model <pattern>)`. `PiLaunchConfig` gained a required `model`
  field, now passed as `--model` alongside `--provider` in `launch()`'s argv.

Both are pinned by `tests/test_pi_adapter_session.py::test_launch_uses_the_real_pi_cli_flags`. What
this smoke test still doesn't cover, by design: no model credentials means no prompt was ever sent
and no tool was ever actually invoked by a live model, so the relay round trip itself (a real call
arriving over the Unix socket from a live `pi` run) remains the one thing only a credentialed run
can prove.

## Open questions and risks

- **Resolved by the verification spike**: `new_session` is real (confirmed); the
  `extension_ui_request`/`response` channel does carry structured values, but is reserved for
  genuine user-facing dialogs only, never the relay itself, which uses its own socket instead; the
  handshake no longer depends on `onSessionStart` timing at all, since it's a tool call the opening
  prompt explicitly requests.
- **How poor would Pi's tool-call accuracy actually be** on the loose `{tool, method, params}`
  shape without per-method schemas, in practice, against real procedure text? If retries prove
  expensive, is a richer `doc` string (e.g. an embedded, prose-rendered method table) enough, or
  does this eventually justify the rejected `ToolInfo` widening as its own future ADR? Still open;
  only answerable against a live model.
- **Where exactly does `PiLaunchConfig.provider_base_url` get plumbed** — a Pi provider config
  file, a CLI flag, an env var — once ADR 0021's proxy actually exists? Still a named stub; not
  plumbed by this implementation.
- **Resolved**: a code-review pass flagged that the first implementation relied entirely on the
  `tool_call` allowlist hook — an in-Pi-process check — to keep built-in tools from running, with
  no host-enforced restriction at spawn, in tension with ADR 0018's "the bridge enforces, not
  merely advertises" standard. `cli.md` documents the exact flag needed: `-nbt`/`--no-builtin-tools`
  ("Disables default built-in tools while retaining extension and custom tools"), confirmed from
  the real installed package's docs, not guessed. `launch()` now passes it at spawn
  (`tests/test_pi_adapter_session.py::test_launch_spawns_pi_with_builtin_tools_disabled`), so the
  `tool_call` hook is genuine defense-in-depth on top of a host-enforced restriction, not the sole
  boundary. Still unverified: an actual live run confirming `--no-builtin-tools` behaves as
  documented in practice.

## Next implementation step

Done: `translate.py`, `schema.py`, `rpc.py`, `relay.py`, `session.py`, and `gate/extension.ts` are
all implemented and tested (see Implementation reconciliation). The next real step is an actual
end-to-end run against a live `pi` subprocess with real model credentials — the one thing this
pass couldn't verify, since it had neither.

## Explicitly out of scope

- ADR 0021's credential-proxy implementation. `provider_base_url` is the seam it plugs into;
  minting the budget-capped virtual key is a separate module.
- Bedrock and Vertex support (ADR 0025's own named limitation — ambient cloud credentials, no
  `baseUrl`-shaped proxy mechanism found for either).
- Compaction, retry/backoff tuning, and model-provider selection policy inside Pi itself — left at
  Pi's own defaults, which is the point of using it.
- The gate extension's build/bundling pipeline, beyond assuming Pi can load a raw `.ts` file via
  `--extensions` as documented; if that assumption is wrong, that's an implementation detail to
  fix, not an architectural one.
- Pi's own public-SDK-gap maintenance burden (ADR 0025 names this cost explicitly); not pre-solved
  here, inherited over time the same way it is for every other serious Pi integrator.
