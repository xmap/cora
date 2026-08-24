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

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from datetime import UTC, datetime

import pytest

from cora.api._bleps_supply_observer import (
    BlepsChannel,
    BlepsSupplyObserver,
    flag_state_from_reading,
)
from cora.infrastructure.ports.clock import FakeClock
from cora.operation.ports.control_port import ControlNotConnectedError, Measurement, Quality
from cora.supply.ports.supply_observer import ReachTier, SupplyObservation, SupplyObserverScope

_T = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
_T_CLOCK = datetime(2026, 7, 29, 13, 0, 0, tzinfo=UTC)

_WATER = "2-BM cooling water"
_VACUUM = "2-BM beamline vacuum"
_COMMS = "2bmBLEPS:BLEPS:COMMUNICATIONS_FAULT"

_FLOW2 = BlepsChannel(
    supply_code=_WATER,
    label="Flow2 (M1 and DMM circuit)",
    trip_pv="2bmBLEPS:BLEPS:FLOW2_TRIP",
    fault_pv="2bmBLEPS:BLEPS:FLOW2_OVER_RANGE",
)
_FLOW6 = BlepsChannel(
    supply_code=_WATER,
    label="Flow6 (Station B entrance slits)",
    trip_pv="2bmBLEPS:BLEPS:FLOW6_TRIP",
    fault_pv="2bmBLEPS:BLEPS:FLOW6_OVER_RANGE",
)
_VS1 = BlepsChannel(
    supply_code=_VACUUM,
    label="Vacuum section 1",
    trip_pv="2bmBLEPS:BLEPS:VS1_TRIP",
)
_FLOW2_W = BlepsChannel(
    supply_code=_WATER,
    label="Flow2 (M1 and DMM circuit)",
    trip_pv="2bmBLEPS:BLEPS:FLOW2_TRIP",
    fault_pv="2bmBLEPS:BLEPS:FLOW2_OVER_RANGE",
    warning_pv="2bmBLEPS:BLEPS:FLOW_2_UNDER_WRN",
)
_FLOW6_W = BlepsChannel(
    supply_code=_WATER,
    label="Flow6 (Station B entrance slits)",
    trip_pv="2bmBLEPS:BLEPS:FLOW6_TRIP",
    fault_pv="2bmBLEPS:BLEPS:FLOW6_OVER_RANGE",
    warning_pv="2bmBLEPS:BLEPS:FLOW_6_UNDER_WRN",
)


def _reading(value: object, quality: str = "Good") -> Measurement:
    return Measurement(value=value, kind="Scalar", quality=quality, produced_at=_T)  # type: ignore[arg-type]


def _enum_reading(label: str, ordinal: int | None, quality: Quality = "Good") -> Measurement:
    """A DBR_ENUM-shaped reading: the label plus the index behind it.

    Kept distinct from `_reading` above, and the distinction is
    load-bearing rather than tidiness. A real `bi` record NEVER arrives
    as `kind="Scalar"` carrying a number; it arrives as `Categorical`
    carrying a facility-authored label. Every test in this file used the
    Scalar shape, which is why none of them could see the defect that
    stopped BLEPS reading at 2-BM: the shape under test was one the
    substrate cannot produce. The same blind spot shipped twice before,
    on the hutch permit and the beam permits.
    """
    return Measurement(
        value=label,
        kind="Categorical",
        quality=quality,
        produced_at=_T,
        ordinal=ordinal,
    )


@pytest.mark.unit
def test_real_bleps_enum_labels_read_through_the_ordinal() -> None:
    """The four label pairs the deployed 2-BM IOC publishes, at the observer.

    Measured on arcturus 2026-08-23: trips and warnings are
    `NO_FAULT` / `TRIP`, faults and the comms flag are `""` / `Present`.
    Asserted here and not only at `binary_code` because this is the
    function the pump actually calls, and because the observer adds a
    quality floor on top that the decoder knows nothing about.
    """
    assert flag_state_from_reading(_enum_reading("TRIP", 1)) is True
    assert flag_state_from_reading(_enum_reading("NO_FAULT", 0)) is False
    assert flag_state_from_reading(_enum_reading("Present", 1)) is True
    assert flag_state_from_reading(_enum_reading("", 0)) is False


@pytest.mark.unit
def test_real_bleps_enum_labels_are_unreadable_without_an_ordinal() -> None:
    """The negative half: these labels carry no meaning CORA can decode.

    Pins WHY the ordinal is load-bearing rather than a convenience. If
    someone later widens the shared label set to include these words,
    this test fails and says so, because that is the wrong fix: it puts
    one facility's vocabulary in `cora.shared` and the next facility
    breaks anyway.
    """
    assert flag_state_from_reading(_enum_reading("TRIP", None)) is None
    assert flag_state_from_reading(_enum_reading("NO_FAULT", None)) is None
    assert flag_state_from_reading(_enum_reading("Present", None)) is None
    assert flag_state_from_reading(_enum_reading("", None)) is None


