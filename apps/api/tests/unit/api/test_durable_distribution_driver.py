"""Unit: what one durable-distribution sweep tick actually does.

Every dependency is a fake here, which is exactly why the SQL behind
`next_candidate` is tested against real Postgres elsewhere and the
locate protocol against a real temporary tree. What this file can
prove, and a database cannot, is the branching: which verdict leads to
a write, which leaves the Dataset a candidate, which skips on to the
next one, and which stops the tick.

## The vault is real here, deliberately

`_Recorder` wraps a real `InMemoryCapturePathStore` rather than
appending to a list, so the minted locator can be resolved back
through `resolve_capture_path_locator`. That round trip is the only
check in this file with two independent sides: the vault row and the
locator are produced by separate calls with separately-passed
arguments, and resolution succeeds only if they agree on `run_id`,
`host`, `root` AND filename. A test that merely asserted the recorder
received the right root would agree with itself by construction, and
an earlier version of this file did exactly that: it passed unchanged
against a driver that minted with the wrong tier and against one that
minted with the wrong host.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any
from uuid import UUID, uuid4

import pytest
import structlog.testing

from cora.api._durable_distribution_driver import (  # pyright: ignore[reportPrivateUsage]
    _MAX_CANDIDATES_PER_TICK,  # pyright: ignore[reportPrivateUsage]
    DurableCopyAlreadyRegistered,
    DurableCopyRegistered,
    DurableCopyRegisterRefused,
    DurableCopyRegisterUnauthorized,
    DurableCopyRegistration,
    DurableDistributionDriver,
)
from cora.api._durable_distribution_sweep import (  # pyright: ignore[reportPrivateUsage]
    DurableDistributionCandidate,
    DurableDistributionCursor,
)
from cora.data.adapters.capture_path_locator import (
    mint_capture_path_locator,
    resolve_capture_path_locator,
)
from cora.run.aggregates.run import InMemoryCapturePathStore
from cora.shared.probe_error import (
    PROBE_ERROR_ORIGIN_CLIENT,
    PROBE_ERROR_ORIGIN_TRANSPORT,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
_MTIME = 1755000000.0
_MTIME_AS_DATETIME = datetime.fromtimestamp(_MTIME, tz=UTC)
_DURABLE_ROOT = "/gdata/dm/2BM"
_ACQUISITION_ROOT = "/local1/2BM"
_SUPPLY_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-0000000000bb")
_HOST = "tomdet"
_FOUND = "/gdata/dm/2BM/2026-08/2026-08-Haridy-1015116/data/scan_005.h5"
_OTHER = "/gdata/dm/2BM/2026-08/2026-08-Other-0/data/scan_005.h5"


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
    """Serves one response per call, so a test can give the first
    candidate a different answer from the second. The single-response
    fake this replaced could not see head-of-line blocking at all:
    with every candidate answering identically, stopping the tick and
    carrying on look the same from the outside."""

    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def locate(self, **kwargs: Any) -> dict[str, object]:
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]


class _Recorder:
    def __init__(self) -> None:
        self.store = InMemoryCapturePathStore()
        self.rows: list[dict[str, Any]] = []

    async def upsert(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)
        await self.store.upsert(**kwargs)


class _Registrar:
    def __init__(self, *, result: DurableCopyRegistration) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    async def register(self, **kwargs: Any) -> DurableCopyRegistration:
        self.calls.append(kwargs)
        return self._result


class _Clock:
    def now(self) -> datetime:
        return _NOW


class _Candidates:
    """Serves candidates in the real query's order, honouring the cursor
    the way its keyset predicate does, so a driver that forgot to
    advance would loop here and one that advanced twice would skip."""

    def __init__(self, candidates: list[DurableDistributionCandidate]) -> None:
        self._candidates = sorted(candidates, key=lambda c: (c.created_at, c.dataset_id))

    async def next_candidate(
        self, *, after: DurableDistributionCursor | None = None
    ) -> DurableDistributionCandidate | None:
        for candidate in self._candidates:
            if after is None or (candidate.created_at, candidate.dataset_id) > (
                after.created_at,
                after.dataset_id,
            ):
                return candidate
        return None


_created_at_sequence = count()


def _candidate(
    *, observed_path: str | None = None, proposal_number: str = "1015116"
) -> DurableDistributionCandidate:
    """Each call is one tick of the query's ordering key, so candidates
    come back in the order they were built."""
    return DurableDistributionCandidate(
        dataset_id=uuid4(),
        created_at=_EPOCH + timedelta(minutes=next(_created_at_sequence)),
        run_id=uuid4(),
        capture_code="2bmb-tomoscan",
        proposal_number=proposal_number,
        observed_path=observed_path or f"{_ACQUISITION_ROOT}/2026-08-Haridy-1015116/scan_005.h5",
        acquisition_root=_ACQUISITION_ROOT,
    )


def _driver(
    *,
    candidates: list[DurableDistributionCandidate],
    responses: list[dict[str, object]],
    location: _Location | None = _DEFAULT_LOCATION,
    registration: DurableCopyRegistration | None = None,
) -> tuple[DurableDistributionDriver, _Probe, _Recorder, _Registrar]:
    probe = _Probe(responses)
    recorder = _Recorder()
    registrar = _Registrar(
        result=registration or DurableCopyRegistered(distribution_id=_DISTRIBUTION_ID)
    )
    driver = DurableDistributionDriver(
        candidate_lookup=_Candidates(candidates),
        durable_locations=_Locations(location),
        probe=probe,
        capture_paths=recorder,
        registrar=registrar,
        host=_HOST,
        clock=_Clock(),
    )
    return driver, probe, recorder, registrar


def _located(*, match_count: int, paths: list[str]) -> dict[str, object]:
    return {
        "kind": "Located",
        "match_count": match_count,
        "matches": [{"path": path, "modified_at": _MTIME} for path in paths],
    }


_FOUND_ONE = _located(match_count=1, paths=[_FOUND])
_FOUND_NONE = _located(match_count=0, paths=[])
_TRANSPORT_DEAD: dict[str, object] = {
    "kind": "ProbeError",
    "origin": PROBE_ERROR_ORIGIN_TRANSPORT,
    "detail": "ssh exited 255",
}
_REQUEST_REFUSED: dict[str, object] = {
    "kind": "ProbeError",
    "origin": PROBE_ERROR_ORIGIN_CLIENT,
    "detail": "refused before probing: no months to search",
}


async def test_one_match_records_the_location_then_registers_it() -> None:
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(candidates=[candidate], responses=[_FOUND_ONE])

    await driver.tick()

    assert len(recorder.rows) == 1
    assert recorder.rows[0]["observed_path"] == _FOUND
    assert recorder.rows[0]["root"] == _DURABLE_ROOT
    assert recorder.rows[0]["host"] == _HOST
    assert len(registrar.calls) == 1
    assert registrar.calls[0]["supply_id"] == _SUPPLY_ID
    assert registrar.calls[0]["durable_path"] == _FOUND


async def test_the_registered_locator_resolves_back_to_the_recorded_path() -> None:
    """The one check here with two independent sides. `resolve` looks
    the vault row up by the `(run_id, host, root)` the LOCATOR names,
    so this fails if the driver minted against anything other than what
    it recorded, which is the whole reason recording comes first."""
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(candidates=[candidate], responses=[_FOUND_ONE])

    await driver.tick()

    resolved = await resolve_capture_path_locator(
        str(registrar.calls[0]["locator"]), capture_path_store=recorder.store
    )

    assert resolved == f"file://{_FOUND}"


@pytest.mark.parametrize(
    ("host", "root"),
    [(_HOST, _ACQUISITION_ROOT), ("arcturus", _DURABLE_ROOT)],
)
async def test_a_locator_minted_against_another_location_does_not_resolve(
    host: str, root: str
) -> None:
    """Pins the round-trip test above as a real check rather than a
    decorative one: it must FAIL for the mutations it exists to catch.

    The wrong locator is built by the REAL minting function, not by
    formatting a string here. A hand-written one is how the first
    version of this test came to prove nothing: it spelled the run
    segment `{run:...}` where the format is `run-...`, so resolution
    refused on the shape long before it compared host or tier, and the
    test passed for a CORRECT locator too.
    """
    candidate = _candidate()
    driver, _, recorder, _ = _driver(candidates=[candidate], responses=[_FOUND_ONE])

    await driver.tick()

    elsewhere = mint_capture_path_locator(
        observed_path=_FOUND, run_id=candidate.run_id, host=host, root=root
    )

    assert elsewhere is not None
    assert await resolve_capture_path_locator(elsewhere, capture_path_store=recorder.store) is None


async def test_a_root_spelled_with_a_trailing_slash_still_round_trips() -> None:
    """Settings are hand-written, and `resolve` matches the vault key
    byte for byte. Normalizing in one place is what keeps a stray
    slash from minting an immutable locator that resolves to nothing."""
    candidate = _candidate()
    driver, probe, recorder, registrar = _driver(
        candidates=[candidate],
        responses=[_FOUND_ONE],
        location=_Location(root=f"{_DURABLE_ROOT}/"),
    )

    await driver.tick()

    assert probe.calls[0]["root"] == _DURABLE_ROOT
    assert recorder.rows[0]["root"] == _DURABLE_ROOT
    resolved = await resolve_capture_path_locator(
        str(registrar.calls[0]["locator"]), capture_path_store=recorder.store
    )
    assert resolved == f"file://{_FOUND}"


async def test_the_recorded_observation_time_is_the_files_own_not_the_clocks() -> None:
    """`observed_at` states when the substrate saw the file. Writing
    `clock.now()` there would also break the vault's monotonic upsert:
    every retry would carry a newer timestamp while claiming to state
    the same unchanged fact."""
    candidate = _candidate()
    driver, _, recorder, _ = _driver(candidates=[candidate], responses=[_FOUND_ONE])

    await driver.tick()

    assert recorder.rows[0]["observed_at"] == _MTIME_AS_DATETIME
    assert recorder.rows[0]["created_at"] == _NOW


async def test_the_location_is_recorded_before_the_copy_is_registered() -> None:
    order: list[str] = []
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(candidates=[candidate], responses=[_FOUND_ONE])

    original_upsert = recorder.upsert
    original_register = registrar.register

    async def _tracked_upsert(**kwargs: Any) -> None:
        order.append("record")
        await original_upsert(**kwargs)

    async def _tracked_register(**kwargs: Any) -> DurableCopyRegistration:
        order.append("register")
        return await original_register(**kwargs)

    recorder.upsert = _tracked_upsert  # pyright: ignore[reportAttributeAccessIssue]
    registrar.register = _tracked_register  # pyright: ignore[reportAttributeAccessIssue]

    await driver.tick()

    assert order == ["record", "register"]


async def test_the_registered_locator_is_indirect_and_carries_no_surname() -> None:
    candidate = _candidate()
    driver, _, _, registrar = _driver(candidates=[candidate], responses=[_FOUND_ONE])

    await driver.tick()

    locator = str(registrar.calls[0]["locator"])
    assert locator.startswith("cora-capture-path://")
    assert "Haridy" not in locator


async def test_no_match_writes_nothing_and_leaves_the_dataset_a_candidate() -> None:
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(candidates=[candidate], responses=[_FOUND_NONE])

    await driver.tick()

    assert recorder.rows == []
    assert registrar.calls == []


async def test_several_matches_write_nothing() -> None:
    """The refusal that fires roughly one month in eight, for internal
    beamtime. Recording either candidate would name the wrong bytes as
    this Dataset's durable copy, permanently."""
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(
        candidates=[candidate], responses=[_located(match_count=2, paths=[_FOUND, _OTHER])]
    )

    await driver.tick()

    assert recorder.rows == []
    assert registrar.calls == []


