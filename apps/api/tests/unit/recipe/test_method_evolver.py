"""Unit tests for the Method aggregate's evolver.

Pinned: list[UUID] in event payload converts to frozenset[UUID] in
state (set semantics for Plan-binding superset checks).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.method import (
    ExecutionPattern,
    Method,
    MethodName,
    MethodStatus,
    RoleName,
    RoleRequirement,
    evolve,
    fold,
)
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodDeprecated,
    MethodParametersSchemaUpdated,
    MethodRequiredRoleAdded,
    MethodRequiredRoleRemoved,
    MethodVersioned,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_method_defined_sets_status_to_defined() -> None:
    """MethodDefined is the genesis event; status defaults to Defined
    via the evolver. Pin so a future change (for example adding
    `initial_status` to the event payload) is a deliberate
    additive-state evolution."""
    method_id = uuid4()
    cap1 = uuid4()
    state = evolve(
        None,
        MethodDefined(
            method_id=method_id,
            name="XRF Fly Mapping",
            needed_family_ids=(cap1,),
            occurred_at=_NOW,
        ),
    )
    assert state == Method(
        id=method_id,
        name=MethodName("XRF Fly Mapping"),
        needed_family_ids=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )


@pytest.mark.unit
def test_evolve_converts_list_to_frozenset() -> None:
    """Event payload carries `list[UUID]` (JSON-friendly); state
    holds `frozenset[UUID]` (set semantics for Plan-binding
    superset checks). Locked because a future refactor that
    drops the conversion would silently break Plan-time set
    operations."""
    cap1 = uuid4()
    cap2 = uuid4()
    cap3 = uuid4()
    state = evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="X",
            needed_family_ids=(cap1, cap2, cap3, cap1),  # duplicate
            occurred_at=_NOW,
        ),
    )
    assert state.needed_family_ids == frozenset({cap1, cap2, cap3})
    assert isinstance(state.needed_family_ids, frozenset)


@pytest.mark.unit
def test_evolve_handles_empty_needed_family_ids() -> None:
    """Procedural Methods (no equipment requirement) fold to empty
    frozenset; Plan-binding's superset check still works
    (frozenset() ⊆ anything)."""
    state = evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="Sample Cleaning",
            needed_family_ids=(),
            occurred_at=_NOW,
        ),
    )
    assert state.needed_family_ids == frozenset()


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_method_defined_returns_method() -> None:
    method_id = uuid4()
    cap1 = uuid4()
    state = fold(
        [
            MethodDefined(
                method_id=method_id,
                name="Step Tomography",
                needed_family_ids=(cap1,),
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Method(
        id=method_id,
        name=MethodName("Step Tomography"),
        needed_family_ids=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    cap1 = uuid4()
    events = [
        MethodDefined(
            method_id=uuid4(),
            name="X",
            needed_family_ids=(cap1,),
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """End-to-end: decider produces events that the evolver folds back
    to the expected state."""
    new_id = uuid4()
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    cap2 = UUID("01900000-0000-7000-8000-000000000222")

    # local Capability fixture (decider takes the loaded state as kwarg).
    from cora.recipe.aggregates.capability import (
        Capability,
        CapabilityCode,
        CapabilityName,
        ExecutorShape,
    )

    capability = Capability(
        id=UUID("01900000-0000-7000-8000-00000000c1da"),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )
    command = DefineMethod(
        name="  XRF Fly Mapping  ",
        capability_id=capability.id,
        execution_pattern=ExecutionPattern.BATCH,
        needed_family_ids=frozenset({cap1, cap2}),
    )
    events = define_method.decide(
        state=None, command=command, capability=capability, now=_NOW, new_id=new_id
    )
    rebuilt = fold(events)
    assert rebuilt == Method(
        id=new_id,
        name=MethodName("XRF Fly Mapping"),
        needed_family_ids=frozenset({cap1, cap2}),
        capability_id=capability.id,
        status=MethodStatus.DEFINED,
        execution_pattern=ExecutionPattern.BATCH,
    )


# ---------- MethodVersioned ----------


@pytest.mark.unit
def test_evolve_method_defined_starts_with_null_version() -> None:
    """Genesis-only stream folds with version=None
    (additive-state pattern; streams without the new field fold cleanly without
    an upcaster)."""
    state = evolve(
        None,
        MethodDefined(method_id=uuid4(), name="X", needed_family_ids=(), occurred_at=_NOW),
    )
    assert state.version is None


@pytest.mark.unit
def test_evolve_method_versioned_flips_status_and_sets_version() -> None:
    method_id = uuid4()
    cap1 = uuid4()
    defined = Method(
        id=method_id,
        name=MethodName("XRF Mapping"),
        needed_family_ids=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.status is MethodStatus.VERSIONED
    assert versioned.version == "v2"
    # needed_family_ids preserved.
    assert versioned.needed_family_ids == frozenset({cap1})
    assert versioned.id == method_id


@pytest.mark.unit
def test_evolve_method_versioned_replaces_prior_version_tag() -> None:
    """Subsequent revisions overwrite version with the new label."""
    method_id = uuid4()
    versioned_v1 = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.VERSIONED,
        version="v1",
    )
    versioned_v2 = evolve(
        versioned_v1,
        MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned_v2.version == "v2"


@pytest.mark.unit
def test_evolve_method_versioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            MethodVersioned(method_id=uuid4(), version_tag="v1", occurred_at=_NOW),
        )


# ---------- MethodDeprecated ----------


@pytest.mark.unit
def test_evolve_method_deprecated_flips_status_and_preserves_version() -> None:
    """Version is preserved across deprecation. Mirrors
    Family's preserve-on-deprecate semantics from Equipment 5f-2."""
    method_id = uuid4()
    cap1 = uuid4()
    versioned = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset({cap1}),
        status=MethodStatus.VERSIONED,
        version="v3",
    )
    deprecated = evolve(
        versioned,
        MethodDeprecated(method_id=method_id, occurred_at=_NOW),
    )
    assert deprecated.status is MethodStatus.DEPRECATED
    assert deprecated.version == "v3"
    # needed_family_ids preserved across deprecation too.
    assert deprecated.needed_family_ids == frozenset({cap1})


