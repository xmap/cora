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
  - `enum_value`   (DBR_ENUM,   `mbbo` with 3 strings) -> `Measurement(kind="Categorical")`
  - `bad_quality_value` (`ao` with HIHI threshold tripped) -> `Measurement(quality="Bad")`

## areaDetector ADCore-shaped PVs for the acquisition action bodies

The `cam1:*` PV family mirrors areaDetector's ADCore PV convention so
`cora.operation.acquisitions.{collect,discrete,continuous}` can talk
real CA against this fixture. Acquire_RBV is seeded to `0` (always-Done
state); the body's poll loop exits on the first read. Real-detector
timing (Acquire_RBV staying 1 mid-flight) is exercised by the unit
tests via the IteratingPort fixture; this integration tier proves the
EPICS wire framing, not the detector finite-state machine.

  - `cam1:TriggerMode`        (mbbo: Internal / External)
  - `cam1:AcquireTime`        (ao,  per-acquisition seconds)
  - `cam1:NumImages`          (longout, bounded count)
  - `cam1:Acquire`            (bo,  start command)
  - `cam1:Acquire_RBV`        (longin, 0 = Done)
  - `cam1:DetectorState_RBV`  (mbbi: Idle / Acquiring / Error)

PV names are pure test-shape (`double_value`, etc.); they do NOT
mirror production EPICS conventions at APS 2-BM (`2bma:m1.RBV` etc.).

Writability: all records use the `*o` (output) variant so tests can
caput. `ao`/`longout`/`stringout`/`mbbo` are the EPICS-canonical
writable records; `waveform` is bidirectional by default.

`bad_quality_value`: VAL=99.9, HIHI=50, HHSV=MAJOR. Reading VAL > HIHI
trips MAJOR_ALARM naturally on every read. No startup hook needed
(softIOC doesn't have caproto-style decorators); the alarm is a
declarative consequence of the field values.

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

record(mbbo, "$(P)enum_value") {
  field(DESC, "DBR_ENUM with closed label set")
  field(DTYP, "Soft Channel")
  field(ZRST, "off")
  field(ONST, "on")
  field(TWST, "fault")
  field(VAL, "0")
  field(PINI, "YES")
}

record(ao, "$(P)bad_quality_value") {
  field(DESC, "MAJOR via HIHI tripped")
  field(DTYP, "Soft Channel")
  field(VAL, 99.9)
  field(HIHI, 50.0)
  field(HHSV, "MAJOR")
  field(PINI, "YES")
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
      "alarm": {+type:"meta", +channel:"SEVR"},
      "timeStamp": {+type:"meta", +channel:"TIME"}
    }
  })
}

# areaDetector ADCore PV family for collect / discrete / continuous
# action body integration tests. Acquire_RBV starts at 0 (Done) so the
# body's poll loop exits on the first read; the wire framing + record-
# routing assertions are what the integration tier is here to prove.

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

record(longin, "$(P)cam1:Acquire_RBV") {
  field(DESC, "Acquire status readback; 0 = done")
  field(DTYP, "Soft Channel")
  field(VAL, 0)
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
"""


def free_localhost_port() -> int:
    """Allocate a free loopback port via bind-and-close.

    The kernel never reissues an in-use port to a concurrent bind,
    so each xdist worker gets a distinct port even under `-n 4+`.
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
