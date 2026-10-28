"""The relay tool names and fields `translate.py` and the gate extension both agree on.

There is no generated schema pipeline: the six relay tools are a small,
closed, rarely-changing set (they're exactly `AgentAction`'s own six
variants), so `gate/extension.ts` hand-writes its TypeBox schemas directly
rather than reading them from a file this module would otherwise have to
produce and keep in sync at runtime. This module is the parity anchor
instead: `tests/test_pi_adapter_translate.py` asserts `translate.py`'s
actual field requirements match `RELAY_TOOL_FIELDS`, and a comment in
`gate/extension.ts` points back at this module as the source of truth a
human keeps the two in sync against.

`exhaust_handshake` is not an `AgentAction` and carries no fields: it
exists only so `PiAgentSession` can prove the gate extension loaded in a
freshly started Pi session before trusting any real turn (ADR 0025, the
`pi-schedule-prompt` default-off finding).
"""

RELAY_TOOL_FIELDS: dict[str, tuple[str, ...]] = {
    "sandbox_call": ("tool", "method", "params"),
    "real_target_call": ("tool", "method", "params", "target"),
    "record_finding": ("claim", "severity", "scope", "evidence_scratch_path"),
    "propose_verdict": ("finding_id", "verdict_type"),
    "self_report": ("tools_exercised", "findings_dispositioned", "no_further_avenues"),
    "set_vertical_state": ("reason",),
    "exhaust_handshake": (),
}

RELAY_TOOL_NAMES: frozenset[str] = frozenset(RELAY_TOOL_FIELDS)

HANDSHAKE_TOOL_NAME = "exhaust_handshake"
