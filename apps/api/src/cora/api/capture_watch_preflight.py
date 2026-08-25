"""Preflight read: report every configured `capture_watch_pvs` PV,
every `capture_baseline_pvs` PV, and every `capture_experiment_identity_pvs`
PV, against the live control system, before the recording switch flips.

`python -m cora.api.capture_watch_preflight` reads every PV named under
`Settings.capture_watch_pvs` exactly once and reports, per role: whether it
connects, what `Measurement.kind` CORA's `ControlPort` sees it as, the raw
decoded value, and whether CORA's own decoder for that role accepts it. It
also sweeps `Settings.capture_baseline_pvs` (slice 12): those channels have
no per-role decoder in production (every baseline channel is treated
identically by wire kind, see `cora.api._capture_baseline_reader`), so the
report shows `kind` / `value` / `units` with verdict `n/a`, EXCEPT that a
non-numeric, non-categorical value is flagged BAD -- the one thing
checkable ahead of time, since `Observation.value` /
`Observation.categorical_value` are the only two shapes
`AppendObservations` accepts. A `Categorical` reading (an EPICS
`mbbo`/`bo` scan-configuration PV) reports its resolved label as the
verdict instead of being flagged BAD: `CaptureBaselineReader` stores
that label directly, so a healthy categorical PV is not a defect. It
also sweeps `Settings.capture_experiment_identity_pvs`
(slice 14a): the one thing worth flagging ahead of time here is that the
substrate's own `"Unknown"` placeholder reads as a perfectly healthy
string unless this preflight calls it out explicitly, so the verdict
column shows `placeholder` (distinct from `empty` and `text(len=N)`) rather
than letting an unpopulated PV masquerade as a good reading -- see
"Trap 1" in `cora.api._capture_experiment_identity_reader`'s own
docstring. The `orchestrator_ref` role (see "Per-role decode
verdict" below) is checked against `Settings.capture_orchestrator_ref_schemes`
as part of the same `capture_watch_pvs` sweep, not a separate group.
Run this command once the host is reachable and before
`RUN_WITNESS_RECORDING_ENABLED` is set, and again after any
`CAPTURE_WATCH_PVS` / `CAPTURE_STATUS_PHASES` / `CAPTURE_BASELINE_PVS` /
`CAPTURE_EXPERIMENT_IDENTITY_PVS` / `CAPTURE_ORCHESTRATOR_REF_SCHEMES` edit.

## Why this exists

Three defects have now shipped on this exact PV set because a decoder was
written from a docstring's assumed shape rather than what the real IOC
puts on the wire: `NumAngles` a 1-element array not a scalar, `AbortScan`
an ENUM label `'No'` not `0`, `ImagesSaved` / `ImagesCollected` a
`"<done>/<total>"` string not a float. Two of the three would have shown
up in one run of this command: via `classify_capture_status` /
`binary_code` / `progress_counts`, a decode verdict flags the `AbortScan`
enum label and the `ImagesSaved` / `ImagesCollected` string. The third,
`NumAngles`, would NOT: it is read from the HDF5 file
(`data_exchange_scan_reader.py:106`), never from a PV, so it is not in
`CAPTURE_WATCH_PVS` and no channel-access preflight can reach it.

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
command ever sees a reading. That is enough to catch the two wire-shape
defects this preflight can actually reach: `kind` flags a DBR_ENUM
masquerading as a scalar (`AbortScan` resolves as Categorical, not
Scalar) and the raw `value` makes a `"12/100"` string visibly not a bare
float. It is NOT enough to flag a one-element array as anything but a
Scalar: `_kind_for` classifies an array by `element_count > 1`, so a
genuinely 1-element array (`NumAngles`'s own shape, had it been readable
as a PV here) reports `kind=Scalar`, indistinguishable from a real
scalar via `kind` alone. Reaching past `ControlPort` for the raw aioca
`.datatype` would add a substrate-specific escape hatch that no other
caller needs, breaking the discipline every other consumer in this
codebase already keeps of never leaking EPICS specifics past the
adapter.

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
  - `testing` (`ROLE_TESTING`): `binary_code`, same decoder as `abort`
    (2-BM's `Testing` PV is the identical `DBR_ENUM` record type as
    `AbortScan`). BAD when it returns `None`.
  - `full_file_name` (`ROLE_FULL_FILE_NAME`, slice 13): the value is
    PERSONAL DATA (see `_capture_observer.py`), so this is the one role
    whose printed `value` field is REDACTED to a length-only placeholder
    rather than the raw reading -- `kind` and `element_count` still
    print real. Verdict reports `text(len=N)`, `empty`, or
    `suspected-truncated` (mirroring `_from_full_file_name_reading`'s
    own truncation threshold); BAD only for `suspected-truncated`. A
    non-str reading is BAD as `non-text`.
  - `orchestrator_ref` (`ROLE_ORCHESTRATOR_REF`): the value is NOT
    personal data, so it prints unredacted (defensive path-shape
    redaction still applies, mirroring the baseline/experiment-identity
    sweeps' own guard). Verdict reports `text(len=N)` when a scheme is
    configured for this code in `capture_orchestrator_ref_schemes`,
    `empty` for a blank reading (the orchestrator's own cleared state,
    not a defect); BAD as `non-text` for a non-string reading, over
    length, or `scheme-not-configured` when the PV is declared here but
    absent from `CAPTURE_ORCHESTRATOR_REF_SCHEMES` -- mirroring
    `_from_orchestrator_ref_reading`'s own rejection reasons exactly so
    this can never drift from what production accepts.
  - any other declared role (e.g. `server_running`, which production
    itself declares and never decodes): reports `kind` / `value` only,
    verdict `n/a`. Not decoding it here does not make it undecodable
    elsewhere; it means no decoder exists in production for it either.

`capture_experiment_identity_pvs`'s three roles (`proposal_number`,
`esaf_number`, `esaf_doi_number`, slice 14a) are a separate `group="experiment_identity"`
sweep, dispatched on `resolved_experiment_identity_text` from
`cora.api._capture_experiment_identity_reader` so this can never drift
from what the reader actually vaults. None of the three is personal
data, so the printed `value` is the raw reading, unredacted (defensive
path-shape redaction still applies if a `full_file_name` PV were
accidentally declared here instead, mirroring the baseline sweep's own
defense-in-depth). Verdict is `placeholder` for the substrate's own
`"Unknown"` literal, `empty` for a blank string, `text(len=N)` for a
real value, BAD only as `non-text`.

## Camera-prefix cross-check

2-BM has two cameras behind two different PV prefixes (`2bmSP1:`,
`2bmSP2:`), and `full_file_name`'s configured PV is a hardcoded string:
nothing makes it follow which camera the operator actually has
selected. On 2026-08-20 an operator's camera switch left that role
reading the idle camera's stale filename readback, which is exactly the
value `RunWitnessRecorder` vaults into `run_capture_path` (personal
data) as the Run's capture path. When a code declares BOTH
`full_file_name` and the optional `camera_selected` role (the live
camera-selection readback PV, e.g. 2-BM's
`2bm:MCTOptics:CameraSelected`), this adds ONE further report line per
code, `camera_prefix_check`, comparing the two: reused readings only,
never a second `control_port.read()` of either PV. See
`_camera_prefix_check`.

CORA does not know, and must not guess, whether the substrate's
`CameraSelected` resolves to a bare index or an ENUM label, so the
resolved-reading -> expected-prefix mapping is a deployment-declared
table (`Settings.capture_camera_select_prefixes`), never hardcoded
here. Verdict is `match` (OK) when the live selection resolves to the
same prefix `full_file_name` is configured with; `mismatch(...)`, an
unrecognized reading, an empty mapping table, or an unreadable PV are
all BAD, never a silent pass: this check either confirms the two agree
or says plainly that it cannot.

A code declaring `full_file_name` WITHOUT `camera_selected` is that
same "cannot confirm", so it reports BAD `undeclared(...)` rather than
no line at all. It read as a silent pass until 2026-08-22, and 2-BM
was in exactly that state: `camera_selected` was never added to the
deployment's `capture_watch_pvs`, so the cross-check that shipped to
catch a camera switch never ran once, and the preflight's own
`N/N PVs OK` tail counted a config it had not checked. An optional
role is a reasonable thing for a deployment not to declare; a safety
check that disappears when it is missing is not.

Exit codes: 0 every configured PV connected and decoded clean; 2 anything
disconnected, timed out, was access-denied, or a decoder rejected it.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeGuard

from cora.api._capture_experiment_identity_reader import (
    UNKNOWN_EXPERIMENT_IDENTITY_LITERAL,
    resolved_experiment_identity_text,
)
from cora.api._capture_observer import (
    FULL_FILE_NAME_TRUNCATION_THRESHOLD,
    ROLE_ABORT,
    ROLE_FULL_FILE_NAME,
    ROLE_IMAGES_COLLECTED,
    ROLE_IMAGES_SAVED,
    ROLE_ORCHESTRATOR_REF,
    ROLE_STATUS,
    ROLE_TESTING,
    binary_code,
    classify_capture_status,
    finite_float,
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
from cora.run.aggregates.run import READING_CATEGORICAL_VALUE_MAX_LENGTH
from cora.shared.capture_phase import CapturePhase
from cora.shared.identifier import IDENTIFIER_VALUE_MAX_LENGTH

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.ports.control_port import ControlPort, Measurement

_EXIT_CLEAN = 0
_EXIT_PROBLEM = 2

_PROGRESS_ROLES = (ROLE_IMAGES_SAVED, ROLE_IMAGES_COLLECTED)

ROLE_CAMERA_SELECTED = "camera_selected"
"""Optional `capture_watch_pvs` role, declared-and-unread by production
exactly like `server_running` (`ControlPortCaptureObserver` builds no
pump for either): the beamline's live camera-selection readback PV.
Read here only, to cross-check against the `full_file_name` role's
configured PV prefix; see `_camera_prefix_check` and this module's
"Camera-prefix cross-check" docstring section."""


@dataclass
class _PvReport:
    """One configured PV's preflight result. `ok=False` is the signal this
    command exists to surface; every other field is forensic detail for a
    human reading the printed report."""

    code: str
    pv_key: str
    """The `capture_watch_pvs` role (`"status"`, `"abort"`, ...) for a
    `group="watch"` line, the `capture_baseline_pvs` channel_name for a
    `group="baseline"` line, or the `capture_experiment_identity_pvs`
    role (`"proposal_number"`, `"esaf_number"`, `"esaf_doi_number"`) for a
    `group="experiment_identity"` line. Named for what it structurally is (the
    PV's inner-dict key) rather than "role", which is only true of two
    of this report's three groups."""
    pv: str
    ok: bool
    connected: bool
    detail: str = ""
    kind: str | None = None
    element_count: int | None = None
    value: object = None
    units: str | None = None
    verdict: str = "n/a"
    group: str = "watch"
    """`"watch"` (`capture_watch_pvs`, the default), `"baseline"`
    (`capture_baseline_pvs`, slice 12), or `"experiment_identity"`
    (`capture_experiment_identity_pvs`, slice 14a). Purely a
    report-rendering distinction; all groups share every other field."""

    def render(self) -> str:
        tag = "OK  " if self.ok else "BAD "
        key_label = self.pv_key if self.group == "watch" else f"{self.group}:{self.pv_key}"
        head = f"{tag}{self.code}/{key_label:<17} {self.pv}"
        if not self.connected:
            return f"{head}  NOT CONNECTED ({self.detail})"
        shape = self.kind if self.element_count is None else f"{self.kind}[{self.element_count}]"
        unit_part = f"  units={self.units}" if self.units is not None else ""
        return f"{head}  kind={shape}  value={self.value!r}{unit_part}  decode={self.verdict}"


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
    baseline_pvs: Mapping[str, Mapping[str, str]] | None = None,
    experiment_identity_pvs: Mapping[str, Mapping[str, str]] | None = None,
    camera_select_prefixes: Mapping[str, str] | None = None,
    orchestrator_ref_schemes: Mapping[str, str] | None = None,
) -> _Report:
    """Read every configured `capture_watch_pvs` role, then every
    `capture_baseline_pvs` channel (slice 12), then every
    `capture_experiment_identity_pvs` role (slice 14a), once each;
    report shape.

    Iteration order is sorted (code, then role/channel_name), watch
    lines before baseline lines before experiment-identity lines, so two runs
    against an unchanged config produce line-for-line identical output.
    Each PV is read independently: one dead or misconfigured PV does
    not abort the sweep, it reports as its own failed line.

    A code declaring BOTH `full_file_name` and `camera_selected` gets
    one further line, `camera_prefix_check`, appended after that code's
    own roles (see "Camera-prefix cross-check" in this module's
    docstring): reused readings only, no extra `control_port.read()`.
    """
    report = _Report()
    for code in sorted(capture_pvs):
        roles = capture_pvs[code]
        role_reports: dict[str, _PvReport] = {}
        for role, pv in sorted(roles.items()):
            pv_report = await _read_one(
                control_port, code, role, pv, status_phases, orchestrator_ref_schemes or {}
            )
            report.lines.append(pv_report)
            role_reports[role] = pv_report
        if ROLE_FULL_FILE_NAME in roles:
            if ROLE_CAMERA_SELECTED in roles:
                report.lines.append(
                    _camera_prefix_check(
                        code=code,
                        full_file_name_pv=roles[ROLE_FULL_FILE_NAME],
                        camera_selected_pv=roles[ROLE_CAMERA_SELECTED],
                        camera_selected_report=role_reports[ROLE_CAMERA_SELECTED],
                        camera_select_prefixes=camera_select_prefixes or {},
                    )
                )
            else:
                report.lines.append(_camera_prefix_check_undeclared(code=code, roles=roles))
    for code in sorted(baseline_pvs or {}):
        for channel_name, pv in sorted((baseline_pvs or {})[code].items()):
            report.lines.append(await _read_one_baseline(control_port, code, channel_name, pv))
    for code in sorted(experiment_identity_pvs or {}):
        for role, pv in sorted((experiment_identity_pvs or {})[code].items()):
            report.lines.append(await _read_one_experiment_identity(control_port, code, role, pv))
    return report


