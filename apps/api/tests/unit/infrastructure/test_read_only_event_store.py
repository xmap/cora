"""The degraded-boot write guard: reads pass, appends refuse."""

from __future__ import annotations

import typing
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import EventStore
from cora.infrastructure.read_only_event_store import (
    EventWritesDisabledError,
    ReadOnlyEventStore,
)

_APPLIED = "20260624000000"
_EXPECTED = "20260713000000"


class _SpyEventStore:
    """Records what reached the inner store. Any append arriving here is
    the failure this guard exists to prevent, so the spy records rather
    than raises: a test asserting `appends == []` reads better than one
    asserting an exception did not escape."""

    def __init__(self) -> None:
        self.loads: list[tuple[str, UUID]] = []
        self.appends: list[str] = []

    async def load(self, stream_type: str, stream_id: UUID) -> tuple[list[Any], int]:
        self.loads.append((stream_type, stream_id))
        return ([], 7)

    async def append(
        self, stream_type: str, stream_id: UUID, expected_version: int, events: Any
    ) -> int:
        self.appends.append(stream_type)
        return 1

    async def append_streams(self, streams: Any, *, conn: object | None = None) -> dict[UUID, int]:
        self.appends.append("append_streams")
        return {}


def _guarded() -> tuple[ReadOnlyEventStore, _SpyEventStore]:
    inner = _SpyEventStore()
    return ReadOnlyEventStore(inner, applied=_APPLIED, expected=_EXPECTED), inner


@pytest.mark.asyncio
async def test_load_delegates_to_the_inner_store() -> None:
    guard, inner = _guarded()
    stream_id = uuid4()

    events, version = await guard.load("Run", stream_id)

    assert (events, version) == ([], 7)
    assert inner.loads == [("Run", stream_id)]


@pytest.mark.asyncio
async def test_append_refuses_and_never_reaches_the_inner_store() -> None:
    guard, inner = _guarded()

    with pytest.raises(EventWritesDisabledError):
        await guard.append("Run", uuid4(), 0, [])

    assert inner.appends == []


@pytest.mark.asyncio
async def test_append_streams_refuses_and_never_reaches_the_inner_store() -> None:
    guard, inner = _guarded()

    with pytest.raises(EventWritesDisabledError):
        await guard.append_streams([])

    assert inner.appends == []


@pytest.mark.asyncio
async def test_refusal_names_both_versions() -> None:
    """Whoever hits this is usually not whoever set the override, so the
    message has to carry the mismatch rather than assume context."""
    guard, _ = _guarded()

    with pytest.raises(EventWritesDisabledError) as caught:
        await guard.append("Run", uuid4(), 0, [])

    message = str(caught.value)
    assert _APPLIED in message
    assert _EXPECTED in message


def test_read_only_event_store_covers_every_protocol_method() -> None:
    """A method added to `EventStore` must be added here too.

    Without this, a new write method would pass straight through the
    guard to the real store: Protocol conformance is structural, so an
    unimplemented method is a missing attribute rather than a type error
    anything reports at runtime. This is the same class of gap that made
    a partial `ControlPort` wrapper leak connections by omitting
    `aclose`.
    """
    required = typing.get_protocol_members(EventStore)
    missing = {name for name in required if not hasattr(ReadOnlyEventStore, name)}
    assert not missing, (
        f"EventStore declares {sorted(missing)} but ReadOnlyEventStore does "
        f"not implement them, so calls would fall through unguarded. Add "
        f"each one, refusing if it writes and delegating if it reads."
    )
