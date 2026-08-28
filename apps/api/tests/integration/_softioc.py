"""Subprocess softIOC helper for `ControlPort` adapter integration tests.

Per [[project_control_port_test_isolation_research]], CORA tests all
EPICS-family ControlPort adapters (`CaprotoControlPort`,
`EpicsCaControlPort`, future `EpicsPvaControlPort`) against an
external softIOC subprocess spawned via `epicscorelibs.ioc` (a pip
wheel; no system EPICS Base install required).

The corpus-unanimous pattern (Diamond aioca + ophyd-async + fastcs +
caproto's own client tests):

  1. Session-scoped autouse env-var pin to loopback (see `conftest.py`).
  2. Module-scoped IOC subprocess (this file's `start_softioc` helper).
  3. `aioca.purge_channel_caches()` between tests (function-scoped
     autouse fixture in `conftest.py`).

This dodges the process-global `libca` / `pvxs` broadcaster state
problem: the IOC outlives the test loop (it's a subprocess), and
between-test `purge_channel_caches()` is enough to reset client
state without trying to call the unsafe `ca_context_destroy`.

## PV menu (same names as the prior in-process CoraTestIOC)

  - `double_value` (DBR_DOUBLE, `ao` record) -> `Measurement(kind="Scalar")`
  - `long_value`   (DBR_LONG,   `longout`)   -> `Measurement(kind="Scalar")`
  - `string_value` (DBR_STRING, `stringout`) -> `Measurement(kind="Scalar")`
  - `waveform`     (DBR_DOUBLE x 4, `waveform`) -> `Measurement(kind="Array")`
  - `text_waveform` (DBR_CHAR x 256, `waveform`) -> `Measurement(kind="Array")`
    by default; `Measurement(kind="Scalar", value=<str>)` when the caller
    declares it via `EpicsCaControlPort(text_addresses={...})`, exercising
    the tomoscan `ScanStatus`-shaped ambiguity (see that adapter's
    "DBR_CHAR waveforms" module-docstring section)
  - `text_waveform_nelm1` (DBR_CHAR x 1, `waveform`) -> aioca collapses a
    length-1 char waveform to its scalar `ca_int` type; declaring it via
    `text_addresses` must stay inert (no `.tolist()` / not iterable, so
    the naive "any DBR_CHAR is a waveform" version of the decode crashed
    here before the `element_count > 1` guard was added)
  - `enum_value`   (DBR_ENUM,   `mbbo` with 3 strings) -> `Measurement(kind="Categorical")`
  - `unconventional_flag` (DBR_ENUM, `bo` labelled `NO_FAULT` / `TRIP`) and
    `empty_zero_label_flag` (DBR_ENUM, `bo` whose ZNAM is the EMPTY STRING,
    ONAM `Present`) -> the two label pairs 2-BM's BLEPS IOC actually
    publishes, measured on arcturus 2026-08-23. Neither is in any
    conventional set, so both are undecodable from the label alone and
    exist to pin that `Measurement.ordinal` carries the answer. A real
    DBR_ENUM is the point: the equivalent defect shipped twice behind
    unit fakes built as `kind="Scalar"` with a numeric value, a shape no
    `bi` record ever produces.
  - `major_alarm_value` (`ao` with HIHI threshold tripped, HHSV=MAJOR)
    -> `Measurement(quality="Uncertain")`
  - `invalid_alarm_value` (`ao` with HIHI threshold tripped, HHSV=INVALID)
    -> `Measurement(quality="Bad")`
  - `unstamped_value` (`ao` with NO `PINI`) -> `Measurement(produced_at=None)`

## areaDetector ADCore-shaped PVs for the acquisition action bodies

The `cam1:*` PV family mirrors areaDetector's ADCore PV convention so
`cora.operation.acquisitions.{collect,discrete,continuous}` can talk
real CA against this fixture. Acquire_RBV is seeded to `Done` (ZNAM,
index 0); the body's poll loop exits on the first read. Real-detector
timing (Acquire_RBV staying at `Acquiring` mid-flight) is exercised by
the unit tests via the IteratingPort fixture; this integration tier
proves the EPICS wire framing, not the detector finite-state machine.

`Acquire_RBV` is `bi`, not `longin`, and that is load-bearing rather
than cosmetic: a real ADCore `Acquire_RBV` is DBR_ENUM, so it arrives
over CA as `kind="Categorical"` carrying the record's `ZNAM` label
(`"Done"` by default, but facility- and build-editable) with the index
behind it on `Measurement.ordinal`. A `longin` fixture can only ever
produce the `kind="Scalar"` shape the real detector never sends, which
is why this specific record type was the one place in this file the
label-vs-ordinal decode bug (see `cora.operation.acquisitions`'s
`_acquisition_finished`) could not be exercised at all.

  - `cam1:TriggerMode`        (mbbo: Internal / External)
  - `cam1:AcquireTime`        (ao,  per-acquisition seconds)
  - `cam1:ImageMode`          (mbbo: Single / Multiple / Continuous; starts
                               at Continuous, mirroring the real APS 2-BM
                               left-on-Continuous condition `collect` must
                               move off of)
  - `cam1:NumImages`          (longout, bounded count)
  - `cam1:Acquire`            (bo,  start command)
  - `cam1:Acquire_RBV`        (bi,  ZNAM=Done / ONAM=Acquiring)
  - `cam1:DetectorState_RBV`  (mbbi: Idle / Acquiring / Error)

## `cam2:*` -- ADSpinnaker-shaped TriggerMode camera

A second, otherwise-identical AD camera family whose `TriggerMode` enum
is shaped like the real APS 2-BM FLIR/Spinnaker driver
(`2bmSP1:cam1:TriggerMode`, confirmed live): a DBF_ENUM with EXACTLY
two choices, `ZRST=Off` / `ONST=On`. The string `"Internal"` is not a
member of that set, so a dialect bug that writes the ADCore string
against this camera fails LOUDLY (`ControlValueCoercionError` /
`caput` rejection), not silently. This is the "both sides of the check
derive from the same source" gap the ADCore-only `cam1:*` family left
open: every prior integration assertion against `cam1:TriggerMode`
proved CORA can write a string that camera's OWN fixture happens to
accept, never that the string matches what a REAL camera accepts. A
second record family with a genuinely different enum is the least
invasive way to close that gap without perturbing any `cam1:*`
assertion already in place (a parametrised IOC would have required
templating every record in this file for one PV's difference).

  - `cam2:TriggerMode`        (mbbo: Off / On, ADSpinnaker-shaped)
  - `cam2:AcquireTime`        (ao,  per-acquisition seconds)
  - `cam2:ImageMode`          (mbbo: Single / Multiple / Continuous, same
                               shape as `cam1:ImageMode`; confirmed
                               dialect-invariant against the real
                               `2bmSP1:cam1:ImageMode`)
  - `cam2:NumImages`          (longout, bounded count)
  - `cam2:Acquire`            (bo,  start command)
  - `cam2:Acquire_RBV`        (bi,  ZNAM=Done / ONAM=Acquiring)
  - `cam2:DetectorState_RBV`  (mbbi: Idle / Acquiring / Error)

PV names are pure test-shape (`double_value`, etc.); they do NOT
mirror production EPICS conventions at APS 2-BM (`2bma:m1.RBV` etc.).

Writability: all records use the `*o` (output) variant so tests can
caput. `ao`/`longout`/`stringout`/`mbbo` are the EPICS-canonical
writable records; `waveform` is bidirectional by default.

`major_alarm_value` and `invalid_alarm_value`: both VAL=99.9, HIHI=50,
differing only in HHSV (MAJOR vs INVALID). Reading VAL > HIHI trips
the configured severity naturally on every read. No startup hook
needed (softIOC doesn't have caproto-style decorators); the alarm is a
declarative consequence of the field values. The pair exists because
the two severities land on opposite sides of the quality trichotomy
(Uncertain vs Bad), so one record cannot pin both arms.

`unstamped_value` is the ONLY record here without `PINI`, and the
omission is the whole point: a record that never processes keeps
EPICS `TIME` at zero, which is what an undefined timestamp looks like
on the wire. Every other record processes at init and carries a real
stamp. Do not add `PINI` to it. This reproduces the live APS 2-BM
condition where both PSS permit signals report an undefined stamp on
every update, which the adapters used to render as a real-looking
1990-01-01. Reading VAL still works; only the time is missing.

## Slow / timeout PV is intentionally absent

The original `slow_value` (caproto `@getter` with `asyncio.sleep`) has
no clean softIOC equivalent : EPICS records process synchronously in
C. The `pv.read` timeout ACL arm is exercised via aioca unit tests
with mocked `caget` (separate from this fixture) per
[[project_control_port_test_isolation_research]] watch item 4.
`ControlNotConnectedError` (the wait_for_connection timeout arm) is
still exercised via nonexistent-PV tests against this fixture.

## xdist isolation

Each xdist worker is a separate OS process with its own libca state.
Per-worker PV-prefix uniqueness via `uuid4().hex[:8]` prevents
cross-worker name collision even when ephemeral ports happen to
overlap (unlikely on loopback, but the prefix is belt-and-braces).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

import asyncio
import contextlib
import socket
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


_DB_TEMPLATE = """\
record(ao, "$(P)double_value") {
  field(DESC, "DBR_DOUBLE scalar")
  field(DTYP, "Soft Channel")
  field(VAL, 0.0)
  field(PINI, "YES")
}

