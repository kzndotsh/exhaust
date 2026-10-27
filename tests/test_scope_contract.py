from pathlib import Path

from exhaust.scope_contract import CONTRACT_FILENAME, is_in_scope, load_scope_contract


def test_no_contract_is_out_of_scope(tmp_path: Path) -> None:
    assert load_scope_contract(tmp_path) is None
    assert is_in_scope(tmp_path, "example.com", "recon") is False


def test_matching_contract_is_in_scope(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text(
        "target: example.com\nbasis: owned_infrastructure\nextent: full\n"
    )
    assert is_in_scope(tmp_path, "example.com", "recon") is True


def test_mismatched_target_is_out_of_scope(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text(
        "target: example.com\nbasis: owned_infrastructure\nextent: full\n"
    )
    assert is_in_scope(tmp_path, "other.example", "recon") is False


def test_unknown_basis_fails_closed(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text(
        "target: example.com\nbasis: just-trust-me\nextent: full\n"
    )
    assert load_scope_contract(tmp_path) is None
    assert is_in_scope(tmp_path, "example.com", "recon") is False


def test_unknown_extent_fails_closed(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text(
        "target: example.com\nbasis: owned_infrastructure\nextent: everything\n"
    )
    assert load_scope_contract(tmp_path) is None
    assert is_in_scope(tmp_path, "example.com", "recon") is False


def test_recon_extent_does_not_authorize_a_full_call(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text(
        "target: example.com\nbasis: owned_infrastructure\nextent: recon\n"
    )
    assert is_in_scope(tmp_path, "example.com", "recon") is True
    assert is_in_scope(tmp_path, "example.com", "full") is False


def test_full_extent_authorizes_a_recon_call(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text(
        "target: example.com\nbasis: owned_infrastructure\nextent: full\n"
    )
    assert is_in_scope(tmp_path, "example.com", "recon") is True
    assert is_in_scope(tmp_path, "example.com", "full") is True


def test_unknown_required_extent_fails_closed(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text(
        "target: example.com\nbasis: owned_infrastructure\nextent: full\n"
    )
    assert is_in_scope(tmp_path, "example.com", "exploit") is False


def test_malformed_yaml_fails_closed(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text("target: [unterminated\n")
    assert load_scope_contract(tmp_path) is None
    assert is_in_scope(tmp_path, "example.com", "recon") is False


def test_non_mapping_contract_fails_closed(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text("- just\n- a\n- list\n")
    assert load_scope_contract(tmp_path) is None


def test_missing_field_fails_closed(tmp_path: Path) -> None:
    (tmp_path / CONTRACT_FILENAME).write_text("target: example.com\nbasis: owned_infrastructure\n")
    assert load_scope_contract(tmp_path) is None
