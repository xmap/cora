"""Pure-decider tests for `register_procedure` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    InvalidProcedureIterationCapError,
    InvalidProcedureKindError,
    InvalidProcedureNameError,
    Procedure,
    ProcedureAlreadyExistsError,
    ProcedureCapabilityExecutorMismatchError,
    ProcedureName,
    ProcedureStatus,
)
from cora.operation.features import register_procedure
from cora.operation.features.register_procedure import RegisterProcedure
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    ExecutorShape,
)

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _capability(
    *, shapes: frozenset[ExecutorShape] = frozenset({ExecutorShape.PROCEDURE})
) -> Capability:
    """Build a Capability fixture for cross-BC tests."""
    return Capability(
        id=uuid4(),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        executor_shapes=shapes,
    )


@pytest.mark.unit
def test_decide_emits_procedure_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    asset = uuid4()
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(
            name="2-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=frozenset({asset}),
            parent_run_id=None,
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    assert events[0].procedure_id == new_id
    assert events[0].name == "2-BM rotation-axis alignment"
    assert events[0].kind == "alignment"
    assert set(events[0].target_asset_ids) == {asset}
    assert events[0].parent_run_id is None
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_kind_and_name() -> None:
    new_id = uuid4()
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(
            name="  Vessel-A bakeout  ",
            kind="  bakeout  ",
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Vessel-A bakeout"
    assert events[0].kind == "bakeout"


@pytest.mark.unit
def test_decide_accepts_empty_target_asset_ids() -> None:
    """Facility-envelope procedures (beam-mode change) don't act on a
    specific Asset and are valid with empty target_asset_ids."""
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(
            name="Beam-mode change to white",
            kind="beam_mode_change",
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].target_asset_ids == ()


@pytest.mark.unit
def test_decide_accepts_phase_of_run_with_parent_run_id() -> None:
    parent_run = uuid4()
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(
            name="Mid-run calibration",
            kind="calibration",
            parent_run_id=parent_run,
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].parent_run_id == parent_run


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Procedure(
        id=uuid4(),
        name=ProcedureName("Existing"),
        kind="bakeout",
        target_asset_ids=frozenset(),
        status=ProcedureStatus.DEFINED,
    )
    with pytest.raises(ProcedureAlreadyExistsError) as exc_info:
        register_procedure.decide(
            state=existing,
            command=RegisterProcedure(name="Other", kind="alignment"),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.procedure_id == existing.id


@pytest.mark.unit
def test_decide_records_patience_cap_on_event() -> None:
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(
            name="X", kind="center_alignment", max_consecutive_unconverged_iterations=5
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].max_consecutive_unconverged_iterations == 5


@pytest.mark.unit
def test_decide_defaults_patience_cap_to_none() -> None:
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(name="X", kind="bakeout"),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].max_consecutive_unconverged_iterations is None


@pytest.mark.unit
@pytest.mark.parametrize("bad_cap", [0, -1, -5])
def test_decide_rejects_patience_cap_below_one(bad_cap: int) -> None:
    with pytest.raises(InvalidProcedureIterationCapError):
        register_procedure.decide(
            state=None,
            command=RegisterProcedure(
                name="X", kind="bakeout", max_consecutive_unconverged_iterations=bad_cap
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_empty_kind() -> None:
    with pytest.raises(InvalidProcedureKindError):
        register_procedure.decide(
            state=None,
            command=RegisterProcedure(name="X", kind="   "),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_too_long_kind() -> None:
    with pytest.raises(InvalidProcedureKindError):
        register_procedure.decide(
            state=None,
            command=RegisterProcedure(name="X", kind="a" * 51),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_empty_name() -> None:
    with pytest.raises(InvalidProcedureNameError):
        register_procedure.decide(
            state=None,
            command=RegisterProcedure(name="   ", kind="bakeout"),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_does_not_validate_target_asset_existence() -> None:
    """Eventual-consistency stance per Trust Conduit zone refs (3b),
    Asset parent refs (5b), and Method's needed_family_ids (6a)."""
    fake_asset = uuid4()
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(
            name="X",
            kind="bakeout",
            target_asset_ids=frozenset({fake_asset}),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert fake_asset in set(events[0].target_asset_ids)


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = RegisterProcedure(name="Vessel-A bakeout", kind="bakeout")
    first = register_procedure.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = register_procedure.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second


@pytest.mark.unit
def test_decide_returns_emitted_id_in_event() -> None:
    """Decider trusts the injected new_id (handler's IdGenerator)."""
    deterministic_id = uuid4()
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(name="X", kind="bakeout"),
        now=_NOW,
        new_id=deterministic_id,
    )
    assert events[0].procedure_id == deterministic_id


