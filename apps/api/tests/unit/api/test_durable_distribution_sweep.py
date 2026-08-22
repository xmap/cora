"""Unit: the durable-copy candidate's derived values.

The SQL itself is exercised against real Postgres in
`tests/integration/test_durable_distribution_sweep_postgres.py`; a fake
lookup here could only agree with itself. What this file covers is the
part that is pure logic and therefore genuinely testable in isolation:
turning an acquisition-tier path into the months and the filename the
remote `locate` op will search on.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.api._durable_distribution_sweep import (  # pyright: ignore[reportPrivateUsage]
    DurableDistributionCandidate,
    DurableDistributionCursor,
    NeverDurableDistributionCandidateLookup,
    months_to_search,
)

pytestmark = pytest.mark.unit

_ACQUISITION_ROOT = "/local1/2BM"
_NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)


def _candidate(
    *,
    observed_path: str = "/local1/2BM/2026-08-Haridy-1015116/scan_005.h5",
    proposal_number: str = "1015116",
) -> DurableDistributionCandidate:
    return DurableDistributionCandidate(
        dataset_id=uuid4(),
        created_at=_NOW,
        run_id=uuid4(),
        capture_code="2bmb-tomoscan",
        proposal_number=proposal_number,
        observed_path=observed_path,
        acquisition_root=_ACQUISITION_ROOT,
    )


def test_months_to_search_returns_the_experiment_month_and_both_neighbours() -> None:
    months = months_to_search("/local1/2BM/2026-08-Haridy-1015116/scan_005.h5", _ACQUISITION_ROOT)

    assert months == ("2026-08", "2026-07", "2026-09")


def test_months_to_search_crosses_a_year_boundary_in_both_directions() -> None:
    """January's neighbour is the previous December and December's is
    the next January. Arithmetic on a month index rather than on the
    month number, which would produce `2026-00` and `2026-13`."""
    assert months_to_search("/local1/2BM/2026-01-X-1/f.h5", _ACQUISITION_ROOT) == (
        "2026-01",
        "2025-12",
        "2026-02",
    )
    assert months_to_search("/local1/2BM/2026-12-X-1/f.h5", _ACQUISITION_ROOT) == (
        "2026-12",
        "2026-11",
        "2027-01",
    )


def test_months_to_search_reads_the_folder_below_the_root_not_the_first_folder() -> None:
    """The month comes from the EXPERIMENT folder, which is the segment
    directly under the configured root. Reading the path's first
    segment instead would find `local1` and return nothing."""
    months = months_to_search(
        "/local1/2BM/2026-08-Haridy-1015116/subdir/scan_005.h5", _ACQUISITION_ROOT
    )

    assert months[0] == "2026-08"


def test_months_to_search_tolerates_a_root_written_with_a_trailing_slash() -> None:
    months = months_to_search("/local1/2BM/2026-08-X-1/f.h5", "/local1/2BM/")

    assert months[0] == "2026-08"


@pytest.mark.parametrize(
    "observed_path",
    [
        "/local1/2BM/Haridy-2021-03/scan.h5",
        "/local1/2BM/no-month-here/scan.h5",
        "/local1/2BM/scan_005.h5",
        "/somewhere/else/2026-08-X-1/scan.h5",
    ],
)
def test_months_to_search_declines_rather_than_widening(observed_path: str) -> None:
    """An unparseable folder yields no months, which the caller treats
    as do-not-search. The pre-2025-07 folders in the real archive are
    named surname-first with no proposal number at all, so searching
    them could only ever return a wrong answer more expensively. The
    last case is a path under a different root entirely.
    """
    assert months_to_search(observed_path, _ACQUISITION_ROOT) == ()


def test_filename_is_the_last_segment_and_carries_no_directory() -> None:
    candidate = _candidate()

    assert candidate.filename == "scan_005.h5"
    assert "Haridy" not in candidate.filename


def test_directory_suffix_keeps_the_leading_hyphen() -> None:
    """Without it, proposal `1015116` would also match an experiment
    folder ending `11015116`, which is a different experiment."""
    assert _candidate().directory_suffix == "-1015116"


def test_directory_suffix_for_internal_beamtime_is_the_bare_zero() -> None:
    """Internal beamtime carries no proposal and DMagic names the folder
    `...-0`. Measured on the real archive, several such folders coexist
    in one month, so this suffix is expected to match more than once and
    the caller refuses rather than guessing."""
    assert _candidate(proposal_number="0").directory_suffix == "-0"


async def test_the_no_pool_lookup_never_offers_a_candidate() -> None:
    lookup = NeverDurableDistributionCandidateLookup()

    assert await lookup.next_candidate() is None
    cursor = DurableDistributionCursor(created_at=_NOW, dataset_id=uuid4())
    assert await lookup.next_candidate(after=cursor) is None
