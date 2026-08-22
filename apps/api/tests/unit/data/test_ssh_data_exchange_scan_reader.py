"""Unit tests for `SshDataExchangeScanReader`'s response parsing.

The transport itself (`run_probe`) is tested in `test_ssh_probe.py`; these
tests pin the adapter's own contract -- what it sends, and how it turns a
probe's JSON verdict back into the exact `ScanReader` result shapes the
local `DataExchangeScanReader` produces, field for field.
"""

from __future__ import annotations

from typing import Any

import pytest

from cora.data.adapters._ssh_probe import SshProbeConfig
from cora.data.adapters.ssh_data_exchange_scan_reader import SshDataExchangeScanReader
from cora.data.ports.scan_reader import Description, Unreadable, Unrecognized

_CONFIG = SshProbeConfig(
    host="tomdet",
    remote_python="/venv/bin/python3",
    allowed_roots=("/local1/2BM",),
    connect_timeout_seconds=5.0,
    command_timeout_seconds=30.0,
    max_walk_seconds=60.0,
)


@pytest.mark.unit
async def test_describe_sends_the_configured_captured_at_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        captured["request"] = request
        return {"kind": "Unrecognized", "reason": "stub"}

    monkeypatch.setattr(
        "cora.data.adapters.ssh_data_exchange_scan_reader.run_probe", _fake_run_probe
    )
    reader = SshDataExchangeScanReader(config=_CONFIG, captured_at_source="end_date")
    await reader.describe(locator_uri="file:///local1/2BM/scan.h5")

    assert captured["request"]["op"] == "describe"
    assert captured["request"]["captured_at_source"] == "end_date"


@pytest.mark.unit
async def test_describe_reconstructs_a_full_description(monkeypatch: pytest.MonkeyPatch) -> None:
    response = {
        "kind": "Description",
        "media_type": "application/x-hdf5",
        "structurally_complete": True,
        "projection_count": 1501,
        "flat_count": 20,
        "dark_count": 20,
        "invalid_count": 0,
        "commanded_projection_count": 1501,
        "commanded_flat_count": 20,
        "commanded_dark_count": 20,
        "dropped_frame_count": 0,
        "projection_angles_deg": [0.0, 0.12, 180.0],
        "flat_angles_deg": None,
        "dark_angles_deg": None,
        "captured_at": "2026-08-18T06:21:17-05:00",
        "captured_at_raw": "2026-08-18T06:21:17-0500",
        "captured_at_source": "end_date",
        "byte_size": 24504057268,
        "mtime_ns": 1755509877000000000,
    }

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        return response

    monkeypatch.setattr(
        "cora.data.adapters.ssh_data_exchange_scan_reader.run_probe", _fake_run_probe
    )
    reader = SshDataExchangeScanReader(config=_CONFIG)
    result = await reader.describe(locator_uri="file:///local1/2BM/scan.h5")

    assert isinstance(result, Description)
    assert result.projection_count == 1501
    assert result.projection_angles_deg == (0.0, 0.12, 180.0)
    assert result.flat_angles_deg is None
    assert result.captured_at is not None
    assert result.captured_at.isoformat() == "2026-08-18T06:21:17-05:00"
    assert result.captured_at_source == "end_date"
    assert result.byte_size == 24504057268


@pytest.mark.unit
async def test_describe_unrecognized_response_maps_to_unrecognized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        return {"kind": "Unrecognized", "reason": "no /exchange/data dataset"}

    monkeypatch.setattr(
        "cora.data.adapters.ssh_data_exchange_scan_reader.run_probe", _fake_run_probe
    )
    reader = SshDataExchangeScanReader(config=_CONFIG)
    result = await reader.describe(locator_uri="file:///local1/2BM/scan.h5")

    assert isinstance(result, Unrecognized)
    assert result.reason == "no /exchange/data dataset"