@pytest.mark.unit
def test_decide_does_not_mutate_input_state() -> None:
    """Pure decider invariant: same input state object is returned untouched."""
    existing = Procedure(
        id=uuid4(),
        name=ProcedureName("Existing"),
        kind="bakeout",
        target_asset_ids=frozenset(),
        status=ProcedureStatus.DEFINED,
    )
    snapshot = (
        existing.id,
        existing.name,
        existing.kind,
        existing.target_asset_ids,
        existing.status,
    )
    with pytest.raises(ProcedureAlreadyExistsError):
        register_procedure.decide(
            state=existing,
            command=RegisterProcedure(name="Other", kind="alignment"),
            now=_NOW,
            new_id=uuid4(),
        )
    assert (
        existing.id,
        existing.name,
        existing.kind,
        existing.target_asset_ids,
        existing.status,
    ) == snapshot


# ---------- cross-BC capability guard ----------


@pytest.mark.unit
def test_decide_skips_capability_validation_when_command_omits_capability_id() -> None:
    """When capability_id is None on the command, the decider skips the
    Capability + executor-shape check entirely. Procedures with no template
    binding (including ceremony Procedures) keep working with no extra context
    required."""
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(name="Bakeout", kind="bakeout"),
        capability=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].capability_id is None


@pytest.mark.unit
def test_decide_raises_capability_not_found_when_stream_missing() -> None:
    """Command supplied capability_id but the handler couldn't load a
    Capability stream for it (capability=None). Maps to 404 via routes.py
    registration. Mirrors define_method's capability-binding guard."""
    bogus = UUID("01900000-0000-7000-8000-deadbeefcafe")
    with pytest.raises(CapabilityNotFoundError) as exc_info:
        register_procedure.decide(
            state=None,
            command=RegisterProcedure(name="X", kind="alignment", capability_id=bogus),
            capability=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.capability_id == bogus


@pytest.mark.unit
def test_decide_raises_executor_mismatch_when_capability_excludes_procedure() -> None:
    """Bound Capability exists but its `executor_shapes` does NOT contain
    ExecutorShape.PROCEDURE (for example, a Method-only Capability template).
    Maps to 409 via routes.py registration. Mirror of the sibling guard that
    gates Method bindings on ExecutorShape.METHOD."""
    cap = _capability(shapes=frozenset({ExecutorShape.METHOD}))
    new_id = uuid4()
    with pytest.raises(ProcedureCapabilityExecutorMismatchError) as exc_info:
        register_procedure.decide(
            state=None,
            command=RegisterProcedure(name="X", kind="alignment", capability_id=cap.id),
            capability=cap,
            now=_NOW,
            new_id=new_id,
        )
    assert exc_info.value.procedure_id == new_id
    assert exc_info.value.capability_id == cap.id


@pytest.mark.unit
def test_decide_accepts_procedure_shaped_capability_and_propagates_id() -> None:
    """Happy path: capability_id is set, the bound Capability declares
    PROCEDURE in its executor_shapes, and the decided event carries the
    bound capability_id (so projections / Run binding can read it back)."""
    cap = _capability(shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}))
    events = register_procedure.decide(
        state=None,
        command=RegisterProcedure(name="X", kind="alignment", capability_id=cap.id),
        capability=cap,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1
    assert events[0].capability_id == cap.id
