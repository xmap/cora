"""Unit tests for the Plan aggregate's evolver."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanStatus,
    Wire,
    evolve,
    fold,
)
from cora.recipe.aggregates.plan.events import (
    PlanDefaultParametersUpdated,
    PlanDefined,
    PlanDeprecated,
    PlanVersioned,
    PlanWireAdded,
    PlanWireRemoved,
)

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _plan_defined(
    *,
    plan_id: UUID | None = None,
    practice_id: UUID | None = None,
    asset_ids: tuple[UUID, ...] | None = None,
) -> PlanDefined:
    """Test helper: PlanDefined with sensible defaults for non-relevant fields."""
    return PlanDefined(
        plan_id=plan_id or uuid4(),
        name="32-ID FlyScan",
        practice_id=practice_id or uuid4(),
        asset_ids=asset_ids if asset_ids is not None else (uuid4(),),
        method_id=uuid4(),
        method_needed_family_ids_snapshot=(uuid4(),),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_plan_defined_sets_status_to_defined() -> None:
    """PlanDefined is the genesis event; status defaults to Defined
    via the evolver. method_id is folded as of 6g-b (the
    update_plan_default_parameters decider needs it). Other audit
    snapshots in payload are NOT folded into state (slim aggregate).
    """
    plan_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    method_id = uuid4()
    state = evolve(
        None,
        PlanDefined(
            plan_id=plan_id,
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=(asset_id,),
            method_id=method_id,
            method_needed_family_ids_snapshot=(uuid4(),),
            asset_families_snapshot={asset_id: (uuid4(),)},
            occurred_at=_NOW,
        ),
    )
    assert state == Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=practice_id,
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
        method_id=method_id,
    )


@pytest.mark.unit
def test_evolve_plan_defined_converts_asset_ids_list_to_frozenset() -> None:
    """Event payload carries `list[UUID]` (JSON-friendly); state
    holds `frozenset[UUID]` (set semantics for membership). Same
    precedent as Method's needed_family_ids."""
    a1 = uuid4()
    a2 = uuid4()
    state = evolve(None, _plan_defined(asset_ids=(a1, a2, a1)))  # duplicate
    assert state.asset_ids == frozenset({a1, a2})
    assert isinstance(state.asset_ids, frozenset)


@pytest.mark.unit
def test_evolve_plan_defined_does_not_fold_other_audit_snapshots() -> None:
    """Slim aggregate: snapshots in payload are NOT folded into state. Plan
    state holds method_id (promoted for the update_plan_default_parameters
    decider) but NOT method_needed_family_ids_snapshot or
    asset_families_snapshot. This test pins the contract so future additions
    are deliberate. default_parameters is also on state (defaults to {} via
    additive-state pattern). wires is also on state (defaults to frozenset()
    via additive-state pattern). content_hash is also on state (defaults to
    None pre-PlanVersioned; last-attested SHA-256 of the canonical Plan
    content subset per [[project_content_addressed_identity_design]]). Field
    set IS the contract."""
    state = evolve(None, _plan_defined())
    assert {f for f in state.__dataclass_fields__} == {
        "id",
        "name",
        "practice_id",
        "asset_ids",
        "status",
        "version",
        "method_id",
        "default_parameters",
        "wires",
        "content_hash",
        # role_bindings joined the slim aggregate when slice 2 of
        # positional role-tagging landed (Plan-side closure of the
        # IEC 81346 Function-aspect workstream).
        "role_bindings",
    }


@pytest.mark.unit
def test_evolve_plan_defined_starts_with_null_version() -> None:
    """Genesis-only stream folds with version=None (additive-state
    pattern; streams without the new field fold cleanly without an upcaster)."""
    state = evolve(None, _plan_defined())
    assert state.version is None


# ---------- PlanVersioned ----------


@pytest.mark.unit
def test_evolve_plan_versioned_flips_status_and_sets_version() -> None:
    plan_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    defined = Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=practice_id,
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.status is PlanStatus.VERSIONED
    assert versioned.version == "v2"
    # Other state preserved.
    assert versioned.id == plan_id
    assert versioned.practice_id == practice_id
    assert versioned.asset_ids == frozenset({asset_id})


