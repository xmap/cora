"""Unit tests for the Capability aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import (
    CapabilityCode,
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilityName,
    CapabilityStatus,
    CapabilityVersioned,
    ExecutorShape,
    evolve,
    fold,
)

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)


def _defined(**overrides: object) -> CapabilityDefined:
    base: dict[str, object] = dict(
        capability_id=uuid4(),
        code="cora.capability.x",
        name="X",
        description=None,
        required_affordances=frozenset[Affordance](),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        parameters_schema=None,
        occurred_at=_NOW,
    )
    base.update(overrides)
    return CapabilityDefined(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_capability_defined_folds_into_defined_status() -> None:
    state = evolve(None, _defined())
    assert state.status == CapabilityStatus.DEFINED
    assert state.version is None


@pytest.mark.unit
def test_capability_defined_folds_full_declarative_contract() -> None:
    cid = uuid4()
    event = _defined(
        capability_id=cid,
        code="cora.capability.flyscan",
        name="FlyScan",
        description="Continuous rotation",
        required_affordances=frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE}),
        executor_shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}),
        parameters_schema={"$schema": "https://json-schema.org/draft/2020-12/schema"},
    )
    state = evolve(None, event)
    assert state.id == cid
    assert state.code == CapabilityCode("cora.capability.flyscan")
    assert state.name == CapabilityName("FlyScan")
    assert state.description == "Continuous rotation"
    assert state.required_affordances == frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE})
    assert state.executor_shapes == frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE})
    assert state.parameters_schema == {"$schema": "https://json-schema.org/draft/2020-12/schema"}


@pytest.mark.unit
def test_capability_versioned_replaces_declarative_contract_wholesale() -> None:
    """A new version IS a new declaration: required_affordances,
    executor_shapes, description, parameters_schema all REPLACE prior."""
    cid = uuid4()
    initial = evolve(
        None,
        _defined(
            capability_id=cid,
            required_affordances=frozenset({Affordance.ROTATABLE}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
            description="original",
        ),
    )
    versioned = evolve(
        initial,
        CapabilityVersioned(
            capability_id=cid,
            version_tag="v2",
            description="replaced",
            required_affordances=frozenset({Affordance.IMAGEABLE}),
            executor_shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}),
            parameters_schema=None,
            occurred_at=_NOW,
        ),
    )
    assert versioned.status == CapabilityStatus.VERSIONED
    assert versioned.version == "v2"
    assert versioned.required_affordances == frozenset({Affordance.IMAGEABLE})
    assert versioned.executor_shapes == frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE})
    assert versioned.description == "replaced"
    # Identity preserved
    assert versioned.id == cid
    assert versioned.code == initial.code


@pytest.mark.unit
def test_capability_deprecated_preserves_declarative_contract() -> None:
    """Audit-critical: a Deprecated Capability still shows what it declared."""
    cid = uuid4()
    initial = evolve(
        None,
        _defined(
            capability_id=cid,
            required_affordances=frozenset({Affordance.ROTATABLE, Affordance.HOMEABLE}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
            description="audit me",
        ),
    )
    deprecated = evolve(
        initial,
        CapabilityDeprecated(
            reason="Superseded",
            capability_id=cid,
            replaced_by_capability_id=None,
            occurred_at=_NOW,
        ),
    )
    assert deprecated.status == CapabilityStatus.DEPRECATED
    assert deprecated.required_affordances == initial.required_affordances
    assert deprecated.executor_shapes == initial.executor_shapes
    assert deprecated.description == "audit me"
    assert deprecated.replaced_by_capability_id is None


@pytest.mark.unit
def test_capability_deprecated_with_replaced_by_pointer() -> None:
    cid = uuid4()
    successor = uuid4()
    initial = evolve(None, _defined(capability_id=cid))
    deprecated = evolve(
        initial,
        CapabilityDeprecated(
            reason="Superseded",
            capability_id=cid,
            replaced_by_capability_id=successor,
            occurred_at=_NOW,
        ),
    )
    assert deprecated.replaced_by_capability_id == successor


@pytest.mark.unit
def test_capability_versioned_preserves_replaced_by_field() -> None:
    """version_capability doesn't touch replaced_by; only deprecate sets it."""
    cid = uuid4()
    initial = evolve(None, _defined(capability_id=cid))
    versioned = evolve(
        initial,
        CapabilityVersioned(
            capability_id=cid,
            version_tag="v2",
            required_affordances=frozenset[Affordance](),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
            occurred_at=_NOW,
        ),
    )
    assert versioned.replaced_by_capability_id is None


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_full_lifecycle_chain() -> None:
    cid = uuid4()
    state = fold(
        [
            _defined(capability_id=cid),
            CapabilityVersioned(
                capability_id=cid,
                version_tag="v2",
                required_affordances=frozenset({Affordance.ROTATABLE}),
                executor_shapes=frozenset({ExecutorShape.METHOD}),
                occurred_at=_NOW,
            ),
            CapabilityDeprecated(
                reason="Superseded",
                capability_id=cid,
                replaced_by_capability_id=None,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == CapabilityStatus.DEPRECATED
    assert state.version == "v2"
    assert state.required_affordances == frozenset({Affordance.ROTATABLE})


@pytest.mark.unit
def test_versioned_event_on_empty_state_raises() -> None:
    """Transition events on empty state are stream contamination."""
    with pytest.raises(ValueError, match="CapabilityVersioned"):
        evolve(
            None,
            CapabilityVersioned(
                capability_id=uuid4(),
                version_tag="v2",
                required_affordances=frozenset[Affordance](),
                executor_shapes=frozenset({ExecutorShape.METHOD}),
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_deprecated_event_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="CapabilityDeprecated"):
        evolve(
            None,
            CapabilityDeprecated(reason="Superseded", capability_id=uuid4(), occurred_at=_NOW),
        )
