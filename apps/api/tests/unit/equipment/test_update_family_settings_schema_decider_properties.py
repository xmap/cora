"""Property-based tests for `update_family_settings_schema.decide` (Equipment BC).

Complements the example-based
`test_update_family_settings_schema_decider.py` with universal claims
across generated inputs. The decider is a pure, guard-free condition
mutation

    (state, command, now) -> list[FamilySettingsSchemaUpdated]

with no source-state check: schema iteration is independent of the
Defined / Versioned / Deprecated content lifecycle.

Load-bearing properties:

  - state=None always raises `FamilyNotFoundError` carrying
    command.family_id, regardless of the proposed schema.
  - Any existing state with a schema that differs from the proposed one
    emits exactly one `FamilySettingsSchemaUpdated`
    (settings_schema=proposed, occurred_at=now) in EVERY `FamilyStatus`:
    the decider is lifecycle-agnostic, so a future status value cannot
    silently suppress the event.
  - The emitted event's family_id is `state.id`, never `command.family_id`.
  - Proposing the schema already held is a no-op (returns []), including
    the None == None case.
  - A non-None settings_schema that violates the subset raises
    `InvalidFamilySettingsSchemaError`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.family import (
    Family,
    FamilyName,
    FamilyNotFoundError,
    FamilySettingsSchemaUpdated,
    FamilyStatus,
    InvalidFamilySettingsSchemaError,
)
from cora.equipment.features import update_family_settings_schema
from cora.equipment.features.update_family_settings_schema import UpdateFamilySettingsSchema
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _capability(
    *,
    status: FamilyStatus = FamilyStatus.DEFINED,
    settings_schema: dict[str, Any] | None = None,
    family_id: UUID,
) -> Family:
    return Family(
        id=family_id,
        name=FamilyName("Tomography"),
        status=status,
        settings_schema=settings_schema,
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
@given(family_id=st.uuids(), now=aware_datetimes())
def test_update_schema_with_none_state_always_raises_not_found(
    family_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `FamilyNotFoundError` carrying command.family_id."""
    with pytest.raises(FamilyNotFoundError) as exc:
        update_family_settings_schema.decide(
            state=None,
            command=UpdateFamilySettingsSchema(
                family_id=family_id, settings_schema=_valid_schema()
            ),
            now=now,
        )
    assert exc.value.family_id == family_id


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    status=st.sampled_from(FamilyStatus),
    now=aware_datetimes(),
)
def test_update_schema_in_any_lifecycle_state_emits_single_event(
    family_id: UUID,
    status: FamilyStatus,
    now: datetime,
) -> None:
    """Lifecycle-agnostic: a changed schema emits one event in every status."""
    new_schema = _valid_schema(min_val=10)
    events = update_family_settings_schema.decide(
        state=_capability(status=status, settings_schema=None, family_id=family_id),
        command=UpdateFamilySettingsSchema(family_id=family_id, settings_schema=new_schema),
        now=now,
    )
    assert events == [
        FamilySettingsSchemaUpdated(
            family_id=family_id,
            settings_schema=new_schema,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    state_family_id=st.uuids(),
    command_family_id=st.uuids(),
    now=aware_datetimes(),
)
def test_update_schema_emits_event_with_state_id_not_command_id(
    state_family_id: UUID,
    command_family_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's family_id is state.id, not command.family_id."""
    assume(state_family_id != command_family_id)
    events = update_family_settings_schema.decide(
        state=_capability(settings_schema=None, family_id=state_family_id),
        command=UpdateFamilySettingsSchema(
            family_id=command_family_id, settings_schema=_valid_schema()
        ),
        now=now,
    )
    assert events[0].family_id == state_family_id


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    status=st.sampled_from(FamilyStatus),
    now=aware_datetimes(),
)
def test_update_schema_with_unchanged_value_returns_empty(
    family_id: UUID,
    status: FamilyStatus,
    now: datetime,
) -> None:
    """Re-proposing the held schema is a no-op (returns []) in any status."""
    schema = _valid_schema()
    events = update_family_settings_schema.decide(
        state=_capability(status=status, settings_schema=schema, family_id=family_id),
        command=UpdateFamilySettingsSchema(family_id=family_id, settings_schema=schema),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(family_id=st.uuids(), now=aware_datetimes())
def test_update_schema_with_none_on_both_sides_returns_empty(
    family_id: UUID,
    now: datetime,
) -> None:
    """None == None is the unchanged case: returns [] (no clear event)."""
    events = update_family_settings_schema.decide(
        state=_capability(settings_schema=None, family_id=family_id),
        command=UpdateFamilySettingsSchema(family_id=family_id, settings_schema=None),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(family_id=st.uuids(), now=aware_datetimes())
def test_update_schema_without_dollar_schema_raises_invalid(
    family_id: UUID,
    now: datetime,
) -> None:
    """A non-None schema missing $schema raises InvalidFamilySettingsSchemaError."""
    with pytest.raises(InvalidFamilySettingsSchemaError):
        update_family_settings_schema.decide(
            state=_capability(settings_schema=None, family_id=family_id),
            command=UpdateFamilySettingsSchema(
                family_id=family_id, settings_schema={"type": "object"}
            ),
            now=now,
        )


@pytest.mark.unit
@given(family_id=st.uuids(), now=aware_datetimes())
def test_update_schema_is_pure_same_input_same_output(
    family_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _capability(settings_schema=None, family_id=family_id)
    command = UpdateFamilySettingsSchema(family_id=family_id, settings_schema=_valid_schema())
    first = update_family_settings_schema.decide(state=state, command=command, now=now)
    second = update_family_settings_schema.decide(state=state, command=command, now=now)
    assert first == second
