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
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from cora.data.adapters.data_exchange_scan_reader import DataExchangeScanReader
from cora.data.adapters.posix_checksum import PosixChecksumAdapter
from cora.data.ports.checksum_computer import ComputedChecksum
from cora.data.ports.scan_reader import Description, Unreadable, Unrecognized

if TYPE_CHECKING:
    from cora.data.ports.checksum_verifier import Unreachable as ChecksumUnreachable

_OP_DESCRIBE = "describe"
_OP_CHECKSUM = "checksum"


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


async def _handle(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("op")
    locator_uri = request.get("locator_uri")
    if not isinstance(locator_uri, str):
        return {"kind": "ProbeError", "detail": "malformed request: locator_uri"}
    allowed_roots = tuple(request.get("allowed_roots") or ())

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
