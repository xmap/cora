"""Property-based tests for `define_plan.decide` (Recipe BC).

Complements the example-based `test_define_plan_decider.py` (and its
affordance-cover gate siblings) with universal claims across generated
inputs. `define_plan` is a gated cross-aggregate genesis taking a loaded
`PlanBindingContext` and returning a list of `PlanDefined`. The full gate
matrix is pinned by the example tests; the PBT asserts the universal
claims that hold across the whole input space:

  - Any non-None state always raises `PlanAlreadyExistsError` carrying
    state.id (idempotency-as-error), regardless of context / command.
  - An empty `asset_ids` set always raises `PlanAssetsRequiredError`,
    regardless of name / clock / new_id.
  - A Deprecated bound Practice always raises
    `PlanBoundPracticeDeprecatedError`.
  - On the happy path (non-Deprecated upstream, one Active asset whose
    family_ids cover the Method's needed_family_ids, no Capability) the
    single `PlanDefined` carries the injected ids: plan_id=new_id, name
    (trimmed), practice_id=command.practice_id, method_id=method.id,
    occurred_at=now.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetName,
    AssetTier,
)
from cora.recipe.aggregates.method import Method, MethodName, MethodStatus
from cora.recipe.aggregates.plan import (
    Plan,
    PlanAlreadyExistsError,
    PlanAssetsRequiredError,
    PlanBoundPracticeDeprecatedError,
    PlanDefined,
    PlanName,
    PlanStatus,
)
from cora.recipe.aggregates.practice import Practice, PracticeName, PracticeStatus
from cora.recipe.features import define_plan
from cora.recipe.features.define_plan import DefinePlan, PlanBindingContext
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_NAME = printable_ascii_text(min_size=1, max_size=200)


def _practice(
    *,
    practice_id: UUID | None = None,
    method_id: UUID | None = None,
    site_id: UUID | None = None,
    status: PracticeStatus = PracticeStatus.DEFINED,
) -> Practice:
    return Practice(
        id=practice_id or uuid4(),
        name=PracticeName("APS XRF Fly Scan at 32-ID"),
        method_id=method_id or uuid4(),
        site_id=site_id or uuid4(),
        status=status,
    )


def _method(
    *,
    method_id: UUID | None = None,
    needed_family_ids: frozenset[UUID] | None = None,
    status: MethodStatus = MethodStatus.DEFINED,
) -> Method:
    return Method(
        id=method_id or uuid4(),
        name=MethodName("XRF Fly Scan Mapping"),
        needed_family_ids=needed_family_ids if needed_family_ids is not None else frozenset(),
        status=status,
    )


def _asset(
    *,
    asset_id: UUID | None = None,
    family_ids: frozenset[UUID] | None = None,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    return Asset(
        id=asset_id or uuid4(),
        name=AssetName("EigerDetector"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        family_ids=family_ids if family_ids is not None else frozenset(),
    )


def _context(
    *,
    practice: Practice | None = None,
    method: Method | None = None,
    assets: dict[UUID, Asset] | None = None,
) -> PlanBindingContext:
    """Build a default-valid binding context, overrideable per test."""
    p = practice or _practice()
    m = method or _method()
    if assets is None:
        default_id = uuid4()
        assets = {default_id: _asset(asset_id=default_id)}
    return PlanBindingContext(practice=p, method=m, assets=assets)


def _command(*, name: str, practice_id: UUID, asset_ids: frozenset[UUID]) -> DefinePlan:
    return DefinePlan(name=name, practice_id=practice_id, asset_ids=asset_ids)


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=st.sampled_from(list(PlanStatus)),
    name=_NAME,
    practice_id=st.uuids(),
    asset_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: PlanStatus,
    name: str,
    practice_id: UUID,
    asset_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises PlanAlreadyExistsError carrying state.id."""
    existing = Plan(
        id=existing_id,
        name=PlanName("prior"),
        practice_id=UUID(int=1),
        asset_ids=frozenset({UUID(int=2)}),
        status=existing_status,
    )
    with pytest.raises(PlanAlreadyExistsError) as exc:
        define_plan.decide(
            state=existing,
            command=_command(name=name, practice_id=practice_id, asset_ids=frozenset({asset_id})),
            context=_context(),
            now=now,
            new_id=new_id,
        )
    assert exc.value.plan_id == existing_id


@pytest.mark.unit
@given(name=_NAME, practice_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_define_with_empty_asset_ids_always_raises_assets_required(
    name: str,
    practice_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """An empty asset_ids set always raises PlanAssetsRequiredError."""
    with pytest.raises(PlanAssetsRequiredError):
        define_plan.decide(
            state=None,
            command=_command(name=name, practice_id=practice_id, asset_ids=frozenset()),
            context=_context(),
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(name=_NAME, now=aware_datetimes(), new_id=st.uuids())
def test_define_with_deprecated_practice_always_raises_practice_deprecated(
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """A Deprecated bound Practice always raises PlanBoundPracticeDeprecatedError."""
    practice = _practice(status=PracticeStatus.DEPRECATED)
    context = _context(practice=practice)
    with pytest.raises(PlanBoundPracticeDeprecatedError) as exc:
        define_plan.decide(
            state=None,
            command=_command(
                name=name,
                practice_id=practice.id,
                asset_ids=frozenset(context.assets.keys()),
            ),
            context=context,
            now=now,
            new_id=new_id,
        )
    assert exc.value.practice_id == practice.id


@pytest.mark.unit
@given(name=_NAME, now=aware_datetimes(), new_id=st.uuids())
def test_define_happy_path_emits_single_plan_defined_with_injected_ids(
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """The happy path emits one PlanDefined with new_id + injected fields."""
    family_id = uuid4()
    method = _method(needed_family_ids=frozenset({family_id}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id, family_ids=frozenset({family_id}))
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    events = define_plan.decide(
        state=None,
        command=_command(name=name, practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PlanDefined)
    assert event.plan_id == new_id
    assert event.name == name
    assert event.practice_id == practice.id
    assert event.method_id == method.id
    assert event.asset_ids == (asset_id,)
    assert event.occurred_at == now


@pytest.mark.unit
@given(now=aware_datetimes(), new_id=st.uuids())
def test_define_trims_surrounding_whitespace_from_name_in_event(
    now: datetime,
    new_id: UUID,
) -> None:
    """A name with surrounding whitespace is trimmed in the emitted event."""
    method = _method()
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id)
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    events = define_plan.decide(
        state=None,
        command=_command(name="  X  ", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=now,
        new_id=new_id,
    )
    assert events[0].name == "X"


@pytest.mark.unit
@given(name=_NAME, now=aware_datetimes(), new_id=st.uuids())
def test_define_is_pure_same_input_same_output(
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal results (no clock/id leakage)."""
    family_id = uuid4()
    method = _method(needed_family_ids=frozenset({family_id}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id, family_ids=frozenset({family_id}))
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    command = _command(name=name, practice_id=practice.id, asset_ids=frozenset({asset_id}))
    first = define_plan.decide(state=None, command=command, context=context, now=now, new_id=new_id)
    second = define_plan.decide(
        state=None, command=command, context=context, now=now, new_id=new_id
    )
    assert first == second
