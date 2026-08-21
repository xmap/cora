"""The scan-ingest remote probe: runs on the host holding the bytes.

Slice 17's transport seam. A witnessed capture's file lives on the
detector host (e.g. `tomdet`), never on the CORA host: measured 2026-08-18,
pulling one ~24 GB file over the deployment's 1 GbE link takes roughly
twice the scan cadence, so the bytes must not move. This module is the
other half of that decision: it runs, via SSH, ON the host holding the
file, and does exactly what `DataExchangeScanReader` / `PosixChecksumAdapter`
already do locally -- unchanged, reused, not re-implemented. Only a JSON
verdict (a few hundred bytes) crosses the network.

This is a COMPOSITION, not a new layout or digest implementation: fusing
transport into a rewritten reader is exactly the mistake
`cora.data.ports.scan_reader`'s module docstring warns against ("layout"
and "transport" are independent axes). Here transport is handled entirely
by `cora.data.adapters._ssh_probe` (the client side) and this module (the
server side); the layout and digest code is the same class, imported
unchanged, and confinement is the same `resolve_confined_file_uri` both
local adapters already share -- one safety rule, enforced on whichever
host actually has the bytes.

## Protocol

One JSON object on stdin, one JSON object on stdout, newline-terminated.
No argv, no shell: the locator is untrusted (`full_file_name` comes from
`2bmSP2:HDF1:FullFileName_RBV`, writable by anyone with Channel Access),
so it must never be re-parsed by a shell. See
`cora.data.adapters._ssh_probe` for the client side of this contract and
why stdin, not argv, carries it.

Request:

    {"op": "describe", "locator_uri": "file://...", "allowed_roots": [...],
     "captured_at_source": "start_date"|"end_date"}
    {"op": "checksum", "locator_uri": "file://...", "allowed_roots": [...],
     "supply_id": "<uuid>"}

Response, one line, always valid JSON, always exit 0: a malformed request
or an uncaught exception is a `ProbeError` verdict, not a process failure,
so the client only ever has one thing to parse (never raise, mirroring
the never-raise contract both composed adapters already hold).

`allowed_roots` arrives FROM the request, not from a local default: this
process trusts the caller's confinement policy rather than defending
itself with one of its own. That is sound only because reaching this
process's stdin already requires SSH access as the deployment's own
service account (`scan_probe_remote_host`'s configured account); a
principal that could set the request's `allowed_roots` arbitrarily would
already need that access, at which point the confinement check is
defense against the WRONG kind of accident (a stale config, a copy-paste
error), not against an adversary who has not yet arrived here.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from cora.data.adapters.data_exchange_scan_reader import DataExchangeScanReader
from cora.data.adapters.posix_checksum import PosixChecksumAdapter
from cora.data.ports.checksum_computer import ComputedChecksum
from cora.data.ports.scan_reader import Description, Unreadable, Unrecognized
from cora.shared.path_segment import is_safe_path_segment
from cora.shared.storage_root import matched_storage_root

if TYPE_CHECKING:
    from cora.data.ports.checksum_verifier import Unreachable as ChecksumUnreachable

_OP_DESCRIBE = "describe"
_OP_CHECKSUM = "checksum"
_OP_LOCATE = "locate"

MAX_LOCATE_MONTHS = 4
"""Cap on the month directories one `locate` may scan. A caller sends
the experiment month plus its neighbours because beamtime can straddle
a month boundary; it has no reason to sweep the archive."""

MAX_LOCATE_MATCHES = 8
"""Cap on the paths one `locate` verdict carries. `match_count` is
reported UNCAPPED beside them, so a caller can tell 2 matches from 50
even though it only ever sees the first few: the caller refuses
anything but exactly one match, and a silently truncated list would let
a pathological request return a response sized by the directory rather
than by the answer."""


def _description_to_json(result: Description | Unreadable | Unrecognized) -> dict[str, Any]:
    if isinstance(result, Description):
        payload = asdict(result)
        payload["captured_at"] = result.captured_at.isoformat() if result.captured_at else None
        payload["kind"] = "Description"
        return payload
    if isinstance(result, Unreadable):
        return {"kind": "Unreadable", "reason": result.reason}
    return {"kind": "Unrecognized", "reason": result.reason}


def _checksum_to_json(result: ComputedChecksum | ChecksumUnreachable) -> dict[str, Any]:
    if isinstance(result, ComputedChecksum):
        payload = asdict(result)
        payload["kind"] = "ComputedChecksum"
        return payload
    return {"kind": "Unreachable", "error_detail": result.error_detail}


def _locate(request: dict[str, Any], *, allowed_roots: tuple[str, ...]) -> dict[str, Any]:
    """Find the durable copy of a file whose directory CORA cannot name.

    At 2-BM an experiment folder is `{yyyy-mm}-{PIsurname}-{GUP}`, and
    CORA deliberately holds no surname (`run_experiment_identity`
    carries proposal, ESAF and ESAF-DOI numbers and nothing else), so
    the durable copy has to be found from the parts CORA does hold. The
    request therefore names each path segment literally except the
    experiment directory, which it matches by suffix.

    No pattern is ever built from the request. Every segment is checked
    against `is_safe_path_segment` first, matching is `str.endswith` on
    entries this process itself enumerated, and the resolved match is
    re-confined afterwards so a symlink out of the tree is refused
    rather than followed. Deciding what a given match COUNT means is
    the caller's policy, not this process's: it reports what it found.
    """
    root = request.get("root")
    if not isinstance(root, str):
        return {"kind": "ProbeError", "detail": "malformed request: root"}
    if matched_storage_root(root, allowed_roots) is None:
        return {"kind": "ProbeError", "detail": "root is not under an allowed root"}

    segments = {name: request.get(name) for name in ("directory_suffix", "filename")}
    for name, value in segments.items():
        if not isinstance(value, str) or not is_safe_path_segment(value):
            return {"kind": "ProbeError", "detail": f"malformed request: {name}"}
    directory_suffix = str(segments["directory_suffix"])
    filename = str(segments["filename"])

    raw_months = request.get("months")
    if not isinstance(raw_months, list) or not raw_months:
        return {"kind": "ProbeError", "detail": "malformed request: months"}
    months = cast("list[Any]", raw_months)
    if len(months) > MAX_LOCATE_MONTHS or not all(
        isinstance(month, str) and is_safe_path_segment(month) for month in months
    ):
        return {"kind": "ProbeError", "detail": "malformed request: months"}

    subdirectory = request.get("subdirectory")
    if subdirectory is not None and (
        not isinstance(subdirectory, str) or not is_safe_path_segment(subdirectory)
    ):
        return {"kind": "ProbeError", "detail": "malformed request: subdirectory"}

    entries: list[Path] = []
    for month in months:
        try:
            entries.extend(entry for entry in (Path(root) / str(month)).iterdir() if entry.is_dir())
        except OSError:
            continue
    entries.sort()

    matches: list[str] = []
    for entry in entries:
        if not entry.name.endswith(directory_suffix):
            continue
        candidate = entry / subdirectory / filename if subdirectory else entry / filename
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_file() or matched_storage_root(str(resolved), allowed_roots) is None:
            continue
        matches.append(str(resolved))

    return {
        "kind": "Located",
        "paths": matches[:MAX_LOCATE_MATCHES],
        "match_count": len(matches),
    }


async def _handle(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("op")
    allowed_roots = tuple(request.get("allowed_roots") or ())
    if op == _OP_LOCATE:
        return _locate(request, allowed_roots=allowed_roots)

    locator_uri = request.get("locator_uri")
    if not isinstance(locator_uri, str):
        return {"kind": "ProbeError", "detail": "malformed request: locator_uri"}

    if op == _OP_DESCRIBE:
        captured_at_source = request.get("captured_at_source") or "start_date"
        reader = DataExchangeScanReader(
            allowed_roots=allowed_roots, captured_at_source=captured_at_source
        )
        return _description_to_json(await reader.describe(locator_uri=locator_uri))
    if op == _OP_CHECKSUM:
        raw_supply_id = request.get("supply_id")
        if not isinstance(raw_supply_id, str):
            return {"kind": "ProbeError", "detail": "malformed request: supply_id"}
        try:
            supply_id = UUID(raw_supply_id)
        except ValueError:
            return {"kind": "ProbeError", "detail": "malformed request: supply_id is not a UUID"}
        computer = PosixChecksumAdapter(allowed_roots=allowed_roots)
        return _checksum_to_json(
            await computer.compute(locator_uri=locator_uri, supply_id=supply_id)
        )
    return {"kind": "ProbeError", "detail": f"unknown op: {op!r}"}


async def _main() -> None:
    line = sys.stdin.readline()
    try:
        parsed: Any = json.loads(line)
        if not isinstance(parsed, dict):
            raise TypeError("request is not a JSON object")
        response = await _handle(cast("dict[str, Any]", parsed))
    except Exception as exc:
        response = {"kind": "ProbeError", "detail": f"{type(exc).__name__}: {exc}"}
    sys.stdout.write(json.dumps(response))
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