async def test_a_dead_transport_stops_the_tick_instead_of_walking_on() -> None:
    """A dead SSH hop fails identically for every candidate, so walking
    the rest of the population into it just multiplies the timeout."""
    candidates = [_candidate(), _candidate(), _candidate()]
    driver, probe, _, _ = _driver(candidates=candidates, responses=[_TRANSPORT_DEAD])

    await driver.tick()

    assert len(probe.calls) == 1


async def test_one_refused_request_does_not_stop_the_sweep_reaching_the_next() -> None:
    """The head-of-line blocking a gate review removed from
    `CaptureScanIngestor` once. A refusal is scoped to one request, so
    a single misconfigured Dataset must not wedge every other one, and
    the Dataset behind it must still get registered in the same tick."""
    stuck, healthy = _candidate(), _candidate()
    driver, probe, _, registrar = _driver(
        candidates=[stuck, healthy], responses=[_REQUEST_REFUSED, _FOUND_ONE]
    )

    await driver.tick()

    assert len(probe.calls) == 2
    assert len(registrar.calls) == 1
    assert registrar.calls[0]["dataset_id"] == healthy.dataset_id


async def test_a_capture_code_with_no_durable_location_is_skipped_without_probing() -> None:
    candidate = _candidate()
    driver, probe, recorder, _ = _driver(
        candidates=[candidate], responses=[_FOUND_ONE], location=None
    )

    await driver.tick()

    assert probe.calls == []
    assert recorder.rows == []


