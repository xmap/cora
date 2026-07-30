"""Unit tests for the composition-root BLEPS supply observer bridge.

Three layers are pinned: the pure flag reading (`flag_state_from_reading`,
where "unknown" must stay distinct from "low"), the many-channels-to-one-
Supply verdict, and the asymmetry that makes it safe (any believable trip
calls the resource down; only every channel believable and clear calls it
clear).

Scaffolding follows `test_enclosure_permit_observer.py`.

The fail-open regression drives `_observations` directly: it needs a trip
believed BEFORE its own instrument faults, and the scripted port drains
one PV to completion before starting the next, so it cannot interleave
two PVs of a single channel the way real ones do.
"""

# pyright: reportPrivateUsage=false

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime

import pytest

from cora.api._bleps_supply_observer import (
    BlepsChannel,
    BlepsSupplyObserver,
    flag_state_from_reading,
)
from cora.infrastructure.ports.clock import FakeClock
from cora.operation.ports.control_port import ControlNotConnectedError, Measurement
from cora.supply.ports.supply_observer import SupplyObservation, SupplyObserverScope

_T = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
_T_CLOCK = datetime(2026, 7, 29, 13, 0, 0, tzinfo=UTC)

_WATER = "2-BM cooling water"
_VACUUM = "2-BM beamline vacuum"
_COMMS = "2bmBLEPS:BLEPS:COMMUNICATIONS_FAULT"

_FLOW2 = BlepsChannel(
    supply_code=_WATER,
    label="Flow2 (M1 and DMM circuit)",
    trip_pv="2bmBLEPS:BLEPS:FLOW2_BELOW_SET_POINT_TRIP",
    fault_pv="2bmBLEPS:BLEPS:FLOW2_OVER_RANGE_FAULT",
)
_FLOW6 = BlepsChannel(
    supply_code=_WATER,
    label="Flow6 (Station B entrance slits)",
    trip_pv="2bmBLEPS:BLEPS:FLOW6_BELOW_SET_POINT_TRIP",
    fault_pv="2bmBLEPS:BLEPS:FLOW6_OVER_RANGE_FAULT",
)
_VS1 = BlepsChannel(
    supply_code=_VACUUM,
    label="Vacuum section 1",
    trip_pv="2bmBLEPS:BLEPS:VS1_TRIP",
)


def _reading(value: object, quality: str = "Good") -> Measurement:
    return Measurement(value=value, kind="Scalar", quality=quality, produced_at=_T)  # type: ignore[arg-type]


@pytest.mark.unit
def test_asserted_flag_reads_high() -> None:
    assert flag_state_from_reading(_reading(1)) is True
    assert flag_state_from_reading(_reading("1")) is True
    assert flag_state_from_reading(_reading(True)) is True


@pytest.mark.unit
def test_clear_flag_reads_low() -> None:
    assert flag_state_from_reading(_reading(0)) is False
    assert flag_state_from_reading(_reading("0")) is False


@pytest.mark.unit
def test_unreadable_flag_is_unknown_not_low() -> None:
    """A dead PV must never read as "no fault here"."""
    assert flag_state_from_reading(_reading(1, quality="Bad")) is None
    assert flag_state_from_reading(_reading(0, quality="Uncertain")) is None
    assert flag_state_from_reading(_reading(None)) is None
    assert flag_state_from_reading(_reading("tripped")) is None


class _ScriptedControlPort:
    """Fake `ControlPort` replaying a per-address reading script."""

    def __init__(
        self,
        *,
        readings: dict[str, list[Measurement]],
        disconnect: frozenset[str] = frozenset(),
    ) -> None:
        self._readings = readings
        self._disconnect = disconnect

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        return self._stream(address)

    async def _stream(self, address: str) -> AsyncGenerator[Measurement]:
        for reading in self._readings.get(address, []):
            yield reading
        if address in self._disconnect:
            raise ControlNotConnectedError(address)


