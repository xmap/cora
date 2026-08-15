"""Unit tests for the composition-root capture observer bridge.

Mirrors `test_enclosure_permit_observer.py`'s two-layer shape: the pure
`classify_capture_status` mapping, and the async multi-PV merge /
clean-stream-end / disconnect behaviour of `ControlPortCaptureObserver`
driven against a scripted fake `ControlPort`. The one behavioral
difference pinned throughout: where the Enclosure bridge synthesizes an
`Unknown` status on disconnect (to fail a real gate closed),
`ControlPortCaptureObserver` synthesizes NO status claim at all, because
there is no gate here and a synthesized phase would fabricate a
terminal.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from datetime import UTC, datetime

import pytest

from cora.api._capture_observer import ControlPortCaptureObserver, classify_capture_status
from cora.operation.ports.control_port import ControlNotConnectedError, Measurement
from cora.run.ports.capture_observer import (
    AnyCaptureObservation,
    CaptureLifecycleObservation,
    CaptureObserverScope,
    CapturePhase,
    CaptureProgressObservation,
)
from cora.shared.reach import ReachTier

_T = datetime(2026, 8, 13, 12, 0, 0, tzinfo=UTC)

_PHASES = {
    "Beginning scan": "Begun",
    "Collecting projections": "Progressing",
    "Scan complete": "Ended",
    "Scan aborted": "Aborted",
}


def _reading(value: object, produced_at: datetime | None = _T) -> Measurement:
    return Measurement(value=value, kind="Categorical", quality="Good", produced_at=produced_at)  # type: ignore[arg-type]


@pytest.mark.unit
def test_classify_maps_a_declared_literal_to_its_phase() -> None:
    assert classify_capture_status("Beginning scan", _PHASES) is CapturePhase.BEGUN
    assert classify_capture_status("Scan complete", _PHASES) is CapturePhase.ENDED
    assert classify_capture_status("Scan aborted", _PHASES) is CapturePhase.ABORTED


@pytest.mark.unit
def test_classify_an_undeclared_literal_is_unrecognized() -> None:
    """A vocabulary drift (a tool upgrade renaming a status) must be
    visible, never silently dropped or coerced into a nearby phase."""
    assert classify_capture_status("Some new status", _PHASES) is CapturePhase.UNRECOGNIZED


@pytest.mark.unit
def test_classify_against_an_empty_table_is_always_unrecognized() -> None:
    assert classify_capture_status("Scan complete", {}) is CapturePhase.UNRECOGNIZED


class _ScriptedControlPort:
    """Fake `ControlPort`: replays a per-address reading script.

    Same shape as `test_enclosure_permit_observer.py`'s
    `_ScriptedControlPort`: each address yields its scripted readings in
    order, then ends cleanly, hangs (models a live subscription with no
    more traffic), or disconnects. `read_results` scripts the poll path.
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
    capture_pvs: dict[str, dict[str, str]],
    *,
    status_phases: dict[str, str] | None = None,
    tick_seconds: float | None = None,
) -> ControlPortCaptureObserver:
    return ControlPortCaptureObserver(
        control_port=port,  # type: ignore[arg-type]
        capture_pvs=capture_pvs,
        status_phases=status_phases if status_phases is not None else _PHASES,
        tick_seconds=tick_seconds,
    )


async def _collect(
    observer: ControlPortCaptureObserver, codes: set[str]
) -> list[CaptureLifecycleObservation]:
    """Collect only the lifecycle kind. None of the scenarios this feeds
    declare a progress role, so this is a lossless narrowing, not a
    filter hiding anything -- see `_collect_any` for tests that mix
    both kinds on purpose."""
    scope = CaptureObserverScope(capture_codes=frozenset(codes))
    return [
        observation
        async for observation in observer.observe(scope)
        if isinstance(observation, CaptureLifecycleObservation)
    ]


async def _collect_any(
    observer: ControlPortCaptureObserver, codes: set[str]
) -> list[CaptureLifecycleObservation | CaptureProgressObservation]:
    scope = CaptureObserverScope(capture_codes=frozenset(codes))
    return [observation async for observation in observer.observe(scope)]