async def test_a_refused_registration_keeps_the_recorded_location() -> None:
    """The vault row states where the file is, which stays true whether
    or not the register succeeded, and the Dataset stays a candidate
    because candidacy turns on the Distribution."""
    candidate = _candidate()
    driver, _, recorder, registrar = _driver(
        candidates=[candidate],
        responses=[_FOUND_ONE],
        registration=DurableCopyRegisterRefused(detail="bytes unreadable"),
    )

    await driver.tick()

    assert len(recorder.rows) == 1
    assert len(registrar.calls) == 1


async def test_a_refused_registration_does_not_stop_the_sweep_reaching_the_next() -> None:
    stuck, healthy = _candidate(), _candidate()
    driver, _, _, registrar = _driver(
        candidates=[stuck, healthy],
        responses=[_FOUND_ONE],
        registration=DurableCopyRegisterRefused(detail="bytes unreadable"),
    )

    await driver.tick()

    assert [call["dataset_id"] for call in registrar.calls] == [
        stuck.dataset_id,
        healthy.dataset_id,
    ]


async def test_an_unauthorized_registration_stops_the_tick() -> None:
    candidates = [_candidate(), _candidate(), _candidate()]
    driver, _, _, registrar = _driver(
        candidates=candidates,
        responses=[_FOUND_ONE],
        registration=DurableCopyRegisterUnauthorized(),
    )

    await driver.tick()

    assert len(registrar.calls) == 1