def _observer(
    port: _ScriptedControlPort,
    channels: list[BlepsChannel],
    *,
    communications_fault_pv: str | None = None,
) -> BlepsSupplyObserver:
    return BlepsSupplyObserver(
        control_port=port,  # type: ignore[arg-type]
        channels=channels,
        communications_fault_pv=communications_fault_pv,
        clock=FakeClock(_T_CLOCK),
    )


async def _collect(observer: BlepsSupplyObserver, codes: set[str]) -> list[SupplyObservation]:
    scope = SupplyObserverScope(supply_codes=frozenset(codes))
    return [observation async for observation in observer.observe(scope)]


@pytest.mark.unit
async def test_empty_scope_yields_nothing() -> None:
    observer = _observer(_ScriptedControlPort(readings={}), [_FLOW2])
    assert await _collect(observer, set()) == []


@pytest.mark.unit
async def test_scope_excludes_other_supplies() -> None:
    """A Supply not in scope contributes no subscriptions and no observations."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
            _VS1.trip_pv: [_reading(1)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2, _VS1]), {_VACUUM})
    assert [o.supply_code for o in observed] == [_VACUUM]


@pytest.mark.unit
async def test_a_healthy_beamline_reports_clear_as_recovering() -> None:
    """Clear is reported as a level; the runtime decides whether it means anything.

    The adapter holds no memory of where the Supply has been, so it
    cannot know whether "clear" is news. It says what it sees and
    `cora.supply._monitor` drops it unless the Supply is Unavailable.
    """
    port = _ScriptedControlPort(
        readings={_FLOW2.trip_pv: [_reading(0)], _FLOW2.fault_pv or "": [_reading(0)]}
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert [o.observed_status for o in observed] == ["Recovering"]


@pytest.mark.unit
async def test_a_trip_drives_unavailable_and_names_the_circuit() -> None:
    port = _ScriptedControlPort(
        readings={_FLOW2.trip_pv: [_reading(1)], _FLOW2.fault_pv or "": [_reading(0)]}
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert [o.observed_status for o in observed] == ["Unavailable"]
    assert "Flow2 (M1 and DMM circuit)" in observed[0].reason
    assert observed[0].source_kind == "EpicsPv"


@pytest.mark.unit
async def test_one_trip_among_many_circuits_is_enough() -> None:
    """Eight circuits behind one Supply: any trip makes the resource unusable."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(0)],
            _FLOW2.fault_pv or "": [_reading(0)],
            _FLOW6.trip_pv: [_reading(1)],
            _FLOW6.fault_pv or "": [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2, _FLOW6]), {_WATER})
    assert [o.observed_status for o in observed] == ["Unavailable"]
    assert "Flow6" in observed[0].reason
    assert "Flow2" not in observed[0].reason


@pytest.mark.unit
async def test_clearing_a_trip_emits_recovering_not_available() -> None:
    """The signal reading clear is an observation; being back is a judgment."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1), _reading(0)],
            _FLOW2.fault_pv or "": [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert [o.observed_status for o in observed] == ["Unavailable", "Recovering"]
    assert "awaiting operator confirmation" in observed[1].reason


@pytest.mark.unit
async def test_a_still_tripped_channel_re_asserts_the_same_level() -> None:
    """Levels, not edges: a latched flag republishing itself says so again.

    Repetition is deliberate and is what makes a dropped append harmless,
    since the next reading re-asserts the same verdict. The decider
    collapses the repeats into one event.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1), _reading(1), _reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert [o.observed_status for o in observed] == ["Unavailable"] * 3