@pytest.mark.unit
def test_an_out_of_range_ordinal_reads_as_unbelievable() -> None:
    """A channel pointed at a multi-state record is a config error, not a flag.

    Fails closed to `None` (excluded from the verdict) rather than
    collapsing to asserted or clear. The label is one the fallback would
    decode, so only the ordinal short-circuit can produce this answer.
    """
    assert flag_state_from_reading(_enum_reading("ON", 2)) is None


@pytest.mark.unit
def test_a_bad_quality_enum_reading_is_unbelievable_even_with_an_ordinal() -> None:
    """`Bad` still wins. An ordinal is not a reason to trust an invalid read."""
    assert flag_state_from_reading(_enum_reading("TRIP", 1, quality="Bad")) is None
    assert flag_state_from_reading(_enum_reading("NO_FAULT", 0, quality="Bad")) is None


@pytest.mark.unit
def test_an_alarming_trip_is_believed_because_the_alarm_is_the_signal() -> None:
    """The case that made this observer blind at 2-BM.

    A BLEPS record raises MAJOR precisely when its flag asserts, and the
    CA adapter collapses MAJOR to `Uncertain`. Under the old `!= "Good"`
    floor that discarded every tripped flag while keeping every clear
    one, so the observer could only ever see a healthy beamline.

    Measured on arcturus 2026-08-23: all eight cooling circuits read
    `TRIP` with `STATE MAJOR`, and not one was visible.
    """
    assert flag_state_from_reading(_enum_reading("TRIP", 1, quality="Uncertain")) is True


@pytest.mark.unit
def test_an_alarming_clear_reading_is_believed_as_clear() -> None:
    """The other direction of the same loosening, stated rather than assumed.

    Not reachable at 2-BM, where a clear flag carries no alarm, but the
    floor admits it and the record should say what it does: an alarmed
    `NO_FAULT` counts as clear rather than withholding the verdict.
    """
    assert flag_state_from_reading(_enum_reading("NO_FAULT", 0, quality="Uncertain")) is False


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
    """A dead PV must never read as "no fault here".

    The `Uncertain` case moved OUT of this test when the floor loosened
    to `Bad`, and it moved rather than being deleted: an alarmed reading
    is now believed, and
    `test_an_alarming_clear_reading_is_believed_as_clear` pins that
    directly. What remains here is the property that never changed, that
    an unreadable or uninterpretable flag is withheld instead of being
    reported as clear.
    """
    assert flag_state_from_reading(_reading(1, quality="Bad")) is None
    assert flag_state_from_reading(_reading(0, quality="Bad")) is None
    assert flag_state_from_reading(_reading(None)) is None
    assert flag_state_from_reading(_reading("tripped")) is None


class _ScriptedControlPort:
    """Fake `ControlPort` replaying a per-address reading script.

    `hang` models a live subscription that has gone quiet: the address
    yields its script then blocks forever instead of ending, which is
    what a real CA monitor on an unchanging PV does and the only shape
    under which the poll tests can observe a tick at all.

    `read_failures` scripts the poll path. Unlike the enclosure fake's
    per-address result QUEUE, an address here either always answers or
    always fails, because a supply poller re-reads its whole channel set
    on every tick and a queue would silently change behaviour between
    ticks. The tests care which channels are reachable, not how many
    times each was asked.
    """

    def __init__(
        self,
        *,
        readings: dict[str, list[Measurement]],
        disconnect: frozenset[str] = frozenset(),
        hang: frozenset[str] = frozenset(),
        read_failures: frozenset[str] = frozenset(),
    ) -> None:
        self._readings = readings
        self._disconnect = disconnect
        self._hang = hang
        self._read_failures = read_failures

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        return self._stream(address)

    async def _stream(self, address: str) -> AsyncGenerator[Measurement]:
        for reading in self._readings.get(address, []):
            yield reading
        if address in self._hang:
            await asyncio.Event().wait()  # never released; models a live subscription
            return  # pragma: no cover - unreachable
        if address in self._disconnect:
            raise ControlNotConnectedError(address)

    async def read(self, address: str) -> Measurement:
        if address in self._read_failures:
            raise ControlNotConnectedError(address)
        return _reading(0)


def _observer(
    port: _ScriptedControlPort,
    channels: list[BlepsChannel],
    *,
    communications_fault_pv: str | None = None,
    probe_tick_seconds: float | None = None,
) -> BlepsSupplyObserver:
    return BlepsSupplyObserver(
        control_port=port,  # type: ignore[arg-type]
        channels=channels,
        communications_fault_pv=communications_fault_pv,
        clock=FakeClock(_T_CLOCK),
        probe_tick_seconds=probe_tick_seconds,
    )


async def _collect(observer: BlepsSupplyObserver, codes: set[str]) -> list[SupplyObservation]:
    scope = SupplyObserverScope(supply_codes=frozenset(codes))
    return [observation async for observation in observer.observe(scope)]


