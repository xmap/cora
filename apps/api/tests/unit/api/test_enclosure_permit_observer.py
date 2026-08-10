"""Unit tests for the composition-root permit observer bridge.

Two layers are pinned here: the pure, deterministic SecureM ->
permit-status mapping (`permit_status_from_reading`), and the async
multi-PV merge / clean-stream-end / disconnect behaviour of
`ControlPortEnclosureObserver` driven against a scripted fake
`ControlPort`.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from datetime import UTC, datetime

import pytest

from cora.api._enclosure_permit_observer import (
    ControlPortEnclosureObserver,
    permit_status_from_reading,
)
from cora.enclosure.aggregates.enclosure import ReachTier
from cora.enclosure.ports.enclosure_observer import (
    EnclosureObservation,
    EnclosureObserverScope,
)
from cora.operation.ports.control_port import ControlNotConnectedError, Measurement

_T = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _reading(
    value: object, quality: str = "Good", produced_at: datetime | None = _T
) -> Measurement:
    return Measurement(value=value, kind="Scalar", quality=quality, produced_at=produced_at)  # type: ignore[arg-type]


def _enum_reading(label: str, quality: str = "Good") -> Measurement:
    """A DBR_ENUM reading as `EpicsCaControlPort` delivers it: label, no index."""
    return Measurement(value=label, kind="Categorical", quality=quality, produced_at=_T)  # type: ignore[arg-type]


@pytest.mark.unit
def test_secure_maps_to_permitted() -> None:
    assert permit_status_from_reading(_reading(1)) == "Permitted"
    assert permit_status_from_reading(_reading(1.0)) == "Permitted"
    assert permit_status_from_reading(_reading("1")) == "Permitted"
    assert permit_status_from_reading(_reading(True)) == "Permitted"


@pytest.mark.unit
def test_insecure_maps_to_not_permitted() -> None:
    assert permit_status_from_reading(_reading(0)) == "NotPermitted"
    assert permit_status_from_reading(_reading("0")) == "NotPermitted"


@pytest.mark.unit
def test_bad_quality_flattens_to_unknown() -> None:
    assert permit_status_from_reading(_reading(1, quality="Bad")) == "Unknown"
    assert permit_status_from_reading(_reading(0, quality="Bad")) == "Unknown"


@pytest.mark.unit
def test_uncertain_quality_is_still_read_both_ways() -> None:
    """Uncertain says the process is in alarm, not that the value is wrong.

    The floor for this consumer is `Bad`, so an alarmed permit signal is
    read rather than discarded. Pinned both ways because the loosening
    is one-directional: `0` under alarm still closes the gate, `1` under
    alarm now opens it.
    """
    assert permit_status_from_reading(_reading(0, quality="Uncertain")) == "NotPermitted"
    assert permit_status_from_reading(_reading(1, quality="Uncertain")) == "Permitted"


@pytest.mark.unit
def test_unexpected_value_flattens_to_unknown() -> None:
    assert permit_status_from_reading(_reading(2)) == "Unknown"
    assert permit_status_from_reading(_reading(None)) == "Unknown"
    assert permit_status_from_reading(_reading("secure")) == "Unknown"


@pytest.mark.unit
def test_enum_label_on_maps_to_permitted() -> None:
    # The shape a real bi record delivers: 2-BM's StaA:SecureM reads 'ON'.
    assert permit_status_from_reading(_enum_reading("ON")) == "Permitted"


@pytest.mark.unit
def test_enum_label_off_maps_to_not_permitted() -> None:
    assert permit_status_from_reading(_enum_reading("OFF")) == "NotPermitted"


@pytest.mark.unit
def test_conventional_binary_labels_map_both_ways() -> None:
    for permitted, not_permitted in (("TRUE", "FALSE"), ("YES", "NO"), ("1", "0")):
        assert permit_status_from_reading(_enum_reading(permitted)) == "Permitted"
        assert permit_status_from_reading(_enum_reading(not_permitted)) == "NotPermitted"


@pytest.mark.unit
def test_enum_label_matching_ignores_case_and_padding() -> None:
    assert permit_status_from_reading(_enum_reading(" on ")) == "Permitted"
    assert permit_status_from_reading(_enum_reading("Off")) == "NotPermitted"


@pytest.mark.unit
def test_renamed_enum_label_flattens_to_unknown() -> None:
    # A facility that renames ZNAM / ONAM fails the gate closed rather
    # than guessing which of its own words means secured.
    assert permit_status_from_reading(_enum_reading("SEARCHED")) == "Unknown"
    assert permit_status_from_reading(_enum_reading("NOT SEARCHED")) == "Unknown"


@pytest.mark.unit
def test_enum_label_under_alarm_is_read_not_discarded() -> None:
    # The live 2-BM case this exists for: StaB:SecureM reads 'OFF' with a
    # designed STATE alarm, which the CA adapter reports as Uncertain.
    # An unsecured hutch should record as NotPermitted, not Unknown.
    assert permit_status_from_reading(_enum_reading("OFF", quality="Uncertain")) == "NotPermitted"


@pytest.mark.unit
def test_enum_label_under_bad_quality_still_unknown() -> None:
    # Bad is the one severity saying the value itself is untrustworthy,
    # so the label carries no weight and the gate fails closed.
    assert permit_status_from_reading(_enum_reading("OFF", quality="Bad")) == "Unknown"
    assert permit_status_from_reading(_enum_reading("ON", quality="Bad")) == "Unknown"


class _ScriptedControlPort:
    """Fake `ControlPort`: replays a per-address reading script.

    Each address yields its scripted readings in order, then either ends
    the stream cleanly, hangs forever (when listed in `hang`, modelling a
    live ongoing subscription with no more traffic), or (when listed in
    `disconnect`) raises `ControlNotConnectedError` to model a dropped
    subscription. `read_results` scripts `read()` outcomes per address
    for the poll path; a `Measurement` succeeds, an `Exception` instance
    is raised, and an address with no results left raises
    `ControlNotConnectedError`.
    """

    def __init__(
        self,
        *,
        readings: dict[str, list[Measurement]],
        disconnect: frozenset[str] = frozenset(),
        hang: frozenset[str] = frozenset(),
        read_results: dict[str, list[Measurement | Exception]] | None = None,
    ) -> None:
        self._readings = readings
        self._disconnect = disconnect
        self._hang = hang
        self._read_results = {k: list(v) for k, v in (read_results or {}).items()}

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
        results = self._read_results.get(address)
        if not results:
            raise ControlNotConnectedError(address)
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _observer(
    port: _ScriptedControlPort,
    permit_pvs: dict[str, str],
    *,
    tick_seconds: float | None = None,
) -> ControlPortEnclosureObserver:
    return ControlPortEnclosureObserver(
        control_port=port,  # type: ignore[arg-type]
        permit_pvs=permit_pvs,
        tick_seconds=tick_seconds,
    )


async def _collect(
    observer: ControlPortEnclosureObserver, codes: set[str]
) -> list[EnclosureObservation]:
    scope = EnclosureObserverScope(enclosure_codes=frozenset(codes))
    return [observation async for observation in observer.observe(scope)]


@pytest.mark.unit
async def test_observe_empty_scope_yields_nothing() -> None:
    observer = _observer(_ScriptedControlPort(readings={}), {"hutch-a": "pvA"})
    assert await _collect(observer, set()) == []


@pytest.mark.unit
async def test_observe_unconfigured_code_yields_nothing() -> None:
    observer = _observer(_ScriptedControlPort(readings={}), {"hutch-a": "pvA"})
    assert await _collect(observer, {"hutch-z"}) == []


@pytest.mark.unit
async def test_observe_maps_readings_then_unknown_on_clean_end() -> None:
    port = _ScriptedControlPort(readings={"pvA": [_reading(1), _reading(0)]})
    observer = _observer(port, {"hutch-a": "pvA"})

    observations = await _collect(observer, {"hutch-a"})

    assert [(o.enclosure_code, o.observed_status) for o in observations] == [
        ("hutch-a", "Permitted"),
        ("hutch-a", "NotPermitted"),
        ("hutch-a", "Unknown"),
    ]
    assert observations[0].observed_at == _T
    assert observations[0].source_kind == "EpicsPv"
    assert observations[0].source_id == "pvA"
    # The clean-stream-end Unknown has NO substrate time. It is synthesized
    # by CORA because the stream ended, not reported by the substrate, and
    # a clock reading here would be indistinguishable from a real one once
    # written down. When CORA learned of it lives on the event's occurred_at.
    assert observations[-1].observed_at is None


@pytest.mark.unit
async def test_observe_disconnect_yields_single_unknown() -> None:
    port = _ScriptedControlPort(readings={"pvA": []}, disconnect=frozenset({"pvA"}))
    observer = _observer(port, {"hutch-a": "pvA"})

    observations = await _collect(observer, {"hutch-a"})

    assert len(observations) == 1
    assert observations[0].observed_status == "Unknown"
    # A disconnect is the case that matters most at 2-BM: both PSS PVs
    # report an undefined stamp, so real readings already yield None. If
    # disconnects stamped a clock, the substrate-time field would be
    # populated exactly when the substrate said nothing.
    assert observations[0].observed_at is None


@pytest.mark.unit
async def test_observe_passes_through_an_absent_substrate_time() -> None:
    """A reading with no substrate time reaches the seam as None, not as a date.

    This is the live 2-BM shape, not a hypothetical: both PSS permit PVs
    report an undefined EPICS stamp on every update, so `produced_at` is
    None for every real reading there. Pinned because the bridge is the
    one place that could quietly substitute a clock.
    """
    port = _ScriptedControlPort(readings={"pvA": [_reading(1, produced_at=None)]})
    observer = _observer(port, {"hutch-a": "pvA"})

    observations = await _collect(observer, {"hutch-a"})

    assert [o.observed_status for o in observations] == ["Permitted", "Unknown"]
    # The status is still read; only the time is absent.
    assert observations[0].observed_at is None


@pytest.mark.unit
async def test_observe_preserves_a_present_substrate_time() -> None:
    """The other arm: a substrate that DOES stamp is carried verbatim.

    Paired with the absent case so neither direction can regress into a
    constant. A test that only pinned None would pass if the bridge
    dropped the field entirely.
    """
    port = _ScriptedControlPort(readings={"pvA": [_reading(1, produced_at=_T)]})
    observer = _observer(port, {"hutch-a": "pvA"})

    observations = await _collect(observer, {"hutch-a"})

    assert observations[0].observed_at == _T


@pytest.mark.unit
async def test_observe_merges_multiple_pvs() -> None:
    port = _ScriptedControlPort(readings={"pvA": [_reading(1)], "pvB": [_reading(0)]})
    observer = _observer(port, {"hutch-a": "pvA", "hutch-b": "pvB"})

    observations = await _collect(observer, {"hutch-a", "hutch-b"})

    emitted = {(o.enclosure_code, o.observed_status) for o in observations}
    assert emitted == {
        ("hutch-a", "Permitted"),
        ("hutch-a", "Unknown"),
        ("hutch-b", "NotPermitted"),
        ("hutch-b", "Unknown"),
    }


async def _collect_until(
    gen: AsyncGenerator[EnclosureObservation],
    predicate: Callable[[list[EnclosureObservation]], bool],
    *,
    timeout_seconds: float = 2.0,
) -> list[EnclosureObservation]:
    """Drain `gen` until `predicate(collected)` is true, then close it.

    Used for the poll tests below, whose generator never ends on its own
    (a live push subscription hangs; the poller ticks forever), unlike
    `_collect`, which relies on the scripted stream running out.
    """
    collected: list[EnclosureObservation] = []

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


@pytest.mark.unit
async def test_poll_disabled_by_default_emits_nothing_extra() -> None:
    # tick_seconds defaults to None: no poll task is created at all, so a
    # live (never-ending) subscription with no push traffic yields nothing.
    port = _ScriptedControlPort(readings={"pvA": []}, hang=frozenset({"pvA"}))
    observer = _observer(port, {"hutch-a": "pvA"})
    gen = observer.observe(EnclosureObserverScope(enclosure_codes=frozenset({"hutch-a"})))
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(gen), timeout=0.05)
    finally:
        await gen.aclose()


@pytest.mark.unit
async def test_poll_emits_relayed_probe_on_successful_read() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": []},
        hang=frozenset({"pvA"}),  # push subscription stays open, no traffic
        read_results={"pvA": [_reading(1)]},
    )
    observer = _observer(port, {"hutch-a": "pvA"}, tick_seconds=0.01)
    gen = observer.observe(EnclosureObserverScope(enclosure_codes=frozenset({"hutch-a"})))

    collected = await _collect_until(gen, lambda obs: len(obs) >= 1)

    assert len(collected) == 1
    probe = collected[0]
    assert probe.enclosure_code == "hutch-a"
    assert probe.observed_status is None  # probe-only: makes no status claim
    assert probe.reach_tier is ReachTier.RELAYED
    assert probe.source_kind == "EpicsPv"
    assert probe.source_id == "pvA"


@pytest.mark.unit
async def test_poll_emits_unreached_probe_on_failed_read() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": []},
        hang=frozenset({"pvA"}),
        read_results={"pvA": [ControlNotConnectedError("pvA")]},
    )
    observer = _observer(port, {"hutch-a": "pvA"}, tick_seconds=0.01)
    gen = observer.observe(EnclosureObserverScope(enclosure_codes=frozenset({"hutch-a"})))

    collected = await _collect_until(gen, lambda obs: len(obs) >= 1)

    assert len(collected) == 1
    probe = collected[0]
    assert probe.observed_status is None
    assert probe.reach_tier is ReachTier.UNREACHED


@pytest.mark.unit
async def test_poll_survives_a_disconnected_sibling_pump() -> None:
    """A poller keeps ticking for its own PV even after ANOTHER PV's pump
    disconnects.

    `_drain` only returns once EVERY pump has finished (pvB's subscribe
    hangs forever here, modelling a live PV with nothing to say), so
    pvA's poller keeps running and ticking after pvA's pump has already
    emitted its disconnect Unknown and exited. This is the load-bearing
    property that makes the poller a sibling of its pump, not a stage
    nested inside it: nesting would kill the poller the moment its own
    pump dies, with no way left to notice that PV's recovery.
    """
    port = _ScriptedControlPort(
        readings={"pvB": []},
        hang=frozenset({"pvB"}),  # pvB's pump never finishes
        disconnect=frozenset({"pvA"}),  # pvA's pump dies immediately
        read_results={"pvA": [_reading(1), _reading(1)]},
    )
    observer = _observer(port, {"hutch-a": "pvA", "hutch-b": "pvB"}, tick_seconds=0.01)
    gen = observer.observe(
        EnclosureObserverScope(enclosure_codes=frozenset({"hutch-a", "hutch-b"}))
    )

    def _seen_disconnect_and_a_probe(obs: list[EnclosureObservation]) -> bool:
        disconnected = any(
            o.enclosure_code == "hutch-a" and o.observed_status == "Unknown" for o in obs
        )
        probed = any(o.enclosure_code == "hutch-a" and o.observed_status is None for o in obs)
        return disconnected and probed

    collected = await _collect_until(gen, _seen_disconnect_and_a_probe, timeout_seconds=2.0)

    disconnect_obs = [
        o for o in collected if o.enclosure_code == "hutch-a" and o.observed_status == "Unknown"
    ]
    probe_obs = [
        o for o in collected if o.enclosure_code == "hutch-a" and o.observed_status is None
    ]
    assert disconnect_obs, "pump A's disconnect Unknown must still be observed"
    assert probe_obs, "the poller for A must keep ticking after A's pump has died"
    assert probe_obs[0].reach_tier is ReachTier.RELAYED
