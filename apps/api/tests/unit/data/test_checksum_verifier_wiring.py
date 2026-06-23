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


def _wired_verifiers(roots: tuple[str, ...]) -> dict[str, object]:
    deps = build_deps(ids=[_ID], now=_NOW)
    deps = replace(deps, settings=Settings(app_env="test", posix_checksum_roots=roots))
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