record(longout, "$(P)long_value") {
  field(DESC, "DBR_LONG scalar")
  field(DTYP, "Soft Channel")
  field(VAL, 0)
  field(PINI, "YES")
}

record(stringout, "$(P)string_value") {
  field(DESC, "DBR_STRING scalar")
  field(DTYP, "Soft Channel")
  field(VAL, "initial")
  field(PINI, "YES")
}

record(waveform, "$(P)waveform") {
  field(DESC, "DBR_DOUBLE waveform")
  field(DTYP, "Soft Channel")
  field(NELM, "4")
  field(FTVL, "DOUBLE")
  field(PINI, "YES")
}

record(waveform, "$(P)text_waveform") {
  field(DESC, "DBR_CHAR waveform, NUL-terminated string")
  field(DTYP, "Soft Channel")
  field(NELM, "256")
  field(FTVL, "UCHAR")
  field(PINI, "YES")
}

record(waveform, "$(P)text_waveform_nelm1") {
  field(DESC, "DBR_CHAR waveform, NELM=1")
  field(DTYP, "Soft Channel")
  field(NELM, "1")
  field(FTVL, "UCHAR")
  field(PINI, "YES")
}

record(mbbo, "$(P)enum_value") {
  field(DESC, "DBR_ENUM with closed label set")
  field(DTYP, "Soft Channel")
  field(ZRST, "off")
  field(ONST, "on")
  field(TWST, "fault")
  field(VAL, "0")
  field(PINI, "YES")
}