@pytest.mark.unit
async def test_describe_probe_error_fails_toward_unreadable_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead host, a timeout, or a protocol mismatch must never raise
    past this adapter -- `ScanReader.describe`'s never-raise contract."""

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        return {"kind": "ProbeError", "detail": "timed out after 60.0s"}

    monkeypatch.setattr(
        "cora.data.adapters.ssh_data_exchange_scan_reader.run_probe", _fake_run_probe
    )
    reader = SshDataExchangeScanReader(config=_CONFIG)
    result = await reader.describe(locator_uri="file:///local1/2BM/scan.h5")

    assert isinstance(result, Unreadable)
    assert "timed out" in result.reason


@pytest.mark.unit
async def test_describe_malformed_description_fails_toward_unreadable_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `kind: "Description"` response missing a required field (a
    probe-version skew, the two sides drifting) must still resolve to a
    result, never raise a bare KeyError/ValueError past the port's
    never-raise contract."""

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        # Missing every other required field.
        return {"kind": "Description", "media_type": "application/x-hdf5"}

    monkeypatch.setattr(
        "cora.data.adapters.ssh_data_exchange_scan_reader.run_probe", _fake_run_probe
    )
    reader = SshDataExchangeScanReader(config=_CONFIG)
    result = await reader.describe(locator_uri="file:///local1/2BM/scan.h5")

    assert isinstance(result, Unreadable)
    assert "malformed probe response" in result.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "captured_at",
    [None, "not-a-timestamp", 1755509877],
    ids=["absent", "unparseable", "wrong-type"],
)
async def test_describe_leaves_captured_at_none_when_the_probe_cannot_date_the_scan(
    monkeypatch: pytest.MonkeyPatch, captured_at: object
) -> None:
    """2-BM writes `start_date` / `end_date` as free-form strings, so a
    scan aborted mid-write, an older tomoscan, or a probe-version skew
    can all yield something undateable. That must degrade to a null
    timestamp the ingest handler's own policy then refuses, never a
    `ValueError` escaping `describe`'s never-raise contract."""
    response = {
        "kind": "Description",
        "media_type": "application/x-hdf5",
        "structurally_complete": True,
        "projection_count": 1501,
        "flat_count": 20,
        "dark_count": 20,
        "invalid_count": 0,
        "commanded_projection_count": 1501,
        "commanded_flat_count": 20,
        "commanded_dark_count": 20,
        "dropped_frame_count": 0,
        "projection_angles_deg": [0.0, 180.0],
        "flat_angles_deg": None,
        "dark_angles_deg": None,
        "captured_at": captured_at,
        "captured_at_raw": None,
        "captured_at_source": "start_date",
        "byte_size": 24504057268,
        "mtime_ns": 1755509877000000000,
    }

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        return response

    monkeypatch.setattr(
        "cora.data.adapters.ssh_data_exchange_scan_reader.run_probe", _fake_run_probe
    )
    reader = SshDataExchangeScanReader(config=_CONFIG)
    result = await reader.describe(locator_uri="file:///local1/2BM/scan.h5")

    assert isinstance(result, Description)
    assert result.captured_at is None


@pytest.mark.unit
async def test_describe_unrecognized_response_shape_does_not_dump_the_whole_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mirrors the checksum computer's identical fix: a response this
    adapter cannot recognize must never fall back to dumping the whole
    probe dict, which could relay a path through an unrecognized field."""
    secret_fragment = "Smith-1015116"

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        return {"kind": "SomeFutureKind", "path": f"/gdata/dm/2BM/2026-08-{secret_fragment}/x.h5"}

    monkeypatch.setattr(
        "cora.data.adapters.ssh_data_exchange_scan_reader.run_probe", _fake_run_probe
    )
    reader = SshDataExchangeScanReader(config=_CONFIG)
    result = await reader.describe(locator_uri="file:///local1/2BM/scan.h5")

    assert isinstance(result, Unreadable)
    assert secret_fragment not in result.reason


@pytest.mark.unit
def test_constructor_rejects_a_captured_at_source_the_layout_does_not_offer() -> None:
    """Fail at construction time, not on the first remote round trip;
    reuses `DataExchangeScanReader`'s own closed-vocabulary check."""
    with pytest.raises(ValueError, match="captured_at_source"):
        SshDataExchangeScanReader(config=_CONFIG, captured_at_source="not_a_real_source")
