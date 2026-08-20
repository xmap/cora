"""Unit tests for `cora-capture-path://` locator minting and resolution.

Covers: minting refuses when no configured root matches (rather than
fabricating a tier segment); resolution passes through every scheme
except `cora-capture-path` unchanged (the manual POST route / MCP tool are
never touched by this module); resolution refuses on a malformed
locator, an absent vault row (the erasure case), and a filename that
disagrees with the vault's own current value (the one genuine
cross-check this module makes, alongside host and tier, which are now
the LOOKUP KEY rather than something re-verified after the fact); and
the mint/resolve round trip recovers
the exact real path, matching `_file_uri.py`'s expected `file://` form.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID

import pytest

from cora.data.adapters.capture_path_locator import (
    CAPTURE_PATH_SCHEME,
    active_scan_transport,
    mint_capture_path_locator,
    resolve_capture_path_locator,
)
from cora.run.aggregates.run import InMemoryCapturePathStore

pytestmark = pytest.mark.unit

_RUN_ID = UUID("01900000-0000-7000-8000-000000009001")
_PERSONAL_PATH_FRAGMENT = "Smith-1015116"
_OBSERVED_PATH = f"/local1/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan_005.h5"
_NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
_HOST = "tomdet"
_ROOT = "/local1/2BM"


async def _seeded_store(*, run_id: UUID = _RUN_ID, observed_path: str = _OBSERVED_PATH):
    store = InMemoryCapturePathStore()
    await store.upsert(
        run_id=run_id,
        observed_path=observed_path,
        observed_at=_NOW,
        created_at=_NOW,
        host=_HOST,
        root=_ROOT,
    )
    return store


def test_mint_produces_a_locator_carrying_no_personal_path_fragment() -> None:
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH,
        run_id=_RUN_ID,
        host="tomdet",
        root="/local1/2BM",
    )

    assert locator is not None
    assert _PERSONAL_PATH_FRAGMENT not in locator
    assert locator.startswith(f"{CAPTURE_PATH_SCHEME}://tomdet/local1/2BM/run-{_RUN_ID}/")
    assert locator.endswith("scan_005.h5")


def test_mint_embeds_the_whole_matched_root_verbatim_including_its_own_last_segment() -> None:
    """`observed_path == root` exactly: `Path("/local1/2BM").name` is
    `"2BM"`, not empty, so mint does NOT refuse this -- it mints a
    (degenerate but well-formed) locator whose `filename` segment is
    actually the root's own last path component.

    This is not merely a curiosity: it demonstrates that mint trusts
    the ENTIRE matched root as safe-to-embed-verbatim with no way to
    verify that from inside this function. If `roots` were ever
    misconfigured to a path that itself contains personal data (an
    experiment folder, say, rather than the facility-level tier), that
    personal data would flow straight into the locator's "safe" tier
    segment, silently defeating this module's whole purpose. Operators
    configuring `posix_checksum_roots` / `scan_probe_allowed_roots`
    must point them at the facility-level storage tier ONLY -- see
    `mint_capture_path_locator`'s own docstring, which states this
    requirement explicitly."""
    locator = mint_capture_path_locator(
        observed_path="/local1/2BM", run_id=_RUN_ID, host="tomdet", root="/local1/2BM"
    )

    assert locator == f"cora-capture-path://tomdet/local1/2BM/run-{_RUN_ID}/2BM"


async def test_mint_and_resolve_round_trip_a_filename_with_spaces() -> None:
    """`quote`/`unquote` must round-trip a filename that isn't already
    URL-safe; scan files are not guaranteed to avoid spaces."""
    observed_path = f"/local1/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan 005 (copy).h5"
    store = InMemoryCapturePathStore()
    await store.upsert(
        run_id=_RUN_ID,
        observed_path=observed_path,
        observed_at=_NOW,
        created_at=_NOW,
        host=_HOST,
        root=_ROOT,
    )
    locator = mint_capture_path_locator(
        observed_path=observed_path, run_id=_RUN_ID, host="tomdet", root="/local1/2BM"
    )
    assert locator is not None

    resolved = await resolve_capture_path_locator(locator, capture_path_store=store)

    assert resolved == "file://" + quote(observed_path)


async def test_resolve_passes_through_a_non_vault_scheme_unchanged() -> None:
    """The manual POST route / MCP tool send real `file://` (or
    `http://`, etc.) locators directly; this module must never alter
    them, since only `CaptureScanIngestor` mints `cora-capture-path://`."""
    store = await _seeded_store()
    real_locator = "file:///local/cora-scans/test_005.h5"

    resolved = await resolve_capture_path_locator(real_locator, capture_path_store=store)

    assert resolved == real_locator


async def test_resolve_recovers_the_real_path_as_a_file_uri() -> None:
    store = await _seeded_store()
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host="tomdet", root="/local1/2BM"
    )
    assert locator is not None

    resolved = await resolve_capture_path_locator(locator, capture_path_store=store)

    assert resolved == "file://" + _OBSERVED_PATH


async def test_resolve_refuses_when_the_vault_row_is_absent() -> None:
    """No row for this run_id: never observed, or a future erasure
    slice deleted it. Either way, resolution must refuse quietly rather
    than fall back to anything -- this IS the correct behavior for an
    erased run, not a placeholder for it."""
    store = InMemoryCapturePathStore()
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host="tomdet", root="/local1/2BM"
    )
    assert locator is not None

    resolved = await resolve_capture_path_locator(locator, capture_path_store=store)

    assert resolved is None


async def test_resolve_rejects_a_filename_that_drifted_since_mint_time() -> None:
    """The one genuine cross-check, demonstrated as real drift rather
    than a tampered string: the candidate query at mint time and the
    fresh `get(run_id)` at resolve time are TWO SEPARATE reads of the
    vault, and this proves a locator minted from the first read is
    rejected once the second read disagrees with it -- exactly the
    scenario the module docstring calls a genuine independent check,
    not a mismatch fabricated by editing the locator string itself."""
    store = InMemoryCapturePathStore()
    await store.upsert(
        run_id=_RUN_ID,
        observed_path=_OBSERVED_PATH,
        observed_at=_NOW,
        created_at=_NOW,
        host=_HOST,
        root=_ROOT,
    )
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host="tomdet", root="/local1/2BM"
    )
    assert locator is not None
    # The vault row for the SAME run_id is upserted again with a
    # DIFFERENT filename before resolve ever runs -- a real second
    # read that disagrees with the first, not a doctored locator.
    await store.upsert(
        run_id=_RUN_ID,
        observed_path=f"/local1/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan_006.h5",
        observed_at=_NOW,
        created_at=_NOW,
        # SAME location, so this genuinely overwrites the row the
        # locator was minted from. A different host/root would insert a
        # second row instead, leaving the original intact and testing
        # nothing.
        host=_HOST,
        root=_ROOT,
    )

    resolved = await resolve_capture_path_locator(locator, capture_path_store=store)

    # `resolve` returns None for six distinct reasons. Pin that THIS
    # None is the filename cross-check firing, by showing the row really
    # was replaced rather than the lookup simply missing it.
    stored = await store.get(_RUN_ID, host=_HOST, root=_ROOT)
    assert stored is not None
    assert stored.observed_path.endswith("scan_006.h5")
    assert resolved is None


async def test_two_locations_for_one_run_each_resolve_to_their_own_path() -> None:
    """The reason the vault is keyed by location at all. A Run's file
    observed on BOTH the acquisition tier and the archive tier is two
    rows, and each tier's locator resolves to that tier's real path.
    Under the old run_id-only key the second observation overwrote the
    first, and the first tier's already-minted locator resolved to the
    wrong bytes or to nothing at all."""
    archive_root = "/gdata/dm/2BM"
    archive_path = f"{archive_root}/2026-08/2026-08-{_PERSONAL_PATH_FRAGMENT}/data/scan_005.h5"
    store = InMemoryCapturePathStore()
    await store.upsert(
        run_id=_RUN_ID,
        observed_path=_OBSERVED_PATH,
        observed_at=_NOW,
        created_at=_NOW,
        host=_HOST,
        root=_ROOT,
    )
    await store.upsert(
        run_id=_RUN_ID,
        observed_path=archive_path,
        observed_at=_NOW,
        created_at=_NOW,
        host=_HOST,
        root=archive_root,
    )
    acquisition_locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host=_HOST, root=_ROOT
    )
    archive_locator = mint_capture_path_locator(
        observed_path=archive_path, run_id=_RUN_ID, host=_HOST, root=archive_root
    )
    assert acquisition_locator is not None
    assert archive_locator is not None
    assert acquisition_locator != archive_locator

    assert (
        await resolve_capture_path_locator(acquisition_locator, capture_path_store=store)
        == "file://" + _OBSERVED_PATH
    )
    assert (
        await resolve_capture_path_locator(archive_locator, capture_path_store=store)
        == "file://" + archive_path
    )


async def test_resolve_refuses_a_location_the_run_was_never_observed_on() -> None:
    """A locator naming the archive tier must NOT fall back to the
    acquisition-tier row when no archive row exists. Falling back would
    hand back bytes from a different copy than the one named, which is
    worse than refusing."""
    store = await _seeded_store()
    archive_locator = mint_capture_path_locator(
        observed_path="/gdata/dm/2BM/2026-08/exp/data/scan_005.h5",
        run_id=_RUN_ID,
        host=_HOST,
        root="/gdata/dm/2BM",
    )
    assert archive_locator is not None

    assert await resolve_capture_path_locator(archive_locator, capture_path_store=store) is None


async def test_resolve_refuses_a_locator_naming_a_different_host() -> None:
    """The host half of the (run_id, host, root) key, which nothing
    else exercises: every other test holds host constant, so deleting
    `AND host IS NOT DISTINCT FROM $2` from the lookup left the whole
    suite green. It matters because `active_scan_transport` flips host
    between the SSH host and localhost WITHOUT changing the root, so
    host is the only thing separating those two locations."""
    store = await _seeded_store()
    other_host_locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host="localhost", root=_ROOT
    )
    assert other_host_locator is not None

    resolved = await resolve_capture_path_locator(other_host_locator, capture_path_store=store)

    assert resolved is None
    # Positive control: the same store DOES resolve the right host, so
    # the refusal above is about the host and not a store that returns
    # None for everything.
    right_host_locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host=_HOST, root=_ROOT
    )
    assert right_host_locator is not None
    assert (
        await resolve_capture_path_locator(right_host_locator, capture_path_store=store)
        == "file://" + _OBSERVED_PATH
    )


async def test_resolve_refuses_a_legacy_row_whose_location_was_never_recorded() -> None:
    """Rows predating the location columns carry NULL host and root.
    `resolve` derives both from the locator and can never produce NULL,
    so such a row is unreachable by any locator. That is deliberate, and
    `_CANDIDATE_SQL` excludes those rows so the sweep never mints for
    them, but it is worth pinning: the empty-string default in the parse
    is load-bearing, and turning it into None would make every legacy
    row reachable from a bare locator."""
    store = InMemoryCapturePathStore()
    await store.upsert(
        run_id=_RUN_ID,
        observed_path=_OBSERVED_PATH,
        observed_at=_NOW,
        created_at=_NOW,
        host=None,
        root=None,
    )
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host=_HOST, root=_ROOT
    )
    assert locator is not None

    assert await resolve_capture_path_locator(locator, capture_path_store=store) is None


def test_mint_declines_when_the_row_recorded_no_location() -> None:
    """A NULL-location row produces no locator at all, rather than one
    built from a guessed tier."""
    assert (
        mint_capture_path_locator(
            observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host=None, root=None
        )
        is None
    )


async def test_resolve_rejects_a_locator_with_too_few_path_segments() -> None:
    """`len(segments) < 2`: a locator with no room for BOTH a run
    segment and a filename, distinct from the "has two segments but
    the first isn't run-prefixed" case below."""
    store = await _seeded_store()

    resolved = await resolve_capture_path_locator(
        f"{CAPTURE_PATH_SCHEME}://tomdet/onlyfile.h5", capture_path_store=store
    )

    assert resolved is None


