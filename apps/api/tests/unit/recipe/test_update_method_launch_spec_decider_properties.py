"""Property-based tests for `update_method_launch_spec.decide` (Recipe BC).

Complements the example-based `test_update_method_launch_spec_decider.py`
with universal claims across generated inputs. The decider is a pure
function

    (state, command, now) -> list[MethodLaunchSpecUpdated]

orthogonal to lifecycle (any non-None status accepts the update),
idempotent on an unchanged spec, and validating each LaunchArg against
the Method's parameters_schema.

Load-bearing properties:

  - state=None always raises `MethodNotFoundError` carrying
    command.method_id.
  - A valid spec whose args all name schema keys emits exactly one
    `MethodLaunchSpecUpdated` whose method_id is `state.id`, in any
    lifecycle status.
  - Setting the spec already on state is a no-op ([]).
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.recipe.aggregates.method import (
    ArgStyle,
    LaunchArg,
    LaunchSpec,
    Method,
    MethodLaunchSpecUpdated,
    MethodName,
    MethodNotFoundError,
    MethodStatus,
)
from cora.recipe.features.update_method_launch_spec import UpdateMethodLaunchSpec, decide
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"num_iter": {"type": "integer"}, "flag": {"type": "boolean"}},
}
_SPEC = LaunchSpec(
    base_command=("tomopy", "recon"),
    args=(
        LaunchArg(name="num_iter", flag="--num-iter", required=True),
        LaunchArg(name="flag", flag="--flag", style=ArgStyle.FLAG_ONLY),
    ),
)


def _method(*, method_id: UUID, status: MethodStatus, launch_spec: LaunchSpec | None) -> Method:
    return Method(
        id=method_id,
        name=MethodName("recon"),
        status=status,
        parameters_schema=_SCHEMA,
        launch_spec=launch_spec,
    )


@pytest.mark.unit
@given(method_id=st.uuids(), now=aware_datetimes())
def test_decide_with_none_state_always_raises_not_found(method_id: UUID, now: datetime) -> None:
    with pytest.raises(MethodNotFoundError) as exc:
        decide(None, UpdateMethodLaunchSpec(method_id=method_id, launch_spec=_SPEC), now=now)
    assert exc.value.method_id == method_id


@pytest.mark.unit
@given(method_id=st.uuids(), status=st.sampled_from(MethodStatus), now=aware_datetimes())
def test_decide_emits_single_event_with_state_id_for_valid_spec(
    method_id: UUID, status: MethodStatus, now: datetime
) -> None:
    state = _method(method_id=method_id, status=status, launch_spec=None)
    events = decide(state, UpdateMethodLaunchSpec(method_id=method_id, launch_spec=_SPEC), now=now)
    assert len(events) == 1
    assert isinstance(events[0], MethodLaunchSpecUpdated)
    assert events[0].method_id == state.id


@pytest.mark.unit
@given(method_id=st.uuids(), status=st.sampled_from(MethodStatus), now=aware_datetimes())
def test_decide_is_idempotent_when_spec_unchanged(
    method_id: UUID, status: MethodStatus, now: datetime
) -> None:
    state = _method(method_id=method_id, status=status, launch_spec=_SPEC)
    assert (
        decide(state, UpdateMethodLaunchSpec(method_id=method_id, launch_spec=_SPEC), now=now) == []
    )


@pytest.mark.unit
@given(method_id=st.uuids(), now=aware_datetimes())
def test_decide_is_pure(method_id: UUID, now: datetime) -> None:
    state = _method(method_id=method_id, status=MethodStatus.DEFINED, launch_spec=None)
    command = UpdateMethodLaunchSpec(method_id=method_id, launch_spec=_SPEC)
    assert decide(state, command, now=now) == decide(state, command, now=now)