async def test_an_already_registered_copy_moves_on_rather_than_ending_the_tick() -> None:
    """The expected answer while the Distribution projection lags: the
    register already happened, so this tick did no work and should
    spend its turn on a Dataset that still needs one. Counting it as a
    success would let a stalled projector reduce the sweep to one
    no-op per tick."""
    done, pending = _candidate(), _candidate()
    driver, probe, _, _ = _driver(
        candidates=[done, pending],
        responses=[_FOUND_ONE],
        registration=DurableCopyAlreadyRegistered(distribution_id=_DISTRIBUTION_ID),
    )

    await driver.tick()

    assert len(probe.calls) == 2


async def test_the_probe_is_asked_for_the_month_and_its_neighbours() -> None:
    candidate = _candidate()
    driver, probe, _, _ = _driver(candidates=[candidate], responses=[_FOUND_NONE])

    await driver.tick()

    assert probe.calls[0]["months"] == ("2026-08", "2026-07", "2026-09")
    assert probe.calls[0]["directory_suffix"] == "-1015116"
    assert probe.calls[0]["filename"] == "scan_005.h5"
    assert probe.calls[0]["subdirectory"] == "data"
    assert probe.calls[0]["root"] == _DURABLE_ROOT


async def test_an_unparseable_acquisition_folder_is_skipped_without_probing() -> None:
    """No month means no safe search. Widening to the whole archive
    would scan back to 2020 for folders whose naming scheme predates
    proposal numbers entirely."""
    candidate = _candidate(observed_path=f"{_ACQUISITION_ROOT}/no-month-here/scan_005.h5")
    driver, probe, _, _ = _driver(candidates=[candidate], responses=[_FOUND_ONE])

    await driver.tick()

    assert probe.calls == []


