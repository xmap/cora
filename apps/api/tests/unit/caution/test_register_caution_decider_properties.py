"""Property-based tests for `register_caution.decide` (Caution BC).

Complements the example-based `test_register_caution_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id, authored_by) -> list[CautionRegistered]

Load-bearing properties:

  - Any non-None state always raises `CautionAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the happy path the single `CautionRegistered` carries the
    injected/passthrough fields: caution_id=new_id, target, category,
    severity, text (trimmed), workaround (trimmed), authored_by,
    parent_id=None (top-level register), occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.caution.aggregates.caution import (
    AssetTarget,
    Caution,
    CautionAlreadyExistsError,
    CautionCategory,
    CautionRegistered,
    CautionSeverity,
    CautionStatus,
    CautionText,
    CautionWorkaround,
)
from cora.caution.features import register_caution
from cora.caution.features.register_caution import RegisterCaution
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_TEXT = printable_ascii_text(min_size=1, max_size=2000)
_WORKAROUND = printable_ascii_text(min_size=1, max_size=2000)
_CATEGORY = st.sampled_from(list(CautionCategory))
_SEVERITY = st.sampled_from(list(CautionSeverity))
_STATUS = st.sampled_from(list(CautionStatus))


def _command(
    *,
    asset_uuid: UUID,
    category: CautionCategory,
    severity: CautionSeverity,
    text: str,
    workaround: str,
) -> RegisterCaution:
    return RegisterCaution(
        target=AssetTarget(asset_id=asset_uuid),
        category=category,
        severity=severity,
        text=text,
        workaround=workaround,
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=_STATUS,
    asset_uuid=st.uuids(),
    category=_CATEGORY,
    severity=_SEVERITY,
    text=_TEXT,
    workaround=_WORKAROUND,
    now=aware_datetimes(),
    new_id=st.uuids(),
    authored_by_uuid=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: CautionStatus,
    asset_uuid: UUID,
    category: CautionCategory,
    severity: CautionSeverity,
    text: str,
    workaround: str,
    now: datetime,
    new_id: UUID,
    authored_by_uuid: UUID,
) -> None:
    """Any non-None state raises CautionAlreadyExistsError carrying state.id."""
    existing = Caution(
        id=existing_id,
        target=AssetTarget(asset_id=UUID(int=8)),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.NOTICE,
        text=CautionText("prior"),
        workaround=CautionWorkaround("prior workaround"),
        authored_by=ActorId(UUID(int=9)),
        status=existing_status,
    )
    with pytest.raises(CautionAlreadyExistsError) as exc:
        register_caution.decide(
            state=existing,
            command=_command(
                asset_uuid=asset_uuid,
                category=category,
                severity=severity,
                text=text,
                workaround=workaround,
            ),
            now=now,
            new_id=new_id,
            authored_by=ActorId(authored_by_uuid),
        )
    assert exc.value.caution_id == existing_id


@pytest.mark.unit
@given(
    asset_uuid=st.uuids(),
    category=_CATEGORY,
    severity=_SEVERITY,
    text=_TEXT,
    workaround=_WORKAROUND,
    now=aware_datetimes(),
    new_id=st.uuids(),
    authored_by_uuid=st.uuids(),
)
def test_register_emits_single_event_with_injected_fields(
    asset_uuid: UUID,
    category: CautionCategory,
    severity: CautionSeverity,
    text: str,
    workaround: str,
    now: datetime,
    new_id: UUID,
    authored_by_uuid: UUID,
) -> None:
    """Empty stream + valid command emits one CautionRegistered with injected fields."""
    authored_by = ActorId(authored_by_uuid)
    events = register_caution.decide(
        state=None,
        command=_command(
            asset_uuid=asset_uuid,
            category=category,
            severity=severity,
            text=text,
            workaround=workaround,
        ),
        now=now,
        new_id=new_id,
        authored_by=authored_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, CautionRegistered)
    assert event.caution_id == new_id
    assert event.target == AssetTarget(asset_id=asset_uuid)
    assert event.category == category.value
    assert event.severity == severity.value
    assert event.text == text
    assert event.workaround == workaround
    assert event.authored_by == authored_by
    assert event.parent_id is None
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    asset_uuid=st.uuids(),
    category=_CATEGORY,
    severity=_SEVERITY,
    text=_TEXT,
    workaround=_WORKAROUND,
    now=aware_datetimes(),
    new_id=st.uuids(),
    authored_by_uuid=st.uuids(),
)
def test_register_is_pure_same_input_same_output(
    asset_uuid: UUID,
    category: CautionCategory,
    severity: CautionSeverity,
    text: str,
    workaround: str,
    now: datetime,
    new_id: UUID,
    authored_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command(
        asset_uuid=asset_uuid,
        category=category,
        severity=severity,
        text=text,
        workaround=workaround,
    )
    authored_by = ActorId(authored_by_uuid)
    first = register_caution.decide(
        state=None, command=command, now=now, new_id=new_id, authored_by=authored_by
    )
    second = register_caution.decide(
        state=None, command=command, now=now, new_id=new_id, authored_by=authored_by
    )
    assert first == second
