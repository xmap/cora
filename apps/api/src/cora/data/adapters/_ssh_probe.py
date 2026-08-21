"""Shared SSH transport for the two remote scan-ingest adapters.

`SshDataExchangeScanReader` and `SshPosixChecksumComputer` both need the
same thing: run `cora.data._remote_scan_probe` on a host that holds bytes
CORA's own host cannot reach in time (see that module's docstring for the
measured reasoning), ship it a request over stdin, and read one JSON
verdict back over stdout. Splitting that mechanism across two copies is
how the two adapters would drift on the one property that actually
matters here -- how the untrusted locator reaches the far side -- so it
lives once, here, mirroring `_file_uri.py`'s reason for existing.

## The locator is untrusted; this is the module's whole reason to exist

`full_file_name` (the source of every locator this ever runs against)
comes from `2bmSP2:HDF1:FullFileName_RBV`, writable by anyone with
Channel Access. `run_probe` NEVER lets it reach a shell or an argv
element: the ssh argv is fixed at call time (host, a pinned interpreter
path, `-m`, the probe module name) and the request -- including the
locator -- travels as one JSON line over the child's stdin. `ssh
host cmd arg` would otherwise be re-parsed by the remote shell, turning a
crafted PV value into remote code execution on the detector host; stdin
is not re-parsed by anything.

Two more guards run before any process is ever spawned, both refusing
rather than probing:

- `_charset_ok`: the decoded path must be printable, control-character
  and NUL free. Cheap, and it means a malformed PV value never even
  reaches the network.
- `_prefix_allowed`: the raw (unresolved) path must start with one of the
  deployment's configured roots. This is NOT the authoritative
  confinement check -- it cannot be, since `..` and symlinks resolve on
  the REMOTE host's filesystem, which this process cannot see. The
  authoritative check is `resolve_confined_file_uri`, run inside
  `_remote_scan_probe.py` on the host that actually owns the path. This
  is only the early refusal that saves a network round trip on an
  obviously-wrong value.

## Never raises

Mirrors every port this feeds (`ScanReader.describe`, `ChecksumComputer.compute`):
a dead host, a timed-out probe, a malformed response, or a refused
locator all return a `{"kind": "ProbeError", ...}` dict, never an
exception. The two adapter classes translate that into the shape their
own port expects (`Unreadable` / `Unreachable`).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import unquote, urlparse

from cora.shared.path_segment import is_safe_path_segment
from cora.shared.storage_root import matched_storage_root

_PROBE_MODULE = "cora.data._remote_scan_probe"


@dataclass(frozen=True)
class SshProbeConfig:
    """Deployment-declared transport parameters for one remote host.

    `allowed_roots` are roots as valid ON `host`, never on CORA's own
    filesystem; see `Settings.scan_probe_allowed_roots`.
    """

    host: str
    remote_python: str
    allowed_roots: tuple[str, ...]
    connect_timeout_seconds: float
    command_timeout_seconds: float


def raw_path_from_file_uri(uri: str) -> str | None:
    """Decode a `file://` URI's path with NO filesystem resolution.

    Unlike `cora.data.adapters._file_uri.resolve_confined_file_uri`, this
    never calls `os.path.realpath`: that would resolve against THIS
    process's filesystem, which is the wrong host. Returns `None` for a
    non-`file` scheme or a non-local netloc, mirroring that module's own
    scheme rule.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return None
    raw_path = unquote(parsed.path)
    return raw_path or None


def _charset_ok(path: str) -> bool:
    """Printable, control-character and NUL free."""
    return path.isprintable() and "\x00" not in path


def _prefix_allowed(path: str, allowed_roots: tuple[str, ...]) -> bool:
    """Early, non-authoritative refusal; see the module docstring."""
    return any(path == root or path.startswith(root.rstrip("/") + "/") for root in allowed_roots)


def _refuse(reason: str) -> dict[str, Any]:
    # NEVER embeds the locator: this detail string is what
    # `SshDataExchangeScanReader.describe` / `SshPosixChecksumComputer.compute`
    # log verbatim on refusal (`reason=` / `error_detail=`), and the
    # locator is the same personal-data value
    # `run.aggregates.run.capture_path` vaults rather than logs.
    return {"kind": "ProbeError", "detail": f"refused before probing: {reason}"}