async def _read_one(
    control_port: ControlPort,
    code: str,
    role: str,
    pv: str,
    status_phases: Mapping[str, str],
    orchestrator_ref_schemes: Mapping[str, str],
) -> _PvReport:
    try:
        reading = await control_port.read(pv)
    except (ControlNotConnectedError, ControlTimeoutError, ControlAccessDeniedError) as exc:
        return _PvReport(code=code, pv_key=role, pv=pv, ok=False, connected=False, detail=str(exc))
    except ControlValueCoercionError as exc:
        # Connected, but the adapter could not unpack the wire value into a
        # `Measurement` at all: a shape gap even more basic than a decoder
        # rejection, and exactly the kind of thing this command exists to
        # surface before the recording switch flips.
        return _PvReport(
            code=code,
            pv_key=role,
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
    verdict, ok = _decode_verdict(role, reading, status_phases, code, orchestrator_ref_schemes)
    return _PvReport(
        code=code,
        pv_key=role,
        pv=pv,
        ok=ok,
        connected=True,
        kind=reading.kind,
        element_count=element_count,
        value=_redacted_value(role, reading.value),
        verdict=verdict,
    )


def _looks_like_a_filesystem_path(value: object) -> TypeGuard[str]:
    """True for a string shaped like an absolute filesystem path.

    Defense-in-depth redaction trigger, independent of role/channel
    key: a `capture_watch_pvs` or `capture_baseline_pvs` operator typo
    on the intended role/channel name (`"full_filename"`,
    `"fullFileName"`, or the `full_file_name` PV accidentally declared
    under `capture_baseline_pvs`) would otherwise fall through to a
    generic branch and print the real path -- precisely the shape of
    mistake this tool exists to catch, in the one case where catching
    it here matters most: this preflight command is what an operator
    runs, screenshots, and pastes into a ticket while debugging exactly
    this kind of misconfiguration.
    """
    return isinstance(value, str) and value.startswith("/")


def _redacted_value(role: str, value: object) -> object:
    """The printed `value` for a `capture_watch_pvs` `_PvReport` line:
    real for every role except `full_file_name` (slice 13, PERSONAL
    DATA), which prints a length-only placeholder instead. Also
    redacts defensively when the role doesn't match but the value is
    still path-shaped; see `_looks_like_a_filesystem_path`. Production
    (`_capture_observer.py`) fails safe on a role-key typo (no pump is
    created for an undeclared role), so the defensive branch here is
    this tool's own, not a mirror of a production check.
    """
    if role == ROLE_FULL_FILE_NAME:
        return f"<redacted, len={len(value)}>" if isinstance(value, str) else "<redacted, non-text>"
    if _looks_like_a_filesystem_path(value):
        return f"<redacted, len={len(value)}>"
    return value


def _decode_verdict(
    role: str,
    reading: Measurement,
    status_phases: Mapping[str, str],
    capture_code: str,
    orchestrator_ref_schemes: Mapping[str, str],
) -> tuple[str, bool]:
    """The per-role decode check, dispatched on the exact role keys and
    decoders production uses (`cora.api._capture_observer`)."""
    if role == ROLE_STATUS:
        phase = classify_capture_status(str(reading.value), status_phases)
        return phase.value, phase is not CapturePhase.UNRECOGNIZED
    if role == ROLE_ABORT:
        code = binary_code(reading.value, ordinal=reading.ordinal)
        if code is None:
            return "unrecognized", False
        return ("asserted" if code == 1 else "clear"), True
    if role == ROLE_FULL_FILE_NAME:
        return _full_file_name_verdict(reading.value)
    if role == ROLE_ORCHESTRATOR_REF:
        return _orchestrator_ref_verdict(reading.value, capture_code, orchestrator_ref_schemes)
    if role == ROLE_TESTING:
        code = binary_code(reading.value, ordinal=reading.ordinal)
        if code is None:
            return "unrecognized", False
        return ("testing" if code == 1 else "real"), True
    if role in _PROGRESS_ROLES:
        counts = progress_counts(reading.value)
        if counts is None:
            return "unrecognized", False
        reached, commanded_total = counts
        return f"reached={reached} commanded_total={commanded_total}", True
    return "n/a", True


def _orchestrator_ref_verdict(
    value: object, capture_code: str, orchestrator_ref_schemes: Mapping[str, str]
) -> tuple[str, bool]:
    """The `orchestrator_ref` role's decode check, mirroring
    `_from_orchestrator_ref_reading`'s own rejection reasons
    (`cora.api._capture_observer`) so this can never drift from what
    production accepts. NOT personal data, so (unlike
    `_full_file_name_verdict`) the length-N verdict is the only
    redaction; the raw value itself is still never printed here either,
    matching every other role's verdict-not-value convention.
    """
    if not isinstance(value, str):
        return "non-text", False
    if not value:
        return "empty", True
    # Measured AFTER trimming, matching `Identifier.__post_init__`'s own
    # strip-then-bound order (and `_from_orchestrator_ref_reading`'s
    # identical fix): a whitespace-padded reading over the raw threshold
    # but under it once trimmed is a value the running system accepts,
    # not a defect this preflight should flag.
    trimmed_length = len(value.strip())
    if trimmed_length > IDENTIFIER_VALUE_MAX_LENGTH:
        return "over-length", False
    if capture_code not in orchestrator_ref_schemes:
        return "scheme-not-configured", False
    return f"text(len={trimmed_length})", True


def _full_file_name_verdict(value: object) -> tuple[str, bool]:
    """The `full_file_name` role's decode check (slice 13): reports a
    length-only verdict, NEVER the value, mirroring the same three
    rejection reasons `_from_full_file_name_reading` applies in
    production (`cora.api._capture_observer`) so this can never drift
    from what the running system actually accepts.
    """
    if not isinstance(value, str):
        return "non-text", False
    if not value:
        return "empty", True
    if len(value) >= FULL_FILE_NAME_TRUNCATION_THRESHOLD:
        return "suspected-truncated", False
    return f"text(len={len(value)})", True


def _configured_pv_prefix(pv: str) -> str:
    """The IOC-prefix segment of a configured PV name, up to and
    including the first colon (`"2bmSP2:HDF1:FullFileName_RBV"` ->
    `"2bmSP2:"`). Plain string parsing, not a lookup against any
    facility-specific vocabulary: this reads the STATIC config string,
    never a live value.
    """
    head, sep, _ = pv.partition(":")
    return f"{head}{sep}"


def _camera_prefix_check(
    *,
    code: str,
    full_file_name_pv: str,
    camera_selected_pv: str,
    camera_selected_report: _PvReport,
    camera_select_prefixes: Mapping[str, str],
) -> _PvReport:
    """The camera-prefix cross-check (see this module's docstring):
    compares `full_file_name`'s CONFIGURED PV prefix against the live
    `camera_selected` reading, resolved through the deployment-declared
    `camera_select_prefixes` table.

    Never reports a clean match on a reading it cannot actually
    confirm: an unreadable `camera_selected` PV, a reading the table
    does not resolve, or an empty table are each their own distinct BAD
    verdict, not a fallback pass. Reuses `camera_selected_report`
    (already read by the caller's own `capture_watch_pvs` sweep); makes
    no second `control_port.read()` of its own.
    """
    configured_prefix = _configured_pv_prefix(full_file_name_pv)
    if not camera_selected_report.connected:
        return _PvReport(
            code=code,
            pv_key="camera_prefix_check",
            pv=camera_selected_pv,
            ok=False,
            connected=False,
            detail=f"camera_selected PV unreadable: {camera_selected_report.detail}",
        )
    if camera_selected_report.value is None:
        return _PvReport(
            code=code,
            pv_key="camera_prefix_check",
            pv=camera_selected_pv,
            ok=False,
            connected=True,
            kind="PrefixCheck",
            value=configured_prefix,
            verdict="unrecognized-reading(camera_selected PV did not decode)",
        )
    if not camera_select_prefixes:
        return _PvReport(
            code=code,
            pv_key="camera_prefix_check",
            pv=camera_selected_pv,
            ok=False,
            connected=True,
            kind="PrefixCheck",
            value=configured_prefix,
            verdict="not-configured(CAPTURE_CAMERA_SELECT_PREFIXES empty)",
        )
    resolved = str(camera_selected_report.value)
    expected_prefix = camera_select_prefixes.get(resolved)
    if expected_prefix is None:
        return _PvReport(
            code=code,
            pv_key="camera_prefix_check",
            pv=camera_selected_pv,
            ok=False,
            connected=True,
            kind="PrefixCheck",
            value=configured_prefix,
            verdict=f"unrecognized-reading({resolved!r})",
        )
    if expected_prefix != configured_prefix:
        return _PvReport(
            code=code,
            pv_key="camera_prefix_check",
            pv=camera_selected_pv,
            ok=False,
            connected=True,
            kind="PrefixCheck",
            value=configured_prefix,
            verdict=f"mismatch(selected camera expects {expected_prefix!r})",
        )
    return _PvReport(
        code=code,
        pv_key="camera_prefix_check",
        pv=camera_selected_pv,
        ok=True,
        connected=True,
        kind="PrefixCheck",
        value=configured_prefix,
        verdict="match",
    )


def _camera_prefix_check_undeclared(*, code: str, roles: Mapping[str, str]) -> _PvReport:
    """A code declaring `full_file_name` but NOT `camera_selected`.

    This reports BAD rather than emitting nothing, because the absence
    of the role is not the absence of the risk: `full_file_name`'s PV
    is still a hardcoded prefix that an operator's camera switch can
    strand on the idle camera's stale readback, and that value still
    reaches the `run_capture_path` PII vault. Every other way this
    cross-check can fail to confirm already reports BAD (see
    `_camera_prefix_check`); leaving this one case silent made "not
    configured yet" indistinguishable from "checked and agreed" in the
    one report an operator reads before flipping the recording switch.
    """
    return _PvReport(
        code=code,
        pv_key="camera_prefix_check",
        pv=roles[ROLE_FULL_FILE_NAME],
        ok=False,
        connected=True,
        kind="PrefixCheck",
        value=_configured_pv_prefix(roles[ROLE_FULL_FILE_NAME]),
        verdict=f"undeclared({ROLE_CAMERA_SELECTED!r} role not in capture_watch_pvs)",
    )


async def _read_one_baseline(
    control_port: ControlPort,
    code: str,
    channel_name: str,
    pv: str,
) -> _PvReport:
    """A `capture_baseline_pvs` channel's preflight result.

    No per-channel decoder exists in production (every baseline channel
    is treated identically; see `cora.api._capture_baseline_reader`), so
    the only checkable-ahead-of-time defect is a non-numeric value:
    `Observation.value` is `float`, so a textual reading here is BAD
    even though this command has no decode verdict to report beyond that.
    """
    try:
        reading = await control_port.read(pv)
    except (ControlNotConnectedError, ControlTimeoutError, ControlAccessDeniedError) as exc:
        return _PvReport(
            code=code,
            pv_key=channel_name,
            pv=pv,
            ok=False,
            connected=False,
            detail=str(exc),
            group="baseline",
        )
    except ControlValueCoercionError as exc:
        return _PvReport(
            code=code,
            pv_key=channel_name,
            pv=pv,
            ok=False,
            connected=True,
            detail=f"adapter could not decode the reading: {exc}",
            group="baseline",
        )
    element_count = (
        len(reading.value)
        if reading.kind == "Array" and hasattr(reading.value, "__len__")
        else None
    )
    verdict, ok = _baseline_verdict(reading)
    return _PvReport(
        code=code,
        pv_key=channel_name,
        pv=pv,
        ok=ok,
        connected=True,
        kind=reading.kind,
        element_count=element_count,
        # Defense-in-depth, not the primary guard: a `full_file_name` PV
        # accidentally declared under `capture_baseline_pvs` (the wrong
        # dict) would otherwise print its real, personal-data-bearing
        # value here. See `_looks_like_a_filesystem_path`.
        value=(
            f"<redacted, len={len(reading.value)}>"
            if _looks_like_a_filesystem_path(reading.value)
            else reading.value
        ),
        units=reading.units,
        verdict=verdict,
        group="baseline",
    )


def _baseline_verdict(reading: Measurement) -> tuple[str, bool]:
    """A `Categorical` reading (an EPICS `mbbo`/`bo` scan-configuration
    PV) reports its resolved label as the verdict, BAD only for a
    non-string/empty value or one over
    `READING_CATEGORICAL_VALUE_MAX_LENGTH`: `CaptureBaselineReader`
    stores the label unchanged, so a healthy label is not a defect.
    Every other kind is BAD only when the value cannot coerce to a
    finite float: that is the one baseline defect checkable ahead of a
    real append attempt. Reuses `finite_float`, the same coercion
    `CaptureBaselineReader` itself applies, so this can never drift
    from what production accepts.
    """
    if reading.kind == "Categorical":
        label = reading.value
        if not isinstance(label, str) or not label:
            return "non-text", False
        if len(label) > READING_CATEGORICAL_VALUE_MAX_LENGTH:
            return "label-too-long", False
        return f"label={label!r}", True
    if finite_float(reading.value) is None:
        return "non-numeric", False
    return "n/a", True


async def _read_one_experiment_identity(
    control_port: ControlPort,
    code: str,
    role: str,
    pv: str,
) -> _PvReport:
    """A `capture_experiment_identity_pvs` role's preflight result
    (slice 14a).

    None of the three roles (`proposal_number`, `esaf_number`,
    `esaf_doi_number`) is personal data, so the printed `value` is the raw
    reading; the defensive path-shape redaction mirrors the baseline
    sweep's own guard against a `full_file_name` PV being declared
    under the wrong config key.
    """
    try:
        reading = await control_port.read(pv)
    except (ControlNotConnectedError, ControlTimeoutError, ControlAccessDeniedError) as exc:
        return _PvReport(
            code=code,
            pv_key=role,
            pv=pv,
            ok=False,
            connected=False,
            detail=str(exc),
            group="experiment_identity",
        )
    except ControlValueCoercionError as exc:
        return _PvReport(
            code=code,
            pv_key=role,
            pv=pv,
            ok=False,
            connected=True,
            detail=f"adapter could not decode the reading: {exc}",
            group="experiment_identity",
        )
    element_count = (
        len(reading.value)
        if reading.kind == "Array" and hasattr(reading.value, "__len__")
        else None
    )
    verdict, ok = _experiment_identity_verdict(reading.value)
    return _PvReport(
        code=code,
        pv_key=role,
        pv=pv,
        ok=ok,
        connected=True,
        kind=reading.kind,
        element_count=element_count,
        value=(
            f"<redacted, len={len(reading.value)}>"
            if _looks_like_a_filesystem_path(reading.value)
            else reading.value
        ),
        verdict=verdict,
        group="experiment_identity",
    )


def _experiment_identity_verdict(value: object) -> tuple[str, bool]:
    """The `capture_experiment_identity_pvs` decode check (slice 14a),
    dispatched through `resolved_experiment_identity_text` so this can
    never drift from what `CaptureExperimentIdentityReader` actually
    vaults.

    `non-text` is the only BAD outcome: a non-string reading is a
    deployment misconfiguration, not a value to guess at. `placeholder`
    (the substrate's own `"Unknown"` literal, Trap 1) and `empty` are
    both OK -- they are legitimate substrate states this preflight
    exists to make VISIBLE, not defects to fail on -- and are reported
    as their own distinct verdicts specifically so an operator does not
    mistake either for a healthy value. `placeholder`, not `unknown`:
    this report's own `status` role already uses `unrecognized` for a
    different failure (CORA's decoder rejected the literal, rather than
    the substrate never having populated it), and `unknown` would read
    as a synonym for that instead of naming this row's own condition.
    """
    if not isinstance(value, str):
        return "non-text", False
    resolved = resolved_experiment_identity_text(value)
    if resolved is not None:
        return f"text(len={len(resolved)})", True
    if value.strip() == UNKNOWN_EXPERIMENT_IDENTITY_LITERAL:
        return "placeholder", True
    return "empty", True


def _finish(report: _Report) -> int:
    print("capture-watch preflight")
    if not report.lines:
        print("  (no PVs configured under CAPTURE_WATCH_PVS or CAPTURE_BASELINE_PVS)")
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
            "Read every PV configured under CAPTURE_WATCH_PVS, every "
            "channel under CAPTURE_BASELINE_PVS, and every role under "
            "CAPTURE_EXPERIMENT_IDENTITY_PVS, once against the live "
            "control system and report whether each connects, what shape "
            "CORA's ControlPort sees it as, the raw value, and (for "
            "CAPTURE_WATCH_PVS / CAPTURE_EXPERIMENT_IDENTITY_PVS roles) "
            "whether CORA's own decoder for that role accepts it. "
            "Read-only; changes nothing. Run once the host is reachable, "
            "before RUN_WITNESS_RECORDING_ENABLED is set, and again after "
            "any CAPTURE_WATCH_PVS / CAPTURE_STATUS_PHASES / "
            "CAPTURE_BASELINE_PVS / CAPTURE_EXPERIMENT_IDENTITY_PVS edit."
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
                baseline_pvs=settings.capture_baseline_pvs,
                experiment_identity_pvs=settings.capture_experiment_identity_pvs,
                camera_select_prefixes=settings.capture_camera_select_prefixes,
                orchestrator_ref_schemes=settings.capture_orchestrator_ref_schemes,
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
