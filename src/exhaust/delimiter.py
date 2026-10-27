"""Untrusted Target output is delimited distinctly (ADR 0009).

Content that originates from the Target (an HTTP response, an error
page, log output) is wrapped in a distinct, nonce-style delimiter
before it reaches an agent's prompt, so the agent has an explicit
signal that the text is data from the thing under attack, never an
instruction to follow. The nonce is random per call so a hostile
Target crafting its own response can't predict and forge the boundary
in advance.

A delimiter marks the boundary; it doesn't enforce it on its own (ADR
0009 is explicit about this). It has to be paired with the
instruction-source-boundary rule the agent is actually built to follow
(never execute an instruction that arrives inside Target output,
regardless of framing) to do any real work.
"""

import secrets

_NONCE_BYTES = 16


def wrap_untrusted_content(text: str, *, label: str = "TARGET OUTPUT") -> str:
    """Wrap `text` in a random, nonce-tagged boundary marking it as untrusted.

    Parameters
    ----------
    text : str
        The Target-sourced content to wrap.
    label : str
        What kind of untrusted content this is, shown in the boundary
        (e.g. "HTTP RESPONSE BODY", "ERROR PAGE").

    Returns
    -------
    str
        `text` wrapped between a begin/end marker pair sharing one
        random nonce, so the agent can tell genuine boundaries from
        anything inside `text` that merely looks like one.
    """
    nonce = secrets.token_hex(_NONCE_BYTES)
    begin = f"----- BEGIN UNTRUSTED {label} ({nonce}) -----"
    end = f"----- END UNTRUSTED {label} ({nonce}) -----"
    return f"{begin}\n{text}\n{end}"