@pytest.mark.unit
async def test_observe_empty_scope_yields_nothing() -> None:
    observer = _observer(_ScriptedControlPort(readings={}), {"tomoscan": {"status": "pvA"}})
    assert await _collect(observer, set()) == []


@pytest.mark.unit
async def test_observe_unconfigured_code_yields_nothing() -> None:
    observer = _observer(_ScriptedControlPort(readings={}), {"tomoscan": {"status": "pvA"}})
    assert await _collect(observer, {"other-tomoscan"}) == []


@pytest.mark.unit
async def test_observe_a_code_with_no_status_role_is_excluded_from_scope() -> None:
    """A configured code missing the `status` role cannot be watched: it
    is silently excluded rather than raising, mirroring the Enclosure
    adapter's unconfigured-code behaviour."""
    observer = _observer(_ScriptedControlPort(readings={}), {"tomoscan": {"server_running": "pvA"}})
    assert await _collect(observer, {"tomoscan"}) == []


@pytest.mark.unit
async def test_observe_maps_readings_then_no_status_claim_on_clean_end() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan"), _reading("Scan complete")]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA"}})

    observations = await _collect(observer, {"tomoscan"})

    assert [(o.capture_code, o.reported_status, o.phase) for o in observations] == [
        ("tomoscan", "Beginning scan", CapturePhase.BEGUN),
        ("tomoscan", "Scan complete", CapturePhase.ENDED),
        ("tomoscan", None, None),
    ]
    assert observations[0].observed_at == _T
    assert observations[0].source_kind == "EpicsPv"
    assert observations[0].source_id == "pvA"
    # The clean-stream-end observation has NO substrate time, matching
    # the disconnect case: nothing was reported, so nothing is stamped.
    assert observations[-1].observed_at is None
    assert observations[-1].reach_tier is ReachTier.UNREACHED


@pytest.mark.unit
async def test_observe_disconnect_yields_a_single_no_status_observation() -> None:
    """The deliberate inversion from Enclosure: a disconnect must NOT
    carry `phase=CapturePhase.ENDED` or any other phase. Reading a
    disconnect as a real terminal would fabricate one the substrate
    never reported."""
    port = _ScriptedControlPort(readings={"pvA": []}, disconnect=frozenset({"pvA"}))
    observer = _observer(port, {"tomoscan": {"status": "pvA"}})

    observations = await _collect(observer, {"tomoscan"})

    assert len(observations) == 1
    assert observations[0].reported_status is None
    assert observations[0].phase is None
    assert observations[0].reach_tier is ReachTier.UNREACHED
    assert observations[0].observed_at is None


@pytest.mark.unit
async def test_observe_an_undeclared_literal_classifies_unrecognized_not_dropped() -> None:
    port = _ScriptedControlPort(readings={"pvA": [_reading("Some future firmware status")]})
    observer = _observer(port, {"tomoscan": {"status": "pvA"}})

    observations = await _collect(observer, {"tomoscan"})

    assert observations[0].reported_status == "Some future firmware status"
    assert observations[0].phase is CapturePhase.UNRECOGNIZED
    # A reading was still delivered: RELAYED, not UNREACHED. Classification
    # failure is not the same fact as a communication failure.
    assert observations[0].reach_tier is ReachTier.RELAYED


@pytest.mark.unit
async def test_observe_passes_through_an_absent_substrate_time() -> None:
    port = _ScriptedControlPort(readings={"pvA": [_reading("Scan complete", produced_at=None)]})
    observer = _observer(port, {"tomoscan": {"status": "pvA"}})

    observations = await _collect(observer, {"tomoscan"})

    assert observations[0].phase is CapturePhase.ENDED
    assert observations[0].observed_at is None


@pytest.mark.unit
async def test_observe_preserves_a_present_substrate_time() -> None:
    port = _ScriptedControlPort(readings={"pvA": [_reading("Scan complete", produced_at=_T)]})
    observer = _observer(port, {"tomoscan": {"status": "pvA"}})

    observations = await _collect(observer, {"tomoscan"})

    assert observations[0].observed_at == _T