@pytest.mark.unit
def test_evolve_method_deprecated_from_defined_preserves_null_version() -> None:
    defined = Method(
        id=uuid4(),
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.DEFINED,
    )
    deprecated = evolve(
        defined,
        MethodDeprecated(method_id=defined.id, occurred_at=_NOW),
    )
    assert deprecated.status is MethodStatus.DEPRECATED
    assert deprecated.version is None


@pytest.mark.unit
def test_evolve_method_deprecated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, MethodDeprecated(method_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_define_version_yields_versioned_method() -> None:
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needed_family_ids=(), occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is MethodStatus.VERSIONED
    assert state.version == "v2"


@pytest.mark.unit
def test_fold_define_version_version_yields_latest_version_tag() -> None:
    """Multi-revision fold: latest version_tag wins."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needed_family_ids=(), occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v1", occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v3", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.version == "v3"


@pytest.mark.unit
def test_fold_define_deprecate_yields_deprecated_method() -> None:
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needed_family_ids=(), occurred_at=_NOW),
            MethodDeprecated(method_id=method_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is MethodStatus.DEPRECATED


@pytest.mark.unit
def test_fold_define_version_deprecate_preserves_version_through_deprecation() -> None:
    """Full lifecycle audit: define → version → deprecate keeps the
    last version_tag as a historical record on the deprecated state."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needed_family_ids=(), occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
            MethodDeprecated(method_id=method_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is MethodStatus.DEPRECATED
    assert state.version == "v2"


@pytest.mark.unit
def test_evolve_method_versioned_loads_content_hash_into_state() -> None:
    """Candidate A: the evolver MUST surface the captured content_hash
    on state so consumers reading `Method.content_hash` see the value
    that the decider pinned, not None."""
    method_id = uuid4()
    h = "d" * 64
    defined = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW, content_hash=h),
    )
    assert versioned.content_hash == h