def _statuses(observed: list[SupplyObservation]) -> list[str]:
    """The real-verdict sequence, filtering out probe-only entries.

    Every tick now yields something for every configured Supply in
    scope, either a real verdict or a probe-only reach fact
    (`observed_status=None`, see `_bleps_supply_observer`'s "Probes"
    section). Most of this file's tests are about the verdict sequence,
    not the reach trail, so this helper recovers the pre-probe
    assertion shape; the probe-specific tests below check
    `observed_status is None` and `reach_tier` directly instead.
    """
    return [o.observed_status for o in observed if o.observed_status is not None]


def _is_probe(observation: SupplyObservation) -> bool:
    return observation.observed_status is None


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
    assert _statuses(observed) == ["Recovering"]


@pytest.mark.unit
async def test_an_alarmed_but_clear_fault_flag_no_longer_blinds_its_channel() -> None:
    """The trust axis's half of the loosening, which the process-axis tests miss.

    `flag_state_from_reading` serves three PV roles and they use
    different label pairs, so a floor argument proved on trip flags does
    not automatically hold for `fault_pv`. Under the strict floor an
    alarmed fault reading was unbelievable, and `_verdict` blinds a
    channel whose fault flag is anything but a believable `False`, so
    ANY standing alarm on a fault record blinded that channel forever.

    Now it is believed, the channel stays in the fold, and its clear
    trip reading can be reported. Not reachable on measured 2-BM data,
    where fault flags read clear with no alarm, and pinned here so a
    facility where it IS reachable shows up as a test change rather
    than as silence.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_enum_reading("NO_FAULT", 0)],
            _FLOW2.fault_pv or "": [_enum_reading("", 0, quality="Uncertain")],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert _statuses(observed) == ["Recovering"]


@pytest.mark.unit
async def test_an_alarmed_but_clear_comms_flag_does_not_read_as_a_dark_feed() -> None:
    """The system axis's half, which suppresses EVERY Supply when it trips.

    `_communications_lost` treats the comms flag as dark unless it reads
    a believable `False`, so under the strict floor an alarmed comms
    reading suppressed the whole observer, not one channel. This is the
    widest of the three widenings and so the one most worth pinning.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_enum_reading("TRIP", 1, quality="Uncertain")],
            _FLOW2.fault_pv or "": [_enum_reading("", 0)],
            _COMMS: [_enum_reading("", 0, quality="Uncertain")],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2], communications_fault_pv=_COMMS), {_WATER})
    assert _statuses(observed) == ["Unavailable"]


@pytest.mark.unit
def test_an_alarming_scalar_reading_is_believed_too() -> None:
    """The loosened floor is about quality, not about reading shape.

    A BLEPS channel on a `longin` / `ai` arrives as `kind="Scalar"`
    carrying a number rather than an enum label plus ordinal. The
    Uncertain-quality Scalar case was covered before this change (as an
    assertion that it read `None`) and would otherwise have been dropped
    rather than relocated when that assertion moved to the enum-shaped
    test.
    """
    assert flag_state_from_reading(_reading(1, quality="Uncertain")) is True
    assert flag_state_from_reading(_reading(0, quality="Uncertain")) is False


@pytest.mark.unit
async def test_the_live_2bm_shape_drives_unavailable_end_to_end() -> None:
    """The whole failure, reproduced as the beamline actually reports it.

    Every ingredient is measured, not invented (arcturus 2026-08-23):
    the flags are DBR_ENUM carrying `NO_FAULT` / `TRIP`, which no
    conventional label set contains, so the ordinal is what resolves
    them; a tripped flag carries `STATE MAJOR`, which the CA adapter
    collapses to `Uncertain`; the instrument-fault flag reads the EMPTY
    STRING for healthy with no alarm; and the comms flag likewise.

    Both defects had to be fixed for this to pass, and either one alone
    still yields silence: the label is undecodable without the ordinal,
    and the reading is discarded without the loosened floor. Driving the
    whole observer rather than `flag_state_from_reading` is the point,
    since the comms gate and the verdict fold sit between them and each
    can independently swallow the result.
    """
    tripped = _enum_reading("TRIP", 1, quality="Uncertain")
    healthy_fault = _enum_reading("", 0)
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [tripped],
            _FLOW2.fault_pv or "": [healthy_fault],
            _FLOW6.trip_pv: [tripped],
            _FLOW6.fault_pv or "": [healthy_fault],
            _COMMS: [_enum_reading("", 0)],
        }
    )
    observed = await _collect(
        _observer(port, [_FLOW2, _FLOW6], communications_fault_pv=_COMMS), {_WATER}
    )
    statuses = _statuses(observed)
    assert statuses, "the observer claimed nothing at all, which is the bug this pins"
    # Asserting the SET rather than the sequence: both channels are
    # tripped from their first reading, so the verdict is re-emitted per
    # reading and the count is an artifact of the scripted drain order.
    # What matters is that every claim made was Unavailable and none
    # said otherwise.
    assert set(statuses) == {"Unavailable"}
    # The LAST reason, not the first. Flow2 alone keeps the Supply
    # Unavailable from its first reading onward, so `reasons[0]` names
    # only Flow2 and a regression that dropped or mis-decoded Flow6
    # entirely would leave both the status set and the first reason
    # untouched. Only the final fold has seen every channel.
    reasons = [o.reason for o in observed if o.observed_status is not None]
    assert "Flow2 (M1 and DMM circuit)" in reasons[-1]
    assert "Flow6 (Station B entrance slits)" in reasons[-1]


