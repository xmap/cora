"""Unit: the two locked rules for reading a `locate` verdict.

Tested apart from the sweep because these are policy, and policy is
what gets quietly altered by someone fixing something else. A test that
needed a sweep, a probe and a database to reach them would be skipped
the day one of those changed.
"""

import pytest

from cora.api._durable_copy_verdict import (  # pyright: ignore[reportPrivateUsage]
    DurableCopyAmbiguous,
    DurableCopyFound,
    DurableCopyNotYetThere,
    DurableCopyUnreachable,
    read_locate_response,
)

pytestmark = pytest.mark.unit

_DURABLE = "/gdata/dm/2BM/2026-08/2026-08-Haridy-1015116/data/scan_005.h5"
_OTHER = "/gdata/dm/2BM/2026-08/2026-08-Other-1015116/data/scan_005.h5"


def _located(*, match_count: int, paths: list[str]) -> dict[str, object]:
    return {"kind": "Located", "match_count": match_count, "paths": paths}


def test_exactly_one_match_is_found_and_carries_the_path() -> None:
    verdict = read_locate_response(_located(match_count=1, paths=[_DURABLE]))

    assert verdict == DurableCopyFound(path=_DURABLE)


def test_no_match_is_not_yet_there_and_carries_no_reason() -> None:
    """The durable copy appears days later and only when an operator
    makes it, so nothing is wrong and there is nothing to report."""
    assert read_locate_response(_located(match_count=0, paths=[])) == DurableCopyNotYetThere()


def test_several_matches_refuse_and_name_the_colliding_folders() -> None:
    """Measured on the real archive, internal beamtime collides in 8 of
    14 months, so this fires in production. An operator who cannot see
    WHICH folders collided cannot resolve it."""
    verdict = read_locate_response(_located(match_count=2, paths=[_DURABLE, _OTHER]))

    assert verdict == DurableCopyAmbiguous(match_count=2, paths=(_DURABLE, _OTHER))


def test_ambiguity_reports_the_true_count_even_when_paths_are_capped() -> None:
    """The probe caps how many paths one verdict carries. Reporting
    `len(paths)` instead would tell an operator two when the truth is
    fifty, and a truncated list reads like the whole story."""
    verdict = read_locate_response(_located(match_count=50, paths=[_DURABLE, _OTHER]))

    assert isinstance(verdict, DurableCopyAmbiguous)
    assert verdict.match_count == 50
    assert len(verdict.paths) == 2


def test_a_probe_error_is_unreachable_not_not_yet_there() -> None:
    """The distinction that matters most here. Treating a failing probe
    as "still waiting" hides a deployment that is looking at nothing on
    every sweep, forever, while every Dataset quietly waits."""
    verdict = read_locate_response({"kind": "ProbeError", "detail": "ssh exited 255"})

    assert verdict == DurableCopyUnreachable(detail="ssh exited 255")


def test_an_unrecognized_response_is_unreachable_with_a_stated_reason() -> None:
    assert read_locate_response({}) == DurableCopyUnreachable(
        detail="probe returned no usable verdict"
    )


@pytest.mark.parametrize(
    "response",
    [
        {"kind": "Located", "paths": []},
        {"kind": "Located", "match_count": 1},
        {"kind": "Located", "match_count": "1", "paths": [_DURABLE]},
        {"kind": "Located", "match_count": 1, "paths": _DURABLE},
    ],
)
def test_a_malformed_located_verdict_is_unreachable(response: dict[str, object]) -> None:
    assert isinstance(read_locate_response(response), DurableCopyUnreachable)


def test_one_counted_match_with_no_path_is_unreachable_not_found() -> None:
    """An incoherent answer must not become a silent wait. Reading it as
    "not there" would park the Dataset forever behind a probe that is
    answering nonsense."""
    verdict = read_locate_response(_located(match_count=1, paths=[]))

    assert isinstance(verdict, DurableCopyUnreachable)


def test_non_string_entries_in_paths_are_dropped_rather_than_carried() -> None:
    verdict = read_locate_response({"kind": "Located", "match_count": 2, "paths": [_DURABLE, 7]})

    assert isinstance(verdict, DurableCopyAmbiguous)
    assert verdict.paths == (_DURABLE,)
    assert verdict.match_count == 2
