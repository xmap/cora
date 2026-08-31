"""Unit tests for `CaptureBaselineReader` (cora.api._capture_baseline_reader).

Covers the one-shot read-every-channel-and-append-once contract, the
three per-reading skip rules (bad quality, no substrate time,
non-numeric), that one bad PV does not abort the sweep over the rest,
and that every failure mode -- a dead PV, an uncoercible reading, or
the append call itself -- is caught and logged rather than raised.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.api._capture_baseline_reader import CaptureBaselineReader
from cora.infrastructure.routing import NIL_SENTINEL_ID, SYSTEM_IN_PROCESS_SURFACE_ID
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    Measurement,
)
from cora.run.aggregates.run import RunObservationLogbookClosedError, RunStatus
from cora.run.errors import UnauthorizedError
from cora.run.features.append_observations.command import AppendObservations
from tests.unit._helpers import build_deps

_CODE = "2bmb-tomoscan"
_NOW = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-000000007112")
_PRINCIPAL_ID = uuid4()

_BASELINE_PVS = {
    _CODE: {
        "ExposureTime": "2bmb:TomoScan:ExposureTime",
        "NumAngles": "2bmb:TomoScan:NumAngles",
    }
}


def _reading(
    value: object = 1.0,
    *,
    kind: str = "Scalar",
    quality: str = "Good",
    produced_at: datetime | None = _NOW,
    units: str | None = None,
) -> Measurement:
    return Measurement(  # type: ignore[arg-type]
        value=value,
        kind=kind,  # type: ignore[arg-type]
        quality=quality,  # type: ignore[arg-type]
        produced_at=produced_at,
        units=units,
    )


class _FakeControlPort:
    """Scripted `read()`-only fake, mirroring the F2 preflight test's own."""

    def __init__(self, script: dict[str, Measurement | Exception]) -> None:
        self._script = script

    async def read(self, address: str) -> Measurement:
        outcome = self._script[address]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeAppendObservations:
    """Records every call; raises the scripted error, if any, when called."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[AppendObservations] = []
        self.surface_ids: list[UUID] = []
        self._raises = raises

    async def __call__(
        self,
        command: AppendObservations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        if self._raises is not None:
            raise self._raises
        self.calls.append(command)
        self.surface_ids.append(surface_id)
        return len(command.entries)


def _reader(
    *,
    control_port: _FakeControlPort,
    append_observations: _FakeAppendObservations | None = None,
    baseline_pvs: dict[str, dict[str, str]] | None = None,
) -> tuple[CaptureBaselineReader, _FakeAppendObservations]:
    append = append_observations if append_observations is not None else _FakeAppendObservations()
    reader = CaptureBaselineReader(
        deps=build_deps(ids=[uuid4() for _ in range(50)], now=_NOW),
        control_port=control_port,  # type: ignore[arg-type]
        baseline_pvs=baseline_pvs if baseline_pvs is not None else _BASELINE_PVS,
        append_observations=append,  # type: ignore[arg-type]
        principal_id=_PRINCIPAL_ID,
    )
    return reader, append


@pytest.mark.unit
async def test_read_baseline_appends_one_batch_for_every_declared_channel() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(1.5, units="s"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    command = append.calls[0]
    assert command.run_id == _RUN_ID
    channels = {(e.channel_name, e.value, e.units) for e in command.entries}
    assert channels == {
        ("ExposureTime", 1.5, "s"),
        ("NumAngles", 3000.0, None),
    }
    assert all(e.sampling_procedure == "baseline" for e in command.entries)
    assert all(e.is_simulated is False for e in command.entries)
    assert all(e.sampled_at == _NOW for e in command.entries)
    assert append.surface_ids == [SYSTEM_IN_PROCESS_SURFACE_ID], (
        "CaptureBaselineReader.read must pass the internal Surface, not "
        "fall through to NIL_SENTINEL_ID."
    )


@pytest.mark.unit
async def test_read_baseline_for_an_undeclared_code_is_a_no_op() -> None:
    reader, append = _reader(control_port=_FakeControlPort({}))

    await reader.read("some-other-code", _RUN_ID)

    assert append.calls == []


@pytest.mark.unit
async def test_read_baseline_with_no_channels_declared_for_the_code_is_a_no_op() -> None:
    reader, append = _reader(control_port=_FakeControlPort({}), baseline_pvs={_CODE: {}})

    await reader.read(_CODE, _RUN_ID)

    assert append.calls == []


@pytest.mark.unit
async def test_non_numeric_reading_is_skipped_but_the_rest_of_the_sweep_survives() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading("garbled"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_oversized_units_is_skipped_and_does_not_fail_the_rest_of_the_batch() -> None:
    """PostgresObservationStore.append writes the whole batch in one
    executemany call: a units string past the DB's CHECK bound would
    otherwise fail every OTHER reading in this same batch too, not just
    the offending channel. Rejected here, ahead of the batch."""
    from cora.run.aggregates.run import READING_UNITS_MAX_LENGTH

    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(1.5, units="x" * (READING_UNITS_MAX_LENGTH + 1)),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_categorical_reading_becomes_categorical_value_entry_not_numeric() -> None:
    """A `Categorical` reading (an EPICS mbbo/bo scan-configuration PV)
    carries the substrate's own enum label unchanged into
    `categorical_value`, leaving `value` unset -- never coerced through
    `finite_float`."""
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading("Fly", kind="Categorical"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    entries = {e.channel_name: e for e in append.calls[0].entries}
    assert entries["ExposureTime"].value is None
    assert entries["ExposureTime"].categorical_value == "Fly"
    assert entries["NumAngles"].value == 3000.0
    assert entries["NumAngles"].categorical_value is None


@pytest.mark.unit
async def test_categorical_reading_with_non_string_value_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(1, kind="Categorical"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_categorical_reading_with_empty_label_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading("", kind="Categorical"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_categorical_label_over_max_length_is_skipped() -> None:
    from cora.run.aggregates.run import READING_CATEGORICAL_VALUE_MAX_LENGTH

    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(
                "x" * (READING_CATEGORICAL_VALUE_MAX_LENGTH + 1), kind="Categorical"
            ),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_categorical_label_at_exactly_the_max_length_is_kept() -> None:
    from cora.run.aggregates.run import READING_CATEGORICAL_VALUE_MAX_LENGTH

    label = "x" * READING_CATEGORICAL_VALUE_MAX_LENGTH
    port = _FakeControlPort({"2bmb:TomoScan:ExposureTime": _reading(label, kind="Categorical")})
    reader, append = _reader(
        control_port=port, baseline_pvs={_CODE: {"ExposureTime": "2bmb:TomoScan:ExposureTime"}}
    )

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert append.calls[0].entries[0].categorical_value == label


@pytest.mark.unit
async def test_categorical_reading_with_oversized_units_is_skipped() -> None:
    """The units-too-long guard applies to categorical readings the
    same way it applies to numeric ones."""
    from cora.run.aggregates.run import READING_UNITS_MAX_LENGTH

    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(
                "Fly", kind="Categorical", units="x" * (READING_UNITS_MAX_LENGTH + 1)
            ),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_units_at_exactly_the_max_length_is_kept() -> None:
    from cora.run.aggregates.run import READING_UNITS_MAX_LENGTH

    port = _FakeControlPort(
        {"2bmb:TomoScan:ExposureTime": _reading(1.5, units="x" * READING_UNITS_MAX_LENGTH)}
    )
    reader, append = _reader(
        control_port=port, baseline_pvs={_CODE: {"ExposureTime": "2bmb:TomoScan:ExposureTime"}}
    )

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert append.calls[0].entries[0].units == "x" * READING_UNITS_MAX_LENGTH


@pytest.mark.unit
async def test_bad_quality_reading_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(1.5, quality="Bad"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_uncertain_quality_reading_is_kept_not_skipped() -> None:
    """Only Bad is untrustworthy; a MAJOR/MINOR-collapsed Uncertain
    reading is still a believable value per the alarm-vs-fault split
    shipped elsewhere in this codebase."""
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(1.5, quality="Uncertain"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert {e.channel_name for e in append.calls[0].entries} == {"ExposureTime", "NumAngles"}


@pytest.mark.unit
async def test_reading_with_no_substrate_time_is_skipped_not_synthesized() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading(1.5, produced_at=None),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_every_reading_skipped_writes_nothing() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": _reading("garbled"),
            "2bmb:TomoScan:NumAngles": _reading(produced_at=None),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert append.calls == []


@pytest.mark.unit
async def test_a_dead_pv_does_not_abort_the_sweep_over_the_rest() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": ControlNotConnectedError("2bmb:TomoScan:ExposureTime"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_a_timed_out_pv_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": ControlTimeoutError("2bmb:TomoScan:ExposureTime", 5.0),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_an_access_denied_pv_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": ControlAccessDeniedError("2bmb:TomoScan:ExposureTime"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_a_value_coercion_error_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": ControlValueCoercionError(
                "2bmb:TomoScan:ExposureTime", "structured", "Scalar"
            ),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_an_unexpected_read_exception_is_caught_and_the_sweep_survives() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ExposureTime": RuntimeError("boom"),
            "2bmb:TomoScan:NumAngles": _reading(3000.0),
        }
    )
    reader, append = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert [e.channel_name for e in append.calls[0].entries] == ["NumAngles"]


@pytest.mark.unit
async def test_append_survives_unauthorized_and_does_not_raise() -> None:
    port = _FakeControlPort({"2bmb:TomoScan:ExposureTime": _reading(1.5)})
    reader, _append = _reader(
        control_port=port,
        baseline_pvs={_CODE: {"ExposureTime": "2bmb:TomoScan:ExposureTime"}},
        append_observations=_FakeAppendObservations(raises=UnauthorizedError("denied")),
    )

    await reader.read(_CODE, _RUN_ID)  # must not raise


@pytest.mark.unit
async def test_append_survives_a_closed_logbook_and_does_not_raise() -> None:
    port = _FakeControlPort({"2bmb:TomoScan:ExposureTime": _reading(1.5)})
    reader, _append = _reader(
        control_port=port,
        baseline_pvs={_CODE: {"ExposureTime": "2bmb:TomoScan:ExposureTime"}},
        append_observations=_FakeAppendObservations(
            raises=RunObservationLogbookClosedError(_RUN_ID, RunStatus.COMPLETED)
        ),
    )

    await reader.read(_CODE, _RUN_ID)  # must not raise


@pytest.mark.unit
async def test_append_survives_an_unexpected_exception_and_does_not_raise() -> None:
    port = _FakeControlPort({"2bmb:TomoScan:ExposureTime": _reading(1.5)})
    reader, _append = _reader(
        control_port=port,
        baseline_pvs={_CODE: {"ExposureTime": "2bmb:TomoScan:ExposureTime"}},
        append_observations=_FakeAppendObservations(raises=RuntimeError("boom")),
    )

    await reader.read(_CODE, _RUN_ID)  # must not raise