@pytest.mark.unit
async def test_observe_merges_multiple_codes() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvB": [_reading("Scan complete")]}
    )
    observer = _observer(port, {"tomoscan-a": {"status": "pvA"}, "tomoscan-b": {"status": "pvB"}})

    observations = await _collect(observer, {"tomoscan-a", "tomoscan-b"})

    emitted = {(o.capture_code, o.phase) for o in observations if o.phase is not None}
    assert emitted == {
        ("tomoscan-a", CapturePhase.BEGUN),
        ("tomoscan-b", CapturePhase.ENDED),
    }


# ---------- Abort role ----------


@pytest.mark.unit
async def test_observe_a_code_with_no_abort_role_watches_status_only() -> None:
    """A code missing the `abort` entry behaves exactly as before this
    role existed: no abort pump is spawned, no extra observation."""
    port = _ScriptedControlPort(readings={"pvA": [_reading("Beginning scan")]})
    observer = _observer(port, {"tomoscan": {"status": "pvA"}})

    observations = await _collect(observer, {"tomoscan"})

    assert [(o.capture_code, o.phase) for o in observations] == [
        ("tomoscan", CapturePhase.BEGUN),
        ("tomoscan", None),  # status pump's clean stream end
    ]


@pytest.mark.unit
async def test_observe_a_truthy_abort_reading_is_a_direct_aborted_claim() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Collecting projections")], "pvAbort": [_reading(1)]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "abort": "pvAbort"}})

    observations = await _collect(observer, {"tomoscan"})

    aborted = [o for o in observations if o.phase is CapturePhase.ABORTED]
    assert len(aborted) == 1
    assert aborted[0].capture_code == "tomoscan"
    assert aborted[0].reported_status == "1"
    assert aborted[0].reach_tier is ReachTier.RELAYED
    assert aborted[0].source_id == "pvAbort"
    assert aborted[0].observed_at == _T


@pytest.mark.unit
async def test_observe_a_falsy_abort_reading_emits_nothing() -> None:
    """The busy record's idle/reset value between scans makes no phase
    claim at all: it must not be enqueued as a no-op observation. The
    stream then ends cleanly, which still yields its own no-status
    observation (same shape as `_pump`'s clean end) -- what must NOT
    appear is an `ABORTED` claim from the falsy reading itself."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvAbort": [_reading(0)]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "abort": "pvAbort"}})

    observations = await _collect(observer, {"tomoscan"})

    assert not any(o.phase is CapturePhase.ABORTED for o in observations)


@pytest.mark.unit
@pytest.mark.parametrize("clear_label", ["No", "no", "OFF", "False", "0"])
async def test_observe_a_clear_enum_label_reading_is_not_a_python_truthiness_trap(
    clear_label: str,
) -> None:
    """Regression: 2-BM's real `AbortScan` is a DBR_ENUM that resolves
    through the aioca adapter to the label `'No'` when idle, and
    `bool('No')` is `True` in Python. A naive truthiness check on
    `reading.value` would misclassify every idle reading as an abort;
    `_binary_code` must decode the label instead."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvAbort": [_reading(clear_label)]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "abort": "pvAbort"}})

    observations = await _collect(observer, {"tomoscan"})

    assert not any(o.phase is CapturePhase.ABORTED for o in observations)


@pytest.mark.unit
@pytest.mark.parametrize("asserted_label", ["Yes", "yes", "ON", "True", "1"])
async def test_observe_an_asserted_enum_label_reading_is_aborted(asserted_label: str) -> None:
    port = _ScriptedControlPort(
        readings={
            "pvA": [_reading("Collecting projections")],
            "pvAbort": [_reading(asserted_label)],
        }
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "abort": "pvAbort"}})

    observations = await _collect(observer, {"tomoscan"})

    assert any(o.phase is CapturePhase.ABORTED for o in observations)


