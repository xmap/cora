"""Unit tests for `wire._build_scan_ingest_pair`'s local-vs-SSH selection.

Untested before this gate review: nothing pinned that setting
`scan_probe_remote_host` actually selects the SSH pair with
`scan_probe_allowed_roots`, rather than silently falling back to the
local pair (which would ingest nothing real at 2-BM and no test would
notice, per the same reviewer finding as
`test_ssh_probe.py`'s argv-safety tests).
"""

from __future__ import annotations

# reportPrivateUsage: this file's whole point is pinning
# `_build_scan_ingest_pair`'s selection logic (untested before this gate
# review) and the SSH adapters' resolved `allowed_roots`, so reaching
# into wire.py's and the adapters' internals is deliberate, not a leak.
# pyright: reportPrivateUsage=false
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from cora.data.adapters.data_exchange_scan_reader import DataExchangeScanReader
from cora.data.adapters.posix_checksum import PosixChecksumAdapter
from cora.data.adapters.ssh_data_exchange_scan_reader import SshDataExchangeScanReader
from cora.data.adapters.ssh_posix_checksum_computer import SshPosixChecksumComputer
from cora.data.wire import _build_scan_ingest_pair
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


def _kernel(**settings_kwargs: object) -> Kernel:
    settings = Settings(**settings_kwargs)  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
def test_no_remote_host_selects_the_local_pair() -> None:
    deps = _kernel(posix_checksum_roots=("/local/cora-scans",))

    reader, computer = _build_scan_ingest_pair(deps)

    assert isinstance(reader, DataExchangeScanReader)
    assert isinstance(computer, PosixChecksumAdapter)


@pytest.mark.unit
def test_a_remote_host_selects_the_ssh_pair() -> None:
    deps = _kernel(
        scan_probe_remote_host="tomdet",
        scan_probe_remote_python="/venv/bin/python3",
        scan_probe_allowed_roots=("/local1/2BM",),
    )

    reader, computer = _build_scan_ingest_pair(deps)

    assert isinstance(reader, SshDataExchangeScanReader)
    assert isinstance(computer, SshPosixChecksumComputer)


@pytest.mark.unit
def test_the_ssh_pair_uses_scan_probe_allowed_roots_not_posix_checksum_roots() -> None:
    """A deployment could plausibly set BOTH settings (one for a local
    dev fallback, one for the real remote host); the SSH pair must use
    its OWN allowlist, never the local one -- the wrong pick here means
    a correctly-configured `scan_probe_allowed_roots` is silently
    ignored and every locator is refused (or, worse, a stale
    `posix_checksum_roots` value from local testing quietly widens what
    the remote probe accepts)."""
    deps = _kernel(
        scan_probe_remote_host="tomdet",
        scan_probe_remote_python="/venv/bin/python3",
        scan_probe_allowed_roots=("/local1/2BM",),
        posix_checksum_roots=("/completely/different/root",),
    )

    reader, computer = _build_scan_ingest_pair(deps)

    assert isinstance(reader, SshDataExchangeScanReader)
    assert isinstance(computer, SshPosixChecksumComputer)
    assert reader._config.allowed_roots == ("/local1/2BM",)
    assert computer._config.allowed_roots == ("/local1/2BM",)