async def test_resolve_rejects_a_locator_with_no_run_segment() -> None:
    """Two-plus path segments, but neither of the last two is
    `run-`-prefixed: the distinct branch from too-few-segments above."""
    store = await _seeded_store()

    resolved = await resolve_capture_path_locator(
        f"{CAPTURE_PATH_SCHEME}://tomdet/local1/2BM/scan_005.h5", capture_path_store=store
    )

    assert resolved is None


async def test_resolve_refuses_a_malformed_run_id() -> None:
    store = await _seeded_store()

    resolved = await resolve_capture_path_locator(
        f"{CAPTURE_PATH_SCHEME}://tomdet/local1/2BM/run-not-a-uuid/scan_005.h5",
        capture_path_store=store,
    )

    assert resolved is None


def test_active_scan_locator_context_uses_ssh_settings_when_remote_host_is_set() -> None:
    class _Settings:
        scan_probe_remote_host = "tomdet"
        scan_probe_allowed_roots = ("/local1/2BM",)
        posix_checksum_roots = ("/should/not/be/used",)

    class _Deps:
        settings = _Settings()

    host, roots = active_scan_transport(_Deps())  # type: ignore[arg-type]

    assert host == "tomdet"
    assert roots == ("/local1/2BM",)


def test_active_scan_locator_context_falls_back_to_local_settings() -> None:
    class _Settings:
        scan_probe_remote_host = None
        scan_probe_allowed_roots = ()
        posix_checksum_roots = ("/local/cora-scans",)

    class _Deps:
        settings = _Settings()

    host, roots = active_scan_transport(_Deps())  # type: ignore[arg-type]

    assert host == "localhost"
    assert roots == ("/local/cora-scans",)