record(bo, "$(P)unconventional_flag") {
  field(DESC, "Enum labels outside conventional set")
  field(DTYP, "Soft Channel")
  field(ZNAM, "NO_FAULT")
  field(ONAM, "TRIP")
  field(VAL, "1")
  field(PINI, "YES")
}

record(bo, "$(P)empty_zero_label_flag") {
  field(DESC, "Enum with empty zero-state label")
  field(DTYP, "Soft Channel")
  field(ONAM, "Present")
  field(VAL, "0")
  field(PINI, "YES")
}

record(ao, "$(P)major_alarm_value") {
  field(DESC, "MAJOR via HIHI tripped")
  field(DTYP, "Soft Channel")
  field(VAL, 99.9)
  field(HIHI, 50.0)
  field(HHSV, "MAJOR")
  field(PINI, "YES")
}

record(ao, "$(P)invalid_alarm_value") {
  field(DESC, "INVALID via HIHI tripped")
  field(DTYP, "Soft Channel")
  field(VAL, 99.9)
  field(HIHI, 50.0)
  field(HHSV, "INVALID")
  field(PINI, "YES")
}

record(ao, "$(P)unstamped_value") {
  field(DESC, "No PINI: TIME stays undefined")
  field(DTYP, "Soft Channel")
  field(VAL, 7.5)
}

# NTNDArray Q:group for the PVA adapter (EpicsPvaControlPort). Exposes a 2x3
# uint8 image at $(P)image via PVA. CA cannot carry NTNDArray.
#
# Q:group composition shape:
#  - $(P)image:data (waveform)      -> NTNDArray.value
#  - $(P)image:dim0_size (longout)  -> NTNDArray.dimension[0].size
#  - $(P)image:dim1_size (longout)  -> NTNDArray.dimension[1].size
# +putorder enforces composition before the value field triggers a
# monitor; mirrors the ophyd-async test_records_pva.db pattern.
#
# The `""` target on the meta mapping is deliberate and easy to get
# wrong. `+type:"meta"` contributes the record's alarm AND time to
# the NT structure, so it must be aimed at the structure ROOT. Aiming
# it at named subfields (`"alarm"`, `"timeStamp"`) nests them one
# level too deep, at `image.timeStamp.timeStamp`, where p4p's unwrap
# does not look: `.severity` then silently defaults to 0 and
# `.timestamp` to 0.0, so every image read reported NO_ALARM and
# 1970-01-01 regardless of the record. That was the shape here until
# 2026-08-09 and no test caught it, because the alarm default matched
# the expected value and the time was only asserted to be timezone-aware.

