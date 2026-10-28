"""Errors `PiAgentSession` raises (ADR 0025)."""


class GateNotLoadedError(RuntimeError):
    """Pi's gate extension didn't prove itself loaded before a turn needed it.

    Raised by `PiAgentSession.launch`/`_begin_vertical` when the handshake
    tool call doesn't arrive within the configured timeout. Never assumed
    from an earlier session's success: Pi doesn't load extensions into a
    freshly started session by default, so every session gets its own
    check (the `pi-schedule-prompt` finding this guards against).
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
