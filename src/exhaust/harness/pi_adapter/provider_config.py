"""Writes Pi's own provider config so a run can front Anthropic through a proxy (ADR 0021).

Pi reads `models.json` and `auth.json` from its agent directory
(`docs/configuration.md`), not from CLI flags or Anthropic's own env
vars, to redirect a built-in provider's base URL or credential. This
module writes exactly those two files, in Pi's own documented shape —
confirmed from the real installed package's docs, not guessed — so
`PiAgentSession.launch()` can point Pi at `CredentialProxy` without
reaching into Pi's internals to do it.
"""

import json
from pathlib import Path


def write_anthropic_proxy_config(
    agent_dir: Path, *, base_url: str, virtual_key_file: Path | None = None
) -> None:
    """Write `models.json`, and `auth.json` if a virtual-key file is given.

    Parameters
    ----------
    agent_dir : Path
        Pi's agent directory for this run (`PI_CODING_AGENT_DIR`).
        Created if it doesn't already exist.
    base_url : str
        The local proxy's base URL (`CredentialProxy.base_url`), written
        as the `anthropic` provider's `baseUrl` override.
    virtual_key_file : Path | None
        Where the run's budget-capped virtual key lives on disk. When
        given, `auth.json` points Pi's own `!<command>` credential
        mechanism at `cat`-ing that file, so the virtual key reaches Pi
        as a file Pi itself reads, never as a value in its process
        environment (ADR 0021: the same shape as the real credential
        the proxy holds, for the same leak-surface reason). When
        `None`, Pi keeps using whatever `ANTHROPIC_API_KEY` or stored
        credential it already has — the base-URL redirect alone is
        still useful without a virtual key, e.g. pointing at a gateway
        that does its own authentication.
    """
    agent_dir.mkdir(parents=True, exist_ok=True)

    models = {"providers": {"anthropic": {"baseUrl": base_url}}}
    (agent_dir / "models.json").write_text(json.dumps(models, indent=2))

    if virtual_key_file is not None:
        auth = {"anthropic": {"type": "api_key", "key": f"!cat {virtual_key_file}"}}
        (agent_dir / "auth.json").write_text(json.dumps(auth, indent=2))