async def test_a_skipped_candidate_is_not_reoffered_within_the_same_tick() -> None:
    candidates = [_candidate(), _candidate()]
    driver, probe, _, _ = _driver(candidates=candidates, responses=[_FOUND_NONE])

    await driver.tick()

    assert len(probe.calls) == len(candidates)


async def test_a_tick_past_its_attempt_cap_stops_walking_candidates() -> None:
    """Without the cap, a population of stuck candidates larger than
    the cap would be re-walked in full on every tick forever."""
    candidates = [_candidate() for _ in range(_MAX_CANDIDATES_PER_TICK + 5)]
    driver, probe, _, _ = _driver(candidates=candidates, responses=[_FOUND_NONE])

    await driver.tick()

    assert len(probe.calls) == _MAX_CANDIDATES_PER_TICK


async def test_a_stuck_queue_head_longer_than_the_cap_still_lets_the_rest_through() -> None:
    """The starvation the per-tick skip list did not prevent. The
    candidate query is ordered and the head is stable, and three skip
    reasons never clear on their own, so with more permanently-stuck
    Datasets than one tick can walk, a driver that forgot them between
    ticks would spend every tick on the same ten and never reach the
    eleventh. Ambiguity alone is expected one month in eight, which
    makes ten a steady state rather than a pathological case."""
    stuck = [_candidate() for _ in range(_MAX_CANDIDATES_PER_TICK + 2)]
    healthy = _candidate()
    ambiguous = _located(match_count=2, paths=[_FOUND, _OTHER])
    driver, _, _, registrar = _driver(
        candidates=[*stuck, healthy],
        responses=[*([ambiguous] * len(stuck)), _FOUND_ONE],
    )

    # Two ticks is what it takes to walk twelve stuck Datasets at ten
    # attempts each. A driver that forgot them between ticks spends both
    # on the same first ten and registers nothing.
    await driver.tick()
    await driver.tick()

    assert {call["dataset_id"] for call in registrar.calls} == {healthy.dataset_id}


async def test_a_drained_cycle_starts_over_so_a_waiting_dataset_is_looked_at_again() -> None:
    """The other half of carrying the walked set: "not there yet" is
    the normal state for days, so a Dataset skipped for it has to come
    back round rather than be excluded for the life of the process."""
    candidate = _candidate()
    driver, probe, _, _ = _driver(candidates=[candidate], responses=[_FOUND_NONE])

    await driver.tick()
    await driver.tick()

    assert len(probe.calls) == 2


