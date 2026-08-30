"""Unit-tier tests for the `conduct_until_converged` slice handler (slice 6c).

Covers:
  - handler dispatches to Conductor.conduct_until_converged with the passed-
    through envelope + convergence predicate (convergence_capture_name +
    criterion)
  - the patience cap falls back to the Procedure's registered
    max_consecutive_unconverged_iterations when the command omits it, and the
    command's explicit cap overrides it
  - handler returns ConductUntilConvergedResult mirroring ConductorResult
  - handler raises UnauthorizedError when the Authorize port denies (Conductor
    not invoked)
  - result_to_wire serializes success + failure
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import Allow, Deny
from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.ports.id_generator import UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._recipe_expansion import steps_to_wire_with_closing
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.aggregates.procedure import (
    ProcedureRegistered,
    RecipeExpansionRecorded,
    event_type_name,
    to_payload,
)
from cora.operation.conductor import (
    CheckCriterion,
    ConductorFailure,
    ConductorResult,
    SetpointStep,
    Step,
    WithinToleranceCriterion,
)
from cora.operation.errors import UnauthorizedError, UnsupportedClosingStepsError
from cora.operation.features.conduct_until_converged.command import (
    ConductUntilConverged,
    ConductUntilConvergedResult,
)
from cora.operation.features.conduct_until_converged.handler import bind
from cora.operation.features.conduct_until_converged.route import result_to_wire
from cora.recipe.aggregates.recipe import RecipeDefined, RecipeSetpointStep
from cora.recipe.aggregates.recipe import event_type_name as recipe_event_type_name
from cora.recipe.aggregates.recipe import to_payload as recipe_to_payload
from cora.shared.canonical_json import canonical_json_bytes

_NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)
_CRITERION = WithinToleranceCriterion(expected=0.0, tolerance=0.5)


async def _seed_recipe_driven_procedure_with_closing_steps(
    store: InMemoryEventStore, procedure_id: UUID
) -> None:
    """Seed a recipe-driven, Defined Procedure whose Recipe carries a
    non-empty closing_steps -- the shape conduct_until_converged must
    refuse (v1 scope). No Capability stream needed: `load_capability`
    returning None is treated as "not deprecated"."""
    recipe_id = uuid4()
    capability_id = uuid4()
    recipe_steps = (RecipeSetpointStep(address="dev:x", value=1.0),)
    recipe_closing_steps = (RecipeSetpointStep(address="dev:shutter", value=0.0),)
    recipe_event = RecipeDefined(
        recipe_id=recipe_id,
        name="R",
        capability_id=capability_id,
        steps=recipe_steps,
        closing_steps=recipe_closing_steps,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Recipe",
        stream_id=recipe_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=recipe_event_type_name(recipe_event),
                payload=recipe_to_payload(recipe_event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            ),
        ],
    )
    expanded: tuple[Step, ...] = tuple(
        SetpointStep(address=s.address, value=s.value)  # type: ignore[arg-type]
        for s in recipe_steps
    )
    expanded_closing: tuple[Step, ...] = tuple(
        SetpointStep(address=s.address, value=s.value)  # type: ignore[arg-type]
        for s in recipe_closing_steps
    )
    steps_hash = hashlib.sha256(
        canonical_json_bytes(steps_to_wire_with_closing(expanded, expanded_closing))
    ).hexdigest()
    bindings_hash = hashlib.sha256(canonical_json_bytes({})).hexdigest()
    events = [
        ProcedureRegistered(
            procedure_id=procedure_id,
            name="P",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            capability_id=capability_id,
            recipe_id=recipe_id,
            occurred_at=_NOW,
        ),
        RecipeExpansionRecorded(
            procedure_id=procedure_id,
            recipe_id=recipe_id,
            recipe_version=None,
            capability_id=capability_id,
            capability_version=None,
            bindings={},
            expansion_port_version="v2-pseudoaxis-aware",
            steps_hash=steps_hash,
            bindings_hash=bindings_hash,
            step_count=len(recipe_steps) + len(recipe_closing_steps),
            occurred_at=_NOW,
        ),
    ]
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),  # type: ignore[arg-type]
                payload=to_payload(event),  # type: ignore[arg-type]
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            )
            for event in events
        ],
    )


async def _seed_procedure(
    store: InMemoryEventStore,
    procedure_id: UUID,
    *,
    max_consecutive_unconverged_iterations: int | None = None,
) -> None:
    """Seed a legacy (no-recipe) Procedure carrying an optional patience cap."""
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name="auto align",
        kind="rotation_alignment",
        target_asset_ids=(),
        parent_run_id=None,
        capability_id=None,
        recipe_id=None,
        max_consecutive_unconverged_iterations=max_consecutive_unconverged_iterations,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            ),
        ],
    )


@dataclass
class _FakeAuthz:
    deny_reason: str | None = None

    async def authorize(
        self,
        *,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID,
    ) -> Allow | Deny:
        _ = (principal_id, command_name, conduit_id, surface_id)
        return Deny(reason=self.deny_reason) if self.deny_reason is not None else Allow()


@dataclass
class _ConvergeCall:
    procedure_id: UUID
    convergence_capture_name: str
    criterion: CheckCriterion
    steps: Sequence[Step]
    max_consecutive_unconverged_iterations: int | None


@dataclass
class _FakeConductor:
    result: ConductorResult
    calls: list[_ConvergeCall] = field(default_factory=list[_ConvergeCall])

    async def conduct_until_converged(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        convergence_capture_name: str,
        criterion: CheckCriterion,
        max_consecutive_unconverged_iterations: int | None = None,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        self.calls.append(
            _ConvergeCall(
                procedure_id=procedure_id,
                convergence_capture_name=convergence_capture_name,
                criterion=criterion,
                steps=steps,
                max_consecutive_unconverged_iterations=max_consecutive_unconverged_iterations,
            )
        )
        return self.result


def _deps(authz: _FakeAuthz, store: InMemoryEventStore):  # type: ignore[no-untyped-def]
    @dataclass
    class _MinimalKernel:
        authz: _FakeAuthz
        event_store: InMemoryEventStore
        clock: FakeClock
        id_generator: UUIDv7Generator

    return _MinimalKernel(
        authz=authz,
        event_store=store,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
    )


@pytest.mark.unit
async def test_handler_dispatches_with_predicate_and_envelope() -> None:
    procedure_id = uuid4()
    store = InMemoryEventStore()
    await _seed_procedure(store, procedure_id)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=3))
    handler = bind(
        _deps(_FakeAuthz(), store),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    steps: tuple[Step, ...] = (SetpointStep(address="dev:rot:center", value=1.0),)
    result = await handler(
        ConductUntilConverged(
            procedure_id=procedure_id,
            convergence_capture_name="offset",
            criterion=_CRITERION,
            steps=steps,
        ),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert len(conductor.calls) == 1
    call = conductor.calls[0]
    assert call.procedure_id == procedure_id
    assert call.convergence_capture_name == "offset"
    assert call.criterion == _CRITERION
    assert call.steps == steps
    assert isinstance(result, ConductUntilConvergedResult)
    assert result.succeeded is True


@pytest.mark.unit
async def test_handler_falls_back_to_registered_cap_when_command_omits_it() -> None:
    procedure_id = uuid4()
    store = InMemoryEventStore()
    await _seed_procedure(store, procedure_id, max_consecutive_unconverged_iterations=5)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = bind(
        _deps(_FakeAuthz(), store),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    await handler(
        ConductUntilConverged(
            procedure_id=procedure_id,
            convergence_capture_name="offset",
            criterion=_CRITERION,
        ),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert conductor.calls[0].max_consecutive_unconverged_iterations == 5


@pytest.mark.unit
async def test_handler_command_cap_overrides_registered_cap() -> None:
    procedure_id = uuid4()
    store = InMemoryEventStore()
    await _seed_procedure(store, procedure_id, max_consecutive_unconverged_iterations=5)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = bind(
        _deps(_FakeAuthz(), store),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    await handler(
        ConductUntilConverged(
            procedure_id=procedure_id,
            convergence_capture_name="offset",
            criterion=_CRITERION,
            max_consecutive_unconverged_iterations=2,
        ),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert conductor.calls[0].max_consecutive_unconverged_iterations == 2


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_authz_denies() -> None:
    conductor = _FakeConductor(result=ConductorResult(procedure_id=uuid4(), completed_count=0))
    handler = bind(
        _deps(_FakeAuthz(deny_reason="no permission"), InMemoryEventStore()),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    with pytest.raises(UnauthorizedError, match="no permission"):
        await handler(
            ConductUntilConverged(
                procedure_id=uuid4(),
                convergence_capture_name="offset",
                criterion=_CRITERION,
            ),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert conductor.calls == []


@pytest.mark.unit
def test_result_to_wire_serializes_cap_abort_failure() -> None:
    procedure_id = uuid4()
    failure = ConductorFailure(
        step_index=None,
        source_kind="lifecycle",
        target="abort",
        error_class="ConvergenceIterationCapReached",
        message="convergence loop gave up after 3 consecutive unconverged iterations (cap 3)",
    )
    result = ConductUntilConvergedResult(
        procedure_id=procedure_id,
        completed_count=1,
        succeeded=False,
        failure=failure,
    )
    wire = result_to_wire(result)
    assert wire.succeeded is False
    assert wire.failure is not None
    assert wire.failure.error_class == "ConvergenceIterationCapReached"
    assert wire.failure.step_index is None


@pytest.mark.unit
async def test_handler_refuses_a_closing_bearing_recipe() -> None:
    """v1 scope: a loop-driving slice has no defined place to run
    _run_closing, so it refuses rather than silently dropping the Recipe's
    closing steps. The Conductor is never invoked."""
    procedure_id = uuid4()
    store = InMemoryEventStore()
    await _seed_recipe_driven_procedure_with_closing_steps(store, procedure_id)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = bind(
        _deps(_FakeAuthz(), store),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    with pytest.raises(UnsupportedClosingStepsError) as exc:
        await handler(
            ConductUntilConverged(
                procedure_id=procedure_id,
                convergence_capture_name="offset",
                criterion=_CRITERION,
            ),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert exc.value.procedure_id == procedure_id
    assert conductor.calls == []
