"""Facility stream-id derivation: deterministic UUID5 over a fixed namespace."""

from uuid import UUID, uuid5

import pytest

from cora.federation.aggregates.facility import facility_stream_id
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.shared.facility_code import FacilityCode

# Expected namespace UUID locked at module load by `_stream_id.py`. The
# literal lives here as a regression guard against silent drift; the
# private constant in _stream_id.py MUST stay byte-identical to this
# value or every existing Facility stream becomes unreachable.
_EXPECTED_FACILITY_NAMESPACE = UUID("01900000-0000-7000-8000-0000fac11111")


@pytest.mark.unit
def test_facility_stream_id_is_deterministic_for_same_code() -> None:
    a = facility_stream_id(FacilityCode("aps"))
    b = facility_stream_id(FacilityCode("aps"))
    assert a == b


@pytest.mark.unit
def test_facility_stream_id_differs_for_different_codes() -> None:
    a = facility_stream_id(FacilityCode("aps"))
    b = facility_stream_id(FacilityCode("maxiv"))
    assert a != b


@pytest.mark.unit
def test_facility_stream_id_matches_uuid5_namespace_derivation() -> None:
    """Regression guard: the namespace UUID is load-bearing for stream
    continuity. Changing it would orphan every existing Facility stream.
    `facility_stream_id` MUST produce the same UUID as
    `uuid5(_EXPECTED_FACILITY_NAMESPACE, code.value)` byte-for-byte."""
    code = FacilityCode("aps")
    assert facility_stream_id(code) == uuid5(_EXPECTED_FACILITY_NAMESPACE, code.value)


@pytest.mark.unit
def test_facility_stream_id_does_not_alias_seal_stream_id() -> None:
    """Cross-aggregate safety: facility_stream_id(code) MUST NOT collide
    with seal_stream_id(code) on any input. The two namespaces are
    distinct sentinels; the smoke test asserts derivation on the same
    string input yields distinct stream ids."""
    code_value = "aps"
    assert facility_stream_id(FacilityCode(code_value)) != seal_stream_id(code_value)
