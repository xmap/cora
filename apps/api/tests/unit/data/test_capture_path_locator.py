"""Unit tests for `cora-capture-path://` locator minting and resolution.

Covers: minting refuses when no configured root matches (rather than
fabricating a tier segment); resolution passes through every scheme
except `cora-capture-path` unchanged (the manual POST route / MCP tool are
never touched by this module); resolution refuses on a malformed
locator, an absent vault row (the erasure case), and a filename that
disagrees with the vault's own current value (the one genuine
cross-check this module makes -- see the module docstring for why host
and tier are NOT re-verified); and the mint/resolve round trip recovers
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


async def _seeded_store(*, run_id: UUID = _RUN_ID, observed_path: str = _OBSERVED_PATH):
    store = InMemoryCapturePathStore()
    await store.upsert(
        run_id=run_id, observed_path=observed_path, observed_at=_NOW, created_at=_NOW
    )
    return store


def test_mint_produces_a_locator_carrying_no_personal_path_fragment() -> None:
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH,
        run_id=_RUN_ID,
        host="tomdet",
        roots=("/local1/2BM",),
    )

    assert locator is not None
    assert _PERSONAL_PATH_FRAGMENT not in locator
    assert locator.startswith(f"{CAPTURE_PATH_SCHEME}://tomdet/local1/2BM/run-{_RUN_ID}/")
    assert locator.endswith("scan_005.h5")


def test_mint_matches_the_second_root_when_the_first_does_not_apply() -> None:
    """The "both is fine" allowlist decision (2026-08-19): a path under
    the SECOND configured root must not be refused just because the
    first root in the tuple doesn't match it."""
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH,
        run_id=_RUN_ID,
        host="tomdet",
        roots=("/local2/2BM", "/local1/2BM"),
    )

    assert locator is not None
    assert "/local1/2BM/" in locator


def test_mint_refuses_a_path_outside_every_configured_root() -> None:
    """A misconfigured or drifted allowlist must not produce a locator
    with a fabricated tier segment; the caller treats this as SKIP."""
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH,
        run_id=_RUN_ID,
        host="tomdet",
        roots=("/somewhere/else",),
    )

    assert locator is None


def test_mint_does_not_treat_a_sibling_directory_as_under_the_root() -> None:
    """`/local1/2BM` must not prefix-match `/local1/2BMX/...`."""
    locator = mint_capture_path_locator(
        observed_path="/local1/2BMX/2026-08-Smith-1/scan.h5",
        run_id=_RUN_ID,
        host="tomdet",
        roots=("/local1/2BM",),
    )

    assert locator is None


def test_mint_refuses_every_path_when_roots_is_empty() -> None:
    """An unconfigured deployment (no roots at all) must SKIP every
    candidate, not treat an empty tuple as "anything matches"."""
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host="tomdet", roots=()
    )

    assert locator is None


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
        observed_path="/local1/2BM", run_id=_RUN_ID, host="tomdet", roots=("/local1/2BM",)
    )

    assert locator == f"cora-capture-path://tomdet/local1/2BM/run-{_RUN_ID}/2BM"


async def test_mint_and_resolve_round_trip_a_filename_with_spaces() -> None:
    """`quote`/`unquote` must round-trip a filename that isn't already
    URL-safe; scan files are not guaranteed to avoid spaces."""
    observed_path = f"/local1/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan 005 (copy).h5"
    store = InMemoryCapturePathStore()
    await store.upsert(
        run_id=_RUN_ID, observed_path=observed_path, observed_at=_NOW, created_at=_NOW
    )
    locator = mint_capture_path_locator(
        observed_path=observed_path, run_id=_RUN_ID, host="tomdet", roots=("/local1/2BM",)
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
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host="tomdet", roots=("/local1/2BM",)
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
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host="tomdet", roots=("/local1/2BM",)
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
        run_id=_RUN_ID, observed_path=_OBSERVED_PATH, observed_at=_NOW, created_at=_NOW
    )
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host="tomdet", roots=("/local1/2BM",)
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
    )

    resolved = await resolve_capture_path_locator(locator, capture_path_store=store)

    assert resolved is None


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