@pytest.mark.unit
async def test_a_trip_drives_unavailable_and_names_the_circuit() -> None:
    port = _ScriptedControlPort(
        readings={_FLOW2.trip_pv: [_reading(1)], _FLOW2.fault_pv or "": [_reading(0)]}
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert _statuses(observed) == ["Unavailable"]
    verdict = next(o for o in observed if not _is_probe(o))
    assert "Flow2 (M1 and DMM circuit)" in verdict.reason
    assert verdict.source_kind == "EpicsPv"


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
    assert _statuses(observed) == ["Unavailable"]
    verdict = next(o for o in observed if not _is_probe(o))
    assert "Flow6" in verdict.reason
    assert "Flow2" not in verdict.reason


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
    assert _statuses(observed) == ["Unavailable", "Recovering"]
    verdicts = [o for o in observed if not _is_probe(o)]
    assert "awaiting operator confirmation" in verdicts[1].reason


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
    assert _statuses(observed) == ["Unavailable"] * 3


@pytest.mark.unit
async def test_an_instrument_fault_withholds_rather_than_clearing() -> None:
    """Flow2's sensor is lying, so nothing can be concluded about the resource.

    Flow6 being believable and clear is NOT enough. Clear requires every
    channel, because a blind channel might be the one that is tripped.
    A withhold is a reach probe now, not silence: see
    `test_a_withheld_verdict_reports_as_a_probe_not_silence` for that
    behavior pinned directly; this test's own job stays the verdict.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(1)],
            _FLOW6.trip_pv: [_reading(0)],
            _FLOW6.fault_pv or "": [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2, _FLOW6]), {_WATER})
    assert _statuses(observed) == []


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
    observed = await _collect(_observer(port, [_FLOW2, _FLOW6]), {_WATER})
    assert _statuses(observed) == []


@pytest.mark.unit
async def test_an_unreadable_trip_is_not_treated_as_clear() -> None:
    """Bad quality on the only channel leaves the aggregate unknown."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1, quality="Bad")],
            _FLOW2.fault_pv or "": [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert _statuses(observed) == []


@pytest.mark.unit
async def test_a_withheld_verdict_reports_as_a_probe_not_silence() -> None:
    """The coverage fix: an inconclusive verdict is a reach fact, not nothing.

    Same shape as `test_an_instrument_fault_withholds_rather_than_clearing`,
    checked from the probe side: every entry the withheld tick produces
    is probe-only and UNREACHED, so the trail can tell "CORA looked and
    could not tell" from "CORA was not watching this Supply at all".
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(1)],
            _FLOW6.trip_pv: [_reading(0)],
            _FLOW6.fault_pv or "": [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2, _FLOW6]), {_WATER})
    assert observed
    assert all(_is_probe(o) for o in observed)
    assert all(o.reach_tier == ReachTier.UNREACHED for o in observed)
    assert all(o.supply_code == _WATER for o in observed)


@pytest.mark.unit
async def test_comms_fault_suppresses_every_supply() -> None:
    """While BLEPS cannot be reached, nothing it said is repeatable, but
    each configured Supply still gets a probe recording that CORA was
    blind, not silence."""
    port = _ScriptedControlPort(
        readings={
            _COMMS: [_reading(1)],
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
            _VS1.trip_pv: [_reading(1)],
        }
    )
    observer = _observer(port, [_FLOW2, _VS1], communications_fault_pv=_COMMS)
    observed = await _collect(observer, {_WATER, _VACUUM})
    assert _statuses(observed) == []
    assert observed
    assert all(_is_probe(o) and o.reach_tier == ReachTier.UNREACHED for o in observed)
    assert {o.supply_code for o in observed} == {_WATER, _VACUUM}


@pytest.mark.unit
async def test_an_unread_comms_flag_also_suppresses() -> None:
    """A comms flag we cannot read is the condition it exists to report."""
    port = _ScriptedControlPort(
        readings={_FLOW2.trip_pv: [_reading(1)], _FLOW2.fault_pv or "": [_reading(0)]}
    )
    observer = _observer(port, [_FLOW2], communications_fault_pv=_COMMS)
    observed = await _collect(observer, {_WATER})
    assert _statuses(observed) == []


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
    assert _statuses(observed) == ["Unavailable"]


@pytest.mark.unit
async def test_a_disconnect_does_not_read_as_a_cleared_trip() -> None:
    """Losing the channel must never look like the trip going away.

    The trip is reported while it is believable. Then the subscription
    drops and the channel is voided: no `Recovering` verdict is ever
    emitted, so the Supply stays Unavailable rather than being walked
    back toward Available by a dead PV. That is the whole reason an
    unbelievable reading is distinct from a low one. The disconnect
    itself now surfaces as a probe (the withhold is a reach fact, not
    silence), which this test also pins.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
        },
        disconnect=frozenset({_FLOW2.trip_pv}),
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert _statuses(observed) == ["Unavailable"]
    assert "Recovering" not in _statuses(observed)
    assert _is_probe(observed[-1])
    assert observed[-1].reach_tier == ReachTier.UNREACHED


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
    assert _statuses(observed) == ["Unavailable"]
    verdict = next(o for o in observed if not _is_probe(o))
    assert "Flow2" in verdict.reason


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
    assert set(_statuses(observed)) <= {"Unavailable", "Recovering"}


@pytest.mark.unit
async def test_a_readings_effect_is_scoped_to_its_own_supply_not_every_configured_one() -> None:
    """A reading on one Supply's channel must never touch a sibling Supply.

    Regression: an earlier version recomputed and yielded an entry for
    EVERY configured Supply on every single reading, which defeats the
    probe trail's whole purpose -- a vacuum-section PV ticking would
    refresh the cooling-water Supply's `entries_supply_probes` row too,
    making a genuinely silent Supply look continuously watched for as
    long as any sibling kept talking. Flow2 (water) is read to a full,
    conclusive verdict first; the single vacuum reading that follows
    must produce exactly one entry, for vacuum, not two.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2.trip_pv: [_reading(1)],
            _FLOW2.fault_pv or "": [_reading(0)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2, _VS1]), {_WATER, _VACUUM})
    assert {o.supply_code for o in observed} == {_WATER}, (
        "no channel of _VS1 (vacuum) was ever read, so vacuum must never appear"
    )


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

    while_believed = observer._observations(
        channels, latest, affected_supply_codes=frozenset({_WATER})
    )
    assert [o.observed_status for o in while_believed] == ["Unavailable"]

    # Flow2's own sensor goes over-range. Its trip never cleared.
    latest[_FLOW2.fault_pv or ""] = True
    after_going_blind = observer._observations(
        channels, latest, affected_supply_codes=frozenset({_WATER})
    )

    assert [o.observed_status for o in after_going_blind] == [None], (
        "losing sight of the tripped channel must withhold, not report clear"
    )
    assert after_going_blind[0].reach_tier == ReachTier.UNREACHED


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
    observed = await _collect(_observer(port, [_FLOW6, _FLOW2]), {_WATER})
    assert _statuses(observed) == []


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


@pytest.mark.unit
def test_conventional_epics_binary_labels_decode() -> None:
    """A `bi` record naming ITS states with the stock EPICS ZNAM/ONAM
    pair decodes via `binary_signal.binary_code`, the same convention
    the enclosure permit, beam-availability and capture observers
    already read. This is the one case `test_an_enum_label_is_
    uninterpretable_not_low` above deliberately does NOT cover: BLEPS's
    OWN label pair (hypothesized as "TRIP" / "OK", unconfirmed) is a
    facility choice this function still refuses to guess at, so both
    behaviors stand side by side rather than one replacing the other.
    """
    assert flag_state_from_reading(_reading("ON")) is True
    assert flag_state_from_reading(_reading("OFF")) is False


@pytest.mark.unit
async def test_a_believable_warning_alone_drives_degraded() -> None:
    """No trip, one believable warning: the Supply degrades, not trips."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2_W.fault_pv or "": [_reading(0)],
            _FLOW2_W.trip_pv: [_reading(0)],
            _FLOW2_W.warning_pv or "": [_reading(1)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2_W]), {_WATER})
    assert _statuses(observed) == ["Degraded"]
    verdict = next(o for o in observed if not _is_probe(o))
    assert "Flow2" in verdict.reason
    assert verdict.source_id == _FLOW2_W.warning_pv


