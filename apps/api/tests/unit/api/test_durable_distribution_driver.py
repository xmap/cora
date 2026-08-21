"""Unit: what one durable-distribution sweep tick actually does.

Every dependency is a fake here, which is exactly why the SQL behind
`next_candidate` is tested against real Postgres elsewhere and the
locate protocol against a real temporary tree. What this file can
prove, and a database cannot, is the branching: which verdict leads to
a write, which leaves the Dataset a candidate, and which stops the tick.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.api._durable_distribution_driver import (  # pyright: ignore[reportPrivateUsage]
    DurableDistributionDriver,
)
from cora.api._durable_distribution_sweep import (  # pyright: ignore[reportPrivateUsage]
    DurableDistributionCandidate,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
_DURABLE_ROOT = "/gdata/dm/2BM"
_SUPPLY_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FOUND = "/gdata/dm/2BM/2026-08/2026-08-Haridy-1015116/data/scan_005.h5"


@dataclass(frozen=True)
class _Location:
    root: str = _DURABLE_ROOT
    supply_id: UUID = _SUPPLY_ID
    access_protocol: str = "NFS"
    subdirectory: str | None = "data"


_DEFAULT_LOCATION = _Location()


class _Locations:
    def __init__(self, location: _Location | None) -> None:
        self._location = location

    def durable_location_for(self, capture_code: str) -> _Location | None:
        _ = capture_code
        return self._location


class _Probe:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def locate(self, **kwargs: Any) -> dict[str, object]:
        self.calls.append(kwargs)
        return self._response


class _Recorder:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def upsert(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


class _Registrar:
    def __init__(self, *, result: UUID | None) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    async def register(self, **kwargs: Any) -> UUID | None:
        self.calls.append(kwargs)
        return self._result


class _Clock:
    def now(self) -> datetime:
        return _NOW


class _Candidates:
    """Serves each candidate once, honouring `exclude` the way the real
    SQL does, so a driver that forgot to exclude would loop here."""

    def __init__(self, candidates: list[DurableDistributionCandidate]) -> None:
        self._candidates = candidates

    async def next_candidate(
        self, *, exclude: frozenset[UUID] = frozenset()
    ) -> DurableDistributionCandidate | None:
        for candidate in self._candidates:
            if candidate.dataset_id not in exclude:
                return candidate
        return None


def _candidate() -> DurableDistributionCandidate:
    return DurableDistributionCandidate(
        dataset_id=uuid4(),
        run_id=uuid4(),
        capture_code="2bmb-tomoscan",
        proposal_number="1015116",
        observed_path="/local1/2BM/2026-08-Haridy-1015116/scan_005.h5",
        acquisition_root="/local1/2BM",
    )


def _driver(
    *,
    candidates: list[DurableDistributionCandidate],
    response: dict[str, object],
    location: _Location | None = _DEFAULT_LOCATION,
    register_result: UUID | None = _SUPPLY_ID,
) -> tuple[DurableDistributionDriver, _Probe, _Recorder, _Registrar]:
    probe = _Probe(response)
    recorder = _Recorder()
    registrar = _Registrar(result=register_result)
    driver = DurableDistributionDriver(
        candidate_lookup=_Candidates(candidates),
        durable_locations=_Locations(location),
        probe=probe,
        capture_paths=recorder,
        registrar=registrar,
        host="tomdet",
        clock=_Clock(),
    )
    return driver, probe, recorder, registrar


def _located(*, match_count: int, paths: list[str]) -> dict[str, object]:
    return {"kind": "Located", "match_count": match_count, "paths": paths}


async def test_one_match_records_the_location_then_registers_it() -> None:
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(
        candidates=[candidate], response=_located(match_count=1, paths=[_FOUND])
    )

    await driver.tick()

    assert len(recorder.rows) == 1
    assert recorder.rows[0]["observed_path"] == _FOUND
    assert recorder.rows[0]["root"] == _DURABLE_ROOT
    assert recorder.rows[0]["host"] == "tomdet"
    assert len(registrar.calls) == 1
    assert registrar.calls[0]["supply_id"] == _SUPPLY_ID
    assert registrar.calls[0]["durable_path"] == _FOUND


async def test_the_location_is_recorded_before_the_copy_is_registered() -> None:
    """Order, not both-happened. The locator the Distribution carries
    resolves by looking the vault row up, so registering first would
    mint a reference to a row that does not exist yet."""
    order: list[str] = []
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(
        candidates=[candidate], response=_located(match_count=1, paths=[_FOUND])
    )

    original_upsert = recorder.upsert
    original_register = registrar.register

    async def _tracked_upsert(**kwargs: Any) -> None:
        order.append("record")
        await original_upsert(**kwargs)

    async def _tracked_register(**kwargs: Any) -> UUID | None:
        order.append("register")
        return await original_register(**kwargs)

    recorder.upsert = _tracked_upsert  # pyright: ignore[reportAttributeAccessIssue]
    registrar.register = _tracked_register  # pyright: ignore[reportAttributeAccessIssue]

    await driver.tick()

    assert order == ["record", "register"]


async def test_the_registered_locator_is_indirect_and_carries_no_surname() -> None:
    candidate = _candidate()
    driver, _, _, registrar = _driver(
        candidates=[candidate], response=_located(match_count=1, paths=[_FOUND])
    )

    await driver.tick()

    locator = str(registrar.calls[0]["locator"])
    assert locator.startswith("cora-capture-path://")
    assert "Haridy" not in locator


async def test_no_match_writes_nothing_and_leaves_the_dataset_a_candidate() -> None:
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(
        candidates=[candidate], response=_located(match_count=0, paths=[])
    )

    await driver.tick()

    assert recorder.rows == []
    assert registrar.calls == []


async def test_several_matches_write_nothing() -> None:
    """The refusal that fires roughly one month in eight, for internal
    beamtime. Recording either candidate would name the wrong bytes as
    this Dataset's durable copy, permanently."""
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(
        candidates=[candidate],
        response=_located(match_count=2, paths=[_FOUND, "/gdata/dm/2BM/2026-08/other/data/s.h5"]),
    )

    await driver.tick()

    assert recorder.rows == []
    assert registrar.calls == []


