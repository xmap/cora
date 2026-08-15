"""Preflight read: report every configured `capture_watch_pvs` PV against
the live control system, before the recording switch flips.

`python -m cora.api.capture_watch_preflight` reads every PV named under
`Settings.capture_watch_pvs` exactly once and reports, per role: whether it
connects, what `Measurement.kind` CORA's `ControlPort` sees it as, the raw
decoded value, and whether CORA's own decoder for that role accepts it. Run
it once the host is reachable and before `RUN_WITNESS_RECORDING_ENABLED` is
set, and again after any `CAPTURE_WATCH_PVS` / `CAPTURE_STATUS_PHASES` edit.

## Why this exists

Three defects have now shipped on this exact PV set because a decoder was
written from a docstring's assumed shape rather than what the real IOC
puts on the wire: `NumAngles` a 1-element array not a scalar, `AbortScan`
an ENUM label `'No'` not `0`, `ImagesSaved` / `ImagesCollected` a
`"<done>/<total>"` string not a float. All three would have shown up in
one run of this command: `kind` flags array-vs-scalar and, via
`classify_capture_status` / `binary_code` / `progress_counts`, a decode
verdict flags anything a role's real decoder cannot accept.

## Read-only, changes nothing

Calls `control_port.read()` only, never `.write()`. The port itself is
already read-only by construction unless the deployment has explicitly set
`CONTROL_WRITES_ENABLED=true` elsewhere (see `build_control_port`), so this
command adds no new safety mechanism, it just never reaches for the one
that would let it write. Safe to run at any time, including against a live,
beam-on session.

## Why `Measurement.kind`, not the raw EPICS DBR type code

`ControlPort.read()` already collapses the wire type into the closed
`MeasurementKind` set (`_kind_for` in `epics_ca_control_port.py`: DBR_ENUM
-> Categorical, `element_count > 1` -> Array, else Scalar) before this
command ever sees a reading. That is sufficient to catch all three defects
above: `kind` alone flags array-vs-scalar and enum-vs-int, and the raw
`value` makes a `"12/100"` string visibly not a bare float. Reaching past
`ControlPort` for the raw aioca `.datatype` would add a substrate-specific
escape hatch that no other caller needs, breaking the discipline every
other consumer in this codebase already keeps of never leaking EPICS
specifics past the adapter.

## Per-role decode verdict

Dispatches on the SAME role keys and decoders `ControlPortCaptureObserver`
uses in production (`cora.api._capture_observer`), so this can never drift
from what the running system actually accepts:

  - `status` (`ROLE_STATUS`): `classify_capture_status` against the
    deployment's `capture_status_phases` table. BAD when the reading
    classifies `UNRECOGNIZED`.
  - `abort` (`ROLE_ABORT`): `binary_code`. BAD when it returns `None`.
  - `images_saved` / `images_collected` (`ROLE_IMAGES_SAVED` /
    `ROLE_IMAGES_COLLECTED`): `progress_counts`. BAD when it returns
    `None`.
  - any other declared role (e.g. `server_running`, which production
    itself declares and never decodes): reports `kind` / `value` only,
    verdict `n/a`. Not decoding it here does not make it undecodable
    elsewhere; it means no decoder exists in production for it either.

Exit codes: 0 every configured PV connected and decoded clean; 2 anything
disconnected, timed out, was access-denied, or a decoder rejected it.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cora.api._capture_observer import (
    ROLE_ABORT,
    ROLE_IMAGES_COLLECTED,
    ROLE_IMAGES_SAVED,
    ROLE_STATUS,
    binary_code,
    classify_capture_status,
    progress_counts,
)
from cora.infrastructure.config import Settings
from cora.operation.adapters.control_port_config import build_control_port
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
)
from cora.shared.capture_phase import CapturePhase

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.ports.control_port import ControlPort, Measurement

_EXIT_CLEAN = 0
_EXIT_PROBLEM = 2

_PROGRESS_ROLES = (ROLE_IMAGES_SAVED, ROLE_IMAGES_COLLECTED)


@dataclass
class _PvReport:
    """One configured PV's preflight result. `ok=False` is the signal this
    command exists to surface; every other field is forensic detail for a
    human reading the printed report."""

    code: str
    role: str
    pv: str
    ok: bool
    connected: bool
    detail: str = ""
    kind: str | None = None
    element_count: int | None = None
    value: object = None
    verdict: str = "n/a"

    def render(self) -> str:
        tag = "OK  " if self.ok else "BAD "
        head = f"{tag}{self.code}/{self.role:<17} {self.pv}"
        if not self.connected:
            return f"{head}  NOT CONNECTED ({self.detail})"
        shape = self.kind if self.element_count is None else f"{self.kind}[{self.element_count}]"
        return f"{head}  kind={shape}  value={self.value!r}  decode={self.verdict}"


@dataclass
class _Report:
    lines: list[_PvReport] = field(default_factory=list[_PvReport])

    @property
    def problem(self) -> bool:
        return any(not line.ok for line in self.lines)


async def preflight_read_capture_pvs(
    *,
    control_port: ControlPort,
    capture_pvs: Mapping[str, Mapping[str, str]],
    status_phases: Mapping[str, str],
) -> _Report:
    """Read every configured `capture_watch_pvs` role once; report its shape.

    Iteration order is sorted (code, then role) so two runs against an
    unchanged config produce line-for-line identical output. Each PV is
    read independently: one dead or misconfigured PV does not abort the
    sweep, it reports as its own failed line.
    """
    report = _Report()
    for code in sorted(capture_pvs):
        for role, pv in sorted(capture_pvs[code].items()):
            report.lines.append(await _read_one(control_port, code, role, pv, status_phases))
    return report


async def _read_one(
    control_port: ControlPort,
    code: str,
    role: str,
    pv: str,
    status_phases: Mapping[str, str],
) -> _PvReport:
    try:
        reading = await control_port.read(pv)
    except (ControlNotConnectedError, ControlTimeoutError, ControlAccessDeniedError) as exc:
        return _PvReport(code=code, role=role, pv=pv, ok=False, connected=False, detail=str(exc))
    except ControlValueCoercionError as exc:
        # Connected, but the adapter could not unpack the wire value into a
        # `Measurement` at all: a shape gap even more basic than a decoder
        # rejection, and exactly the kind of thing this command exists to
        # surface before the recording switch flips.
        return _PvReport(
            code=code,
            role=role,
            pv=pv,
            ok=False,
            connected=True,
            detail=f"adapter could not decode the reading: {exc}",
        )
    element_count = (
        len(reading.value)
        if reading.kind == "Array" and hasattr(reading.value, "__len__")
        else None
    )
    verdict, ok = _decode_verdict(role, reading, status_phases)
    return _PvReport(
        code=code,
        role=role,
        pv=pv,
        ok=ok,
        connected=True,
        kind=reading.kind,
        element_count=element_count,
        value=reading.value,
        verdict=verdict,
    )


def _decode_verdict(
    role: str, reading: Measurement, status_phases: Mapping[str, str]
) -> tuple[str, bool]:
    """The per-role decode check, dispatched on the exact role keys and
    decoders production uses (`cora.api._capture_observer`)."""
    if role == ROLE_STATUS:
        phase = classify_capture_status(str(reading.value), status_phases)
        return phase.value, phase is not CapturePhase.UNRECOGNIZED
    if role == ROLE_ABORT:
        code = binary_code(reading.value)
        if code is None:
            return "unrecognized", False
        return ("asserted" if code == 1 else "clear"), True
    if role in _PROGRESS_ROLES:
        counts = progress_counts(reading.value)
        if counts is None:
            return "unrecognized", False
        reached, commanded_total = counts
        return f"reached={reached} commanded_total={commanded_total}", True
    return "n/a", True


def _finish(report: _Report) -> int:
    print("capture-watch preflight")
    if not report.lines:
        print("  (no PVs configured under CAPTURE_WATCH_PVS)")
        return _EXIT_CLEAN
    for line in report.lines:
        print(f"  {line.render()}")
    ok_count = sum(1 for line in report.lines if line.ok)
    print(f"{ok_count}/{len(report.lines)} PVs OK")
    return _EXIT_PROBLEM if report.problem else _EXIT_CLEAN


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, separate from `main` so tests can invoke it without
    building a real `ControlPort`."""
    return argparse.ArgumentParser(
        prog="python -m cora.api.capture_watch_preflight",
        description=(
            "Read every PV configured under CAPTURE_WATCH_PVS once against "
            "the live control system and report, per role, whether it "
            "connects, what shape CORA's ControlPort sees it as, the raw "
            "value, and whether CORA's own decoder for that role accepts "
            "it. Read-only; changes nothing. Run once the host is "
            "reachable, before RUN_WITNESS_RECORDING_ENABLED is set, and "
            "again after any CAPTURE_WATCH_PVS / CAPTURE_STATUS_PHASES edit."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    settings = Settings()
    control_port = build_control_port(
        settings.control_port_routes, writes_enabled=settings.control_writes_enabled
    )

    async def _run() -> int:
        try:
            report = await preflight_read_capture_pvs(
                control_port=control_port,
                capture_pvs=settings.capture_watch_pvs,
                status_phases=settings.capture_status_phases,
            )
            return _finish(report)
        finally:
            # ControlPort Protocol does not declare aclose (it's
            # adapter-optional); getattr + suppress mirrors main.py's own
            # shutdown teardown for the same port.
            aclose = getattr(control_port, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
