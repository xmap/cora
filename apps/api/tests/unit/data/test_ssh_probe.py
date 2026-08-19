"""Unit tests for the SSH transport safety guards in `_ssh_probe.py`.

The locator this transport ever ships is untrusted (`full_file_name`
comes from a PV anyone with Channel Access can set), so the properties
these tests pin are exactly the ones the module docstring calls the
whole reason it exists: the locator never reaches argv, and an
obviously-wrong path never even starts a process.
"""

from __future__ import annotations

from typing import Any

import pytest

from cora.data.adapters._ssh_probe import (
    SshProbeConfig,
    raw_path_from_file_uri,
    run_probe,
)

_CONFIG = SshProbeConfig(
    host="tomdet",
    remote_python="/path/to/venv/bin/python3",
    allowed_roots=("/local1/2BM",),
    connect_timeout_seconds=5.0,
    command_timeout_seconds=5.0,
)

_PERSONAL_PATH_FRAGMENT = "Smith-1015116"


class _NeverCalledExec:
    """Fails the test if `asyncio.create_subprocess_exec` is ever invoked."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("create_subprocess_exec must not be called for a refused locator")


@pytest.mark.unit
def test_raw_path_from_file_uri_decodes_a_plain_local_path() -> None:
    assert raw_path_from_file_uri("file:///local1/2BM/scan.h5") == "/local1/2BM/scan.h5"


@pytest.mark.unit
def test_raw_path_from_file_uri_rejects_a_remote_netloc() -> None:
    """A `file://host/path` URI names a DIFFERENT remote host than the one
    this transport is configured for; refuse rather than guess which."""
    assert raw_path_from_file_uri("file://otherhost/local1/2BM/scan.h5") is None


@pytest.mark.unit
def test_raw_path_from_file_uri_rejects_a_non_file_scheme() -> None:
    assert raw_path_from_file_uri("http://tomdet/scan.h5") is None


@pytest.mark.unit
def test_raw_path_from_file_uri_does_not_resolve_the_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole reason this helper exists rather than reusing
    `resolve_confined_file_uri`: realpath must NEVER run on this host,
    because `..` or a symlink resolves against the WRONG filesystem."""
    import os

    def _boom(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("realpath must not run on the calling host")

    monkeypatch.setattr(os.path, "realpath", _boom)
    assert raw_path_from_file_uri("file:///local1/2BM/../etc/passwd") == "/local1/2BM/../etc/passwd"


@pytest.mark.unit
async def test_run_probe_refuses_a_path_outside_allowed_roots_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("asyncio.create_subprocess_exec", _NeverCalledExec())
    response = await run_probe(
        {"op": "describe", "locator_uri": "file:///etc/passwd"}, config=_CONFIG
    )
    assert response["kind"] == "ProbeError"
    assert "outside the configured allowed roots" in response["detail"]


@pytest.mark.unit
async def test_run_probe_refusal_detail_never_carries_the_locator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal `detail` is logged verbatim by both adapters
    (`reason=` / `error_detail=`); it must never carry the locator, the
    same personal-data value the PII vault refuses to log."""
    monkeypatch.setattr("asyncio.create_subprocess_exec", _NeverCalledExec())
    response = await run_probe(
        {"op": "describe", "locator_uri": f"file:///other-root/{_PERSONAL_PATH_FRAGMENT}/x.h5"},
        config=_CONFIG,
    )
    assert response["kind"] == "ProbeError"
    assert _PERSONAL_PATH_FRAGMENT not in response["detail"]


@pytest.mark.unit
async def test_run_probe_refuses_a_sibling_directory_sharing_a_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/local1/2BM-evil` starts with the string `/local1/2BM` but is a
    different directory; the prefix check must be segment-aware."""
    monkeypatch.setattr("asyncio.create_subprocess_exec", _NeverCalledExec())
    response = await run_probe(
        {"op": "describe", "locator_uri": "file:///local1/2BM-evil/scan.h5"}, config=_CONFIG
    )
    assert response["kind"] == "ProbeError"
    assert "outside the configured allowed roots" in response["detail"]


@pytest.mark.unit
async def test_run_probe_refuses_a_percent_encoded_control_character(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raw `\\n`/`\\r`/`\\t` in a URL is stripped by `urlparse` itself
    before this code ever sees it (a CPython URL-smuggling hardening
    fix), so the realistic attack surface `_charset_ok` guards is a
    control character hidden behind percent-encoding, decoded only
    after `urlparse` has already run: `%01` -> SOH."""
    monkeypatch.setattr("asyncio.create_subprocess_exec", _NeverCalledExec())
    response = await run_probe(
        {"op": "describe", "locator_uri": "file:///local1/2BM/sc%01an.h5"}, config=_CONFIG
    )
    assert response["kind"] == "ProbeError"
    assert "non-printable or control characters" in response["detail"]


@pytest.mark.unit
async def test_run_probe_refuses_a_non_file_uri_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("asyncio.create_subprocess_exec", _NeverCalledExec())
    response = await run_probe(
        {"op": "describe", "locator_uri": "http://tomdet/local1/2BM/scan.h5"}, config=_CONFIG
    )
    assert response["kind"] == "ProbeError"
    assert "not a recognizable file" in response["detail"]


class _CapturingProcess:
    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.returncode = 0

    async def communicate(self, stdin_data: bytes) -> tuple[bytes, bytes]:
        self.stdin_data = stdin_data
        return b'{"kind": "ProbeError", "detail": "stub"}\n', b""

    def kill(self) -> None:  # pragma: no cover - not exercised on the happy path
        pass

    async def wait(self) -> None:  # pragma: no cover
        pass


@pytest.mark.unit
async def test_run_probe_never_puts_the_locator_in_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """The locator travels over stdin, never argv: `ssh host cmd arg`
    would otherwise be re-parsed by the remote shell, and this locator
    is attacker-reachable via Channel Access."""
    captured: dict[str, Any] = {}

    async def _fake_exec(*args: str, **kwargs: Any) -> _CapturingProcess:
        captured["argv"] = list(args)
        process = _CapturingProcess(list(args))
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    locator = "file:///local1/2BM/2026-08-DeCarlo/scan_005.h5"
    await run_probe({"op": "describe", "locator_uri": locator}, config=_CONFIG)

    argv = captured["argv"]
    assert "/local1/2BM/2026-08-DeCarlo/scan_005.h5" not in argv
    for element in argv:
        assert "scan_005" not in element
    # The argv is entirely fixed: host, interpreter, and the probe
    # module name, never anything derived from the request.
    assert argv == [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "--",
        "tomdet",
        "/path/to/venv/bin/python3",
        "-m",
        "cora.data._remote_scan_probe",
    ]


@pytest.mark.unit
async def test_run_probe_floors_a_sub_second_connect_timeout_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ConnectTimeout=0` means "no timeout configured" to OpenSSH, not
    "immediate" -- a sub-1s config value must not silently remove the
    bound entirely."""
    captured: dict[str, Any] = {}

    async def _fake_exec(*args: str, **kwargs: Any) -> _CapturingProcess:
        captured["argv"] = list(args)
        return _CapturingProcess(list(args))

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    config = SshProbeConfig(
        host="tomdet",
        remote_python="/path/to/python3",
        allowed_roots=("/local1/2BM",),
        connect_timeout_seconds=0.2,
        command_timeout_seconds=5.0,
    )
    await run_probe({"op": "describe", "locator_uri": "file:///local1/2BM/scan.h5"}, config=config)

    assert "ConnectTimeout=1" in captured["argv"]
    assert "ConnectTimeout=0" not in captured["argv"]


@pytest.mark.unit
async def test_run_probe_ships_the_locator_over_stdin_as_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_exec(*args: str, **kwargs: Any) -> _CapturingProcess:
        process = _CapturingProcess(list(args))

        async def communicate(stdin_data: bytes) -> tuple[bytes, bytes]:
            captured["stdin"] = stdin_data
            return b'{"kind": "ProbeError", "detail": "stub"}\n', b""

        process.communicate = communicate  # type: ignore[method-assign]
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    locator = "file:///local1/2BM/2026-08-DeCarlo/scan_005.h5"
    await run_probe({"op": "describe", "locator_uri": locator}, config=_CONFIG)

    import json

    sent = json.loads(captured["stdin"])
    assert sent["locator_uri"] == locator
    assert sent["allowed_roots"] == ["/local1/2BM"]


@pytest.mark.unit
async def test_run_probe_times_out_and_kills_the_process(monkeypatch: pytest.MonkeyPatch) -> None:
    killed = {"called": False}

    class _HangingProcess:
        returncode = None

        async def communicate(self, stdin_data: bytes) -> tuple[bytes, bytes]:
            import asyncio

            await asyncio.sleep(10)
            return b"", b""

        def kill(self) -> None:
            killed["called"] = True

        async def wait(self) -> None:
            pass

    async def _fake_exec(*args: Any, **kwargs: Any) -> _HangingProcess:
        return _HangingProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    config = SshProbeConfig(
        host="tomdet",
        remote_python="/path/to/python3",
        allowed_roots=("/local1/2BM",),
        connect_timeout_seconds=5.0,
        command_timeout_seconds=0.05,
    )
    response = await run_probe(
        {"op": "describe", "locator_uri": "file:///local1/2BM/scan.h5"}, config=config
    )
    assert response["kind"] == "ProbeError"
    assert "timed out" in response["detail"]
    assert killed["called"] is True