@pytest.mark.unit
def test_evolve_method_versioned_with_none_content_hash_yields_none_on_state() -> None:
    """Pre-rollout fold path: a legacy MethodVersioned with no
    content_hash field rebuilds via from_stored as
    content_hash=None; the evolver must NOT invent a value."""
    method_id = uuid4()
    defined = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.content_hash is None


@pytest.mark.unit
def test_evolve_method_deprecated_preserves_content_hash() -> None:
    """Deprecation preserves the LAST ATTESTED revision's hash;
    deprecation is lifecycle, not content. The hash stays a valid
    equivalence anchor for the deprecated definition."""
    method_id = uuid4()
    h = "e" * 64
    versioned = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.VERSIONED,
        version="v2",
        content_hash=h,
    )
    deprecated = evolve(versioned, MethodDeprecated(method_id=method_id, occurred_at=_NOW))
    assert deprecated.content_hash == h


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_preserves_content_hash() -> None:
    """Schema updates between attestations leave the hash pointing at
    the prior version (Bazel input/output split semantics); the
    drift between current parameters_schema and the hashed snapshot
    is the intended signal that the Method has uncommitted changes."""
    method_id = uuid4()
    h = "f" * 64
    state = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.VERSIONED,
        version="v2",
        content_hash=h,
        parameters_schema=None,
    )
    updated = evolve(
        state,
        MethodParametersSchemaUpdated(
            method_id=method_id, parameters_schema=_SCHEMA_A, occurred_at=_NOW
        ),
    )
    assert updated.content_hash == h


@pytest.mark.unit
def test_evolve_method_versioned_overwrites_prior_content_hash() -> None:
    """A new MethodVersioned replaces the prior hash on state with the
    fresh one carried in the event payload (the latest attested
    revision wins, same as the version_tag overwrite)."""
    method_id = uuid4()
    old = "1" * 64
    new = "2" * 64
    state_v1 = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.VERSIONED,
        version="v1",
        content_hash=old,
    )
    state_v2 = evolve(
        state_v1,
        MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW, content_hash=new),
    )
    assert state_v2.content_hash == new


@pytest.mark.unit
def test_evolve_method_versioned_preserves_needed_family_ids() -> None:
    """Critical pin: needed_family_ids MUST carry through the
    version transition. Same safety-net pattern as
    test_evolve_<X>_preserves_capabilities for Asset."""
    cap1 = uuid4()
    cap2 = uuid4()
    defined = Method(
        id=uuid4(),
        name=MethodName("X"),
        needed_family_ids=frozenset({cap1, cap2}),
        status=MethodStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        MethodVersioned(method_id=defined.id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.needed_family_ids == frozenset({cap1, cap2})


# ---------- MethodParametersSchemaUpdated ----------


_SCHEMA_A = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
}


@pytest.mark.unit
def test_evolve_method_defined_starts_with_null_parameters_schema() -> None:
    """Genesis-only stream folds with parameters_schema=None
    (additive-state pattern; streams without the new field fold cleanly without
    an upcaster)."""
    state = evolve(
        None,
        MethodDefined(method_id=uuid4(), name="X", needed_family_ids=(), occurred_at=_NOW),
    )
    assert state.parameters_schema is None


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_sets_schema_and_preserves_status() -> None:
    """Schema update is orthogonal to lifecycle: status preserved on apply."""
    method_id = uuid4()
    cap1 = uuid4()
    defined = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )
    updated = evolve(
        defined,
        MethodParametersSchemaUpdated(
            method_id=method_id, parameters_schema=_SCHEMA_A, occurred_at=_NOW
        ),
    )
    assert updated.parameters_schema == _SCHEMA_A
    assert updated.status is MethodStatus.DEFINED
    assert updated.needed_family_ids == frozenset({cap1})


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_with_none_clears_schema() -> None:
    method_id = uuid4()
    state_with_schema = Method(
        id=method_id,
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.DEFINED,
        parameters_schema=_SCHEMA_A,
    )
    cleared = evolve(
        state_with_schema,
        MethodParametersSchemaUpdated(
            method_id=method_id, parameters_schema=None, occurred_at=_NOW
        ),
    )
    assert cleared.parameters_schema is None


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            MethodParametersSchemaUpdated(
                method_id=uuid4(), parameters_schema=_SCHEMA_A, occurred_at=_NOW
            ),
        )


