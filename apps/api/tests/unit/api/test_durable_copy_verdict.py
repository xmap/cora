"""Unit: the locked rules for reading a `locate` verdict.

Tested apart from the sweep because these are policy, and policy is
what gets quietly altered by someone fixing something else. A test that
needed a sweep, a probe and a database to reach them would be skipped
the day one of those changed.
"""

from datetime import UTC, datetime

import pytest

from cora.api._durable_copy_verdict import (  # pyright: ignore[reportPrivateUsage]
    DurableCopyAmbiguous,
    DurableCopyFound,
    DurableCopyNotYetThere,
    DurableCopyRefused,
    DurableCopyUnreachable,
    read_locate_response,
)
from cora.shared.probe_error import (
    PROBE_ERROR_ORIGIN_CLIENT,
    PROBE_ERROR_ORIGIN_TRANSPORT,
)

pytestmark = pytest.mark.unit

_DURABLE = "/gdata/dm/2BM/2026-08/2026-08-Haridy-1015116/data/scan_005.h5"
_OTHER = "/gdata/dm/2BM/2026-08/2026-08-Other-1015116/data/scan_005.h5"
_MTIME = 1755000000.0
_MTIME_AS_DATETIME = datetime.fromtimestamp(_MTIME, tz=UTC)


def _match(path: str, *, modified_at: float = _MTIME) -> dict[str, object]:
    return {"path": path, "modified_at": modified_at}


def _located(*, match_count: int, matches: list[dict[str, object]]) -> dict[str, object]:
    return {"kind": "Located", "match_count": match_count, "matches": matches}


def test_exactly_one_match_is_found_and_carries_the_path() -> None:
    verdict = read_locate_response(_located(match_count=1, matches=[_match(_DURABLE)]))

    assert verdict == DurableCopyFound(path=_DURABLE, modified_at=_MTIME_AS_DATETIME)


def test_a_found_copy_carries_the_files_own_timestamp_not_a_clock_reading() -> None:
    """`observed_at` in the capture-path vault means the SUBSTRATE's
    time, and only the probing host can read it."""
    verdict = read_locate_response(
        _located(match_count=1, matches=[_match(_DURABLE, modified_at=1600000000.0)])
    )

    assert isinstance(verdict, DurableCopyFound)
    assert verdict.modified_at == datetime(2020, 9, 13, 12, 26, 40, tzinfo=UTC)


def test_no_match_is_not_yet_there_and_carries_no_reason() -> None:
    """The durable copy appears days later and only when an operator
    makes it, so nothing is wrong and there is nothing to report."""
    assert read_locate_response(_located(match_count=0, matches=[])) == DurableCopyNotYetThere()


def test_several_matches_refuse_and_name_the_colliding_folders() -> None:
    """Measured on the real archive, internal beamtime collides in 8 of
    14 months, so this fires in production. An operator who cannot see
    WHICH folders collided cannot resolve it."""
    verdict = read_locate_response(
        _located(match_count=2, matches=[_match(_DURABLE), _match(_OTHER)])
    )

    assert verdict == DurableCopyAmbiguous(match_count=2, paths=(_DURABLE, _OTHER))


def test_ambiguity_reports_the_true_count_even_when_matches_are_capped() -> None:
    """The probe caps how many matches one verdict carries. Reporting
    `len(paths)` instead would tell an operator two when the truth is
    fifty, and a truncated list reads like the whole story."""
    verdict = read_locate_response(
        _located(match_count=50, matches=[_match(_DURABLE), _match(_OTHER)])
    )

    assert isinstance(verdict, DurableCopyAmbiguous)
    assert verdict.match_count == 50
    assert len(verdict.paths) == 2


def test_a_transport_origin_failure_is_unreachable() -> None:
    """The one verdict that stops a sweep, so the one that must not be
    reachable from a single bad request."""
    verdict = read_locate_response(
        {
            "kind": "ProbeError",
            "origin": PROBE_ERROR_ORIGIN_TRANSPORT,
            "detail": "ssh exited 255",
        }
    )

    assert verdict == DurableCopyUnreachable(detail="ssh exited 255")