@pytest.mark.unit
async def test_observe_an_unrecognized_abort_label_makes_no_claim() -> None:
    """A label this cannot decode fails toward silence, not toward a
    guessed ABORTED claim, mirroring `_enclosure_permit_observer`'s
    fail-closed posture for its own binary-label decode."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvAbort": [_reading("MAYBE")]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "abort": "pvAbort"}})

    observations = await _collect(observer, {"tomoscan"})

    assert not any(o.phase is CapturePhase.ABORTED for o in observations)


@pytest.mark.unit
async def test_observe_abort_pump_disconnect_yields_a_no_status_observation() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvAbort": []},
        disconnect=frozenset({"pvAbort"}),
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "abort": "pvAbort"}})

    observations = await _collect(observer, {"tomoscan"})

    abort_source_obs = [o for o in observations if o.source_id == "pvAbort"]
    assert len(abort_source_obs) == 1
    assert abort_source_obs[0].phase is None
    assert abort_source_obs[0].reach_tier is ReachTier.UNREACHED


@pytest.mark.unit
async def test_observe_merges_status_and_abort_readings_for_one_code() -> None:
    port = _ScriptedControlPort(
        readings={
            "pvA": [_reading("Beginning scan")],
            "pvAbort": [_reading(1)],
        }
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "abort": "pvAbort"}})

    observations = await _collect(observer, {"tomoscan"})

    phases = {o.phase for o in observations if o.phase is not None}
    assert phases == {CapturePhase.BEGUN, CapturePhase.ABORTED}


async def _only_lifecycle(
    gen: AsyncGenerator[AnyCaptureObservation],
) -> AsyncGenerator[CaptureLifecycleObservation]:
    """Narrow a raw `observe()` stream for the poll tests below, none of
    which declare a progress role: a lossless narrowing at runtime,
    same posture as `_collect`."""
    async for observation in gen:
        if isinstance(observation, CaptureLifecycleObservation):
            yield observation


async def _collect_until(
    gen: AsyncGenerator[CaptureLifecycleObservation],
    predicate: Callable[[list[CaptureLifecycleObservation]], bool],
    *,
    timeout_seconds: float = 2.0,
) -> list[CaptureLifecycleObservation]:
    collected: list[CaptureLifecycleObservation] = []

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
    port = _ScriptedControlPort(readings={"pvA": []}, hang=frozenset({"pvA"}))
    observer = _observer(port, {"tomoscan": {"status": "pvA"}})
    gen = observer.observe(CaptureObserverScope(capture_codes=frozenset({"tomoscan"})))
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(gen), timeout=0.05)
    finally:
        await gen.aclose()


@pytest.mark.unit
async def test_poll_emits_relayed_probe_on_successful_read() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": []},
        hang=frozenset({"pvA"}),
        read_results={"pvA": [_reading("Scan complete")]},
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA"}}, tick_seconds=0.01)
    scope = CaptureObserverScope(capture_codes=frozenset({"tomoscan"}))
    gen = _only_lifecycle(observer.observe(scope))

    collected = await _collect_until(gen, lambda obs: len(obs) >= 1)

    assert len(collected) == 1
    probe = collected[0]
    assert probe.capture_code == "tomoscan"
    assert probe.reported_status is None  # probe-only: makes no status claim
    assert probe.phase is None
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
    observer = _observer(port, {"tomoscan": {"status": "pvA"}}, tick_seconds=0.01)
    scope = CaptureObserverScope(capture_codes=frozenset({"tomoscan"}))
    gen = _only_lifecycle(observer.observe(scope))

    collected = await _collect_until(gen, lambda obs: len(obs) >= 1)

    assert len(collected) == 1
    assert collected[0].reported_status is None
    assert collected[0].reach_tier is ReachTier.UNREACHED


@pytest.mark.unit
async def test_poll_survives_a_disconnected_sibling_pump() -> None:
    """A poller keeps ticking for its own PV even after ANOTHER PV's pump
    disconnects, matching the Enclosure adapter's sibling-poller
    guarantee exactly. See that test for the full reasoning."""
    port = _ScriptedControlPort(
        readings={"pvB": []},
        hang=frozenset({"pvB"}),
        disconnect=frozenset({"pvA"}),
        read_results={"pvA": [_reading("Scan complete"), _reading("Scan complete")]},
    )
    observer = _observer(
        port, {"tomoscan-a": {"status": "pvA"}, "tomoscan-b": {"status": "pvB"}}, tick_seconds=0.01
    )
    gen = _only_lifecycle(
        observer.observe(
            CaptureObserverScope(capture_codes=frozenset({"tomoscan-a", "tomoscan-b"}))
        )
    )

    def _seen_disconnect_and_a_probe(obs: list[CaptureLifecycleObservation]) -> bool:
        disconnected = any(
            o.capture_code == "tomoscan-a"
            and o.reach_tier is ReachTier.UNREACHED
            and o.reported_status is None
            for o in obs
        )
        probed = any(
            o.capture_code == "tomoscan-a"
            and o.reach_tier is ReachTier.RELAYED
            and o.reported_status is None
            for o in obs
        )
        return disconnected and probed

    collected = await _collect_until(gen, _seen_disconnect_and_a_probe, timeout_seconds=2.0)

    disconnect_obs = [
        o
        for o in collected
        if o.capture_code == "tomoscan-a" and o.reach_tier is ReachTier.UNREACHED
    ]
    probe_obs = [
        o for o in collected if o.capture_code == "tomoscan-a" and o.reach_tier is ReachTier.RELAYED
    ]
    assert disconnect_obs, "pump A's disconnect must still be observed"
    assert probe_obs, "the poller for A must keep ticking after A's pump has died"


# ---------- Progress roles (images_saved / images_collected) ----------


@pytest.mark.unit
async def test_observe_a_code_with_no_progress_roles_is_unaffected() -> None:
    """A code declaring no progress role behaves exactly as before this
    role existed: no progress pump, no extra observation."""
    port = _ScriptedControlPort(readings={"pvA": [_reading("Beginning scan")]})
    observer = _observer(port, {"tomoscan": {"status": "pvA"}})

    observations = await _collect_any(observer, {"tomoscan"})

    assert not any(isinstance(o, CaptureProgressObservation) for o in observations)


@pytest.mark.unit
async def test_observe_a_numeric_progress_reading_is_a_progress_observation() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvSaved": [_reading(42)]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    progress = [o for o in observations if isinstance(o, CaptureProgressObservation)]
    assert len(progress) == 1
    assert progress[0].capture_code == "tomoscan"
    assert progress[0].role == "images_saved"
    assert progress[0].value == 42.0
    assert progress[0].reach_tier is ReachTier.RELAYED
    assert progress[0].source_id == "pvSaved"
    assert progress[0].observed_at == _T


@pytest.mark.unit
async def test_observe_a_real_2bm_progress_string_keeps_numerator_and_total() -> None:
    """2-BM's real PVs are `stringout` records: TomoScan's
    `update_status()` writes `"<done>/<total>"`, never a bare number.
    The regression this guards: the first cut assumed a plain float,
    which would have silently recorded nothing against the real
    beamline (caught by checking the upstream source, not by the unit
    tests, which originally only exercised bare integers). Both halves
    are now carried: the total is evidence for a witnessed terminal,
    never a completeness test (see `CaptureProgressSnapshot`)."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvSaved": [_reading("1561/1561")]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    progress = [o for o in observations if isinstance(o, CaptureProgressObservation)]
    assert len(progress) == 1
    assert progress[0].value == 1561.0
    assert progress[0].commanded_total == 1561.0