@pytest.mark.unit
async def test_a_trip_dominates_a_sibling_channels_warning() -> None:
    """Flow6 warns, Flow2 trips: the Supply reports the worse fact."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2_W.fault_pv or "": [_reading(0)],
            _FLOW2_W.trip_pv: [_reading(1)],
            _FLOW6_W.fault_pv or "": [_reading(0)],
            _FLOW6_W.trip_pv: [_reading(0)],
            _FLOW6_W.warning_pv or "": [_reading(1)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2_W, _FLOW6_W]), {_WATER})
    assert set(_statuses(observed)) == {"Unavailable"}


@pytest.mark.unit
def test_a_tripped_channels_own_warning_reading_is_moot() -> None:
    """The same physical quantity cannot be both; the trip already dominates.

    Driven through `_observations` directly so the tripped channel's
    warning PV can be asserted in `latest` alongside its trip, a
    combination a real transducer would never actually report but which
    the fold must still handle without contradicting itself.
    """
    observer = _observer(_ScriptedControlPort(readings={}), [_FLOW2_W])
    channels = [_FLOW2_W]
    latest: dict[str, bool | None] = {
        _FLOW2_W.fault_pv or "": False,
        _FLOW2_W.trip_pv: True,
        _FLOW2_W.warning_pv or "": True,
    }
    observed = observer._observations(channels, latest, affected_supply_codes=frozenset({_WATER}))
    assert [o.observed_status for o in observed] == ["Unavailable"]


@pytest.mark.unit
async def test_an_unread_warning_channel_blocks_clear() -> None:
    """Clear needs every channel's warning reading believable too, not just its trip."""
    port = _ScriptedControlPort(
        readings={
            _FLOW2_W.fault_pv or "": [_reading(0)],
            _FLOW2_W.trip_pv: [_reading(0)],
            # warning_pv never reads: latest[warning_pv] stays absent (None).
        }
    )
    observed = await _collect(_observer(port, [_FLOW2_W]), {_WATER})
    assert _statuses(observed) == []
    assert observed
    assert all(_is_probe(o) and o.reach_tier == ReachTier.UNREACHED for o in observed)