def test_a_client_origin_refusal_is_scoped_to_this_request_not_the_transport() -> None:
    """The distinction that keeps one misconfigured Dataset from
    wedging the sweep for every other one."""
    verdict = read_locate_response(
        {
            "kind": "ProbeError",
            "origin": PROBE_ERROR_ORIGIN_CLIENT,
            "detail": "refused before probing: no months to search",
        }
    )

    assert verdict == DurableCopyRefused(detail="refused before probing: no months to search")


def test_a_probe_error_with_no_origin_is_refused_rather_than_unreachable() -> None:
    """A response the remote produced reached CORA over a transport
    that works, so it says nothing about the next request. The
    fail-safe direction too: over-reporting per-request wastes one
    probe, over-reporting systemic stops a sweep for no reason."""
    verdict = read_locate_response({"kind": "ProbeError", "detail": "unknown op: 'locat'"})

    assert verdict == DurableCopyRefused(detail="unknown op: 'locat'")


def test_a_probe_error_is_never_read_as_not_yet_there() -> None:
    """Treating a failing probe as "still waiting" hides a deployment
    that is looking at nothing on every sweep, forever, while every
    Dataset quietly waits."""
    responses: list[dict[str, object]] = [
        {"kind": "ProbeError", "detail": "x"},
        {"kind": "ProbeError", "origin": PROBE_ERROR_ORIGIN_TRANSPORT, "detail": "x"},
        {},
    ]
    for response in responses:
        assert not isinstance(read_locate_response(response), DurableCopyNotYetThere)


def test_an_unrecognized_response_is_refused_with_a_stated_reason() -> None:
    assert read_locate_response({}) == DurableCopyRefused(detail="probe returned no usable verdict")


@pytest.mark.parametrize(
    "response",
    [
        {"kind": "Located", "matches": [_match(_DURABLE)]},
        {"kind": "Located", "match_count": 1},
        {"kind": "Located", "match_count": "1", "matches": [_match(_DURABLE)]},
        {"kind": "Located", "match_count": 1, "matches": _match(_DURABLE)},
    ],
)
def test_a_malformed_located_verdict_is_refused(response: dict[str, object]) -> None:
    assert isinstance(read_locate_response(response), DurableCopyRefused)


def test_one_counted_match_with_no_entry_is_refused_not_found() -> None:
    """An incoherent answer must not become a silent wait. Reading it as
    "not there" would park the Dataset forever behind a probe that is
    answering nonsense."""
    verdict = read_locate_response(_located(match_count=1, matches=[]))

    assert isinstance(verdict, DurableCopyRefused)


@pytest.mark.parametrize(
    "entry",
    [
        {"modified_at": _MTIME},
        {"path": _DURABLE},
        {"path": 7, "modified_at": _MTIME},
        {"path": _DURABLE, "modified_at": "yesterday"},
        {"path": _DURABLE, "modified_at": True},
    ],
)
def test_a_single_match_missing_its_path_or_timestamp_is_refused(entry: dict[str, object]) -> None:
    """`True` is in this list because `bool` is an `int` in Python, so
    an unguarded numeric check would silently date the file to
    1970-01-01 and vault that as the substrate's own answer."""
    assert isinstance(
        read_locate_response(_located(match_count=1, matches=[entry])), DurableCopyRefused
    )


def test_non_dict_entries_in_matches_are_dropped_rather_than_carried() -> None:
    verdict = read_locate_response(
        {"kind": "Located", "match_count": 2, "matches": [_match(_DURABLE), 7]}
    )

    assert isinstance(verdict, DurableCopyAmbiguous)
    assert verdict.paths == (_DURABLE,)
    assert verdict.match_count == 2