async def test_an_unreachable_probe_stops_the_tick_instead_of_walking_on() -> None:
    """A dead SSH hop fails identically for every candidate, so walking
    the rest of the population into it just multiplies the timeout."""
    candidates = [_candidate(), _candidate(), _candidate()]
    driver, probe, _, _ = _driver(
        candidates=candidates, response={"kind": "ProbeError", "detail": "ssh exited 255"}
    )

    await driver.tick()

    assert len(probe.calls) == 1


async def test_a_capture_code_with_no_durable_location_is_skipped_without_probing() -> None:
    candidate = _candidate()
    driver, probe, recorder, _ = _driver(
        candidates=[candidate], response=_located(match_count=1, paths=[_FOUND]), location=None
    )

    await driver.tick()

    assert probe.calls == []
    assert recorder.rows == []


async def test_a_failed_registration_keeps_the_recorded_location() -> None:
    """The vault row states where the file is, which stays true whether
    or not the register succeeded, and the Dataset stays a candidate
    because candidacy turns on the Distribution."""
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(
        candidates=[candidate],
        response=_located(match_count=1, paths=[_FOUND]),
        register_result=None,
    )

    await driver.tick()

    assert len(recorder.rows) == 1
    assert len(registrar.calls) == 1


async def test_the_probe_is_asked_for_the_month_and_its_neighbours() -> None:
    candidate = _candidate()
    driver, probe, _, _ = _driver(
        candidates=[candidate], response=_located(match_count=0, paths=[])
    )

    await driver.tick()

    assert probe.calls[0]["months"] == ("2026-08", "2026-07", "2026-09")
    assert probe.calls[0]["directory_suffix"] == "-1015116"
    assert probe.calls[0]["filename"] == "scan_005.h5"
    assert probe.calls[0]["subdirectory"] == "data"


async def test_an_unparseable_acquisition_folder_is_skipped_without_probing() -> None:
    """No month means no safe search. Widening to the whole archive
    would scan back to 2020 for folders whose naming scheme predates
    proposal numbers entirely."""
    candidate = DurableDistributionCandidate(
        dataset_id=uuid4(),
        run_id=uuid4(),
        capture_code="2bmb-tomoscan",
        proposal_number="1015116",
        observed_path="/local1/2BM/no-month-here/scan_005.h5",
        acquisition_root="/local1/2BM",
    )
    driver, probe, _, _ = _driver(
        candidates=[candidate], response=_located(match_count=1, paths=[_FOUND])
    )

    await driver.tick()

    assert probe.calls == []


async def test_a_skipped_candidate_is_not_reoffered_within_the_same_tick() -> None:
    """Without the exclusion the driver would take the same stuck head
    ten times and make no progress on anything behind it."""
    candidates = [_candidate(), _candidate()]
    driver, probe, _, _ = _driver(candidates=candidates, response=_located(match_count=0, paths=[]))

    await driver.tick()

    assert len(probe.calls) == len(candidates)