@pytest.mark.unit
async def test_warnings_stay_off_when_channel_carries_no_warning_pv() -> None:
    """`warning_pv=None` (the default, and every pre-existing fixture) behaves
    exactly as before this feature existed: no warning axis at all."""
    port = _ScriptedControlPort(
        readings={_FLOW2.trip_pv: [_reading(0)], _FLOW2.fault_pv or "": [_reading(0)]}
    )
    observed = await _collect(_observer(port, [_FLOW2]), {_WATER})
    assert _statuses(observed) == ["Recovering"]


@pytest.mark.unit
async def test_recovering_from_a_trip_through_the_warning_band_reaches_degraded() -> None:
    """Tripped, then still within the warning band on the way down: the
    observer reports Degraded, not a repeated Unavailable or a bare clear.

    `cora.supply._monitor`'s own skip for this exact sequence (a monitor
    cannot un-downgrade a Supply already Unavailable) is pinned at the
    integration level, against a real Supply aggregate; this test only
    covers what the observer itself reports.
    """
    port = _ScriptedControlPort(
        readings={
            _FLOW2_W.fault_pv or "": [_reading(0)],
            _FLOW2_W.trip_pv: [_reading(1), _reading(0)],
            _FLOW2_W.warning_pv or "": [_reading(0), _reading(1)],
        }
    )
    observed = await _collect(_observer(port, [_FLOW2_W]), {_WATER})
    assert "Degraded" in _statuses(observed)


# --------------------------------------------------------------------------
# Probe ticks
#
# A quiet interlock pushes nothing, so without a timer the trail cannot
# tell "the supply has been fine for six hours" from "CORA stopped
# looking six hours ago". These pin what a tick claims and, more
# importantly, what it refuses to claim.
#
# Every test here needs a subscription that stays OPEN with no traffic
# (`hang`), because a scripted stream that runs out ends `_drain` before
# any tick can fire. That is the real shape anyway: a healthy BLEPS is a
# live monitor saying nothing.
# --------------------------------------------------------------------------

_ALL_WATER_PVS = frozenset(
    {_COMMS, _FLOW2.trip_pv, _FLOW2.fault_pv or "", _FLOW6.trip_pv, _FLOW6.fault_pv or ""}
)
_ALL_PVS = _ALL_WATER_PVS | {_VS1.trip_pv}


async def _collect_probes_until(
    gen: AsyncGenerator[SupplyObservation],
    predicate: Callable[[list[SupplyObservation]], bool],
    *,
    timeout_seconds: float = 2.0,
) -> list[SupplyObservation]:
    """Drain `gen` until `predicate(collected)` holds, then close it.

    The poll tests' generator never ends on its own (subscriptions hang,
    the poller ticks forever), so `_collect` would block until the
    suite's own timeout killed it.
    """
    collected: list[SupplyObservation] = []

    async def _drain() -> None:
        async for observation in gen:
            collected.append(observation)
            if predicate(collected):
                break

    try:
        await asyncio.wait_for(_drain(), timeout=timeout_seconds)
    finally:
        await gen.aclose()
    return collected


def _observe(observer: BlepsSupplyObserver, codes: set[str]) -> AsyncGenerator[SupplyObservation]:
    return observer.observe(SupplyObserverScope(supply_codes=frozenset(codes)))


@pytest.mark.unit
async def test_probe_tick_disabled_by_default_leaves_a_quiet_supply_silent() -> None:
    """The pre-feature behaviour, and the kill switch's off position.

    `probe_tick_seconds` defaults to None, so no poll task is created at
    all and a live-but-quiet subscription yields nothing whatsoever.
    This is also the state every deployment boots in.
    """
    port = _ScriptedControlPort(readings={}, hang=_ALL_WATER_PVS)
    gen = _observe(_observer(port, [_FLOW2], communications_fault_pv=_COMMS), {_WATER})
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(gen), timeout=0.05)
    finally:
        await gen.aclose()


