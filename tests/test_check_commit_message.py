from check_commit_message import check


def test_valid_subject_passes() -> None:
    assert check("feat: add the Scope Contract gate") is None


def test_valid_subject_with_scope_passes() -> None:
    assert check("feat(cli): add the new command") is None


def test_merge_commit_is_exempt() -> None:
    assert check("Merge branch 'main' into feature") is None


def test_revert_commit_is_exempt() -> None:
    assert check('Revert "feat: add the thing"') is None


def test_empty_subject_fails() -> None:
    assert check("") is not None


def test_unknown_type_fails() -> None:
    assert check("feature: add the thing") is not None


def test_missing_colon_fails() -> None:
    assert check("feat add the thing") is not None


def test_trailing_period_fails() -> None:
    assert check("feat: add the thing.") is not None


def test_uppercase_type_fails() -> None:
    assert check("Feat: add the thing") is not None
