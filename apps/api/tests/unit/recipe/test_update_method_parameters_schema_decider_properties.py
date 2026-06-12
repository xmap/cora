"""Property-based tests for `update_method_parameters_schema.decide` (Recipe BC).

Complements the example-based `test_update_method_parameters_schema_decider.py`
with universal claims across generated inputs. The decider is a pure
guard-free in-place mutation

    (state, command, capability=None, now) -> list[MethodParametersSchemaUpdated]

with no source-state partition: schema iteration is independent of the
Defined / Versioned / Deprecated content lifecycle, so every status is a
valid source. The only domain guard on the (capability-free) path is
"Method must exist".

Load-bearing properties:

  - state=None always raises `MethodNotFoundError` carrying command.method_id.
  - Any existing state whose proposed schema differs from the current one
    emits exactly one `MethodParametersSchemaUpdated` (method_id=state.id,
    occurred_at=now), for EVERY MethodStatus value, so a future status
    cannot silently start raising.
  - The emitted event's method_id is `state.id`, never `command.method_id`.
  - Idempotency: proposed == current returns [] (no event emitted).
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    MethodNotFoundError,
    MethodParametersSchemaUpdated,
    MethodStatus,
)
from cora.recipe.features import update_method_parameters_schema
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

_ALL_SOURCES = tuple(MethodStatus)


def _method(
    *,
    method_id: UUID,
    status: MethodStatus = MethodStatus.DEFINED,
    parameters_schema: dict[str, Any] | None = None,
) -> Method:
    return Method(
        id=method_id,
        name=MethodName("Continuous Rotation Tomography"),
        status=status,
        parameters_schema=parameters_schema,
    )


def _valid_schema(min_val: int = 5) -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": min_val,
                "unit": {"system": "udunits", "code": "keV"},
            }
        },
    }


@pytest.mark.unit
@given(method_id=st.uuids(), now=aware_datetimes())
def test_update_with_none_state_always_raises_not_found(
    method_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `MethodNotFoundError` carrying command.method_id."""
    with pytest.raises(MethodNotFoundError) as exc:
        update_method_parameters_schema.decide(
            state=None,
            command=UpdateMethodParametersSchema(
                method_id=method_id, parameters_schema=_valid_schema()
            ),
            now=now,
        )
    assert exc.value.method_id == method_id


@pytest.mark.unit
@given(
    method_id=st.uuids(),
    source=st.sampled_from(_ALL_SOURCES),
    now=aware_datetimes(),
)
def test_update_from_any_status_emits_single_event(
    method_id: UUID,
    source: MethodStatus,
    now: datetime,
) -> None:
    """Every lifecycle status accepts the update and emits one event."""
    events = update_method_parameters_schema.decide(
        state=_method(method_id=method_id, status=source, parameters_schema=None),
        command=UpdateMethodParametersSchema(
            method_id=method_id, parameters_schema=_valid_schema()
        ),
        now=now,
    )
    assert events == [
        MethodParametersSchemaUpdated(
            method_id=method_id,
            parameters_schema=_valid_schema(),
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(method_id=st.uuids(), now=aware_datetimes())
def test_update_clearing_schema_emits_event_with_none_payload(
    method_id: UUID,
    now: datetime,
) -> None:
    """Clearing a present schema via None payload emits exactly one event."""
    events = update_method_parameters_schema.decide(
        state=_method(method_id=method_id, parameters_schema=_valid_schema()),
        command=UpdateMethodParametersSchema(method_id=method_id, parameters_schema=None),
        now=now,
    )
    assert len(events) == 1
    assert events[0].parameters_schema is None


@pytest.mark.unit
@given(
    state_method_id=st.uuids(),
    command_method_id=st.uuids(),
    now=aware_datetimes(),
)
def test_update_emits_event_with_state_id_not_command_method_id(
    state_method_id: UUID,
    command_method_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's method_id is state.id, not command.method_id."""
    assume(state_method_id != command_method_id)
    events = update_method_parameters_schema.decide(
        state=_method(method_id=state_method_id, parameters_schema=None),
        command=UpdateMethodParametersSchema(
            method_id=command_method_id, parameters_schema=_valid_schema()
        ),
        now=now,
    )
    assert events[0].method_id == state_method_id


@pytest.mark.unit
@given(
    method_id=st.uuids(),
    source=st.sampled_from(_ALL_SOURCES),
    now=aware_datetimes(),
)
def test_update_with_unchanged_schema_returns_no_event(
    method_id: UUID,
    source: MethodStatus,
    now: datetime,
) -> None:
    """Re-submitting the current schema is a no-op (returns [])."""
    schema = _valid_schema()
    events = update_method_parameters_schema.decide(
        state=_method(method_id=method_id, status=source, parameters_schema=schema),
        command=UpdateMethodParametersSchema(method_id=method_id, parameters_schema=schema),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(name=printable_ascii_text(max_size=40), method_id=st.uuids(), now=aware_datetimes())
def test_update_is_pure_same_input_same_output(
    name: str,
    method_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = Method(
        id=method_id,
        name=MethodName(name),
        status=MethodStatus.DEFINED,
        parameters_schema=None,
    )
    command = UpdateMethodParametersSchema(method_id=method_id, parameters_schema=_valid_schema())
    first = update_method_parameters_schema.decide(state=state, command=command, now=now)
    second = update_method_parameters_schema.decide(state=state, command=command, now=now)
    assert first == second