@pytest.mark.unit
async def test_probe_tick_relays_one_row_per_supply_when_every_channel_answers() -> None:
    port = _ScriptedControlPort(readings={}, hang=_ALL_PVS)
    observer = _observer(
        port, [_FLOW2, _FLOW6, _VS1], communications_fault_pv=_COMMS, probe_tick_seconds=0.01
    )

    collected = await _collect_probes_until(
        _observe(observer, {_WATER, _VACUUM}),
        lambda obs: {o.supply_code for o in obs} >= {_WATER, _VACUUM},
    )

    by_code = {o.supply_code: o for o in collected}
    assert set(by_code) == {_WATER, _VACUUM}
    for supply_code, probe in by_code.items():
        assert probe.observed_status is None, supply_code
        assert probe.reach_tier is ReachTier.RELAYED, supply_code
        assert probe.source_kind == "EpicsPv"
    # Attributed to the Supply's first trip PV, the same representative
    # channel a real verdict names.
    assert by_code[_WATER].source_id == _FLOW2.trip_pv
    assert by_code[_VACUUM].source_id == _VS1.trip_pv


@pytest.mark.unit
async def test_probe_tick_is_unreached_when_any_single_channel_cannot_be_read() -> None:
    """One dark channel out of five costs the Supply its coverage claim.

    This is the whole safety content of the tick, and the same asymmetry
    `_verdict` applies to believability: a row saying RELAYED means CORA
    saw the WHOLE Supply this tick. Grading on "most channels answered"
    would write exactly the false coverage claim the trail exists to
    rule out, and it would be invisible, because the row looks identical
    to a healthy one.

    The failing PV is named rather than the representative one: an
    UNREACHED row is only actionable if it says which channel to go and
    look at.
    """
    port = _ScriptedControlPort(
        readings={}, hang=_ALL_WATER_PVS, read_failures=frozenset({_FLOW6.trip_pv})
    )
    observer = _observer(
        port, [_FLOW2, _FLOW6], communications_fault_pv=_COMMS, probe_tick_seconds=0.01
    )

    collected = await _collect_probes_until(_observe(observer, {_WATER}), lambda obs: bool(obs))

    probe = collected[0]
    assert probe.supply_code == _WATER
    assert probe.observed_status is None
    assert probe.reach_tier is ReachTier.UNREACHED
    assert probe.source_id == _FLOW6.trip_pv


@pytest.mark.unit
async def test_probe_tick_confines_an_unreachable_channel_to_its_own_supply() -> None:
    """A dark cooling-water circuit must not cost the vacuum Supply its row.

    One poller per Supply is what makes this true. A single poller over
    the union of channels would grade every Supply by the worst channel
    anywhere on the beamline, which is the same smearing the push path's
    `affected_supply_codes` scoping already prevents.
    """
    port = _ScriptedControlPort(
        readings={}, hang=_ALL_PVS, read_failures=frozenset({_FLOW2.fault_pv or ""})
    )
    observer = _observer(
        port, [_FLOW2, _VS1], communications_fault_pv=_COMMS, probe_tick_seconds=0.01
    )

    collected = await _collect_probes_until(
        _observe(observer, {_WATER, _VACUUM}),
        lambda obs: {o.supply_code for o in obs} >= {_WATER, _VACUUM},
    )

    by_code = {o.supply_code: o for o in collected}
    assert by_code[_WATER].reach_tier is ReachTier.UNREACHED
    assert by_code[_WATER].source_id == _FLOW2.fault_pv
    assert by_code[_VACUUM].reach_tier is ReachTier.RELAYED


@pytest.mark.unit
async def test_probe_tick_is_unreached_for_every_supply_when_the_comms_flag_is_dark() -> None:
    """The comms flag is in every Supply's read set, not just the first one's.

    It is a fact about the whole feed: a Supply whose comms flag cannot
    be read cannot be assessed at all (`_communications_lost` withholds
    every verdict), so a tick that missed it has not reached that Supply
    either, however well its own circuits answered.
    """
    port = _ScriptedControlPort(readings={}, hang=_ALL_PVS, read_failures=frozenset({_COMMS}))
    observer = _observer(
        port, [_FLOW2, _VS1], communications_fault_pv=_COMMS, probe_tick_seconds=0.01
    )

    collected = await _collect_probes_until(
        _observe(observer, {_WATER, _VACUUM}),
        lambda obs: {o.supply_code for o in obs} >= {_WATER, _VACUUM},
    )

    by_code = {o.supply_code: o for o in collected}
    assert [p.reach_tier for p in by_code.values()] == [ReachTier.UNREACHED] * 2
    assert {p.source_id for p in by_code.values()} == {_COMMS}


