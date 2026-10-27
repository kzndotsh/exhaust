from exhaust.oracle import (
    OracleMechanism,
    OracleResult,
    oracle_result_from_dict,
    oracle_result_to_dict,
)


def test_to_dict_renders_every_field() -> None:
    result = OracleResult(
        mechanism=OracleMechanism.OUT_OF_BAND_CALLBACK, passed=True, detail="DNS hit observed"
    )
    assert oracle_result_to_dict(result) == {
        "mechanism": "out_of_band_callback",
        "passed": True,
        "detail": "DNS hit observed",
    }


def test_to_dict_of_none_is_none() -> None:
    assert oracle_result_to_dict(None) is None


def test_from_dict_of_none_is_none() -> None:
    assert oracle_result_from_dict(None) is None


def test_round_trip_preserves_the_result() -> None:
    result = OracleResult(
        mechanism=OracleMechanism.CROSS_SESSION_ACCESS_DIFFERENTIAL,
        passed=False,
        detail="second account could not read the first account's data",
    )
    assert oracle_result_from_dict(oracle_result_to_dict(result)) == result