@pytest.mark.unit
async def test_observe_a_real_2bm_progress_string_mid_scan() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Collecting projections")], "pvSaved": [_reading("42/1561")]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    progress = [o for o in observations if isinstance(o, CaptureProgressObservation)]
    assert progress[0].value == 42.0
    assert progress[0].commanded_total == 1561.0


@pytest.mark.unit
async def test_observe_a_bare_numeric_progress_reading_has_no_commanded_total() -> None:
    """A bare-number reading (no `/`) has nothing to carry as a total:
    `commanded_total` is `None`, not a guess."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvSaved": [_reading(42)]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    progress = [o for o in observations if isinstance(o, CaptureProgressObservation)]
    assert progress[0].value == 42.0
    assert progress[0].commanded_total is None


@pytest.mark.unit
async def test_observe_a_progress_reading_with_a_garbled_total_still_keeps_the_count() -> None:
    """A garbled or absent denominator does not drop the reading: the
    reached count is a true progress fact on its own, per
    `_progress_counts`'s fail-toward-silence posture on the numerator
    only, never the denominator."""
    port = _ScriptedControlPort(
        readings={
            "pvA": [_reading("Beginning scan")],
            "pvSaved": [_reading("2987/")],
            "pvCollected": [_reading("2987/abc")],
        }
    )
    observer = _observer(
        port,
        {
            "tomoscan": {
                "status": "pvA",
                "images_saved": "pvSaved",
                "images_collected": "pvCollected",
            }
        },
    )

    observations = await _collect_any(observer, {"tomoscan"})

    progress = {o.role: o for o in observations if isinstance(o, CaptureProgressObservation)}
    assert progress["images_saved"].value == 2987.0
    assert progress["images_saved"].commanded_total is None
    assert progress["images_collected"].value == 2987.0
    assert progress["images_collected"].commanded_total is None


@pytest.mark.unit
async def test_observe_a_malformed_progress_fraction_emits_nothing() -> None:
    """A garbled or absent NUMERATOR still drops the whole reading,
    unlike a garbled denominator (see the sibling test above): there is
    no reached count to report at all."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvSaved": [_reading("/1561")]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    assert not any(isinstance(o, CaptureProgressObservation) for o in observations)