@pytest.mark.unit
async def test_an_instrument_fault_withholds_rather_than_clearing() -> None:
    """Flow2's sensor is lying, so nothing can be concluded about the resource.

    Flow6 being believable and clear is NOT enough. Clear requires every
    channel, because a blind channel might be the one that is tripped.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(1)],
            _FLOW6.trip_pv: [_reading(0)],
            _FLOW6.fault_pv or "": [_reading(0)],
        }
    )
    assert await _collect(_observer(port, [_FLOW2, _FLOW6]), {_WATER}) == []


@pytest.mark.unit
async def test_all_instruments_faulted_says_nothing_rather_than_clear() -> None:
    """Trusting no channel is not the same as knowing the resource is fine."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(0)],
            _FLOW2.fault_pv or "": [_reading(1)],
            _FLOW6.trip_pv: [_reading(0)],
            _FLOW6.fault_pv or "": [_reading(1)],
        }
    )
    assert await _collect(_observer(port, [_FLOW2, _FLOW6]), {_WATER}) == []


@pytest.mark.unit
async def test_an_unreadable_trip_is_not_treated_as_clear() -> None:
    """Bad quality on the only channel leaves the aggregate unknown."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1, quality="Bad")],
            _FLOW2.fault_pv or "": [_reading(0)],
        }
    )
    assert await _collect(_observer(port, [_FLOW2]), {_WATER}) == []


@pytest.mark.unit
async def test_comms_fault_suppresses_every_supply() -> None:
    """While BLEPS cannot be reached, nothing it said is repeatable."""
    port = _ScriptedControlPort(
        readings={
            _COMMS: [_reading(1)],
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
            _VS1.trip_pv: [_reading(1)],
        }
    )
    observer = _observer(port, [_FLOW2, _VS1], communications_fault_pv=_COMMS)
    assert await _collect(observer, {_WATER, _VACUUM}) == []


@pytest.mark.unit
async def test_an_unread_comms_flag_also_suppresses() -> None:
    """A comms flag we cannot read is the condition it exists to report."""
    port = _ScriptedControlPort(
        readings={_FLOW2.trip_pv: [_reading(1)], _FLOW2.fault_pv or "": [_reading(0)]}
    )
    observer = _observer(port, [_FLOW2], communications_fault_pv=_COMMS)
    assert await _collect(observer, {_WATER}) == []


@pytest.mark.unit
async def test_comms_clear_then_a_trip_is_reported() -> None:
    port = _ScriptedControlPort(
        readings={
            _COMMS: [_reading(0)],
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
        }
    )
    observer = _observer(port, [_FLOW2], communications_fault_pv=_COMMS)
    observed = await _collect(observer, {_WATER})
    assert [o.observed_status for o in observed] == ["Unavailable"]


@pytest.mark.unit
async def test_a_disconnect_does_not_read_as_a_cleared_trip() -> None:
    """Losing the channel must never look like the trip going away.

    The trip is reported while it is believable. Then the subscription
    drops, the channel is voided, and the adapter falls silent: no
    `Recovering` is emitted, so the Supply stays Unavailable rather than
    being walked back toward Available by a dead PV. That is the whole
    reason an unbelievable reading is distinct from a low one.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
        },
        disconnect=frozenset({_FLOW2.trip_pv}),
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert [o.observed_status for o in observed] == ["Unavailable"]
    assert "Recovering" not in [o.observed_status for o in observed]


@pytest.mark.unit
async def test_a_clean_stream_end_keeps_the_last_reading() -> None:
    """Unlike the enclosure permit observer, a clean end does not void.

    A Supply's verdict needs several PVs believable at once, so voiding a
    good reading the moment its own stream closed would leave the
    aggregate permanently unable to conclude. Here Flow6's stream ends
    first and its clear reading still counts toward the verdict.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW6.trip_pv: [_reading(0)],
            _FLOW6.fault_pv or "": [_reading(0)],
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW6, _FLOW2]), {_WATER})
    assert [o.observed_status for o in observed] == ["Unavailable"]
    assert "Flow2" in observed[0].reason


@pytest.mark.unit
async def test_available_is_never_emitted() -> None:
    """Across every scripted shape, the adapter never asserts Available."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1), _reading(0), _reading(1), _reading(0)],
            _FLOW2.fault_pv or "": [_reading(0)],
            _VS1.trip_pv: [_reading(0), _reading(1)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2, _VS1]), {_WATER, _VACUUM})
    assert observed
    assert {o.observed_status for o in observed} <= {"Unavailable", "Recovering"}


