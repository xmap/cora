"""Unit tests for the record_attestation verifier wiring (wire_data).

This pins the one place the ``posix_checksum_roots`` gating decision lives:
http/https are always wired; file:// is wired only when roots are configured.
Every other test hand-builds the verifier map, so this gating is verified
only here, through the public ``wire_data`` surface.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.data import wire_data
from cora.data.adapters import HttpRangeChecksumAdapter, PosixChecksumAdapter
from cora.infrastructure.config import Settings
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_ID = UUID("01900000-0000-7000-8000-0000000000c0")


def _wired_verifiers(
    roots: tuple[str, ...], max_walk_seconds: float | None = None
) -> dict[str, object]:
    deps = build_deps(ids=[_ID], now=_NOW)
    settings = (
        Settings(app_env="test", posix_checksum_roots=roots)
        if max_walk_seconds is None
        else Settings(
            app_env="test",
            posix_checksum_roots=roots,
            posix_checksum_max_walk_seconds=max_walk_seconds,
        )
    )
    deps = replace(deps, settings=settings)
    wire_data(deps)  # attaches deps.data.checksum_verifiers
    return dict(deps.data.checksum_verifiers)  # type: ignore[attr-defined]


@pytest.mark.unit
def test_http_and_https_always_wired_to_http_adapter() -> None:
    verifiers = _wired_verifiers(())
    assert isinstance(verifiers["http"], HttpRangeChecksumAdapter)
    assert isinstance(verifiers["https"], HttpRangeChecksumAdapter)
    # One shared instance serves both schemes.
    assert verifiers["http"] is verifiers["https"]


@pytest.mark.unit
def test_file_scheme_absent_when_no_roots_configured() -> None:
    assert "file" not in _wired_verifiers(())


@pytest.mark.unit
def test_file_scheme_wired_to_posix_adapter_when_roots_configured() -> None:
    verifiers = _wired_verifiers(("/gpfs/2bm/archive",))
    assert isinstance(verifiers["file"], PosixChecksumAdapter)


@pytest.mark.unit
def test_posix_adapter_takes_the_configured_walk_budget() -> None:
    """The bound has to be reachable from configuration.

    It was tunable at construction time and nothing passed it, so the
    60 s default governed every deployment. A 24.5 GB scan takes 82 s to
    hash on the 2-BM pilot before CORA's own chunked read is counted, so
    the first real ingest refused with `walk exceeded max_walk_seconds`
    and no deployment could raise it without editing code.
    """
    verifiers = _wired_verifiers(("/gpfs/2bm/archive",), 900.0)

    adapter = verifiers["file"]
    assert isinstance(adapter, PosixChecksumAdapter)
    assert adapter._max_walk_seconds == 900.0  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
def test_posix_adapter_keeps_the_default_walk_budget_when_unset() -> None:
    adapter = _wired_verifiers(("/gpfs/2bm/archive",))["file"]

    assert isinstance(adapter, PosixChecksumAdapter)
    assert adapter._max_walk_seconds == 60.0  # pyright: ignore[reportPrivateUsage]
