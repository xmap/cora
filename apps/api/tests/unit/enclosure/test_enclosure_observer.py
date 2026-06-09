"""Unit tests for `AlwaysPermittedEnclosureObserver` (the test-default stub).

Mirrors `AlwaysQuietCautionLookup` / `AlwaysCoveredClearanceLookup`
unit-test shape: pins that the stub yields one `EnclosureObservation`
per code in `scope.enclosure_codes`, every observation carries
`observed_status="Permitted"` (D6.L2 optimistic default consistent
with the stub's adjective), `source_kind` / `source_id` carry stable
stub-identity strings so consumers can distinguish stub-sourced
observations from production EPICS / Tango adapters, and
`observed_at` is a deterministic UTC epoch sentinel so tests can
assert exact payloads without injecting a clock.

The stub is the inline test-default adapter that lets `build_deps` /
`build_postgres_deps` synthesize an `EnclosureObserver` without
binding to a real substrate; existing Enclosure tests rely on this
default to avoid spinning up EPICS / P4P / Tango in-process.
"""

from datetime import UTC, datetime

import pytest

from cora.enclosure.aggregates.enclosure import EnclosurePermitStatus
from cora.enclosure.ports.enclosure_observer import (
    AlwaysPermittedEnclosureObserver,
    EnclosureObservation,
    EnclosureObserver,
    EnclosureObserverScope,
)

_HUTCH_A = "2-BM-A-Hutch"
_HUTCH_B = "2-BM-B-Hutch"
_CABINET = "2-BM-Control-Cabinet"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@pytest.mark.unit
def test_always_permitted_observer_satisfies_enclosure_observer_protocol() -> None:
    assert isinstance(AlwaysPermittedEnclosureObserver(), EnclosureObserver)


@pytest.mark.unit
async def test_always_permitted_observer_yields_nothing_for_empty_scope() -> None:
    observer = AlwaysPermittedEnclosureObserver()
    scope = EnclosureObserverScope(enclosure_codes=frozenset())
    observations = [obs async for obs in observer.observe(scope)]
    assert observations == []


@pytest.mark.unit
async def test_always_permitted_observer_yields_one_observation_per_code() -> None:
    observer = AlwaysPermittedEnclosureObserver()
    scope = EnclosureObserverScope(enclosure_codes=frozenset({_HUTCH_A}))
    observations = [obs async for obs in observer.observe(scope)]
    assert len(observations) == 1
    assert observations[0].enclosure_code == _HUTCH_A


@pytest.mark.unit
async def test_always_permitted_observer_yields_one_observation_per_code_for_many() -> None:
    observer = AlwaysPermittedEnclosureObserver()
    codes = frozenset({_HUTCH_A, _HUTCH_B, _CABINET})
    scope = EnclosureObserverScope(enclosure_codes=codes)
    observations = [obs async for obs in observer.observe(scope)]
    assert len(observations) == len(codes)
    assert {obs.enclosure_code for obs in observations} == codes


@pytest.mark.unit
async def test_always_permitted_observer_marks_every_observation_permitted() -> None:
    """The stub's adjective is load-bearing: every yielded observation
    carries `observed_status="Permitted"` so existing tests that build
    a default Enclosure stack do not incidentally surface NotPermitted
    states from the substrate seam."""
    observer = AlwaysPermittedEnclosureObserver()
    scope = EnclosureObserverScope(enclosure_codes=frozenset({_HUTCH_A, _HUTCH_B, _CABINET}))
    observations = [obs async for obs in observer.observe(scope)]
    for obs in observations:
        assert obs.observed_status == EnclosurePermitStatus.PERMITTED.value


@pytest.mark.unit
async def test_always_permitted_observer_emits_stable_stub_source_attribution() -> None:
    """`source_kind` + `source_id` carry stable, non-empty stub-identity
    strings so projection consumers can filter stub-sourced rows out of
    operational dashboards (`WHERE last_source_kind != 'Stub'`)."""
    observer = AlwaysPermittedEnclosureObserver()
    scope = EnclosureObserverScope(enclosure_codes=frozenset({_HUTCH_A}))
    observations = [obs async for obs in observer.observe(scope)]
    assert len(observations) == 1
    obs = observations[0]
    assert obs.source_kind == "Stub"
    assert obs.source_id == "AlwaysPermittedEnclosureObserver"


@pytest.mark.unit
async def test_always_permitted_observer_stamps_deterministic_utc_epoch() -> None:
    """The stub captures `observed_at` as `datetime(1970, 1, 1, tzinfo=UTC)`
    so tests can assert exact payloads across machines without depending
    on the runner's system timezone."""
    observer = AlwaysPermittedEnclosureObserver()
    scope = EnclosureObserverScope(enclosure_codes=frozenset({_HUTCH_A}))
    observations = [obs async for obs in observer.observe(scope)]
    assert len(observations) == 1
    obs = observations[0]
    assert obs.observed_at == _EPOCH


@pytest.mark.unit
async def test_always_permitted_observer_yields_observations_for_each_distinct_code() -> None:
    """Two-code scope yields two distinct observations whose
    `enclosure_code` values cover the scope set exactly; no duplicates,
    no extras, no codes outside the scope."""
    observer = AlwaysPermittedEnclosureObserver()
    scope = EnclosureObserverScope(enclosure_codes=frozenset({_HUTCH_A, _HUTCH_B}))
    observations = [obs async for obs in observer.observe(scope)]
    codes_seen = [obs.enclosure_code for obs in observations]
    assert sorted(codes_seen) == sorted({_HUTCH_A, _HUTCH_B})


@pytest.mark.unit
def test_enclosure_observation_is_frozen_dataclass() -> None:
    obs = EnclosureObservation(
        enclosure_code=_HUTCH_A,
        observed_status=EnclosurePermitStatus.PERMITTED.value,
        observed_at=_EPOCH,
        source_kind="Stub",
        source_id="always-permitted",
    )
    with pytest.raises(AttributeError):
        obs.observed_status = EnclosurePermitStatus.NOT_PERMITTED.value  # type: ignore[misc]


@pytest.mark.unit
def test_enclosure_observer_scope_is_frozen_dataclass() -> None:
    scope = EnclosureObserverScope(enclosure_codes=frozenset({_HUTCH_A}))
    with pytest.raises(AttributeError):
        scope.enclosure_codes = frozenset({_HUTCH_B})  # type: ignore[misc]
