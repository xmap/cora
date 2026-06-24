"""Unit tests for the composition-root permit observer bridge.

Two layers are pinned here: the pure, deterministic SecureM ->
permit-status mapping (`permit_status_from_reading`), and the async
multi-PV merge / clean-stream-end / disconnect behaviour of
`ControlPortEnclosureObserver` driven against a scripted fake
`ControlPort`.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime

import pytest

from cora.api._enclosure_permit_observer import (
    ControlPortEnclosureObserver,
    permit_status_from_reading,
)
from cora.enclosure.ports.enclosure_observer import (
    EnclosureObservation,
    EnclosureObserverScope,
)
from cora.infrastructure.ports.clock import FakeClock
from cora.operation.ports.control_port import ControlNotConnectedError, Measurement

_T = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)
_T_UNKNOWN = datetime(2026, 6, 17, 13, 0, 0, tzinfo=UTC)


def _reading(value: object, quality: str = "Good") -> Measurement:
    return Measurement(value=value, kind="Scalar", quality=quality, produced_at=_T)  # type: ignore[arg-type]


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
def test_non_good_quality_flattens_to_unknown() -> None:
    assert permit_status_from_reading(_reading(1, quality="Bad")) == "Unknown"
    assert permit_status_from_reading(_reading(0, quality="Uncertain")) == "Unknown"


@pytest.mark.unit
def test_unexpected_value_flattens_to_unknown() -> None:
    assert permit_status_from_reading(_reading(2)) == "Unknown"
    assert permit_status_from_reading(_reading(None)) == "Unknown"
    assert permit_status_from_reading(_reading("secure")) == "Unknown"


class _ScriptedControlPort:
    """Fake `ControlPort`: replays a per-address reading script.

    Each address yields its scripted readings in order, then either ends
    the stream cleanly or (when listed in `disconnect`) raises
    `ControlNotConnectedError` to model a dropped subscription.
    """

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
    port: _ScriptedControlPort, permit_pvs: dict[str, str]
) -> ControlPortEnclosureObserver:
    return ControlPortEnclosureObserver(
        control_port=port,  # type: ignore[arg-type]
        permit_pvs=permit_pvs,
        clock=FakeClock(_T_UNKNOWN),
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
    # The clean-stream-end Unknown is clock-stamped, not reading-stamped.
    assert observations[-1].observed_at == _T_UNKNOWN


@pytest.mark.unit
async def test_observe_disconnect_yields_single_unknown() -> None:
    port = _ScriptedControlPort(readings={"pvA": []}, disconnect=frozenset({"pvA"}))
    observer = _observer(port, {"hutch-a": "pvA"})

    observations = await _collect(observer, {"hutch-a"})

    assert len(observations) == 1
    assert observations[0].observed_status == "Unknown"
    assert observations[0].observed_at == _T_UNKNOWN


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