@pytest.mark.unit
def test_losing_the_tripped_channel_does_not_read_as_the_trip_clearing() -> None:
    """The fail-open bug gate review caught, pinned as a regression.

    Flow2 carries a standing trip; then Flow2's own instrument faults
    while Flow6 still reads clear. The earlier "no trips among the
    channels I trust" rule concluded the trip had cleared and emitted
    Recovering with a reason saying so, which invites an operator to
    restore a resource that is still down. The trip did not clear, it
    became unobservable, and those are opposite facts.

    Driven through `_observations` rather than a scripted stream because
    the ordering matters: the trip has to be believed BEFORE its
    instrument faults, and the scripted port drains one PV to completion
    before starting the next, so it cannot interleave two PVs of one
    channel. Real PVs update independently, which is exactly when this
    bites.
    """
    observer = _observer(_ScriptedControlPort(readings={}), [_FLOW2, _FLOW6])
    channels = [_FLOW2, _FLOW6]
    latest: dict[str, bool | None] = {
        _FLOW2.fault_pv or "": False,
        _FLOW2.trip_pv: True,
        _FLOW6.fault_pv or "": False,
        _FLOW6.trip_pv: False,
    }

    while_believed = observer._observations(channels, latest)
    assert [o.observed_status for o in while_believed] == ["Unavailable"]

    # Flow2's own sensor goes over-range. Its trip never cleared.
    latest[_FLOW2.fault_pv or ""] = True
    after_going_blind = observer._observations(channels, latest)

    assert [o.observed_status for o in after_going_blind] == [], (
        "losing sight of the tripped channel must withhold, not report clear"
    )


@pytest.mark.unit
async def test_a_blind_channel_blocks_clear_even_when_siblings_are_clear() -> None:
    """Clear needs every channel, because the unseen one might be the tripped one."""
    port = _ScriptedControlPort(
        readings={
            _FLOW6.fault_pv or "": [_reading(0)],
            _FLOW6.trip_pv: [_reading(0)],
            _FLOW2.fault_pv or "": [_reading(1)],
            _FLOW2.trip_pv: [_reading(0)],
        }
    )
    assert await _collect(_observer(port, [_FLOW6, _FLOW2]), {_WATER}) == []


@pytest.mark.unit
async def test_monitor_ref_names_the_culprit_channel() -> None:
    """The audited "which sensor said so" must be the one that tripped.

    It previously pointed at the first configured channel regardless, so
    with eight circuits behind one Supply it named a healthy one on every
    event, and the culprit survived only in free text.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW6.fault_pv or "": [_reading(0)],
            _FLOW6.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
            _FLOW2.trip_pv: [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2, _FLOW6]), {_WATER})
    tripped = [o for o in observed if o.observed_status == "Unavailable"]
    assert tripped
    assert tripped[-1].source_id == _FLOW6.trip_pv
    assert "Flow6" in tripped[-1].reason


@pytest.mark.unit
def test_an_enum_label_is_uninterpretable_not_low() -> None:
    """A `bi` record surfaces its FORMAT_CTRL label, not an integer.

    `EpicsCaControlPort` resolves DBR_ENUM to the label string, so a BLEPS
    flag declared as `bi`/`mbbi` arrives as "TRIP" or "OK". Reading that
    as low would be catastrophic and guessing the vocabulary would be
    fabrication, so it is unbelievable and the caller logs it. Whether
    2-BM's records are enums is an open question for staff.
    """
    assert flag_state_from_reading(_reading("TRIP")) is None
    assert flag_state_from_reading(_reading("OK")) is None
    assert flag_state_from_reading(_reading("MAJOR")) is None
    # The cold-label-cache fallback stringifies the index, which parses.
    assert flag_state_from_reading(_reading("1")) is True
    assert flag_state_from_reading(_reading("0")) is False