@pytest.mark.unit
def test_evolve_plan_versioned_replaces_prior_version_tag() -> None:
    """Subsequent revisions overwrite version with the new label."""
    plan_id = uuid4()
    versioned_v1 = Plan(
        id=plan_id,
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.VERSIONED,
        version="v1",
    )
    versioned_v2 = evolve(
        versioned_v1,
        PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned_v2.version == "v2"


@pytest.mark.unit
def test_evolve_plan_versioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, PlanVersioned(plan_id=uuid4(), version_tag="v1", occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_plan_versioned_preserves_practice_id_and_asset_ids() -> None:
    """Critical invariant: cross-aggregate refs MUST carry through
    the version transition. Same safety-net pattern as Practice's
    evolver preserve tests."""
    practice_id = uuid4()
    a1 = uuid4()
    a2 = uuid4()
    defined = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=practice_id,
        asset_ids=frozenset({a1, a2}),
        status=PlanStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        PlanVersioned(plan_id=defined.id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.practice_id == practice_id
    assert versioned.asset_ids == frozenset({a1, a2})


# ---------- PlanDeprecated ----------


@pytest.mark.unit
def test_evolve_plan_deprecated_flips_status_and_preserves_version() -> None:
    """Version preserved across deprecation. Mirrors Practice/Method/
    Family shape — audit signal of the last revision before
    deprecation stays visible on the Deprecated state."""
    plan_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    versioned = Plan(
        id=plan_id,
        name=PlanName("X"),
        practice_id=practice_id,
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.VERSIONED,
        version="v3",
    )
    deprecated = evolve(
        versioned,
        PlanDeprecated(reason="Superseded", plan_id=plan_id, occurred_at=_NOW),
    )
    assert deprecated.status is PlanStatus.DEPRECATED
    assert deprecated.version == "v3"
    # Cross-aggregate refs preserved across deprecation too.
    assert deprecated.practice_id == practice_id
    assert deprecated.asset_ids == frozenset({asset_id})


@pytest.mark.unit
def test_evolve_plan_deprecated_from_defined_preserves_null_version() -> None:
    defined = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.DEFINED,
    )
    deprecated = evolve(
        defined, PlanDeprecated(reason="Superseded", plan_id=defined.id, occurred_at=_NOW)
    )
    assert deprecated.status is PlanStatus.DEPRECATED
    assert deprecated.version is None


@pytest.mark.unit
def test_evolve_plan_deprecated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, PlanDeprecated(reason="Superseded", plan_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_define_version_yields_versioned_plan() -> None:
    plan_id = uuid4()
    state = fold(
        [
            _plan_defined(plan_id=plan_id),
            PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is PlanStatus.VERSIONED
    assert state.version == "v2"


@pytest.mark.unit
def test_fold_define_version_version_yields_latest_version_tag() -> None:
    """Multi-revision fold: latest version_tag wins."""
    plan_id = uuid4()
    state = fold(
        [
            _plan_defined(plan_id=plan_id),
            PlanVersioned(plan_id=plan_id, version_tag="v1", occurred_at=_NOW),
            PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
            PlanVersioned(plan_id=plan_id, version_tag="v3", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.version == "v3"


@pytest.mark.unit
def test_fold_define_version_deprecate_preserves_version_through_deprecation() -> None:
    """Full lifecycle audit: define → version → deprecate keeps the
    last version_tag as a historical record on the deprecated state."""
    plan_id = uuid4()
    state = fold(
        [
            _plan_defined(plan_id=plan_id),
            PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
            PlanDeprecated(reason="Superseded", plan_id=plan_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is PlanStatus.DEPRECATED
    assert state.version == "v2"


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_plan_defined_returns_plan() -> None:
    plan_id = uuid4()
    state = fold([_plan_defined(plan_id=plan_id)])
    assert state is not None
    assert state.id == plan_id
    assert state.status is PlanStatus.DEFINED


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [_plan_defined()]
    assert fold(events) == fold(events)


# ---------- PlanDefaultParametersUpdated ----------


_DEFAULTS_A: dict[str, object] = {"energy": 12.0, "exposure": 100}


@pytest.mark.unit
def test_evolve_plan_defined_starts_with_empty_default_parameters() -> None:
    """Genesis-only stream folds with default_parameters={}
    (additive-state pattern; streams without the new field fold cleanly)."""
    state = evolve(None, _plan_defined())
    assert state.default_parameters == {}


@pytest.mark.unit
def test_evolve_plan_defined_folds_method_id_from_payload() -> None:
    """method_id was promoted from audit-only payload to state because the
    update_plan_default_parameters decider needs it."""
    method_id = uuid4()
    plan_id = uuid4()
    state = evolve(
        None,
        PlanDefined(
            plan_id=plan_id,
            name="X",
            practice_id=uuid4(),
            asset_ids=(uuid4(),),
            method_id=method_id,
            method_needed_family_ids_snapshot=(),
            asset_families_snapshot={},
            occurred_at=_NOW,
        ),
    )
    assert state.method_id == method_id


@pytest.mark.unit
def test_evolve_plan_default_parameters_updated_sets_defaults_and_preserves_status() -> None:
    """Defaults update is orthogonal to lifecycle: status preserved."""
    plan_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    method_id = uuid4()
    defined = Plan(
        id=plan_id,
        name=PlanName("X"),
        practice_id=practice_id,
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
        method_id=method_id,
    )
    updated = evolve(
        defined,
        PlanDefaultParametersUpdated(
            plan_id=plan_id, default_parameters=_DEFAULTS_A, occurred_at=_NOW
        ),
    )
    assert updated.default_parameters == _DEFAULTS_A
    assert updated.status is PlanStatus.DEFINED
    assert updated.method_id == method_id


@pytest.mark.unit
def test_evolve_plan_default_parameters_updated_with_empty_clears_defaults() -> None:
    state = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.DEFINED,
        default_parameters=_DEFAULTS_A,
    )
    cleared = evolve(
        state,
        PlanDefaultParametersUpdated(plan_id=state.id, default_parameters={}, occurred_at=_NOW),
    )
    assert cleared.default_parameters == {}


@pytest.mark.unit
def test_evolve_plan_default_parameters_updated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            PlanDefaultParametersUpdated(
                plan_id=uuid4(), default_parameters=_DEFAULTS_A, occurred_at=_NOW
            ),
        )


@pytest.mark.unit
def test_evolve_plan_versioned_preserves_method_id_and_default_parameters() -> None:
    """Critical pin: method_id AND default_parameters MUST carry
    through the version transition. Mirrors the
    test_evolve_plan_versioned_preserves_practice_id_and_asset_ids
    safety-net pattern."""
    method_id = uuid4()
    state = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.DEFINED,
        method_id=method_id,
        default_parameters=_DEFAULTS_A,
    )
    versioned = evolve(state, PlanVersioned(plan_id=state.id, version_tag="v2", occurred_at=_NOW))
    assert versioned.method_id == method_id
    assert versioned.default_parameters == _DEFAULTS_A


@pytest.mark.unit
def test_evolve_plan_deprecated_preserves_method_id_and_default_parameters() -> None:
    """Critical pin: same as above for the deprecate transition
    (audit-relevant historical artifact)."""
    method_id = uuid4()
    state = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.VERSIONED,
        version="v1",
        method_id=method_id,
        default_parameters=_DEFAULTS_A,
    )
    deprecated = evolve(
        state, PlanDeprecated(reason="Superseded", plan_id=state.id, occurred_at=_NOW)
    )
    assert deprecated.method_id == method_id
    assert deprecated.default_parameters == _DEFAULTS_A


# ---------- PlanWireAdded / PlanWireRemoved ----------


@pytest.mark.unit
def test_evolve_plan_wire_added_appends_to_wires_set() -> None:
    """Folding PlanWireAdded grows the wires frozenset by one."""
    src_id = uuid4()
    tgt_id = uuid4()
    state = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id, tgt_id}),
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
    )
    new_state = evolve(
        state,
        PlanWireAdded(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
            occurred_at=_NOW,
        ),
    )
    assert len(new_state.wires) == 1
    expected = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )
    assert expected in new_state.wires


@pytest.mark.unit
def test_evolve_plan_wire_removed_removes_from_wires_set() -> None:
    """Folding PlanWireRemoved shrinks the wires frozenset by one."""
    src_id = uuid4()
    tgt_id = uuid4()
    existing = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )
    state = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id, tgt_id}),
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=frozenset({existing}),
    )
    new_state = evolve(
        state,
        PlanWireRemoved(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
            occurred_at=_NOW,
        ),
    )
    assert new_state.wires == frozenset()