record(longout, "$(P)image:dim0_size") {
  field(DESC, "NTNDArray dim 0 size")
  field(DTYP, "Soft Channel")
  field(VAL, "2")
  field(PINI, "YES")
  info(Q:group, {
    "$(P)image": {
      "dimension[0].size": {+channel:"VAL", +type:"plain", +putorder:0}
    }
  })
}

record(longout, "$(P)image:dim1_size") {
  field(DESC, "NTNDArray dim 1 size")
  field(DTYP, "Soft Channel")
  field(VAL, "3")
  field(PINI, "YES")
  info(Q:group, {
    "$(P)image": {
      "dimension[1].size": {+channel:"VAL", +type:"plain", +putorder:1}
    }
  })
}

record(waveform, "$(P)image:data") {
  field(DESC, "NTNDArray flat pixel buffer")
  field(DTYP, "Soft Channel")
  field(FTVL, "UCHAR")
  field(NELM, "6")
  field(PINI, "YES")
  info(Q:group, {
    "$(P)image": {
      +id:"epics:nt/NTNDArray:1.0",
      "value": {+type:"any", +channel:"VAL", +putorder:2, +trigger:"*"},
      "": {+type:"meta", +channel:"VAL"}
    }
  })
}

# areaDetector ADCore PV family for collect / discrete / continuous
# action body integration tests. Acquire_RBV starts at Done (index 0)
# so the body's poll loop exits on the first read; the wire framing +
# record-routing assertions are what the integration tier is here to
# prove.

record(mbbo, "$(P)cam1:TriggerMode") {
  field(DESC, "AD trigger mode")
  field(DTYP, "Soft Channel")
  field(ZRST, "Internal")
  field(ONST, "External")
  field(VAL, "0")
  field(PINI, "YES")
}

record(ao, "$(P)cam1:AcquireTime") {
  field(DESC, "Per-acquisition exposure (seconds)")
  field(DTYP, "Soft Channel")
  field(VAL, 0.0)
  field(PINI, "YES")
}

# VAL starts at 2 (Continuous), mirroring the real APS 2-BM condition a
# previous user left the camera in; the integration test proves `collect`
# moves it to Multiple rather than inheriting whatever it finds.
record(mbbo, "$(P)cam1:ImageMode") {
  field(DESC, "AD image mode")
  field(DTYP, "Soft Channel")
  field(ZRST, "Single")
  field(ONST, "Multiple")
  field(TWST, "Continuous")
  field(VAL, "2")
  field(PINI, "YES")
}

record(longout, "$(P)cam1:NumImages") {
  field(DESC, "Bounded image count")
  field(DTYP, "Soft Channel")
  field(VAL, 0)
  field(PINI, "YES")
}

record(bo, "$(P)cam1:Acquire") {
  field(DESC, "Start (1) / stop (0) acquisition")
  field(DTYP, "Soft Channel")
  field(ZNAM, "Done")
  field(ONAM, "Acquire")
  field(VAL, "0")
  field(PINI, "YES")
}

record(bi, "$(P)cam1:Acquire_RBV") {
  field(DESC, "Acquire status readback; Done/Acquiring")
  field(DTYP, "Soft Channel")
  field(ZNAM, "Done")
  field(ONAM, "Acquiring")
  field(VAL, "0")
  field(PINI, "YES")
}

record(mbbi, "$(P)cam1:DetectorState_RBV") {
  field(DESC, "Detector state readback")
  field(DTYP, "Soft Channel")
  field(ZRST, "Idle")
  field(ONST, "Acquiring")
  field(TWST, "Error")
  field(VAL, "0")
  field(PINI, "YES")
}

