"""Unit tests for the F2 preflight read command.

Drives `preflight_read_capture_pvs` against a scripted fake `ControlPort`
(read-only; this command never calls `.write()` or `.subscribe()`, so the
fake implements `.read()` only). Covers the historical defect shapes
(`AbortScan` an ENUM label, `ImagesSaved` a `"<done>/<total>"` string) as
regression coverage confirming they now decode clean, plus the connectivity
and decode-rejection paths this command exists to surface.
"""

from datetime import UTC, datetime

import pytest

from cora.api.capture_watch_preflight import (
    _EXIT_CLEAN,  # pyright: ignore[reportPrivateUsage]
    _EXIT_PROBLEM,  # pyright: ignore[reportPrivateUsage]
    _finish,  # pyright: ignore[reportPrivateUsage]
    _Report,  # pyright: ignore[reportPrivateUsage]
    build_parser,
    main,
    preflight_read_capture_pvs,
)
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    Measurement,
)

_T = datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC)

_PHASES = {
    "Beginning scan": "Begun",
    "Collecting projections": "Progressing",
    "Scan complete": "Ended",
    "Scan aborted": "Aborted",
}


def _reading(value: object, kind: str = "Scalar") -> Measurement:
    return Measurement(value=value, kind=kind, quality="Good", produced_at=_T)  # type: ignore[arg-type]


class _FakeControlPort:
    """Scripted `read()`-only fake. F2 never writes or subscribes."""

    def __init__(self, script: dict[str, Measurement | Exception]) -> None:
        self._script = script

    async def read(self, address: str) -> Measurement:
        outcome = self._script[address]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def _preflight(
    port: _FakeControlPort,
    capture_pvs: dict[str, dict[str, str]],
    *,
    status_phases: dict[str, str] | None = None,
) -> _Report:
    """`_FakeControlPort` implements `.read()` only (this command never
    writes or subscribes), so it satisfies `ControlPort` in practice but
    not structurally; the ignore mirrors `test_capture_observer.py`'s own
    `_observer` helper for the same fake-vs-Protocol gap."""
    return await preflight_read_capture_pvs(
        control_port=port,  # type: ignore[arg-type]
        capture_pvs=capture_pvs,
        status_phases=status_phases if status_phases is not None else _PHASES,
    )


_CAPTURE_PVS = {
    "2bmb-tomoscan": {
        "status": "2bmb:TomoScan:ScanStatus",
        "abort": "2bmb:TomoScan:AbortScan",
        "images_saved": "2bmb:TomoScan:ImagesSaved",
        "images_collected": "2bmb:TomoScan:ImagesCollected",
        "server_running": "2bmb:TomoScan:ServerRunning",
        "testing": "2bmb:TomoScan:Testing",
    }
}


@pytest.mark.unit
async def test_preflight_read_happy_path_every_role_connects_and_decodes_ok() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ScanStatus": _reading("Collecting projections", kind="Categorical"),
            "2bmb:TomoScan:AbortScan": _reading("No", kind="Categorical"),
            "2bmb:TomoScan:ImagesSaved": _reading("120/500"),
            "2bmb:TomoScan:ImagesCollected": _reading("120/500"),
            "2bmb:TomoScan:ServerRunning": _reading("Yes", kind="Categorical"),
            "2bmb:TomoScan:Testing": _reading("Yes", kind="Categorical"),
        }
    )

    report = await _preflight(port, _CAPTURE_PVS)

    assert not report.problem
    assert len(report.lines) == 6
    assert all(line.ok for line in report.lines)


@pytest.mark.unit
async def test_preflight_read_abort_role_enum_label_no_decodes_as_clear_not_asserted() -> None:
    """Regression for the shipped defect: 2-BM's `AbortScan` is a DBR_ENUM
    resolving to the label `'No'`, not `0`; `bool('No')` is `True`, so this
    pins that the decoder (not Python truthiness) governs the verdict."""
    port = _FakeControlPort({"pv:abort": _reading("No", kind="Categorical")})

    report = await _preflight(port, {"code": {"abort": "pv:abort"}})

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "clear"


@pytest.mark.unit
async def test_preflight_read_progress_role_slash_string_decodes_reached_and_total() -> None:
    """Regression for the shipped defect: `ImagesSaved` / `ImagesCollected`
    are `stringout` records carrying `"<reached>/<commanded>"`, not a bare
    float."""
    port = _FakeControlPort({"pv:saved": _reading("120/500")})

    report = await _preflight(port, {"code": {"images_saved": "pv:saved"}})

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "reached=120.0 commanded_total=500.0"


@pytest.mark.unit
async def test_preflight_read_array_kind_reading_reports_kind_and_element_count() -> None:
    """A role whose reading arrives as an Array (not the Scalar/Categorical
    a decoder expects) is exactly the shape class this command exists to
    surface; the report must show the kind and length, not just the value."""
    port = _FakeControlPort({"pv:status": _reading((5,), kind="Array")})

    report = await _preflight(port, {"code": {"status": "pv:status"}})

    (line,) = report.lines
    assert line.kind == "Array"
    assert line.element_count == 1
    assert not line.ok  # str((5,)) matches no declared phase literal


