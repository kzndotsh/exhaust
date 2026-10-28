# exhaust's Pi gate extension

`extension.ts` is the one piece of TypeScript this adapter introduces (ADR 0025). It
registers exactly seven tools in a Pi subprocess — the six `AgentAction` variants plus a
zero-argument handshake — and relays every call to exhaust's own Harness over a Unix
domain socket. It never decides anything itself.

## Verifying it compiles

```bash
npm install
npx tsc --noEmit
```

Checked clean against the real `@earendil-works/pi-coding-agent@1.4.0` and `typebox`
type definitions (not just assumed from documentation) as part of writing this file.
A later no-credential smoke test went further: it loaded this exact file into a real
`pi --mode rpc` subprocess (via `--extension`, Pi's own `jiti` runtime transform, not
`tsc`) and confirmed all seven tools and the `tool_call` hook register with no runtime
error. A follow-up credentialed run went all the way: a real live model, talking through
a local Anthropic-compatible gateway, actually called the handshake tool and then
`set_vertical_state` over the real Unix socket, and `PiAgentSession` translated and
answered both — the first time any part of this adapter has been proven against a live
model rather than a fake, a local socket with no model behind it, or a type checker. See
`docs/artifacts/2026-10-27-pi-agent-session-design.md`'s reconciliation log.

## Keeping this in sync with the Python side

The `PARAMETERS` table here and `exhaust.harness.pi_adapter.schema.RELAY_TOOL_FIELDS`
describe the same seven tools from two languages, by hand, not by a generated
pipeline — the set is small and rarely changes. `tests/test_pi_adapter_translate.py`
pins the Python side's actual field requirements; change a field in `actions.py`,
update both `schema.py` and this file's `PARAMETERS` together.
