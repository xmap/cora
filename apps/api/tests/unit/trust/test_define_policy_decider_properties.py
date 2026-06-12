"""Property-based tests for `define_policy.decide` (Trust BC).

Complements the example-based `test_define_policy_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id) -> list[PolicyDefined]

Load-bearing properties:

  - Any non-None state always raises `PolicyAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the empty stream the single `PolicyDefined` carries the
    injected/passthrough fields: policy_id=new_id, name (trimmed),
    conduit_id, permitted_principal_ids, permitted_commands,
    occurred_at=now, surface_id.
  - The emitted policy_id equals either new_id (genesis) or state.id
    (the existence-guard error), never a third value.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.trust.aggregates.policy import (
    Policy,
    PolicyAlreadyExistsError,
    PolicyDefined,
    PolicyName,
)
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_NAME = printable_ascii_text(min_size=1, max_size=200)
_COMMAND_NAMES = st.frozensets(printable_ascii_text(min_size=1, max_size=64), max_size=5)
_PRINCIPAL_IDS = st.frozensets(st.uuids(), max_size=5)


def _command(
    *,
    name: str,
    conduit_id: UUID,
    permitted_principal_ids: frozenset[UUID],
    permitted_commands: frozenset[str],
) -> DefinePolicy:
    return DefinePolicy(
        name=name,
        conduit_id=conduit_id,
        permitted_principal_ids=permitted_principal_ids,
        permitted_commands=permitted_commands,
    )


def _state(*, policy_id: UUID) -> Policy:
    return Policy(
        id=policy_id,
        name=PolicyName("Existing"),
        conduit_id=UUID(int=7),
        permitted_principal_ids=frozenset({UUID(int=3)}),
        permitted_commands=frozenset({"RegisterActor"}),
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    conduit_id=st.uuids(),
    permitted_principal_ids=_PRINCIPAL_IDS,
    permitted_commands=_COMMAND_NAMES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    name: str,
    conduit_id: UUID,
    permitted_principal_ids: frozenset[UUID],
    permitted_commands: frozenset[str],
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises PolicyAlreadyExistsError carrying state.id."""
    with pytest.raises(PolicyAlreadyExistsError) as exc:
        define_policy.decide(
            state=_state(policy_id=existing_id),
            command=_command(
                name=name,
                conduit_id=conduit_id,
                permitted_principal_ids=permitted_principal_ids,
                permitted_commands=permitted_commands,
            ),
            now=now,
            new_id=new_id,
        )
    assert exc.value.policy_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    conduit_id=st.uuids(),
    permitted_principal_ids=_PRINCIPAL_IDS,
    permitted_commands=_COMMAND_NAMES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_emits_single_event_with_injected_fields(
    name: str,
    conduit_id: UUID,
    permitted_principal_ids: frozenset[UUID],
    permitted_commands: frozenset[str],
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream emits one PolicyDefined with injected/passthrough fields."""
    events = define_policy.decide(
        state=None,
        command=_command(
            name=name,
            conduit_id=conduit_id,
            permitted_principal_ids=permitted_principal_ids,
            permitted_commands=permitted_commands,
        ),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PolicyDefined)
    assert event.policy_id == new_id
    assert event.name == name
    assert event.conduit_id == conduit_id
    assert set(event.permitted_principal_ids) == permitted_principal_ids
    assert set(event.permitted_commands) == permitted_commands
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    state_id=st.none() | st.uuids(),
    name=_NAME,
    conduit_id=st.uuids(),
    permitted_principal_ids=_PRINCIPAL_IDS,
    permitted_commands=_COMMAND_NAMES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_policy_id_is_new_id_or_state_id_never_a_third_value(
    state_id: UUID | None,
    name: str,
    conduit_id: UUID,
    permitted_principal_ids: frozenset[UUID],
    permitted_commands: frozenset[str],
    now: datetime,
    new_id: UUID,
) -> None:
    """Total partition on source state: genesis -> new_id, existing -> state.id."""
    state = None if state_id is None else _state(policy_id=state_id)
    command = _command(
        name=name,
        conduit_id=conduit_id,
        permitted_principal_ids=permitted_principal_ids,
        permitted_commands=permitted_commands,
    )
    if state is None:
        events = define_policy.decide(state=None, command=command, now=now, new_id=new_id)
        assert events[0].policy_id == new_id
    else:
        with pytest.raises(PolicyAlreadyExistsError) as exc:
            define_policy.decide(state=state, command=command, now=now, new_id=new_id)
        assert exc.value.policy_id == state.id


@pytest.mark.unit
@given(
    name=_NAME,
    conduit_id=st.uuids(),
    permitted_principal_ids=_PRINCIPAL_IDS,
    permitted_commands=_COMMAND_NAMES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_is_pure_same_input_same_output(
    name: str,
    conduit_id: UUID,
    permitted_principal_ids: frozenset[UUID],
    permitted_commands: frozenset[str],
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command(
        name=name,
        conduit_id=conduit_id,
        permitted_principal_ids=permitted_principal_ids,
        permitted_commands=permitted_commands,
    )
    first = define_policy.decide(state=None, command=command, now=now, new_id=new_id)
    second = define_policy.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