# cam2:* mirrors cam1:* except TriggerMode's enum, which is shaped like
# the real ADSpinnaker (FLIR) driver at APS 2-BM: Off/On only, no
# "Internal"/"External" strings in the set at all. See this file's
# module docstring, "cam2:* -- ADSpinnaker-shaped TriggerMode camera".

record(mbbo, "$(P)cam2:TriggerMode") {
  field(DESC, "ADSpinnaker trigger mode")
  field(DTYP, "Soft Channel")
  field(ZRST, "Off")
  field(ONST, "On")
  field(VAL, "0")
  field(PINI, "YES")
}

record(ao, "$(P)cam2:AcquireTime") {
  field(DESC, "Per-acquisition exposure (seconds)")
  field(DTYP, "Soft Channel")
  field(VAL, 0.0)
  field(PINI, "YES")
}

record(mbbo, "$(P)cam2:ImageMode") {
  field(DESC, "AD image mode")
  field(DTYP, "Soft Channel")
  field(ZRST, "Single")
  field(ONST, "Multiple")
  field(TWST, "Continuous")
  field(VAL, "2")
  field(PINI, "YES")
}

record(longout, "$(P)cam2:NumImages") {
  field(DESC, "Bounded image count")
  field(DTYP, "Soft Channel")
  field(VAL, 0)
  field(PINI, "YES")
}

record(bo, "$(P)cam2:Acquire") {
  field(DESC, "Start (1) / stop (0) acquisition")
  field(DTYP, "Soft Channel")
  field(ZNAM, "Done")
  field(ONAM, "Acquire")
  field(VAL, "0")
  field(PINI, "YES")
}

record(bi, "$(P)cam2:Acquire_RBV") {
  field(DESC, "Acquire status readback; Done/Acquiring")
  field(DTYP, "Soft Channel")
  field(ZNAM, "Done")
  field(ONAM, "Acquiring")
  field(VAL, "0")
  field(PINI, "YES")
}

record(mbbi, "$(P)cam2:DetectorState_RBV") {
  field(DESC, "Detector state readback")
  field(DTYP, "Soft Channel")
  field(ZRST, "Idle")
  field(ONST, "Acquiring")
  field(TWST, "Error")
  field(VAL, "0")
  field(PINI, "YES")
}
"""


def free_localhost_port() -> int:
    """Allocate a free loopback port via bind-and-close.

    What this DOES guarantee, and what xdist needs: the kernel will not
    hand the same port to two binds that are live at the same moment, so
    two workers calling this concurrently always get distinct ports, even
    under `-n 4+`.

    What it does NOT guarantee: a reservation. The socket is closed before
    the number is returned, so the port is free again on return, and it
    came from the ephemeral range the kernel draws `bind(0)` from
    (49152-65535 on darwin, typically 32768-60999 on linux). Anything that
    binds an ephemeral port afterwards can be handed it back.
    `_pin_epics_env` calls this at SESSION start while the softIOC does not
    bind until MODULE setup, so that gap can be minutes wide.

    Measured consequence of losing the race (darwin, PyTango 10.3.0 era),
    which is narrower than it looks. EPICS uses this one number for BOTH
    its TCP server and its UDP name-search channel, and those are separate
    port namespaces:

      - A TCP thief is SURVIVABLE (6 of 6 forced trials): CAS falls back to
        another TCP port and UDP name search still resolves the PV, so the
        client is redirected and the fixture comes up green.
      - A UDP thief is FATAL (2 of 2 forced trials): name search goes
        unanswered, `wait_for_softioc_ready` times out, and every test in
        the module ERRORs at setup.

    So the exposure today is nil, and note the asymmetry before "fixing"
    this: `socket.socket()` is SOCK_STREAM, so holding this socket open
    would reserve the TCP number, which is the harmless case, and would
    still leave the UDP number (the fatal one) unreserved. Nothing in the
    test tier binds an ephemeral UDP port; `DeviceTestContext` in
    `test_tango_control_port.py` binds TCP via omniORB, the survivable
    case.

    Revisit when something here starts binding ephemeral UDP. The fix then
    is to reserve BOTH protocols on the number and hold them until the
    consumer binds, which for the softIOC means releasing immediately
    before `start_softioc` spawns the child that binds by number, and
    re-reserving once it exits.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def emit_db_file(target_dir: Path) -> Path:
    """Write the test PV `.db` file to `target_dir` and return the path."""
    db_path = target_dir / "cora_test.db"
    db_path.write_text(_DB_TEMPLATE)
    return db_path