@pytest.mark.unit
async def test_probe_tick_carries_no_status_claim_even_with_a_trip_standing() -> None:
    """A timer can never move a Supply, and this is the test that says so.

    The push path here reports `Unavailable` from a real trip, and every
    subsequent tick reads that same tripped PV successfully. A tick that
    folded its reads into the verdict would start re-emitting
    `Unavailable` on a timer: harmless-looking, but it would mean the
    poll path can drive a status transition without carrying any of the
    believability fold, the comms gate, or the all-channels-clear
    asymmetry that make the push path safe.
    """
    port = _ScriptedControlPort(
        readings={
            _COMMS: [_reading(0)],
            _FLOW2.fault_pv or "": [_reading(0)],
            _FLOW2.trip_pv: [_reading(1)],
        },
        hang=_ALL_WATER_PVS,
    )
    observer = _observer(port, [_FLOW2], communications_fault_pv=_COMMS, probe_tick_seconds=0.01)

    def _ticks(obs: list[SupplyObservation]) -> list[SupplyObservation]:
        # RELAYED with no status claim is reachable only from `_poll`:
        # `_observations` grades its probe-only entries UNREACHED
        # without exception, and its RELAYED entries always carry a
        # status. So this counts poll ticks and nothing else.
        return [o for o in obs if o.observed_status is None and o.reach_tier is ReachTier.RELAYED]

    collected = await _collect_probes_until(
        _observe(observer, {_WATER}), lambda obs: len(_ticks(obs)) >= 3
    )

    assert len(_ticks(collected)) >= 3, "the poller must have ticked repeatedly"
    # The trip is reported ONCE, by the push path, and never re-asserted
    # by a timer. This is the assertion that catches a `_poll` folding
    # its reads into `latest`: the observer emits levels rather than
    # edges, so a verdict-bearing tick would republish `Unavailable`
    # every 10ms for as long as the trip stands.
    assert _statuses(collected).count("Unavailable") == 1


@pytest.mark.unit
async def test_probe_tick_queued_after_the_last_pump_ended_is_still_yielded() -> None:
    """The teardown race `_drain`'s leftover drain exists for.

    A poller can queue a probe AFTER the final `_PumpDone` was queued
    but before the loop reads it, which puts the probe behind the
    sentinel in FIFO order. The loop stops on the sentinel, so without
    the leftover drain that probe is dropped on the floor at every
    re-subscribe.

    Driven by hand rather than with `_collect_probes_until`, which is
    what makes it deterministic instead of a race: the single pump ends
    immediately, so by the time the first push observation is yielded
    the queue already holds its `_PumpDone`. The test's own sleep is
    then the window in which the poller appends probes BEHIND that
    sentinel, and the second `anext` can only produce one by way of the
    leftover drain, because the main loop has already stopped.
    """
    port = _ScriptedControlPort(readings={_VS1.trip_pv: [_reading(0)]})
    observer = _observer(port, [_VS1], probe_tick_seconds=0.001)
    gen = _observe(observer, {_VACUUM})
    try:
        pushed = await anext(gen)
        assert pushed.observed_status == "Recovering", "the push path yields first"

        await asyncio.sleep(0.05)  # the poller ticks, queueing behind _PumpDone

        leftover = await anext(gen)
        assert leftover.observed_status is None
        assert leftover.reach_tier is ReachTier.RELAYED
    finally:
        await gen.aclose()


@pytest.mark.unit
async def test_probe_tick_keeps_running_after_its_supply_push_path_dies() -> None:
    """The reason the poller is a sibling of the pumps, not nested in one.

    The vacuum Supply's only subscription disconnects immediately. Its
    poller must keep ticking anyway: with the push path dead, those
    probes are the only remaining evidence about whether CORA can still
    see that Supply, and they are what would show its recovery. A poller
    created inside `_pump` would die with the subscription and go
    permanently silent on exactly the Supply worth watching.
    """
    port = _ScriptedControlPort(
        readings={_COMMS: [_reading(0)]},
        hang=_ALL_WATER_PVS,
        disconnect=frozenset({_VS1.trip_pv}),
    )
    observer = _observer(
        port, [_FLOW2, _VS1], communications_fault_pv=_COMMS, probe_tick_seconds=0.01
    )

    def _relayed_vacuum(obs: list[SupplyObservation]) -> int:
        return sum(1 for o in obs if o.supply_code == _VACUUM and o.reach_tier is ReachTier.RELAYED)

    collected = await _collect_probes_until(
        _observe(observer, {_WATER, _VACUUM}), lambda obs: _relayed_vacuum(obs) >= 2
    )

    # The dead subscription also makes the push path emit its own
    # UNREACHED entry for the vacuum Supply (its only channel just went
    # unreadable), which is correct and not what this test is about.
    # RELAYED is the discriminator: with the pump gone, nothing but a
    # poll tick can produce one.
    assert _relayed_vacuum(collected) >= 2, "the vacuum poller must outlive its dead subscription"
    assert all(o.observed_status is None for o in collected if o.supply_code == _VACUUM)
