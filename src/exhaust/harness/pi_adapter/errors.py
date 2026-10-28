"""Errors `PiAgentSession` raises (ADR 0025)."""


class GateNotLoadedError(RuntimeError):
    """Pi's gate extension didn't prove itself loaded before a turn needed it.

    Raised by `PiAgentSession._begin_vertical` when nothing is relayed
    within the handshake timeout at all — no evidence the extension ever
    loaded. Never assumed from an earlier session's success: Pi doesn't
    load extensions into a freshly started session by default, so every
    session gets its own check (the `pi-schedule-prompt` finding this
    guards against). Distinct from `HandshakeSkippedError`, which is a
    different diagnosis for a different observation.
    """


class HandshakeSkippedError(RuntimeError):
    """A relay call arrived during handshake, but not the handshake tool itself.

    Raised instead of `GateNotLoadedError` when `_begin_vertical` receives
    a real tool call before the handshake: that call only reaches this
    adapter by actually traveling from the Pi subprocess through the
    loaded gate extension over the relay socket, which is proof the gate
    loaded. The failure here is the model not following the opening
    prompt's instruction to call the handshake tool first, a prompting
    problem, not an infrastructure one — worth a different error so an
    operator doesn't chase the wrong cause.
    """


class PiProtocolError(RuntimeError):
    """Pi's RPC stdio stream sent something off the documented contract.

    Malformed JSON, an unparseable record, or a command response whose
    `success` is false when this adapter expected it to succeed.
    """


class AgentWentSilentError(RuntimeError):
    """A turn settled with no relayable tool call, repeatedly.

    `step()` must always return one `AgentAction`; a model that answers in
    plain text instead of calling a tool, even after being re-prompted,
    can't satisfy that contract, so this is a loud failure, not a hang.
    """


class MalformedRelayCallError(RuntimeError):
    """A relay call's tool name or input didn't translate into an `AgentAction`.

    Raised by `exhaust.harness.pi_adapter.translate.action_from_relay`.
    Never reaches the Harness as an `AgentAction`, since there was never a
    valid one to dispatch; the caller answers the relay connection with a
    rejection and lets the model retry, the same shape `ActionRejected`
    already gives it for a Harness-level refusal.
    """