@pytest.mark.unit
def test_evolve_method_versioned_preserves_parameters_schema() -> None:
    """Critical pin: parameters_schema MUST carry through the version
    transition. Mirrors `test_evolve_method_versioned_preserves_needed_family_ids`."""
    state = Method(
        id=uuid4(),
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.DEFINED,
        parameters_schema=_SCHEMA_A,
    )
    versioned = evolve(
        state, MethodVersioned(method_id=state.id, version_tag="v2", occurred_at=_NOW)
    )
    assert versioned.parameters_schema == _SCHEMA_A


@pytest.mark.unit
def test_evolve_method_deprecated_preserves_parameters_schema() -> None:
    """Critical pin: parameters_schema MUST carry through the deprecate
    transition (audit-relevant historical artifact)."""
    state = Method(
        id=uuid4(),
        name=MethodName("X"),
        needed_family_ids=frozenset(),
        status=MethodStatus.VERSIONED,
        version="v1",
        parameters_schema=_SCHEMA_A,
    )
    deprecated = evolve(state, MethodDeprecated(method_id=state.id, occurred_at=_NOW))
    assert deprecated.parameters_schema == _SCHEMA_A


@pytest.mark.unit
def test_fold_define_update_schema_yields_state_with_schema() -> None:
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needed_family_ids=(), occurred_at=_NOW),
            MethodParametersSchemaUpdated(
                method_id=method_id, parameters_schema=_SCHEMA_A, occurred_at=_NOW
            ),
        ]
    )
    assert state is not None
    assert state.parameters_schema == _SCHEMA_A
    assert state.status is MethodStatus.DEFINED


