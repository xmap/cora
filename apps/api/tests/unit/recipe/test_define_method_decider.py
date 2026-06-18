"""Unit tests for the `define_method` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    ExecutorShape,
)
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    InvalidMethodMonotoneQualityError,
    InvalidMethodNameError,
    Method,
    MethodAlreadyExistsError,
    MethodName,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method.decider import (
    MethodCapabilityExecutorMismatchError,
)

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _capability(
    *,
    shapes: frozenset[ExecutorShape] = frozenset({ExecutorShape.METHOD}),
    capability_id: UUID | None = None,
) -> Capability:
    """Build a Capability fixture for the cross-BC tests."""
    return Capability(
        id=capability_id or uuid4(),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        executor_shapes=shapes,
    )


def _cmd(
    *,
    name: str = "XRF Mapping",
    capability_id: UUID,
    needed_family_ids: frozenset[UUID] = frozenset(),
    execution_pattern: ExecutionPattern = ExecutionPattern.BATCH,
    monotone_quality: bool = False,
    resumable_from_checkpoint: bool = False,
) -> DefineMethod:
    """DefineMethod factory defaulting execution_pattern to BATCH.

    execution_pattern became a required command field with the compute
    classification work. The decider tests that don't exercise the
    workload-classification axis default it to BATCH here; the
    dedicated monotone-quality invariant tests pass it explicitly.
    """
    return DefineMethod(
        name=name,
        capability_id=capability_id,
        execution_pattern=execution_pattern,
        needed_family_ids=needed_family_ids,
        monotone_quality=monotone_quality,
        resumable_from_checkpoint=resumable_from_checkpoint,
    )


@pytest.mark.unit
def test_decide_emits_method_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    cap1 = uuid4()
    cap = _capability()
    events = define_method.decide(
        state=None,
        command=_cmd(name="XRF Mapping", capability_id=cap.id, needed_family_ids=frozenset({cap1})),
        capability=cap,
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    assert events[0].method_id == new_id
    assert events[0].name == "XRF Mapping"
    assert set(events[0].needed_family_ids) == {cap1}
    assert events[0].capability_id == cap.id
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    cap = _capability()
    events = define_method.decide(
        state=None,
        command=_cmd(
            name="  Step Tomography  ", capability_id=cap.id, needed_family_ids=frozenset()
        ),
        capability=cap,
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Step Tomography"


@pytest.mark.unit
def test_decide_accepts_empty_needed_family_ids() -> None:
    """Procedural Methods (purely operational, no Family
    requirement) are valid. Pinned because pilot use cases like
    'Sample Cleaning' might land here."""
    cap = _capability()
    events = define_method.decide(
        state=None,
        command=_cmd(name="Sample Cleaning", capability_id=cap.id, needed_family_ids=frozenset()),
        capability=cap,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].needed_family_ids == ()


@pytest.mark.unit
def test_decide_does_not_validate_capability_existence() -> None:
    """Eventual-consistency stance: decider does NOT verify the
    referenced Family ids exist in the event store. Same precedent
    as Trust Conduit zone refs (3b) and Asset parent refs (5b).
    Mismatch surfaces at Plan binding (6e)."""
    bogus_cap = UUID("01900000-0000-7000-8000-deadbeefcafe")
    cap = _capability()
    events = define_method.decide(
        state=None,
        command=_cmd(name="X", capability_id=cap.id, needed_family_ids=frozenset({bogus_cap})),
        capability=cap,
        now=_NOW,
        new_id=uuid4(),
    )
    assert set(events[0].needed_family_ids) == {bogus_cap}


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    cap = _capability()
    with pytest.raises(InvalidMethodNameError):
        define_method.decide(
            state=None,
            command=_cmd(name="", capability_id=cap.id, needed_family_ids=frozenset()),
            capability=cap,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Method(
        id=uuid4(),
        name=MethodName("XRF Mapping"),
        needed_family_ids=frozenset(),
    )
    cap = _capability()
    with pytest.raises(MethodAlreadyExistsError) as exc_info:
        define_method.decide(
            state=existing,
            command=_cmd(name="Other", capability_id=cap.id, needed_family_ids=frozenset()),
            capability=cap,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.method_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cap1 = uuid4()
    cap = _capability()
    command = _cmd(name="XRF Mapping", capability_id=cap.id, needed_family_ids=frozenset({cap1}))
    first = define_method.decide(
        state=None, command=command, capability=cap, now=_NOW, new_id=new_id
    )
    second = define_method.decide(
        state=None, command=command, capability=cap, now=_NOW, new_id=new_id
    )
    # Compare the relevant fields (lists may be in different orders
    # since command.needed_family_ids is a frozenset; the event's
    # list-of-UUIDs comparison via set equality below is the safe pin).
    assert len(first) == len(second) == 1
    assert first[0].method_id == second[0].method_id
    assert first[0].name == second[0].name
    assert set(first[0].needed_family_ids) == set(second[0].needed_family_ids)
    assert first[0].capability_id == second[0].capability_id == cap.id
    assert first[0].occurred_at == second[0].occurred_at


@pytest.mark.unit
def test_decide_raises_capability_not_found_when_stream_missing() -> None:
    """Command supplied capability_id but the handler couldn't load a
    Capability stream for it (capability=None). Maps to 404 via routes.py
    registration. Mirrors the precedent on AssetParentNotFoundError."""
    bogus = UUID("01900000-0000-7000-8000-deadbeefcafe")
    with pytest.raises(CapabilityNotFoundError) as exc_info:
        define_method.decide(
            state=None,
            command=_cmd(name="X", capability_id=bogus),
            capability=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.capability_id == bogus


@pytest.mark.unit
def test_decide_raises_executor_mismatch_when_capability_excludes_method() -> None:
    """Bound Capability exists but its `executor_shapes` set does NOT contain
    ExecutorShape.METHOD (for example, a procedure-only Capability). Maps to
    409 via routes.py registration. Pinned because the asymmetry is the whole
    point of the Method-vs-Procedure split."""
    cap = _capability(shapes=frozenset({ExecutorShape.PROCEDURE}))
    new_id = uuid4()
    with pytest.raises(MethodCapabilityExecutorMismatchError) as exc_info:
        define_method.decide(
            state=None,
            command=_cmd(name="X", capability_id=cap.id),
            capability=cap,
            now=_NOW,
            new_id=new_id,
        )
    assert exc_info.value.method_id == new_id
    assert exc_info.value.capability_id == cap.id


@pytest.mark.unit
def test_decide_accepts_method_shaped_capability_and_propagates_id() -> None:
    """Happy path: capability_id is set, the bound Capability declares METHOD
    in its executor_shapes, and the decided event carries the bound
    capability_id (so projections / Plan binding can read it back)."""
    cap = _capability(shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}))
    events = define_method.decide(
        state=None,
        command=_cmd(name="X", capability_id=cap.id),
        capability=cap,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1
    assert events[0].capability_id == cap.id


@pytest.mark.unit
def test_decide_returns_event_when_command_has_only_required_fields() -> None:
    """Frozenset() default factory works (calling DefineMethod with
    name + capability_id only produces empty needed_family_ids). Pinned
    because the `field(default_factory=frozenset)` shape is unusual
    and worth locking."""
    cap = _capability()
    events = define_method.decide(
        state=None,
        command=_cmd(name="X", capability_id=cap.id),
        capability=cap,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].needed_family_ids == ()
    assert events[0].capability_id == cap.id


# ---------- compute classification (L3 / L4(b)) ----------


@pytest.mark.unit
def test_decide_event_carries_compute_classification_fields() -> None:
    """The decided MethodDefined threads execution_pattern + the two
    claims through from the command so the fold sees them."""
    cap = _capability()
    events = define_method.decide(
        state=None,
        command=_cmd(
            name="Live Reco",
            capability_id=cap.id,
            execution_pattern=ExecutionPattern.STREAMING,
            resumable_from_checkpoint=True,
        ),
        capability=cap,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].execution_pattern is ExecutionPattern.STREAMING
    assert events[0].monotone_quality is False
    assert events[0].resumable_from_checkpoint is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "pattern",
    [ExecutionPattern.BATCH, ExecutionPattern.STREAMING],
)
def test_decide_rejects_monotone_quality_on_non_iterative(
    pattern: ExecutionPattern,
) -> None:
    """L4(b): the anytime-algorithm claim is only meaningful for
    ITERATIVE workloads; monotone_quality=True on BATCH or STREAMING
    is rejected (Invalid<X> family -> HTTP 400)."""
    cap = _capability()
    with pytest.raises(InvalidMethodMonotoneQualityError) as exc_info:
        define_method.decide(
            state=None,
            command=_cmd(
                name="X",
                capability_id=cap.id,
                execution_pattern=pattern,
                monotone_quality=True,
            ),
            capability=cap,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.execution_pattern is pattern


@pytest.mark.unit
def test_decide_accepts_monotone_quality_on_iterative() -> None:
    """An ITERATIVE Method may claim monotone_quality; the event carries it."""
    cap = _capability()
    events = define_method.decide(
        state=None,
        command=_cmd(
            name="SIRT",
            capability_id=cap.id,
            execution_pattern=ExecutionPattern.ITERATIVE,
            monotone_quality=True,
        ),
        capability=cap,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1
    assert events[0].execution_pattern is ExecutionPattern.ITERATIVE
    assert events[0].monotone_quality is True