@pytest.mark.unit
async def test_preflight_read_status_role_unrecognized_literal_is_bad() -> None:
    port = _FakeControlPort({"pv:status": _reading("Some new status", kind="Categorical")})

    report = await _preflight(port, {"code": {"status": "pv:status"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "Unrecognized"


@pytest.mark.unit
async def test_preflight_read_abort_role_unrecognized_token_is_bad() -> None:
    port = _FakeControlPort({"pv:abort": _reading("Halted", kind="Categorical")})

    report = await _preflight(port, {"code": {"abort": "pv:abort"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "unrecognized"


@pytest.mark.unit
async def test_preflight_read_testing_role_enum_label_no_decodes_as_real_not_asserted() -> None:
    """Same regression class as the `abort` role: 2-BM's `Testing` is the
    identical `DBR_ENUM` record type, resolving to the label `'No'` for a
    real acquisition, and `bool('No')` is `True`."""
    port = _FakeControlPort({"pv:testing": _reading("No", kind="Categorical")})

    report = await _preflight(port, {"code": {"testing": "pv:testing"}})

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "real"


@pytest.mark.unit
async def test_preflight_read_testing_role_enum_label_yes_decodes_as_testing() -> None:
    port = _FakeControlPort({"pv:testing": _reading("Yes", kind="Categorical")})

    report = await _preflight(port, {"code": {"testing": "pv:testing"}})

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "testing"


@pytest.mark.unit
async def test_preflight_read_testing_role_unrecognized_token_is_bad() -> None:
    port = _FakeControlPort({"pv:testing": _reading("Halted", kind="Categorical")})

    report = await _preflight(port, {"code": {"testing": "pv:testing"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "unrecognized"


@pytest.mark.unit
async def test_preflight_read_progress_role_non_numeric_is_bad() -> None:
    port = _FakeControlPort({"pv:saved": _reading("garbled")})

    report = await _preflight(port, {"code": {"images_saved": "pv:saved"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "unrecognized"


@pytest.mark.unit
async def test_preflight_read_role_with_no_decoder_reports_na_and_is_ok() -> None:
    """`server_running` is declared-and-unread in production too; F2 must
    not invent a decoder for it, just report what it can (kind/value)."""
    port = _FakeControlPort({"pv:running": _reading("Yes", kind="Categorical")})

    report = await _preflight(port, {"code": {"server_running": "pv:running"}})

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "n/a"


@pytest.mark.unit
async def test_preflight_read_not_connected_pv_reports_bad_without_aborting_the_sweep() -> None:
    port = _FakeControlPort(
        {
            "pv:good": _reading("Scan complete", kind="Categorical"),
            "pv:dead": ControlNotConnectedError("pv:dead"),
        }
    )

    report = await _preflight(port, {"code": {"status": "pv:good", "abort": "pv:dead"}})

    assert len(report.lines) == 2
    by_role = {line.role: line for line in report.lines}
    assert not by_role["abort"].ok
    assert not by_role["abort"].connected
    assert by_role["status"].ok


@pytest.mark.unit
async def test_preflight_read_timeout_reports_bad() -> None:
    port = _FakeControlPort({"pv:slow": ControlTimeoutError("pv:slow", 5.0)})

    report = await _preflight(port, {"code": {"status": "pv:slow"}})

    (line,) = report.lines
    assert not line.ok
    assert not line.connected


@pytest.mark.unit
async def test_preflight_read_access_denied_reports_bad() -> None:
    port = _FakeControlPort({"pv:locked": ControlAccessDeniedError("pv:locked")})

    report = await _preflight(port, {"code": {"status": "pv:locked"}})

    (line,) = report.lines
    assert not line.ok
    assert not line.connected


@pytest.mark.unit
async def test_preflight_read_value_coercion_error_reports_bad_but_connected() -> None:
    port = _FakeControlPort(
        {"pv:weird": ControlValueCoercionError("pv:weird", "structured", "Scalar")}
    )

    report = await _preflight(port, {"code": {"status": "pv:weird"}})

    (line,) = report.lines
    assert not line.ok
    assert line.connected


@pytest.mark.unit
async def test_preflight_read_empty_capture_pvs_reports_no_lines() -> None:
    report = await _preflight(_FakeControlPort({}), {})

    assert report.lines == []
    assert not report.problem


@pytest.mark.unit
async def test_finish_exit_code_zero_when_every_line_is_ok(
    capsys: pytest.CaptureFixture[str],
) -> None:
    port = _FakeControlPort({"pv:status": _reading("Scan complete", kind="Categorical")})
    report = await _preflight(port, {"code": {"status": "pv:status"}})

    assert _finish(report) == _EXIT_CLEAN
    assert "1/1 PVs OK" in capsys.readouterr().out


@pytest.mark.unit
async def test_finish_exit_code_problem_when_any_line_is_bad(
    capsys: pytest.CaptureFixture[str],
) -> None:
    port = _FakeControlPort({"pv:status": ControlNotConnectedError("pv:status")})
    report = await _preflight(port, {"code": {"status": "pv:status"}})

    assert _finish(report) == _EXIT_PROBLEM
    assert "NOT CONNECTED" in capsys.readouterr().out


@pytest.mark.unit
def test_finish_exit_code_clean_when_no_pvs_are_configured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _finish(_Report()) == _EXIT_CLEAN
    assert "no PVs configured" in capsys.readouterr().out


@pytest.mark.unit
def test_build_parser_accepts_no_arguments() -> None:
    args = build_parser().parse_args([])
    assert args is not None


@pytest.mark.unit
def test_main_with_no_configured_pvs_builds_the_real_wiring_and_exits_clean(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercises `main`'s actual composition (`Settings()` +
    `build_control_port`), not a fake: with no `CAPTURE_WATCH_PVS` /
    `CONTROL_PORT_ROUTES` configured, `build_control_port` returns the
    empty-routes `InMemoryControlPort`, the sweep has nothing to read, and
    `main` still runs its full `_run` / `aclose` path end to end."""
    monkeypatch.delenv("CAPTURE_WATCH_PVS", raising=False)
    monkeypatch.delenv("CONTROL_PORT_ROUTES", raising=False)

    assert main([]) == _EXIT_CLEAN
    assert "no PVs configured" in capsys.readouterr().out
