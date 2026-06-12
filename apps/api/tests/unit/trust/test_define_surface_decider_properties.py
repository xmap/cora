"""Property-based tests for `define_surface.decide` (Trust BC).

Complements the example-based gate coverage with universal claims across
generated inputs. The genesis decider is pure

    (state, command, now, new_id) -> list[SurfaceDefined]

Load-bearing properties:

  - Any non-None state always raises `SurfaceAlreadyExistsError`
    carrying state.id (existence/genesis guard), regardless of command.
  - On the empty-stream happy path the single `SurfaceDefined` carries
    the injected/passthrough fields: surface_id=new_id, name (trimmed),
    kind, occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.trust.aggregates.surface import (
    Surface,
    SurfaceAlreadyExistsError,
    SurfaceDefined,
    SurfaceKind,
    SurfaceName,
    SurfaceStatus,
)
from cora.trust.features.define_surface import decider
from cora.trust.features.define_surface.command import DefineSurface
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=200)
_KIND = st.sampled_from(tuple(SurfaceKind))


def _state(*, surface_id: UUID) -> Surface:
    return Surface(
        id=surface_id,
        name=SurfaceName("System HTTP"),
        kind=SurfaceKind.HTTP,
        status=SurfaceStatus.DEFINED,
    )


def _command(*, name: str, kind: SurfaceKind) -> DefineSurface:
    return DefineSurface(name=name, kind=kind)


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    kind=_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_surface_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    name: str,
    kind: SurfaceKind,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises SurfaceAlreadyExistsError carrying state.id."""
    with pytest.raises(SurfaceAlreadyExistsError) as exc:
        decider.decide(
            state=_state(surface_id=existing_id),
            command=_command(name=name, kind=kind),
            now=now,
            new_id=new_id,
        )
    assert exc.value.surface_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    kind=_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_surface_emits_single_event_with_injected_fields(
    name: str,
    kind: SurfaceKind,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream emits one SurfaceDefined with injected/passthrough fields."""
    events = decider.decide(
        state=None,
        command=_command(name=name, kind=kind),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, SurfaceDefined)
    assert event.surface_id == new_id
    assert event.name == SurfaceName(name).value
    assert event.kind == kind
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    name=_NAME,
    kind=_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_surface_is_pure_same_input_same_output(
    name: str,
    kind: SurfaceKind,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command(name=name, kind=kind)
    first = decider.decide(state=None, command=command, now=now, new_id=new_id)
    second = decider.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
