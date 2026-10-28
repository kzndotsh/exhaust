import json
from pathlib import Path

from exhaust.harness.pi_adapter.provider_config import write_anthropic_proxy_config


def test_writes_models_json_with_the_base_url_override(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agent"
    write_anthropic_proxy_config(agent_dir, base_url="http://127.0.0.1:9000")

    models = json.loads((agent_dir / "models.json").read_text())
    assert models == {"providers": {"anthropic": {"baseUrl": "http://127.0.0.1:9000"}}}


def test_writes_no_auth_json_without_a_virtual_key_file(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agent"
    write_anthropic_proxy_config(agent_dir, base_url="http://127.0.0.1:9000")

    assert not (agent_dir / "auth.json").exists()


def test_writes_auth_json_pointing_at_the_virtual_key_file(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agent"
    key_file = tmp_path / "virtual-key"

    write_anthropic_proxy_config(
        agent_dir, base_url="http://127.0.0.1:9000", virtual_key_file=key_file
    )

    auth = json.loads((agent_dir / "auth.json").read_text())
    assert auth == {"anthropic": {"type": "api_key", "key": f"!cat {key_file}"}}


def test_creates_the_agent_dir_if_it_does_not_exist(tmp_path: Path) -> None:
    agent_dir = tmp_path / "does" / "not" / "exist"
    write_anthropic_proxy_config(agent_dir, base_url="http://127.0.0.1:9000")
    assert agent_dir.is_dir()
