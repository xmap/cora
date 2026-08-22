"""Unit tests for `SshPosixChecksumComputer`'s response parsing.

Sibling of `test_ssh_data_exchange_scan_reader.py`. Transport safety is
covered in `test_ssh_probe.py`; these tests pin how a probe's JSON
verdict becomes the exact `ChecksumComputer` result shapes
`PosixChecksumAdapter.compute` produces locally.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from cora.data.adapters._ssh_probe import SshProbeConfig
from cora.data.adapters.ssh_posix_checksum_computer import SshPosixChecksumComputer
from cora.data.ports.checksum_computer import ComputedChecksum
from cora.data.ports.checksum_verifier import Unreachable

_CONFIG = SshProbeConfig(
    host="tomdet",
    remote_python="/venv/bin/python3",
    allowed_roots=("/local1/2BM",),
    connect_timeout_seconds=5.0,
    command_timeout_seconds=60.0,
)


@pytest.mark.unit
async def test_compute_sends_the_checksum_op_and_supply_id(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    supply_id = uuid4()

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        captured["request"] = request
        return {"kind": "Unreachable", "error_detail": "stub"}

    monkeypatch.setattr("cora.data.adapters.ssh_posix_checksum_computer.run_probe", _fake_run_probe)
    computer = SshPosixChecksumComputer(config=_CONFIG)
    await computer.compute(locator_uri="file:///local1/2BM/scan.h5", supply_id=supply_id)

    assert captured["request"]["op"] == "checksum"
    assert captured["request"]["supply_id"] == str(supply_id)


@pytest.mark.unit
async def test_compute_reconstructs_a_computed_checksum(monkeypatch: pytest.MonkeyPatch) -> None:
    response = {
        "kind": "ComputedChecksum",
        "algorithm": "sha256",
        "value": "9636033413" + "0" * 54,
        "byte_size": 24504057268,
        "mtime_ns": 1755509877000000000,
    }

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        return response

    monkeypatch.setattr("cora.data.adapters.ssh_posix_checksum_computer.run_probe", _fake_run_probe)
    computer = SshPosixChecksumComputer(config=_CONFIG)
    result = await computer.compute(locator_uri="file:///local1/2BM/scan.h5", supply_id=uuid4())

    assert isinstance(result, ComputedChecksum)
    assert result.algorithm == "sha256"
    assert result.byte_size == 24504057268


@pytest.mark.unit
async def test_compute_probe_error_fails_toward_unreachable_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        return {"kind": "ProbeError", "detail": "could not launch ssh: [Errno 2] No such file"}

    monkeypatch.setattr("cora.data.adapters.ssh_posix_checksum_computer.run_probe", _fake_run_probe)
    computer = SshPosixChecksumComputer(config=_CONFIG)
    result = await computer.compute(locator_uri="file:///local1/2BM/scan.h5", supply_id=uuid4())

    assert isinstance(result, Unreachable)
    assert "could not launch ssh" in result.error_detail


@pytest.mark.unit
async def test_compute_malformed_response_fails_toward_unreachable_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `kind: "ComputedChecksum"` response missing a required field (a
    probe-version skew) must resolve to a result, never raise a bare
    KeyError/ValueError past the port's never-raise contract."""

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        # Missing value/byte_size/mtime_ns.
        return {"kind": "ComputedChecksum", "algorithm": "sha256"}

    monkeypatch.setattr("cora.data.adapters.ssh_posix_checksum_computer.run_probe", _fake_run_probe)
    computer = SshPosixChecksumComputer(config=_CONFIG)
    result = await computer.compute(locator_uri="file:///local1/2BM/scan.h5", supply_id=uuid4())

    assert isinstance(result, Unreachable)
    assert "malformed probe response" in result.error_detail


@pytest.mark.unit
async def test_compute_unrecognized_response_shape_does_not_dump_the_whole_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response this adapter cannot recognize (a probe protocol
    change) used to fall back to `f"unexpected response: {response!r}"`,
    which relays every field of the probe dict -- including anything
    unrecognized carrying a path -- into this adapter's own log line.
    The fallback must be a fixed literal instead."""
    secret_fragment = "Smith-1015116"

    async def _fake_run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
        return {"kind": "SomeFutureKind", "path": f"/gdata/dm/2BM/2026-08-{secret_fragment}/x.h5"}

    monkeypatch.setattr("cora.data.adapters.ssh_posix_checksum_computer.run_probe", _fake_run_probe)
    computer = SshPosixChecksumComputer(config=_CONFIG)
    result = await computer.compute(locator_uri="file:///local1/2BM/scan.h5", supply_id=uuid4())

    assert isinstance(result, Unreachable)
    assert secret_fragment not in result.error_detail
