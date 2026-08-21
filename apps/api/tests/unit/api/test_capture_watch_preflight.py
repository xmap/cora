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


def _reading(value: object, kind: str = "Scalar", units: str | None = None) -> Measurement:
    return Measurement(
        value=value,
        kind=kind,  # type: ignore[arg-type]
        quality="Good",
        produced_at=_T,
        units=units,
    )


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
    baseline_pvs: dict[str, dict[str, str]] | None = None,
    experiment_identity_pvs: dict[str, dict[str, str]] | None = None,
    camera_select_prefixes: dict[str, str] | None = None,
) -> _Report:
    """`_FakeControlPort` implements `.read()` only (this command never
    writes or subscribes), so it satisfies `ControlPort` in practice but
    not structurally; the ignore mirrors `test_capture_observer.py`'s own
    `_observer` helper for the same fake-vs-Protocol gap."""
    return await preflight_read_capture_pvs(
        control_port=port,  # type: ignore[arg-type]
        capture_pvs=capture_pvs,
        status_phases=status_phases if status_phases is not None else _PHASES,
        baseline_pvs=baseline_pvs,
        experiment_identity_pvs=experiment_identity_pvs,
        camera_select_prefixes=camera_select_prefixes,
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
async def test_preflight_read_full_file_name_role_redacts_the_real_value() -> None:
    """The one role whose printed `value` is REDACTED: `observed_path`
    is personal data (see `_capture_observer.py`). `kind` stays real."""
    port = _FakeControlPort({"pv:file": _reading("/data/2026-01-Smith-12345/scan_001.h5")})

    report = await _preflight(port, {"code": {"full_file_name": "pv:file"}})

    (line,) = report.lines
    assert line.ok
    assert "Smith" not in str(line.value)
    assert "Smith" not in line.render()
    assert line.value == "<redacted, len=37>"
    assert line.verdict == "text(len=37)"


@pytest.mark.unit
async def test_preflight_read_full_file_name_role_empty_string_is_ok() -> None:
    """The fresh-IOC-boot state: a fine, ordinary outcome, not a
    connectivity or decode problem."""
    port = _FakeControlPort({"pv:file": _reading("")})

    report = await _preflight(port, {"code": {"full_file_name": "pv:file"}})

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "empty"
    assert line.value == "<redacted, len=0>"


@pytest.mark.unit
async def test_preflight_read_full_file_name_role_suspected_truncated_is_bad() -> None:
    from cora.api._capture_observer import FULL_FILE_NAME_TRUNCATION_THRESHOLD

    long_path = "/" + ("a" * (FULL_FILE_NAME_TRUNCATION_THRESHOLD - 1))
    port = _FakeControlPort({"pv:file": _reading(long_path)})

    report = await _preflight(port, {"code": {"full_file_name": "pv:file"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "suspected-truncated"
    assert "a" * 10 not in str(line.value)  # never the real (redacted) content


@pytest.mark.unit
async def test_preflight_read_full_file_name_role_just_under_the_threshold_is_ok() -> None:
    from cora.api._capture_observer import FULL_FILE_NAME_TRUNCATION_THRESHOLD

    ok_path = "/" + ("a" * (FULL_FILE_NAME_TRUNCATION_THRESHOLD - 2))
    port = _FakeControlPort({"pv:file": _reading(ok_path)})

    report = await _preflight(port, {"code": {"full_file_name": "pv:file"}})

    (line,) = report.lines
    assert line.ok
    assert line.verdict == f"text(len={FULL_FILE_NAME_TRUNCATION_THRESHOLD - 1})"


@pytest.mark.unit
async def test_preflight_read_full_file_name_role_non_text_is_bad() -> None:
    port = _FakeControlPort({"pv:file": _reading(0)})

    report = await _preflight(port, {"code": {"full_file_name": "pv:file"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "non-text"
    assert line.value == "<redacted, non-text>"


@pytest.mark.unit
async def test_preflight_read_camera_prefix_check_matching_camera_is_ok() -> None:
    """The 2026-08-20 incident's happy path: `full_file_name` is
    configured for `2bmSP2:`, and the live `camera_selected` reading
    resolves (via the deployment's own table) to that same prefix."""
    port = _FakeControlPort(
        {
            "2bmSP2:HDF1:FullFileName_RBV": _reading("/local1/2BM/2026-08-exp/scan_0001.h5"),
            "2bm:MCTOptics:CameraSelected": _reading("1", kind="Categorical"),
        }
    )

    report = await _preflight(
        port,
        {
            "code": {
                "full_file_name": "2bmSP2:HDF1:FullFileName_RBV",
                "camera_selected": "2bm:MCTOptics:CameraSelected",
            }
        },
        camera_select_prefixes={"0": "2bmSP1:", "1": "2bmSP2:"},
    )

    by_key = {line.pv_key: line for line in report.lines}
    check = by_key["camera_prefix_check"]
    assert check.ok
    assert check.verdict == "match"


@pytest.mark.unit
async def test_preflight_read_camera_prefix_check_wrong_camera_selected_is_a_mismatch() -> None:
    """The actual 2026-08-20 shape: the operator switched to camera 0,
    but `full_file_name` is still hardcoded to camera 1's PV prefix."""
    port = _FakeControlPort(
        {
            "2bmSP2:HDF1:FullFileName_RBV": _reading("/local1/2BM/2026-08-exp/scan_0001.h5"),
            "2bm:MCTOptics:CameraSelected": _reading("0", kind="Categorical"),
        }
    )

    report = await _preflight(
        port,
        {
            "code": {
                "full_file_name": "2bmSP2:HDF1:FullFileName_RBV",
                "camera_selected": "2bm:MCTOptics:CameraSelected",
            }
        },
        camera_select_prefixes={"0": "2bmSP1:", "1": "2bmSP2:"},
    )

    by_key = {line.pv_key: line for line in report.lines}
    check = by_key["camera_prefix_check"]
    assert not check.ok
    assert check.verdict == "mismatch(selected camera expects '2bmSP1:')"


@pytest.mark.unit
async def test_preflight_read_camera_prefix_check_unreadable_camera_pv_is_bad_not_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmSP2:HDF1:FullFileName_RBV": _reading("/local1/2BM/2026-08-exp/scan_0001.h5"),
            "2bm:MCTOptics:CameraSelected": ControlNotConnectedError(
                "2bm:MCTOptics:CameraSelected"
            ),
        }
    )

    report = await _preflight(
        port,
        {
            "code": {
                "full_file_name": "2bmSP2:HDF1:FullFileName_RBV",
                "camera_selected": "2bm:MCTOptics:CameraSelected",
            }
        },
        camera_select_prefixes={"0": "2bmSP1:", "1": "2bmSP2:"},
    )

    by_key = {line.pv_key: line for line in report.lines}
    check = by_key["camera_prefix_check"]
    assert not check.ok
    assert not check.connected


@pytest.mark.unit
async def test_preflight_read_camera_prefix_check_empty_prefix_table_reports_not_configured() -> (
    None
):
    """No `CAPTURE_CAMERA_SELECT_PREFIXES` declared yet: must report
    that the check cannot confirm anything, never a silent pass."""
    port = _FakeControlPort(
        {
            "2bmSP2:HDF1:FullFileName_RBV": _reading("/local1/2BM/2026-08-exp/scan_0001.h5"),
            "2bm:MCTOptics:CameraSelected": _reading("1", kind="Categorical"),
        }
    )

    report = await _preflight(
        port,
        {
            "code": {
                "full_file_name": "2bmSP2:HDF1:FullFileName_RBV",
                "camera_selected": "2bm:MCTOptics:CameraSelected",
            }
        },
    )

    by_key = {line.pv_key: line for line in report.lines}
    check = by_key["camera_prefix_check"]
    assert not check.ok
    assert check.verdict == "not-configured(CAPTURE_CAMERA_SELECT_PREFIXES empty)"


@pytest.mark.unit
async def test_preflight_read_camera_prefix_check_unrecognized_reading_is_bad() -> None:
    """A `camera_selected` reading absent from the deployment's own
    table: the mapping is deployment-declared vocabulary, so an
    unrecognized reading is reported plainly, never guessed at."""
    port = _FakeControlPort(
        {
            "2bmSP2:HDF1:FullFileName_RBV": _reading("/local1/2BM/2026-08-exp/scan_0001.h5"),
            "2bm:MCTOptics:CameraSelected": _reading("Camera 1", kind="Categorical"),
        }
    )

    report = await _preflight(
        port,
        {
            "code": {
                "full_file_name": "2bmSP2:HDF1:FullFileName_RBV",
                "camera_selected": "2bm:MCTOptics:CameraSelected",
            }
        },
        camera_select_prefixes={"0": "2bmSP1:", "1": "2bmSP2:"},
    )

    by_key = {line.pv_key: line for line in report.lines}
    check = by_key["camera_prefix_check"]
    assert not check.ok
    assert check.verdict == "unrecognized-reading('Camera 1')"


@pytest.mark.unit
async def test_preflight_read_camera_prefix_check_skipped_without_camera_selected_role() -> None:
    """A code with `full_file_name` alone (no `camera_selected` role
    declared) gets no cross-check line: this is the pre-existing
    behavior for every deployment that has not yet opted in."""
    port = _FakeControlPort({"pv:file": _reading("2bmSP2:HDF1:FullFileName_RBV")})

    report = await _preflight(port, {"code": {"full_file_name": "pv:file"}})

    assert "camera_prefix_check" not in {line.pv_key for line in report.lines}


@pytest.mark.unit
async def test_preflight_read_a_mis_keyed_role_with_a_path_value_still_redacts() -> None:
    """Defense-in-depth: a `capture_watch_pvs` role-key typo
    (`"full_filename"` instead of `"full_file_name"`) falls through to
    the generic unknown-role branch (verdict `n/a`), which must NOT
    print the real path just because the role name didn't match --
    this preflight tool is exactly what an operator runs, screenshots,
    and pastes into a ticket while debugging that kind of typo."""
    port = _FakeControlPort({"pv:file": _reading("/data/2026-01-Smith-12345/scan_001.h5")})

    report = await _preflight(port, {"code": {"full_filename": "pv:file"}})

    (line,) = report.lines
    assert line.pv_key == "full_filename"
    assert line.verdict == "n/a"
    assert "Smith" not in str(line.value)
    assert "Smith" not in line.render()
    assert line.value == "<redacted, len=37>"


@pytest.mark.unit
async def test_preflight_read_baseline_full_file_name_pv_misdeclared_still_redacts() -> None:
    """Same defense, for the OTHER wrong-dict mistake: the
    `full_file_name` PV declared under `capture_baseline_pvs` instead
    of `capture_watch_pvs`."""
    port = _FakeControlPort({"pv:file": _reading("/data/2026-01-Smith-12345/scan_001.h5")})

    report = await _preflight(port, {}, baseline_pvs={"code": {"FullFileName": "pv:file"}})

    (line,) = report.lines
    assert "Smith" not in str(line.value)
    assert "Smith" not in line.render()
    assert line.value == "<redacted, len=37>"


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
    by_role = {line.pv_key: line for line in report.lines}
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


# ---------------------------------------------------------------------------
# capture_baseline_pvs sweep (slice 12): no per-channel decoder, verdict
# n/a unless the value is non-numeric.
# ---------------------------------------------------------------------------

_BASELINE_PVS = {
    "2bmb-tomoscan": {
        "ExposureTime": "2bmb:TomoScan:ExposureTime",
        "NumAngles": "2bmb:TomoScan:NumAngles",
    }
}


@pytest.mark.unit
async def test_preflight_read_baseline_numeric_reading_is_ok_with_na_verdict() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(1.5, units="s"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )

    report = await _preflight(port, {}, baseline_pvs=_BASELINE_PVS)

    assert len(report.lines) == 2
    assert all(line.ok for line in report.lines)
    assert all(line.verdict == "n/a" for line in report.lines)
    assert all(line.group == "baseline" for line in report.lines)
    by_role = {line.pv_key: line for line in report.lines}
    assert by_role["ExposureTime"].units == "s"
    assert by_role["NumAngles"].units is None


@pytest.mark.unit
async def test_preflight_read_baseline_ignores_quality_and_produced_at_unlike_the_real_reader() -> (
    None
):
    """The real `CaptureBaselineReader` rejects Bad quality and a missing
    substrate time; this preflight sweep has no such rules, since it
    exists only to catch the one defect checkable ahead of time
    (non-numeric). A Bad-quality or timestamp-less reading here must
    still report `ok=True, verdict="n/a"` -- the contrast this module's
    own docstring advertises."""
    port = _FakeControlPort(
        {
            "pv:bad-quality": Measurement(value=1.5, kind="Scalar", quality="Bad", produced_at=_T),
            "pv:no-time": Measurement(value=2.5, kind="Scalar", quality="Good", produced_at=None),
        }
    )

    report = await _preflight(
        port,
        {},
        baseline_pvs={
            "code": {"BadQuality": "pv:bad-quality", "NoTime": "pv:no-time"},
        },
    )

    assert len(report.lines) == 2
    assert all(line.ok for line in report.lines)
    assert all(line.verdict == "n/a" for line in report.lines)


@pytest.mark.unit
async def test_preflight_read_baseline_non_numeric_reading_is_bad() -> None:
    """`Observation.value` is `float`; a textual baseline reading is the
    one defect this sweep can catch ahead of a real append attempt."""
    port = _FakeControlPort({"pv:exp": _reading("garbled")})

    report = await _preflight(port, {}, baseline_pvs={"code": {"ExposureTime": "pv:exp"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "non-numeric"
    assert line.group == "baseline"


@pytest.mark.unit
async def test_preflight_read_baseline_categorical_reading_reports_resolved_label() -> None:
    """A `Categorical` baseline PV (an EPICS mbbo/bo scan-configuration
    PV) must stop being flagged BAD for being non-numeric: it reports
    the resolved label as an OK verdict, since `CaptureBaselineReader`
    stores that label directly."""
    port = _FakeControlPort({"pv:scantype": _reading("Fly", kind="Categorical")})

    report = await _preflight(port, {}, baseline_pvs={"code": {"ScanType": "pv:scantype"}})

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "label='Fly'"
    assert line.group == "baseline"


@pytest.mark.unit
async def test_preflight_read_baseline_categorical_non_text_value_is_bad() -> None:
    port = _FakeControlPort({"pv:scantype": _reading(1, kind="Categorical")})

    report = await _preflight(port, {}, baseline_pvs={"code": {"ScanType": "pv:scantype"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "non-text"


@pytest.mark.unit
async def test_preflight_read_baseline_categorical_over_length_label_is_bad() -> None:
    from cora.run.aggregates.run import READING_CATEGORICAL_VALUE_MAX_LENGTH

    port = _FakeControlPort(
        {
            "pv:scantype": _reading(
                "x" * (READING_CATEGORICAL_VALUE_MAX_LENGTH + 1), kind="Categorical"
            )
        }
    )

    report = await _preflight(port, {}, baseline_pvs={"code": {"ScanType": "pv:scantype"}})

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "label-too-long"


@pytest.mark.unit
async def test_preflight_read_baseline_not_connected_pv_reports_bad() -> None:
    port = _FakeControlPort({"pv:dead": ControlNotConnectedError("pv:dead")})

    report = await _preflight(port, {}, baseline_pvs={"code": {"ExposureTime": "pv:dead"}})

    (line,) = report.lines
    assert not line.ok
    assert not line.connected
    assert line.group == "baseline"


@pytest.mark.unit
async def test_preflight_read_baseline_alongside_watch_pvs_reports_both_groups() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ScanStatus": _reading("Scan complete", kind="Categorical"),
            "2bmb:TomoScan:ExposureTime": _reading(1.5),
        }
    )

    report = await _preflight(
        port,
        {"2bmb-tomoscan": {"status": "2bmb:TomoScan:ScanStatus"}},
        baseline_pvs={"2bmb-tomoscan": {"ExposureTime": "2bmb:TomoScan:ExposureTime"}},
    )

    assert len(report.lines) == 2
    groups = {line.group for line in report.lines}
    assert groups == {"watch", "baseline"}


@pytest.mark.unit
async def test_preflight_read_empty_baseline_pvs_reports_no_baseline_lines() -> None:
    report = await _preflight(_FakeControlPort({}), {}, baseline_pvs={})

    assert report.lines == []


# ---------------------------------------------------------------------------
# capture_experiment_identity_pvs sweep (slice 14a): "Unknown" and empty
# are visible, distinct, non-BAD verdicts; only a non-text reading is BAD.
# ---------------------------------------------------------------------------

_EXPERIMENT_IDENTITY_PVS = {
    "2bmb-tomoscan": {
        "proposal_number": "2bmb:TomoScan:ProposalNumber",
        "esaf_number": "2bmb:TomoScan:ESAFNumber",
        "esaf_doi_number": "2bmb:TomoScan:ESAFDOINumber",
    }
}


@pytest.mark.unit
async def test_preflight_read_identity_real_value_decodes_ok_with_length_verdict() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": _reading("12345"),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("10.1234/esaf.67890"),
        }
    )

    report = await _preflight(port, {}, experiment_identity_pvs=_EXPERIMENT_IDENTITY_PVS)

    assert len(report.lines) == 3
    assert all(line.ok for line in report.lines)
    assert all(line.group == "experiment_identity" for line in report.lines)
    by_role = {line.pv_key: line for line in report.lines}
    assert by_role["proposal_number"].verdict == "text(len=5)"
    assert by_role["proposal_number"].value == "12345"
    assert by_role["esaf_doi_number"].verdict == "text(len=18)"


@pytest.mark.unit
async def test_preflight_read_identity_unknown_literal_is_a_distinct_ok_verdict() -> None:
    """Trap 1: the substrate's own placeholder must never look like a
    healthy, generic reading -- this is the single highest-value thing
    this preflight can say about these PVs."""
    port = _FakeControlPort({"2bmb:TomoScan:ProposalNumber": _reading("Unknown")})

    report = await _preflight(
        port,
        {},
        experiment_identity_pvs={"code": {"proposal_number": "2bmb:TomoScan:ProposalNumber"}},
    )

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "placeholder"


@pytest.mark.unit
async def test_preflight_read_identity_empty_string_is_ok_with_empty_verdict() -> None:
    port = _FakeControlPort({"2bmb:TomoScan:ProposalNumber": _reading("")})

    report = await _preflight(
        port,
        {},
        experiment_identity_pvs={"code": {"proposal_number": "2bmb:TomoScan:ProposalNumber"}},
    )

    (line,) = report.lines
    assert line.ok
    assert line.verdict == "empty"


@pytest.mark.unit
async def test_preflight_read_identity_non_text_is_bad() -> None:
    port = _FakeControlPort({"2bmb:TomoScan:ProposalNumber": _reading(12345)})

    report = await _preflight(
        port,
        {},
        experiment_identity_pvs={"code": {"proposal_number": "2bmb:TomoScan:ProposalNumber"}},
    )

    (line,) = report.lines
    assert not line.ok
    assert line.verdict == "non-text"


@pytest.mark.unit
async def test_preflight_read_identity_not_connected_pv_reports_bad() -> None:
    port = _FakeControlPort({"pv:dead": ControlNotConnectedError("pv:dead")})

    report = await _preflight(
        port, {}, experiment_identity_pvs={"code": {"proposal_number": "pv:dead"}}
    )

    (line,) = report.lines
    assert not line.ok
    assert not line.connected
    assert line.group == "experiment_identity"


@pytest.mark.unit
async def test_preflight_read_identity_value_coercion_error_reports_bad_but_connected() -> None:
    port = _FakeControlPort({"pv:bad": ControlValueCoercionError("pv:bad", "structured", "Scalar")})

    report = await _preflight(
        port, {}, experiment_identity_pvs={"code": {"proposal_number": "pv:bad"}}
    )

    (line,) = report.lines
    assert not line.ok
    assert line.connected


@pytest.mark.unit
async def test_preflight_read_identity_mis_keyed_role_with_a_path_value_still_redacts() -> None:
    """Defense-in-depth: a `full_file_name` PV accidentally declared
    under `capture_experiment_identity_pvs` must not print its real,
    personal-data-bearing value here, even though none of the three
    real identity roles is itself sensitive."""
    port = _FakeControlPort({"pv:misdeclared": _reading("/data/2026-01-Smith-12345/scan.h5")})

    report = await _preflight(
        port, {}, experiment_identity_pvs={"code": {"proposal_number": "pv:misdeclared"}}
    )

    (line,) = report.lines
    assert isinstance(line.value, str)
    assert line.value.startswith("<redacted")


@pytest.mark.unit
async def test_preflight_read_identity_alongside_watch_and_baseline_reports_all_three_groups() -> (
    None
):
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ScanStatus": _reading("Scan complete", kind="Categorical"),
            "2bmb:TomoScan:ExposureTime": _reading(1.5),
            "2bmb:TomoScan:ProposalNumber": _reading("12345"),
        }
    )

    report = await _preflight(
        port,
        {"2bmb-tomoscan": {"status": "2bmb:TomoScan:ScanStatus"}},
        baseline_pvs={"2bmb-tomoscan": {"ExposureTime": "2bmb:TomoScan:ExposureTime"}},
        experiment_identity_pvs={
            "2bmb-tomoscan": {"proposal_number": "2bmb:TomoScan:ProposalNumber"}
        },
    )

    assert len(report.lines) == 3
    groups = {line.group for line in report.lines}
    assert groups == {"watch", "baseline", "experiment_identity"}


@pytest.mark.unit
async def test_preflight_read_empty_experiment_identity_pvs_reports_no_lines() -> None:
    report = await _preflight(_FakeControlPort({}), {}, experiment_identity_pvs={})

    assert report.lines == []


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