async def test_a_registered_dataset_is_not_reprobed_for_the_rest_of_the_cycle() -> None:
    """Candidacy is read from a projection that lags behind the append,
    so the Dataset keeps coming back as a candidate after a successful
    register. Advancing past it is what keeps that lag from costing a
    probe per tick.

    The two candidates carry DIFFERENT proposal numbers on purpose. An
    earlier version asserted on the filename, which `_candidate` gives
    every candidate identically, so it could not tell "probed each once"
    from "probed the first one twice" and passed against a driver that
    never advanced on success."""
    done = _candidate(proposal_number="1000001")
    pending = _candidate(proposal_number="2000002")
    driver, probe, _, _ = _driver(candidates=[done, pending], responses=[_FOUND_ONE])

    await driver.tick()
    await driver.tick()

    assert [call["directory_suffix"] for call in probe.calls] == ["-1000001", "-2000002"]


async def test_a_successful_registration_ends_the_tick() -> None:
    """One digest per tick. The register reads the whole file over SSH,
    so a tick that carried on would hold the sweep open for as long as
    there were candidates."""
    first, second = _candidate(), _candidate()
    driver, _, _, registrar = _driver(candidates=[first, second], responses=[_FOUND_ONE])

    await driver.tick()

    assert len(registrar.calls) == 1


async def test_no_log_line_from_a_tick_carries_the_experiment_folder() -> None:
    """The surname reaches CORA only through the vault, which is
    erasable. A log sink is not, and every branch here has an id or a
    count that says the same thing without the path."""
    candidates = [
        _candidate(),
        _candidate(observed_path=f"{_ACQUISITION_ROOT}/no-month-here/scan_005.h5"),
        _candidate(),
        _candidate(),
    ]
    responses = [
        _located(match_count=2, paths=[_FOUND, _OTHER]),
        _FOUND_ONE,
        _REQUEST_REFUSED,
        _FOUND_ONE,
    ]
    driver, _, _, _ = _driver(candidates=candidates, responses=responses)

    with structlog.testing.capture_logs() as captured:
        await driver.tick()

    rendered = repr(captured)
    assert "Haridy" not in rendered
    assert _FOUND not in rendered
    assert "no-month-here" not in rendered


async def test_the_locator_names_the_file_the_probe_found_not_the_one_it_searched_for() -> None:
    """They are the same string at 2-BM, since the probe searches by
    the acquisition filename. A facility that renamed on archive would
    make them differ, and minting from the candidate rather than the
    verdict would then mint a locator naming a file the vault row does
    not describe."""
    candidate = _candidate()
    renamed = "/gdata/dm/2BM/2026-08/2026-08-Haridy-1015116/data/scan_005_archived.h5"
    driver, _, recorder, registrar = _driver(
        candidates=[candidate], responses=[_located(match_count=1, paths=[renamed])]
    )

    await driver.tick()

    resolved = await resolve_capture_path_locator(
        str(registrar.calls[0]["locator"]), capture_path_store=recorder.store
    )

    assert resolved == f"file://{renamed}"


async def test_a_tick_stopped_by_a_dead_transport_retries_the_same_candidate() -> None:
    """Neither systemic condition is the candidate's fault, so the
    cursor must not step over a Dataset that was never examined. This
    is the one path that deliberately does not advance."""
    first = _candidate(proposal_number="1000001")
    second = _candidate(proposal_number="2000002")
    driver, probe, _, _ = _driver(
        candidates=[first, second], responses=[_TRANSPORT_DEAD, _TRANSPORT_DEAD]
    )

    await driver.tick()
    await driver.tick()

    assert [call["directory_suffix"] for call in probe.calls] == ["-1000001", "-1000001"]


async def test_a_tick_stopped_by_an_unauthorized_register_retries_the_same_candidate() -> None:
    first = _candidate(proposal_number="1000001")
    second = _candidate(proposal_number="2000002")
    driver, probe, _, _ = _driver(
        candidates=[first, second],
        responses=[_FOUND_ONE],
        registration=DurableCopyRegisterUnauthorized(),
    )

    await driver.tick()
    await driver.tick()

    assert [call["directory_suffix"] for call in probe.calls] == ["-1000001", "-1000001"]