async def run_probe(request: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
    """Validate, then run one request against `config.host`; never raises.

    `request` must carry `locator_uri`; `allowed_roots` is filled in from
    `config` here (the caller never supplies it), so the SAME allowlist
    the client-side guard checked is the one the remote probe enforces.
    """
    locator_uri = request.get("locator_uri")
    if not isinstance(locator_uri, str):
        return _refuse("no locator_uri in request")
    raw_path = raw_path_from_file_uri(locator_uri)
    if raw_path is None:
        return _refuse("not a recognizable file:// URI")
    if not _charset_ok(raw_path):
        return _refuse("path contains non-printable or control characters")
    if not _prefix_allowed(raw_path, config.allowed_roots):
        return _refuse("path is outside the configured allowed roots")

    return await _invoke({**request, "allowed_roots": list(config.allowed_roots)}, config=config)


async def run_locate_probe(
    *,
    root: str,
    months: tuple[str, ...],
    directory_suffix: str,
    filename: str,
    subdirectory: str | None,
    config: SshProbeConfig,
) -> dict[str, Any]:
    """Run one `locate` request against `config.host`; never raises.

    The odd one out: `locate` carries no `locator_uri`, because its job
    is to find a path CORA cannot yet name, so `run_probe`'s
    locator-shaped guard does not apply and this validates the
    locate-shaped request instead. Both go through the same transport
    and both fill `allowed_roots` from `config` here rather than from
    the caller, so the allowlist the client checked is the one the
    remote enforces.

    Every segment is checked against the same `is_safe_path_segment`
    rule the remote applies. Checking on both sides is deliberate
    duplication, not redundancy: the values come from PVs writable by
    anyone with Channel Access, and the two processes are separately
    reachable. The remote also caps how many months one request may
    scan; the client does not duplicate that bound, since it is a
    resource limit on the side that pays for it.
    """
    if matched_storage_root(root, config.allowed_roots) is None:
        return _refuse("root is outside the configured allowed roots")
    if not months:
        return _refuse("no months to search")
    unsafe = [
        value for value in (*months, directory_suffix, filename) if not is_safe_path_segment(value)
    ]
    if unsafe or (subdirectory is not None and not is_safe_path_segment(subdirectory)):
        return _refuse("request carries a value that is not one safe path segment")

    payload: dict[str, Any] = {
        "op": "locate",
        "root": root,
        "months": list(months),
        "directory_suffix": directory_suffix,
        "filename": filename,
        "allowed_roots": list(config.allowed_roots),
    }
    if subdirectory is not None:
        payload["subdirectory"] = subdirectory
    return await _invoke(payload, config=config)


async def _invoke(payload: dict[str, Any], *, config: SshProbeConfig) -> dict[str, Any]:
    """Transport only: ssh out, one JSON line in, one JSON line back.

    Shared by both entry points so the timeout handling, the never-raise
    contract and the response parsing cannot drift apart between them.
    """
    # `max(1, ...)`: OpenSSH reads `ConnectTimeout=0` as "no timeout
    # configured here, use the default" -- silently removing the bound
    # for a sub-1s config value instead of enforcing a very short one.
    # `--` before `config.host`: operator-configured, never
    # attacker-reachable, but a host string starting with `-` would
    # otherwise be parsed by `ssh` as an option rather than a hostname.
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={max(1, int(config.connect_timeout_seconds))}",
        "--",
        config.host,
        config.remote_python,
        "-m",
        _PROBE_MODULE,
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        return {"kind": "ProbeError", "detail": f"could not launch ssh: {exc}"}

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(json.dumps(payload).encode("utf-8") + b"\n"),
            timeout=config.command_timeout_seconds,
        )
    except TimeoutError:
        process.kill()
        with contextlib.suppress(ProcessLookupError):
            await process.wait()
        return {
            "kind": "ProbeError",
            "detail": f"timed out after {config.command_timeout_seconds}s",
        }

    if process.returncode != 0:
        tail = stderr.decode(errors="replace").strip()[-300:]
        return {"kind": "ProbeError", "detail": f"ssh exited {process.returncode}: {tail}"}

    try:
        parsed: Any = json.loads(stdout.decode("utf-8").splitlines()[0])
    except (IndexError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"kind": "ProbeError", "detail": f"unparseable probe response: {exc}"}
    if not isinstance(parsed, dict):
        return {"kind": "ProbeError", "detail": "probe response is not a JSON object"}
    return cast("dict[str, Any]", parsed)


__all__ = ["SshProbeConfig", "raw_path_from_file_uri", "run_locate_probe", "run_probe"]
