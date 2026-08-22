"""`ScanReader` over SSH: read a Data Exchange file on a remote host.

Slice 17's transport adapter. Runs the SAME `DataExchangeScanReader` used
locally, unchanged, inside `cora.data._remote_scan_probe` on
`config.host`; see that module's docstring and `cora.data.adapters._ssh_probe`
for the transport-safety reasoning (why stdin, not argv; why the locator
is checked twice, once here and once on the far side).

`captured_at_source` is threaded through exactly like the local adapter's
own constructor argument: which of the layout's timestamps to believe is
a deployment declaration, not a network concern, and the remote probe
must construct the same reader the local adapter would have, or a
deployment whose declared source is `end_date` would silently get
`start_date` back from every remote read. Validated at CONSTRUCTION time
here too (by constructing a throwaway local `DataExchangeScanReader`
solely to reuse its closed-vocabulary check, rather than a second copy
of that vocabulary): an unrecognized value would otherwise fail only on
the far side of a network round trip, once per tick, forever.

`kind = "SshDataExchange"`, distinct from the local `DataExchangeScanReader.kind
= "DataExchange"`, so `AcquisitionEvidence.reader_kind` records not just
the layout but that this reading crossed a network -- forensic
provenance a future NXtomo-over-SSH reader would also want.

Never logs `locator_uri`: it is the same personal-data value
`run.aggregates.run.capture_path` vaults rather than logs (2-BM's
directory layout embeds a surname and proposal number), and this
adapter has no more right to it in a log line than that module does.
"""

from __future__ import annotations

from datetime import datetime

from cora.data.adapters._ssh_probe import SshProbeConfig, run_probe
from cora.data.adapters.data_exchange_scan_reader import DataExchangeScanReader
from cora.data.ports.scan_reader import (
    Description,
    ScanReadResult,
    Unreadable,
    Unrecognized,
)
from cora.infrastructure.logging import get_logger

_log = get_logger(__name__)


class SshDataExchangeScanReader:
    """`ScanReader` that reads a Data Exchange file on a remote host."""

    kind = "SshDataExchange"

    def __init__(self, *, config: SshProbeConfig, captured_at_source: str = "start_date") -> None:
        # Raises ValueError on an unrecognized source, reusing
        # DataExchangeScanReader's own check; see module docstring.
        DataExchangeScanReader(allowed_roots=(), captured_at_source=captured_at_source)
        self._config = config
        self._captured_at_source = captured_at_source

    async def describe(self, *, locator_uri: str) -> ScanReadResult:
        response = await run_probe(
            {
                "op": "describe",
                "locator_uri": locator_uri,
                "captured_at_source": self._captured_at_source,
            },
            config=self._config,
        )
        result = _response_to_result(response)
        if isinstance(result, Unreadable):
            _log.warning(
                "ssh_data_exchange_scan_reader.read_failed",
                host=self._config.host,
                reason=result.reason,
            )
        return result


def _response_to_result(response: dict[str, object]) -> ScanReadResult:
    kind = response.get("kind")
    if kind == "Description":
        try:
            return _description_from_response(response)
        except (KeyError, TypeError, ValueError) as exc:
            # A probe-version skew (a field renamed or dropped on one
            # side but not the other) must read as an ordinary
            # Unreadable, not a 500: the never-raise contract this port
            # promises does not carve out "except for a malformed
            # response from a trusted host."
            return Unreadable(reason=f"malformed probe response: {exc}")
    if kind == "Unrecognized":
        return Unrecognized(reason=str(response.get("reason", "unrecognized")))
    # "Unreadable", "ProbeError", or any response this adapter cannot
    # parse (a probe protocol change on one side but not the other):
    # fail toward Unreadable rather than raise, matching the port's
    # never-raise contract. The fallback is a fixed literal, never
    # `{response!r}`: dumping the whole probe dict would relay
    # whatever an unrecognized field holds verbatim into this
    # adapter's own log line.
    reason = response.get("reason") or response.get("detail") or "unexpected probe response"
    return Unreadable(reason=str(reason))


def _description_from_response(response: dict[str, object]) -> Description:
    return Description(
        media_type=str(response["media_type"]),
        structurally_complete=bool(response["structurally_complete"]),
        projection_count=int(response["projection_count"]),  # type: ignore[arg-type]
        flat_count=int(response["flat_count"]),  # type: ignore[arg-type]
        dark_count=int(response["dark_count"]),  # type: ignore[arg-type]
        invalid_count=int(response["invalid_count"]),  # type: ignore[arg-type]
        commanded_projection_count=_optional_int(response.get("commanded_projection_count")),
        commanded_flat_count=_optional_int(response.get("commanded_flat_count")),
        commanded_dark_count=_optional_int(response.get("commanded_dark_count")),
        dropped_frame_count=_optional_int(response.get("dropped_frame_count")),
        projection_angles_deg=_optional_tuple(response.get("projection_angles_deg")),
        flat_angles_deg=_optional_tuple(response.get("flat_angles_deg")),
        dark_angles_deg=_optional_tuple(response.get("dark_angles_deg")),
        captured_at=_parse_iso(response.get("captured_at")),
        captured_at_raw=_optional_str(response.get("captured_at_raw")),
        captured_at_source=str(response.get("captured_at_source", "start_date")),
        byte_size=int(response["byte_size"]),  # type: ignore[arg-type]
        mtime_ns=int(response["mtime_ns"]),  # type: ignore[arg-type]
    )


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None  # type: ignore[arg-type]


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_tuple(value: object) -> tuple[float, ...] | None:
    if not isinstance(value, list):
        return None
    return tuple(float(item) for item in value)  # type: ignore[arg-type]


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


__all__ = ["SshDataExchangeScanReader"]