@pytest.mark.unit
def test_fold_define_update_schema_version_carries_schema_through_versioning() -> None:
    """Multi-event fold: schema set first, then versioning preserves it."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needed_family_ids=(), occurred_at=_NOW),
            MethodParametersSchemaUpdated(
                method_id=method_id, parameters_schema=_SCHEMA_A, occurred_at=_NOW
            ),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.parameters_schema == _SCHEMA_A
    assert state.version == "v2"
    assert state.status is MethodStatus.VERSIONED


# ---------- compute classification ----------


@pytest.mark.unit
def test_evolve_method_defined_carries_compute_classification() -> None:
    """Genesis folds the three compute fields onto state (None/False
    defaults for legacy streams; explicit values when set)."""
    method_id = uuid4()
    state = evolve(
        None,
        MethodDefined(
            method_id=method_id,
            name="Iterative Reconstruction",
            needed_family_ids=(),
            occurred_at=_NOW,
            execution_pattern=ExecutionPattern.ITERATIVE,
            monotone_quality=True,
            resumable_from_checkpoint=True,
        ),
    )
    assert state.execution_pattern is ExecutionPattern.ITERATIVE
    assert state.monotone_quality is True
    assert state.resumable_from_checkpoint is True


@pytest.mark.unit
def test_evolve_method_defined_defaults_compute_classification_for_legacy_stream() -> None:
    """Genesis without the fields folds to None/False (unclassified, not Batch)."""
    state = evolve(
        None,
        MethodDefined(method_id=uuid4(), name="X", needed_family_ids=(), occurred_at=_NOW),
    )
    assert state.execution_pattern is None
    assert state.monotone_quality is False
    assert state.resumable_from_checkpoint is False


def _defined_with_compute(method_id: UUID, *, status: MethodStatus, version: str | None) -> Method:
    return Method(
        id=method_id,
        name=MethodName("Iterative Reconstruction"),
        needed_family_ids=frozenset(),
        status=status,
        version=version,
        execution_pattern=ExecutionPattern.ITERATIVE,
        monotone_quality=True,
        resumable_from_checkpoint=True,
    )


@pytest.mark.unit
def test_evolve_method_versioned_preserves_compute_classification() -> None:
    """Critical pin: the three compute fields MUST carry through the
    version transition (part of content identity; omitting them in the
    evolver arm would silently wipe them to defaults)."""
    method_id = uuid4()
    prior = _defined_with_compute(method_id, status=MethodStatus.DEFINED, version=None)
    versioned = evolve(
        prior, MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW)
    )
    assert versioned.execution_pattern is ExecutionPattern.ITERATIVE
    assert versioned.monotone_quality is True
    assert versioned.resumable_from_checkpoint is True


@pytest.mark.unit
def test_evolve_method_deprecated_preserves_compute_classification() -> None:
    method_id = uuid4()
    prior = _defined_with_compute(method_id, status=MethodStatus.VERSIONED, version="v1")
    deprecated = evolve(prior, MethodDeprecated(method_id=method_id, occurred_at=_NOW))
    assert deprecated.execution_pattern is ExecutionPattern.ITERATIVE
    assert deprecated.monotone_quality is True
    assert deprecated.resumable_from_checkpoint is True


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_preserves_compute_classification() -> None:
    method_id = uuid4()
    prior = _defined_with_compute(method_id, status=MethodStatus.DEFINED, version=None)
    updated = evolve(
        prior,
        MethodParametersSchemaUpdated(
            method_id=method_id, parameters_schema=_SCHEMA_A, occurred_at=_NOW
        ),
    )
    assert updated.execution_pattern is ExecutionPattern.ITERATIVE
    assert updated.monotone_quality is True
    assert updated.resumable_from_checkpoint is True


@pytest.mark.unit
def test_evolve_method_required_role_added_preserves_compute_classification() -> None:
    """Role-add arm must carry the 3 compute fields through; omitting them
    in this evolver arm would silently wipe them to defaults."""
    method_id = uuid4()
    prior = _defined_with_compute(method_id, status=MethodStatus.DEFINED, version=None)
    with_role = evolve(
        prior,
        MethodRequiredRoleAdded(
            method_id=method_id,
            role_name="detector",
            family_id=uuid4(),
            required_ports=(),
            optional=False,
            occurred_at=_NOW,
        ),
    )
    assert with_role.execution_pattern is ExecutionPattern.ITERATIVE
    assert with_role.monotone_quality is True
    assert with_role.resumable_from_checkpoint is True


@pytest.mark.unit
def test_evolve_method_required_role_removed_preserves_compute_classification() -> None:
    """Role-remove arm must carry the 3 compute fields through."""
    method_id = uuid4()
    role = RoleRequirement(role_name=RoleName("detector"), family_id=uuid4())
    prior = Method(
        id=method_id,
        name=MethodName("Iterative Reconstruction"),
        needed_family_ids=frozenset(),
        status=MethodStatus.DEFINED,
        execution_pattern=ExecutionPattern.ITERATIVE,
        monotone_quality=True,
        resumable_from_checkpoint=True,
        required_roles=frozenset({role}),
    )
    without_role = evolve(
        prior,
        MethodRequiredRoleRemoved(method_id=method_id, role_name="detector", occurred_at=_NOW),
    )
    assert without_role.required_roles == frozenset()
    assert without_role.execution_pattern is ExecutionPattern.ITERATIVE
    assert without_role.monotone_quality is True
    assert without_role.resumable_from_checkpoint is True