@pytest.mark.unit
async def test_observe_two_progress_roles_for_one_code_both_emit() -> None:
    port = _ScriptedControlPort(
        readings={
            "pvA": [_reading("Beginning scan")],
            "pvSaved": [_reading(3)],
            "pvCollected": [_reading(5)],
        }
    )
    observer = _observer(
        port,
        {
            "tomoscan": {
                "status": "pvA",
                "images_saved": "pvSaved",
                "images_collected": "pvCollected",
            }
        },
    )

    observations = await _collect_any(observer, {"tomoscan"})

    progress_roles = {o.role for o in observations if isinstance(o, CaptureProgressObservation)}
    assert progress_roles == {"images_saved", "images_collected"}


@pytest.mark.unit
async def test_observe_a_non_numeric_progress_reading_emits_nothing() -> None:
    """Fail-toward-silence, mirroring the abort role's unrecognized-label
    posture: a garbled reading is dropped, never guessed at."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvSaved": [_reading("not-a-number")]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    assert not any(isinstance(o, CaptureProgressObservation) for o in observations)


@pytest.mark.unit
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
async def test_observe_a_non_finite_progress_reading_emits_nothing(bad_value: float) -> None:
    """NaN and +/-Infinity must never reach `append_observations`, which
    raises `InvalidObservationValueError` and would fail an entire batch
    over one bad reading."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvSaved": [_reading(bad_value)]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    assert not any(isinstance(o, CaptureProgressObservation) for o in observations)


@pytest.mark.unit
async def test_observe_progress_pump_has_no_unreached_counterpart() -> None:
    """A progress reading's disconnect or clean stream end simply stops
    the pump; unlike the status/abort pumps, it must NOT synthesize a
    `CaptureProgressObservation` with a fabricated value."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvSaved": []},
        disconnect=frozenset({"pvSaved"}),
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    assert not any(isinstance(o, CaptureProgressObservation) for o in observations)


@pytest.mark.unit
async def test_observe_progress_reading_preserves_a_present_substrate_time() -> None:
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvSaved": [_reading(7, produced_at=_T)]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    progress = next(o for o in observations if isinstance(o, CaptureProgressObservation))
    assert progress.observed_at == _T


@pytest.mark.unit
async def test_observe_progress_reading_with_no_substrate_time_is_none_not_synthesized() -> None:
    port = _ScriptedControlPort(
        readings={
            "pvA": [_reading("Beginning scan")],
            "pvSaved": [_reading(7, produced_at=None)],
        }
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "images_saved": "pvSaved"}})

    observations = await _collect_any(observer, {"tomoscan"})

    progress = next(o for o in observations if isinstance(o, CaptureProgressObservation))
    assert progress.observed_at is None


@pytest.mark.unit
async def test_observe_server_running_role_stays_declared_and_unread() -> None:
    """`server_running` is not in `_PROGRESS_ROLES`: declaring it must
    not spawn a pump or emit anything, per this slice's deliberate
    scope cut."""
    port = _ScriptedControlPort(
        readings={"pvA": [_reading("Beginning scan")], "pvRunning": [_reading(1)]}
    )
    observer = _observer(port, {"tomoscan": {"status": "pvA", "server_running": "pvRunning"}})

    observations = await _collect_any(observer, {"tomoscan"})

    assert not any(o.source_id == "pvRunning" for o in observations)
