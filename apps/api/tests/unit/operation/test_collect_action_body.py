"""Unit tests for the `collect` action body and its `CollectParams` schema.

Coverage spans the two boundaries the body sits on:

  Params validation (CollectParams.model_validate):
  - Internal trigger valid shapes (with / without repetitions)
  - ExternalEdge valid: polarity + source both present
  - ExternalLevel valid: source present, polarity may be omitted
  - polarity required when trigger_mode == ExternalEdge
  - source required when trigger_mode != Internal
  - source must be None when trigger_mode == Internal
  - repetitions >= 1 (or None); 0 and negatives rejected
  - dwell > 0 (zero and negatives rejected)
  - dwell carries the canonical {system, code} unit annotation in JSON Schema

  Body behaviour (collect called directly with ActionContext):
  - Internal + repetitions=5 happy path: writes the five configure PVs
    (including ImageMode=Multiple before NumImages and Acquire), polls
    Acquire_RBV (seeded Done immediately), reads DetectorState_RBV,
    returns the evidence Mapping with timestamps + final state, and a
    `detector_settings` prior/applied entry for each configuration PV
  - A configuration PV left at its existing value still shows
    prior == applied in `detector_settings` (nothing is omitted)
  - ExternalEdge / ExternalLevel raise UnwiredExternalTriggerError
    before any PV write, on both trigger dialects: CORA does not
    configure the trigger emitter, so arming the detector for external
    triggering and waiting for pulses nothing arranged would hang
  - polarity / source surface under `requested_not_applied` whenever set
  - repetitions=None raises UnboundedAcquisitionError before any PV
    write, including Acquire (a bounded repetitions is required so the
    Acquire_RBV done-poll can ever terminate)
  - Poll loop iterates while Acquire_RBV stays 1 and exits on 0
  - Unseeded Acquire_RBV propagates ControlNotConnectedError
  - Unseeded detector base PVs propagate ControlNotConnectedError from
    the prior-value read that now precedes each configuration write

  Trigger dialect (ctx.trigger_dialect, per-deployment vocabulary):
  - ADCore (default) Internal/ExternalEdge/ExternalLevel -> Internal/External/External
  - ADSpinnaker (APS 2-BM FLIR driver) -> Off/On/On, the INVERTED mapping
  - Unknown dialect raises UnknownTriggerDialectError, not KeyError

  End-to-end via Conductor:
  - InMemoryActionRegistry({"collect": collect}) + ActionStep("collect", ...)
    produces ConductorResult.succeeded=True and a step entry whose
    payload carries name + params + result + result_data with the
    evidence shape from the body
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.acquisitions import (
    CollectParams,
    _run_collect_cycle,  # pyright: ignore[reportPrivateUsage]
    collect,
)
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import (
    ActionContext,
    ActionStep,
    Conductor,
    InMemoryActionRegistry,
)
from cora.operation.errors import (
    UnboundedAcquisitionError,
    UnknownTriggerDialectError,
    UnwiredExternalTriggerError,
)
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    Measurement,
    Quality,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from cora.operation.features.append_activities.command import (
        AppendProcedureActivities,
    )

_FIXED_NOW = datetime(2026, 5, 31, 10, 0, 0, tzinfo=UTC)
_DETECTOR = "2bma:cam1"


def _acquire_rbv_reading(
    label: str = "Done", ordinal: int | None = 0, *, quality: Quality = "Good"
) -> Measurement:
    """A DBR_ENUM-shaped `Acquire_RBV` reading: the label plus the index behind it.

    A real areaDetector `Acquire_RBV` is a `bi` record, so it NEVER
    arrives as `kind="Scalar"` carrying a bare `0`/`1`; it arrives as
    `Categorical` carrying whatever `ZNAM`/`ONAM` the IOC declares
    (`"Done"` is ADCore's default, not a guarantee), with the index it
    resolved from on `ordinal`. Every test in this file used the Scalar
    shape before this fix, which is why none of them could see the same
    label-vs-ordinal defect already found three times elsewhere (the
    hutch permit, the BLEPS interlock flags, the beam-availability
    gate): the shape under test was one the substrate cannot produce.
    """
    return Measurement(
        value=label, kind="Categorical", quality=quality, produced_at=_FIXED_NOW, ordinal=ordinal
    )


def _seed_configure_pvs(port: InMemoryControlPort) -> None:
    """Seed the four configuration PVs with prior values, and connect `Acquire`.

    `set_reading`, not `simulate_connect`: `collect` now reads each
    configuration PV's prior value immediately before writing it, so a
    merely-connected-but-unseeded PV would raise `ControlNotConnectedError`
    on that read. The prior values are deliberately distinct from what
    the happy-path tests apply (mirroring the real APS 2-BM
    left-on-Continuous condition for `ImageMode`), so a test asserting
    `detector_settings` catches a mutation that records the applied
    value as its own prior. `Acquire` stays a bare `simulate_connect`:
    it is a command, never pre-read.
    """
    port.set_reading(
        f"{_DETECTOR}:TriggerMode",
        Measurement(value="External", kind="Categorical", quality="Good", produced_at=_FIXED_NOW),
    )
    port.set_reading(
        f"{_DETECTOR}:AcquireTime",
        Measurement(value=0.0, kind="Scalar", quality="Good", produced_at=_FIXED_NOW),
    )
    port.set_reading(
        f"{_DETECTOR}:ImageMode",
        Measurement(value="Continuous", kind="Categorical", quality="Good", produced_at=_FIXED_NOW),
    )
    port.set_reading(
        f"{_DETECTOR}:NumImages",
        Measurement(value=0, kind="Scalar", quality="Good", produced_at=_FIXED_NOW),
    )
    port.simulate_connect(f"{_DETECTOR}:Acquire")


def _seed_detector(port: InMemoryControlPort, *, acquire_rbv: Measurement | None = None) -> None:
    """Seed the six AD-convention PVs `collect` touches.

    `acquire_rbv` defaults to a Done reading (`_acquire_rbv_reading()`)
    so the poll loop exits on its first read; tests that exercise the
    loop pass a custom `Measurement` or replace the port with a
    stateful fixture.
    """
    _seed_configure_pvs(port)
    port.set_reading(
        f"{_DETECTOR}:Acquire_RBV",
        acquire_rbv if acquire_rbv is not None else _acquire_rbv_reading(),
    )
    port.set_reading(
        f"{_DETECTOR}:DetectorState_RBV",
        Measurement(value="Idle", kind="Categorical", quality="Good", produced_at=_FIXED_NOW),
    )


def _ctx(
    port: InMemoryControlPort, params: Mapping[str, Any], *, trigger_dialect: str = "ADCore"
) -> ActionContext:
    return ActionContext(
        control_port=port,
        clock=FakeClock(_FIXED_NOW),
        params=params,
        trigger_dialect=trigger_dialect,
    )


@dataclass
class _ScriptedRbvPort:
    """Tracks writes + returns a scripted `Acquire_RBV` reading sequence.

    Each element of `rbv_sequence` is a full `Measurement`, not a bare
    value, so a test scripts quality and label/ordinal independently per
    read. Once exhausted the last element repeats, matching
    `InMemoryControlPort`'s "hold the last set reading" behaviour.
    """

    rbv_sequence: list[Measurement] = field(default_factory=list[Measurement])
    writes: list[tuple[str, Any]] = field(default_factory=list[tuple[str, Any]])
    rbv_calls: int = 0

    async def write(
        self,
        address: str,
        value: Any,
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        _ = (wait, timeout_s)
        self.writes.append((address, value))

    async def read(self, address: str) -> Measurement:
        if address == f"{_DETECTOR}:Acquire_RBV":
            idx = min(self.rbv_calls, len(self.rbv_sequence) - 1)
            reading = self.rbv_sequence[idx]
            self.rbv_calls += 1
            return reading
        if address == f"{_DETECTOR}:DetectorState_RBV":
            return Measurement(
                value="Idle",
                kind="Categorical",
                quality="Good",
                produced_at=_FIXED_NOW,
            )
        if address in (
            f"{_DETECTOR}:TriggerMode",
            f"{_DETECTOR}:AcquireTime",
            f"{_DETECTOR}:ImageMode",
            f"{_DETECTOR}:NumImages",
        ):
            # The prior-value read `collect` now issues before each
            # configuration write; this fixture's tests assert write
            # order and Acquire_RBV decoding, not `detector_settings`
            # content, so a placeholder reading is sufficient here.
            return Measurement(
                value="prior", kind="Categorical", quality="Good", produced_at=_FIXED_NOW
            )
        raise AssertionError(f"unexpected read of {address!r}")

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        raise AssertionError("subscribe should not be called by collect at v1")


# --- CollectParams validation ------------------------------------------


@pytest.mark.unit
def test_collect_params_internal_with_repetitions_accepted() -> None:
    params = CollectParams.model_validate(
        {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.1}
    )
    assert params.trigger_mode == "Internal"
    assert params.repetitions == 5
    assert params.polarity is None
    assert params.source is None


@pytest.mark.unit
def test_collect_params_internal_repetitions_omitted_validates_as_none() -> None:
    """Validation only: `repetitions` defaults to `None` (schema-level unbounded
    request). This no longer results in a free-running acquisition; the
    `collect` / `continuous` bodies refuse `None` at runtime instead
    (see `test_collect_repetitions_none_raises_before_any_detector_write`)."""
    params = CollectParams.model_validate(
        {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.1}
    )
    assert params.repetitions is None


@pytest.mark.unit
def test_collect_params_external_edge_with_polarity_and_source_accepted() -> None:
    params = CollectParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "ExternalEdge",
            "polarity": "Rising",
            "source": "2bma:PCOMP1.OUT",
            "repetitions": 1500,
            "dwell": 0.025,
        }
    )
    assert params.polarity == "Rising"
    assert params.source == "2bma:PCOMP1.OUT"


@pytest.mark.unit
def test_collect_params_external_level_without_polarity_accepted() -> None:
    """ExternalLevel does not require polarity; source still required."""
    params = CollectParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "ExternalLevel",
            "source": "2bma:gate:OUT",
            "dwell": 0.1,
        }
    )
    assert params.polarity is None
    assert params.source == "2bma:gate:OUT"


@pytest.mark.unit
def test_collect_params_external_edge_without_polarity_rejected() -> None:
    with pytest.raises(ValidationError, match="polarity required"):
        CollectParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalEdge",
                "source": "2bma:PCOMP1.OUT",
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
def test_collect_params_external_without_source_rejected() -> None:
    with pytest.raises(ValidationError, match="source required"):
        CollectParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalLevel",
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
def test_collect_params_internal_with_source_rejected() -> None:
    with pytest.raises(ValidationError, match="source must be None"):
        CollectParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "source": "should_not_be_here",
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
@pytest.mark.parametrize("bad_repetitions", [0, -1, -100])
def test_collect_params_non_positive_repetitions_rejected(bad_repetitions: int) -> None:
    with pytest.raises(ValidationError):
        CollectParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "repetitions": bad_repetitions,
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
@pytest.mark.parametrize("bad_dwell", [0.0, -0.1])
def test_collect_params_non_positive_dwell_rejected(bad_dwell: float) -> None:
    with pytest.raises(ValidationError):
        CollectParams.model_validate(
            {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": bad_dwell}
        )


@pytest.mark.unit
def test_collect_params_json_schema_carries_unit_annotation_on_dwell() -> None:
    """The `dwell` field's JSON Schema includes {system, code} unit annotation.

    Pins the contract that Capability templates rely on per
    project_units_design: the unit lives on the schema, not the field name.
    """
    schema = CollectParams.model_json_schema()
    dwell_schema = schema["properties"]["dwell"]
    assert dwell_schema["unit"] == {"system": "udunits", "code": "s"}


# --- collect body behaviour --------------------------------------------


@pytest.mark.unit
async def test_collect_internal_trigger_writes_configure_pvs_and_returns_evidence() -> None:
    """Happy path: writes land on the four configure PVs and evidence shape is right."""
    port = InMemoryControlPort()
    _seed_detector(port)
    result = await collect(
        _ctx(
            port,
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "repetitions": 5,
                "dwell": 0.1,
            },
        )
    )
    assert (await port.read(f"{_DETECTOR}:TriggerMode")).value == "Internal"
    assert (await port.read(f"{_DETECTOR}:AcquireTime")).value == 0.1
    assert (await port.read(f"{_DETECTOR}:ImageMode")).value == "Multiple"
    assert (await port.read(f"{_DETECTOR}:NumImages")).value == 5
    assert (await port.read(f"{_DETECTOR}:Acquire")).value == 1
    assert result == {
        "started_at": _FIXED_NOW.isoformat(),
        "stopped_at": _FIXED_NOW.isoformat(),
        "repetitions_requested": 5,
        "trigger_mode": "Internal",
        "trigger_dialect": "ADCore",
        "image_mode": "Multiple",
        "polarity": None,
        "source": None,
        "detector_state_final": "Idle",
        "detector_settings": {
            "TriggerMode": {"prior": "External", "applied": "Internal"},
            "AcquireTime": {"prior": 0.0, "applied": 0.1},
            "ImageMode": {"prior": "Continuous", "applied": "Multiple"},
            "NumImages": {"prior": 0, "applied": 5},
        },
        "requested_not_applied": {"polarity": None, "source": None},
    }


@pytest.mark.unit
async def test_collect_unchanged_setting_records_equal_prior_and_applied() -> None:
    """A configuration PV CORA leaves at its existing value still shows prior == applied.

    `detector_settings` must carry all four configuration PVs regardless
    of whether the applied value happens to match what was already
    there; a reader must never have to guess whether a PV was skipped
    versus genuinely left unchanged.
    """
    port = InMemoryControlPort()
    _seed_detector(port)
    port.set_reading(
        f"{_DETECTOR}:AcquireTime",
        Measurement(value=0.1, kind="Scalar", quality="Good", produced_at=_FIXED_NOW),
    )
    result = await collect(
        _ctx(
            port,
            {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.1},
        )
    )
    assert result["detector_settings"]["AcquireTime"] == {"prior": 0.1, "applied": 0.1}


@pytest.mark.unit
async def test_collect_external_edge_raises_before_any_detector_write() -> None:
    """ExternalEdge raises UnwiredExternalTriggerError and never issues Acquire (ADCore dialect).

    Mirrors `test_collect_repetitions_none_raises_before_any_detector_write`:
    CORA does not configure the trigger emitter (see the module
    docstring's "External triggering is refused, not attempted"), so
    arming the detector for external triggering and then waiting for
    pulses nothing arranged would hang forever against real hardware.
    """
    port = InMemoryControlPort()
    _seed_detector(port)
    with pytest.raises(UnwiredExternalTriggerError, match="ExternalEdge"):
        await collect(
            _ctx(
                port,
                {
                    "detector": _DETECTOR,
                    "trigger_mode": "ExternalEdge",
                    "polarity": "Rising",
                    "source": "2bma:PCOMP1.OUT",
                    "repetitions": 10,
                    "dwell": 0.025,
                },
            )
        )
    with pytest.raises(ControlNotConnectedError):
        await port.read(f"{_DETECTOR}:Acquire")


@pytest.mark.unit
async def test_collect_external_level_raises_before_any_detector_write() -> None:
    """ExternalLevel raises UnwiredExternalTriggerError, never issues Acquire (ADCore dialect)."""
    port = InMemoryControlPort()
    _seed_detector(port)
    with pytest.raises(UnwiredExternalTriggerError, match="ExternalLevel"):
        await collect(
            _ctx(
                port,
                {
                    "detector": _DETECTOR,
                    "trigger_mode": "ExternalLevel",
                    "source": "2bma:gate:OUT",
                    "repetitions": 1,
                    "dwell": 0.5,
                },
            )
        )
    with pytest.raises(ControlNotConnectedError):
        await port.read(f"{_DETECTOR}:Acquire")


@pytest.mark.unit
async def test_collect_internal_trigger_ad_spinnaker_dialect_writes_off() -> None:
    """ADSpinnaker dialect: Internal (free-running) -> 'Off' (external triggering disabled).

    This is the inverted mapping: the FLIR/Spinnaker driver's TriggerMode
    asks whether EXTERNAL triggering is enabled, so CORA's free-running
    Internal is the Off state.
    """
    port = InMemoryControlPort()
    _seed_detector(port)
    result = await collect(
        _ctx(
            port,
            {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.1},
            trigger_dialect="ADSpinnaker",
        )
    )
    assert (await port.read(f"{_DETECTOR}:TriggerMode")).value == "Off"
    assert result["trigger_dialect"] == "ADSpinnaker"


@pytest.mark.unit
async def test_collect_external_edge_raises_regardless_of_dialect() -> None:
    """ExternalEdge is refused regardless of dialect: the guard fires before dialect resolution."""
    port = InMemoryControlPort()
    _seed_detector(port)
    with pytest.raises(UnwiredExternalTriggerError, match="ExternalEdge"):
        await collect(
            _ctx(
                port,
                {
                    "detector": _DETECTOR,
                    "trigger_mode": "ExternalEdge",
                    "polarity": "Rising",
                    "source": "2bma:PCOMP1.OUT",
                    "repetitions": 10,
                    "dwell": 0.025,
                },
                trigger_dialect="ADSpinnaker",
            )
        )
    with pytest.raises(ControlNotConnectedError):
        await port.read(f"{_DETECTOR}:Acquire")


@pytest.mark.unit
async def test_collect_external_level_raises_regardless_of_dialect() -> None:
    """ExternalLevel is refused regardless of dialect: the guard fires before dialect resolution."""
    port = InMemoryControlPort()
    _seed_detector(port)
    with pytest.raises(UnwiredExternalTriggerError, match="ExternalLevel"):
        await collect(
            _ctx(
                port,
                {
                    "detector": _DETECTOR,
                    "trigger_mode": "ExternalLevel",
                    "source": "2bma:gate:OUT",
                    "repetitions": 1,
                    "dwell": 0.5,
                },
                trigger_dialect="ADSpinnaker",
            )
        )
    with pytest.raises(ControlNotConnectedError):
        await port.read(f"{_DETECTOR}:Acquire")


@pytest.mark.unit
async def test_collect_unknown_trigger_dialect_raises_named_error() -> None:
    """An unrecognised trigger_dialect must fail loudly, not KeyError."""
    port = InMemoryControlPort()
    _seed_detector(port)
    with pytest.raises(UnknownTriggerDialectError, match="unknown detector_trigger_dialect"):
        await collect(
            _ctx(
                port,
                {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.1},
                trigger_dialect="NotARealDialect",
            )
        )


@pytest.mark.unit
async def test_collect_repetitions_none_raises_before_any_detector_write() -> None:
    """None repetitions raises UnboundedAcquisitionError and never issues Acquire.

    An unbounded acquisition (areaDetector `Continuous` ImageMode) never
    asserts `Acquire_RBV` Done on its own, so combining it with this
    body's unconditional done-poll would hang the caller forever and
    leave the camera acquiring. `Acquire` is the arm command; a real
    detector left partially configured but never armed is safe, so the
    only write that must never happen is `Acquire`.
    """
    port = InMemoryControlPort()
    _seed_detector(port)
    with pytest.raises(UnboundedAcquisitionError):
        await collect(
            _ctx(port, {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.05})
        )
    # `_seed_detector` only `simulate_connect`s Acquire (no value set), so an
    # unwritten read still raises ControlNotConnectedError: proof the body
    # never issued the arm command.
    with pytest.raises(ControlNotConnectedError):
        await port.read(f"{_DETECTOR}:Acquire")


@pytest.mark.unit
async def test_collect_writes_image_mode_multiple_before_num_images_and_acquire() -> None:
    """ImageMode=Multiple lands after AcquireTime but before NumImages and Acquire.

    The happy-path test above proves the final PV states; this test
    proves the ORDER, using `_ScriptedRbvPort`'s write log. A mutation
    that writes ImageMode after Acquire (or drops it) would still leave
    the final in-memory reads looking correct but would flip or lose
    this order.
    """
    port = _ScriptedRbvPort(rbv_sequence=[_acquire_rbv_reading("Done", 0)])
    await collect(
        _ctx(
            port,  # type: ignore[arg-type]
            {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 7, "dwell": 0.1},
        )
    )
    addresses = [addr for addr, _ in port.writes]
    assert addresses == [
        f"{_DETECTOR}:TriggerMode",
        f"{_DETECTOR}:AcquireTime",
        f"{_DETECTOR}:ImageMode",
        f"{_DETECTOR}:NumImages",
        f"{_DETECTOR}:Acquire",
    ]
    values = dict(port.writes)
    assert values[f"{_DETECTOR}:ImageMode"] == "Multiple"
    assert values[f"{_DETECTOR}:NumImages"] == 7


@pytest.mark.unit
async def test_collect_polarity_and_source_appear_under_requested_not_applied_when_set() -> None:
    """`polarity` / `source` land under `requested_not_applied`, never as written PVs.

    Body execution now refuses every `trigger_mode` other than `Internal`
    (see the `UnwiredExternalTriggerError` tests above), so a real
    `collect()` call can never carry a non-Internal trigger_mode through
    to this evidence-shaping code. `CollectParams.model_construct`
    bypasses the schema's Internal-implies-no-source rule to exercise
    the evidence grouping directly: it must echo whatever `polarity` /
    `source` the params carry, regardless of what a real deployment
    would ever send through `model_validate`.
    """
    port = InMemoryControlPort()
    _seed_detector(port)
    params = CollectParams.model_construct(
        detector=_DETECTOR,
        trigger_mode="Internal",
        polarity="Falling",
        source="2bma:PCOMP1.OUT",
        repetitions=3,
        dwell=0.2,
    )
    result = await _run_collect_cycle(_ctx(port, {}), params)
    assert result["polarity"] == "Falling"
    assert result["source"] == "2bma:PCOMP1.OUT"
    assert result["requested_not_applied"] == {
        "polarity": "Falling",
        "source": "2bma:PCOMP1.OUT",
    }


@pytest.mark.unit
async def test_collect_poll_loop_iterates_while_acquire_rbv_busy() -> None:
    """Acquiring (ordinal 1) transitions to Done (ordinal 0) on the Nth
    read; loop iterates then exits, decoding by ORDINAL, not the label."""
    port = _ScriptedRbvPort(
        rbv_sequence=[
            _acquire_rbv_reading("Acquiring", 1),
            _acquire_rbv_reading("Acquiring", 1),
            _acquire_rbv_reading("Acquiring", 1),
            _acquire_rbv_reading("Done", 0),
        ]
    )
    result = await collect(
        _ctx(
            port,  # type: ignore[arg-type]
            {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.01},
        )
    )
    assert port.rbv_calls == 4
    assert result["detector_state_final"] == "Idle"


@pytest.mark.unit
async def test_collect_relabelled_acquire_rbv_still_terminates_via_ordinal() -> None:
    """A facility (or AD build) that relabels Done/Acquiring to anything
    else must not hang the poll loop: the ordinal decides, not the word.

    This is the live shape of the bug this fix closes. Under the old
    `value in (0, "Done")` check, EITHER label here fails the match
    (`"BUSY"`/`"READY"` are neither `0` nor `"Done"`), so the loop would
    never have exited.
    """
    port = _ScriptedRbvPort(
        rbv_sequence=[_acquire_rbv_reading("BUSY", 1), _acquire_rbv_reading("READY", 0)]
    )
    await collect(
        _ctx(
            port,  # type: ignore[arg-type]
            {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.01},
        )
    )
    assert port.rbv_calls == 2


@pytest.mark.unit
async def test_collect_bad_quality_acquire_rbv_never_terminates_the_loop() -> None:
    """A `Bad`-quality Done reading must not be believed: the number means
    nothing, so concluding the acquisition finished would be a fail-open
    into the recorded evidence."""
    port = _ScriptedRbvPort(
        rbv_sequence=[
            _acquire_rbv_reading("Done", 0, quality="Bad"),
            _acquire_rbv_reading("Done", 0, quality="Bad"),
            _acquire_rbv_reading("Done", 0),
        ]
    )
    await collect(
        _ctx(
            port,  # type: ignore[arg-type]
            {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.01},
        )
    )
    assert port.rbv_calls == 3


@pytest.mark.unit
async def test_collect_uncertain_quality_acquire_rbv_does_terminate() -> None:
    """An alarmed-but-Done reading IS believed: `Uncertain` is not `Bad`.

    Pins the floor choice itself (`believable`, not `actionable`). A
    detector carrying a standing MINOR/MAJOR for a reason unrelated to
    whether it finished (a temperature warning, a nearly-full
    file-writer disk) must still be readable as Done; a future edit that
    tightens this poll to `actionable` would hang every acquisition on
    such a detector, and this is the test that would catch it.
    """
    port = _ScriptedRbvPort(rbv_sequence=[_acquire_rbv_reading("Done", 0, quality="Uncertain")])
    await collect(
        _ctx(
            port,  # type: ignore[arg-type]
            {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.01},
        )
    )
    assert port.rbv_calls == 1


@pytest.mark.unit
async def test_collect_unreadable_acquire_rbv_warns_once_per_episode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An undecodable reading keeps polling (never concludes Done) and
    logs exactly once per continuous unreadable stretch, not once per
    50ms tick: 3 unreadable reads produce 1 warning, and recovering
    produces exactly 1 info, not a flood of either."""
    warnings: list[str] = []
    infos: list[str] = []

    def _record_warning(event: str, **kwargs: Any) -> None:
        _ = kwargs
        warnings.append(event)

    def _record_info(event: str, **kwargs: Any) -> None:
        _ = kwargs
        infos.append(event)

    monkeypatch.setattr("cora.operation.acquisitions._log.warning", _record_warning)
    monkeypatch.setattr("cora.operation.acquisitions._log.info", _record_info)
    port = _ScriptedRbvPort(
        rbv_sequence=[
            _acquire_rbv_reading("SEARCHING", None),
            _acquire_rbv_reading("SEARCHING", None),
            _acquire_rbv_reading("SEARCHING", None),
            _acquire_rbv_reading("Done", 0),
        ]
    )
    await collect(
        _ctx(
            port,  # type: ignore[arg-type]
            {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.01},
        )
    )
    assert port.rbv_calls == 4
    assert warnings == ["acquisitions.acquire_rbv_unreadable"]
    assert infos == ["acquisitions.acquire_rbv_restored"]


@pytest.mark.unit
async def test_collect_unconnected_acquire_rbv_propagates_not_connected_error() -> None:
    """Acquire_RBV not seeded -> ControlNotConnectedError surfaces from the read."""
    port = InMemoryControlPort()
    _seed_configure_pvs(port)
    # Deliberately do NOT seed Acquire_RBV / DetectorState_RBV
    with pytest.raises(ControlNotConnectedError):
        await collect(
            _ctx(
                port,
                {
                    "detector": _DETECTOR,
                    "trigger_mode": "Internal",
                    "repetitions": 5,
                    "dwell": 0.05,
                },
            )
        )


@pytest.mark.unit
async def test_collect_unconnected_trigger_mode_propagates_not_connected_error() -> None:
    """First configuration PV not seeded -> ControlNotConnectedError from its prior-read."""
    port = InMemoryControlPort()  # nothing connected
    with pytest.raises(ControlNotConnectedError):
        await collect(
            _ctx(
                port,
                {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.05},
            )
        )


# --- end-to-end via Conductor ------------------------------------------


@dataclass
class _AppendCall:
    command: AppendProcedureActivities
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID


@dataclass
class _FakeAppendStep:
    calls: list[_AppendCall] = field(default_factory=list[_AppendCall])

    async def __call__(
        self,
        command: AppendProcedureActivities,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        self.calls.append(
            _AppendCall(
                command=command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        )
        return len(command.entries)


@dataclass
class _SequenceIdGenerator:
    ids: list[UUID]
    _index: int = 0

    def new_id(self) -> UUID:
        if self._index >= len(self.ids):
            raise RuntimeError("FixedIdGenerator exhausted")
        out = self.ids[self._index]
        self._index += 1
        return out


@pytest.mark.unit
async def test_conductor_executes_collect_action_and_records_step_entry() -> None:
    """Conductor + registered `collect` body + ActionStep -> success + recorded evidence."""
    port = InMemoryControlPort()
    _seed_detector(port)
    appender = _FakeAppendStep()
    registry = InMemoryActionRegistry({"collect": collect})
    conductor = Conductor(
        control_port=port,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([uuid4(), uuid4()]),
        action_registry=registry,
    )
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            ActionStep(
                name="collect",
                params={
                    "detector": _DETECTOR,
                    "trigger_mode": "Internal",
                    "repetitions": 3,
                    "dwell": 0.05,
                },
            ),
        ),
    )
    assert result.succeeded is True
    assert result.completed_count == 1
    # calls[0] is the pre-effect in-flight marker; calls[1] is the outcome.
    assert appender.calls[0].command.entries[0].payload["result"] == "in_flight"
    entry = appender.calls[1].command.entries[0]
    assert entry.step_kind == "action"
    assert entry.payload["name"] == "collect"
    assert entry.payload["result"] == "ok"
    result_data = entry.payload["result_data"]
    assert result_data["trigger_mode"] == "Internal"
    assert result_data["repetitions_requested"] == 3
    assert result_data["detector_state_final"] == "Idle"