@pytest.mark.unit
def test_evolve_wire_events_preserve_other_state_fields() -> None:
    """Critical pin: wire mutations preserve method_id, default_parameters,
    status, version (orthogonal to lifecycle and parameters)."""
    method_id = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    state = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id, tgt_id}),
        status=PlanStatus.VERSIONED,
        version="v1",
        method_id=method_id,
        default_parameters=_DEFAULTS_A,
    )
    new_state = evolve(
        state,
        PlanWireAdded(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
            occurred_at=_NOW,
        ),
    )
    assert new_state.status == PlanStatus.VERSIONED
    assert new_state.version == "v1"
    assert new_state.method_id == method_id
    assert new_state.default_parameters == _DEFAULTS_A


@pytest.mark.unit
def test_fold_full_wire_lifecycle_yields_empty_wire_set() -> None:
    """Add + remove the same Wire = empty wire set."""
    plan_id = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    events: list[object] = [
        PlanDefined(
            plan_id=plan_id,
            name="X",
            practice_id=practice_id,
            asset_ids=(src_id, tgt_id),
            method_id=method_id,
            method_needed_family_ids_snapshot=(),
            asset_families_snapshot={},
            occurred_at=_NOW,
        ),
        PlanWireAdded(
            plan_id=plan_id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
            occurred_at=_NOW,
        ),
        PlanWireRemoved(
            plan_id=plan_id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
            occurred_at=_NOW,
        ),
    ]
    final = fold(events)  # type: ignore[arg-type]
    assert final is not None
    assert final.wires == frozenset()
