"""Behavioural tests for `ControlPortRegistry`.

Coverage pins the longest-prefix-match invariant + the
NoAdapterForAddressError surface + read/write/subscribe pass-through
+ aclose fan-out idempotency. The unit tier uses InMemoryControlPort
on both routes so the test stays on the unit-tier pyramid.
"""

import pytest

from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.ports.control_port import (
    ActuationKind,
    ControlPort,
    NoAdapterForAddressError,
    Reading,
)


def _reading(value: float, kind: str = "Scalar") -> Reading:
    from datetime import UTC, datetime

    return Reading(
        value=value,
        kind=kind,  # type: ignore[arg-type]
        quality="Good",
        sampled_at=datetime(2026, 5, 29, tzinfo=UTC),
    )


@pytest.mark.unit
def test_registry_satisfies_control_port_protocol() -> None:
    """An empty registry is still a `ControlPort` per `@runtime_checkable`."""
    assert isinstance(ControlPortRegistry(), ControlPort)


@pytest.mark.unit
def test_route_raises_no_adapter_when_no_prefix_matches() -> None:
    registry = ControlPortRegistry()
    registry.register("7bma:", InMemoryControlPort())
    with pytest.raises(NoAdapterForAddressError) as exc_info:
        registry.route("2bma:rot:rbv")
    assert exc_info.value.address == "2bma:rot:rbv"


@pytest.mark.unit
def test_route_returns_matching_adapter() -> None:
    registry = ControlPortRegistry()
    aps = InMemoryControlPort()
    registry.register("2bma:", aps)
    assert registry.route("2bma:rot:rbv") is aps


@pytest.mark.unit
def test_route_picks_longest_matching_prefix_not_registration_order() -> None:
    """A more specific prefix wins regardless of when it was registered.

    Registration in `general -> specific` order would let "first match
    wins" silently steer specific addresses to the wrong adapter.
    Longest-match makes the routing decision deterministic.
    """
    registry = ControlPortRegistry()
    general = InMemoryControlPort()
    specific = InMemoryControlPort()
    registry.register("2bma:", general)
    registry.register("2bma:cam:", specific)
    assert registry.route("2bma:cam:image") is specific
    assert registry.route("2bma:rot:rbv") is general


@pytest.mark.unit
def test_register_replaces_prior_route_for_same_prefix() -> None:
    """Re-registering a prefix replaces the prior adapter (hot-swap)."""
    registry = ControlPortRegistry()
    old = InMemoryControlPort()
    new = InMemoryControlPort()
    registry.register("2bma:", old)
    registry.register("2bma:", new)
    assert registry.route("2bma:rot:rbv") is new


@pytest.mark.unit
async def test_read_dispatches_to_routed_adapter() -> None:
    registry = ControlPortRegistry()
    port = InMemoryControlPort()
    port.set_reading("2bma:rot:rbv", _reading(1.5))
    registry.register("2bma:", port)
    got = await registry.read("2bma:rot:rbv")
    assert got.value == 1.5


@pytest.mark.unit
async def test_write_dispatches_to_routed_adapter() -> None:
    registry = ControlPortRegistry()
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    registry.register("2bma:", port)
    await registry.write("2bma:rot:val", 3.14)
    assert (await port.read("2bma:rot:val")).value == 3.14


@pytest.mark.unit
async def test_subscribe_dispatches_to_routed_adapter() -> None:
    registry = ControlPortRegistry()
    port = InMemoryControlPort()
    port.set_reading("2bma:rot:rbv", _reading(0.0))
    registry.register("2bma:", port)
    iterator = registry.subscribe("2bma:rot:rbv")
    port.set_reading("2bma:rot:rbv", _reading(2.0))
    got = await anext(iterator)
    assert got.value == 2.0
    await iterator.aclose()  # type: ignore[attr-defined]  # InMemoryControlPort returns AsyncGenerator


@pytest.mark.unit
async def test_aclose_closes_every_registered_adapter() -> None:
    registry = ControlPortRegistry()
    a, b = InMemoryControlPort(), InMemoryControlPort()
    registry.register("2bma:", a)
    registry.register("7bma:", b)
    await registry.aclose()
    assert a._closed is True  # pyright: ignore[reportPrivateUsage]
    assert b._closed is True  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
async def test_aclose_is_idempotent() -> None:
    registry = ControlPortRegistry()
    registry.register("2bma:", InMemoryControlPort())
    await registry.aclose()
    await registry.aclose()  # no-op


@pytest.mark.unit
async def test_aclose_continues_when_one_adapter_raises() -> None:
    """A flaky adapter cannot strand its siblings: registry suppresses errors."""

    class _Boom:
        async def read(self, _address: str) -> Reading:  # pragma: no cover
            raise NotImplementedError

        async def write(
            self,
            _address: str,
            _value: object,
            *,
            wait: bool = True,
            timeout_s: float = 30.0,
        ) -> None:  # pragma: no cover
            raise NotImplementedError

        def subscribe(self, _address: str) -> object:  # pragma: no cover
            raise NotImplementedError

        async def aclose(self) -> None:
            raise RuntimeError("boom")

    registry = ControlPortRegistry()
    survivor = InMemoryControlPort()
    registry.register("flaky:", _Boom())  # type: ignore[arg-type]
    registry.register("ok:", survivor)
    await registry.aclose()
    assert survivor._closed is True  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
def test_route_is_simulated_defaults_false() -> None:
    """A route registered without the flag is physical by default."""
    registry = ControlPortRegistry()
    registry.register("2bma:", InMemoryControlPort())
    assert registry.route_is_simulated("2bma:rot:rbv") is False


@pytest.mark.unit
def test_route_is_simulated_returns_declared_flag() -> None:
    registry = ControlPortRegistry()
    registry.register("sim:", InMemoryControlPort(), is_simulated=True)
    assert registry.route_is_simulated("sim:rot:rbv") is True


@pytest.mark.unit
def test_route_is_simulated_uses_longest_prefix_match() -> None:
    """The simulated flag follows the same longest-match rule as `route`.

    A simulated specific prefix overrides a physical general one for
    addresses it covers, and vice versa, so a deployment can carve a
    simulated sub-band out of an otherwise live crate.
    """
    registry = ControlPortRegistry()
    registry.register("2bma:", InMemoryControlPort(), is_simulated=False)
    registry.register("2bma:sim:", InMemoryControlPort(), is_simulated=True)
    assert registry.route_is_simulated("2bma:sim:rot") is True
    assert registry.route_is_simulated("2bma:rot:rbv") is False


@pytest.mark.unit
def test_route_is_simulated_raises_when_no_prefix_matches() -> None:
    """An unrouted address is an error, never silently treated as physical."""
    registry = ControlPortRegistry()
    registry.register("7bma:", InMemoryControlPort(), is_simulated=True)
    with pytest.raises(NoAdapterForAddressError) as exc_info:
        registry.route_is_simulated("2bma:rot:rbv")
    assert exc_info.value.address == "2bma:rot:rbv"


@pytest.mark.unit
def test_register_replacement_preserves_new_simulated_flag() -> None:
    """Re-registering a prefix replaces both the adapter and its flag."""
    registry = ControlPortRegistry()
    registry.register("2bma:", InMemoryControlPort(), is_simulated=False)
    registry.register("2bma:", InMemoryControlPort(), is_simulated=True)
    assert registry.route_is_simulated("2bma:rot:rbv") is True


@pytest.mark.unit
def test_actuation_kind_has_three_values() -> None:
    """The closed enum the gate snapshots: physical, simulated, both."""
    assert [k.value for k in ActuationKind] == ["Physical", "Simulated", "Hybrid"]