def start_softioc(prefix: str, db_path: Path, *, log_dir: Path) -> subprocess.Popen[bytes]:
    """Spawn an `epicscorelibs.ioc` subprocess bound to the given prefix.

    The caller is responsible for setting `EPICS_CA_*` env vars in
    `os.environ` BEFORE invoking this (the subprocess inherits the
    parent's env, AND the parent's aioca client reads the same env
    vars at its first call). The corpus-canonical pattern is to set
    those env vars once per worker at session scope and never mutate
    them afterwards.

    softIOC stdout / stderr are redirected to `log_dir/softioc.{out,err}`.
    `wait_for_softioc_ready` surfaces their tail in the timeout
    RuntimeError so a bad `.db` doesn't manifest as an opaque 5s
    readiness failure (regression-pinned: a DESC-too-long field in
    the implementing session was invisible until stderr was captured).

    Returns the live `Popen`. Caller terminates via
    `stop_softioc_cleanly`.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = (log_dir / "softioc.out").open("wb")
    stderr_log = (log_dir / "softioc.err").open("wb")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "epicscorelibs.ioc",
            "-m",
            f"P={prefix}",
            "-d",
            str(db_path),
        ],
        stdin=subprocess.PIPE,
        stdout=stdout_log,
        stderr=stderr_log,
    )


def _tail_softioc_log(log_dir: Path, *, max_chars: int = 800) -> str:
    """Read the last `max_chars` of softioc.err for error surfacing."""
    err_path = log_dir / "softioc.err"
    if not err_path.exists():
        return ""
    try:
        text = err_path.read_text(errors="replace")
    except OSError:
        return ""
    return text[-max_chars:]


async def wait_for_softioc_ready(
    prefix: str,
    *,
    log_dir: Path,
    deadline_s: float = 5.0,
) -> None:
    """Poll a known PV via caget until it responds, or `deadline_s` elapses.

    softIOC's TCP listener accepts well before the database is fully
    loaded; only a real caget reliably indicates readiness. A short
    timeout per attempt + retry loop keeps the worst-case startup
    bounded to ~5s even on a loaded CI worker. On timeout, the
    RuntimeError carries the tail of softioc.err so a bad `.db` is
    debuggable without inspecting the log file separately.
    """
    from aioca import FORMAT_TIME, CANothing, caget

    deadline = asyncio.get_running_loop().time() + deadline_s
    last_error: Exception | None = None
    while asyncio.get_running_loop().time() < deadline:
        try:
            await caget(f"{prefix}double_value", format=FORMAT_TIME, timeout=0.2)
        except CANothing as exc:
            last_error = exc
            await asyncio.sleep(0.05)
            continue
        except TimeoutError as exc:
            last_error = exc
            await asyncio.sleep(0.05)
            continue
        else:
            return
    msg = f"softIOC for prefix {prefix!r} did not become ready within {deadline_s}s"
    if last_error is not None:
        msg = f"{msg} (last error: {last_error!r})"
    stderr_tail = _tail_softioc_log(log_dir)
    if stderr_tail:
        msg = f"{msg}\nsoftioc.err tail:\n{stderr_tail}"
    raise RuntimeError(msg)


async def stop_softioc_cleanly(process: subprocess.Popen[bytes]) -> None:
    """Tell softIOC to exit cleanly; escalate to SIGTERM then SIGKILL.

    Per [[project_control_port_test_isolation_research]] (ophyd-async
    pattern), call `aioca.purge_channel_caches()` BEFORE this helper
    so subscriptions don't error on teardown. This helper assumes the
    caller has already done that.

    Escalation: stdin `exit\\n` (3s) -> `terminate()` SIGTERM (2s) ->
    `kill()` SIGKILL (1s). Without the SIGKILL terminal step a softIOC
    that ignores SIGTERM (rare but possible if signal handlers
    misbehave) becomes an orphan; the terminal kill prevents that.
    """
    with contextlib.suppress(Exception):
        process.stdin.write(b"exit\n")  # type: ignore[union-attr]
        process.stdin.flush()  # type: ignore[union-attr]
    try:
        process.wait(timeout=3.0)
        return
    except subprocess.TimeoutExpired:
        pass
    process.terminate()
    try:
        process.wait(timeout=2.0)
        return
    except subprocess.TimeoutExpired:
        pass
    process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=1.0)
