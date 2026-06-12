"""Unit-tier tests for the `conduct_procedure` slice.

Covers:

  - handler dispatches to Conductor.conduct() with passed-through
    envelope (procedure_id + principal_id + correlation_id +
    causation_id + surface_id)
  - handler returns ConductProcedureResult mirroring ConductorResult
    (procedure_id + completed_count + succeeded + failure)
  - handler raises UnauthorizedError when the Authorize port denies
  - wire-type converters: SetpointStep / ActionStep / CheckStep
    round-trip through Pydantic + step_from_wire
  - criterion converters: EqualsCriterion / WithinToleranceCriterion round-trip
  - lists on the wire coerce to tuples in the in-process Step values
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import Allow, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_recipe_expander import (
    InMemoryRecipeExpander,
)
from cora.operation.aggregates.procedure import (
    ProcedureRegistered,
    event_type_name,
    to_payload,
)
from cora.operation.conductor import (
    ActionStep,
    CheckStep,
    ConductorFailure,
    ConductorResult,
    EqualsCriterion,
    SetpointStep,
    Step,
    WithinToleranceCriterion,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.conduct_procedure.command import (
    ConductProcedure,
    ConductProcedureResult,
)
from cora.operation.features.conduct_procedure.handler import bind
from cora.operation.features.conduct_procedure.route import (
    ConductProcedureRequest,
    criterion_from_wire,
    result_to_wire,
    step_from_wire,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


async def _seed_procedure(store: InMemoryEventStore, procedure_id: UUID) -> None:
    """Seed a legacy (no-recipe) Procedure so load_procedure_with_events
    returns non-None and the conduct_procedure handler takes the legacy
    (caller-supplied steps) branch per [[project-run-procedure-replay-design]]."""
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name="P",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        capability_id=None,
        recipe_id=None,
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
    """Stand-in for the Authorize port; configurable allow/deny."""

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
class _ConductCall:
    """One recorded invocation of the fake Conductor.conduct()."""

    procedure_id: UUID
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID
    steps: Sequence[Step]


@dataclass
class _FakeConductor:
    """Fake Conductor whose .conduct() captures the call + returns a canned result."""

    result: ConductorResult
    calls: list[_ConductCall] = field(default_factory=list[_ConductCall])

    async def conduct(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        self.calls.append(
            _ConductCall(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
                steps=steps,
            )
        )
        return self.result


def _deps(authz: _FakeAuthz, event_store: InMemoryEventStore | None = None) -> Kernel:
    """Minimal Kernel-shaped stub: authz + event_store (the conduct_procedure
    handler reads `deps.event_store` for `load_procedure_with_events`
    per [[project-run-procedure-replay-design]] Step 8)."""

    @dataclass
    class _MinimalKernel:
        authz: _FakeAuthz
        event_store: InMemoryEventStore

    return _MinimalKernel(  # type: ignore[return-value]
        authz=authz, event_store=event_store or InMemoryEventStore()
    )


# --- handler dispatch ---------------------------------------------------


@pytest.mark.unit
async def test_conduct_procedure_handler_dispatches_to_conductor_with_envelope() -> None:
    procedure_id = uuid4()
    principal_id = uuid4()
    correlation_id = uuid4()
    causation_id = uuid4()
    surface_id = uuid4()
    store = InMemoryEventStore()
    await _seed_procedure(store, procedure_id)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=2))
    handler = bind(
        _deps(_FakeAuthz(), store),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    steps: tuple[Step, ...] = (
        SetpointStep(address="2bma:rot:val", value=45.0),
        SetpointStep(address="2bma:cam:exposure", value=0.025),
    )
    result = await handler(
        ConductProcedure(procedure_id=procedure_id, steps=steps),
        principal_id=principal_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        surface_id=surface_id,
    )
    assert len(conductor.calls) == 1
    call = conductor.calls[0]
    assert call.procedure_id == procedure_id
    assert call.principal_id == principal_id
    assert call.correlation_id == correlation_id
    assert call.causation_id == causation_id
    assert call.surface_id == surface_id
    assert call.steps == steps
    assert isinstance(result, ConductProcedureResult)
    assert result.procedure_id == procedure_id
    assert result.completed_count == 2
    assert result.succeeded is True
    assert result.failure is None


@pytest.mark.unit
async def test_conduct_procedure_handler_propagates_failure_from_conductor() -> None:
    procedure_id = uuid4()
    failure = ConductorFailure(
        step_index=0,
        source_kind="setpoint",
        target="2bma:rot:val",
        error_class="ControlNotConnectedError",
        message="Control address '2bma:rot:val' not connected",
    )
    store = InMemoryEventStore()
    await _seed_procedure(store, procedure_id)
    conductor = _FakeConductor(
        result=ConductorResult(procedure_id=procedure_id, completed_count=0, failure=failure)
    )
    handler = bind(
        _deps(_FakeAuthz(), store),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    result = await handler(
        ConductProcedure(procedure_id=procedure_id, steps=()),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert result.succeeded is False
    assert result.failure == failure


@pytest.mark.unit
async def test_conduct_procedure_handler_raises_unauthorized_when_authz_denies() -> None:
    conductor = _FakeConductor(result=ConductorResult(procedure_id=uuid4(), completed_count=0))
    handler = bind(
        _deps(_FakeAuthz(deny_reason="no permission")),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    with pytest.raises(UnauthorizedError, match="no permission"):
        await handler(
            ConductProcedure(procedure_id=uuid4(), steps=()),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    # Conductor is not invoked when authz denies.
    assert conductor.calls == []


# --- wire-type converters ----------------------------------------------


@pytest.mark.unit
def test_setpoint_step_round_trips_through_wire() -> None:
    body = ConductProcedureRequest.model_validate(
        {
            "steps": [
                {"kind": "setpoint", "address": "2bma:rot:val", "value": 45.0},
                {
                    "kind": "setpoint",
                    "address": "2bma:cam:exposure",
                    "value": 0.025,
                    "verify": True,
                },
            ]
        }
    )
    steps = [step_from_wire(s) for s in body.steps]
    assert isinstance(steps[0], SetpointStep)
    assert steps[0].address == "2bma:rot:val"
    assert steps[0].value == 45.0
    assert steps[0].verify is False
    assert isinstance(steps[1], SetpointStep)
    assert steps[1].verify is True


@pytest.mark.unit
def test_action_step_round_trips_through_wire() -> None:
    body = ConductProcedureRequest.model_validate(
        {"steps": [{"kind": "action", "name": "home_motor", "params": {"axis": "rot"}}]}
    )
    step = step_from_wire(body.steps[0])
    assert isinstance(step, ActionStep)
    assert step.name == "home_motor"
    assert step.params == {"axis": "rot"}


@pytest.mark.unit
def test_check_step_with_equals_round_trips_through_wire() -> None:
    body = ConductProcedureRequest.model_validate(
        {
            "steps": [
                {
                    "kind": "check",
                    "address": "2bma:rot:rbv",
                    "criterion": {"kind": "equals", "expected": 45.0},
                }
            ]
        }
    )
    step = step_from_wire(body.steps[0])
    assert isinstance(step, CheckStep)
    assert step.address == "2bma:rot:rbv"
    assert isinstance(step.criterion, EqualsCriterion)
    assert step.criterion.expected == 45.0


@pytest.mark.unit
def test_check_step_with_within_tolerance_round_trips_through_wire() -> None:
    body = ConductProcedureRequest.model_validate(
        {
            "steps": [
                {
                    "kind": "check",
                    "address": "2bma:temp:rbv",
                    "criterion": {"kind": "within_tolerance", "expected": 295.0, "tolerance": 0.5},
                }
            ]
        }
    )
    step = step_from_wire(body.steps[0])
    assert isinstance(step, CheckStep)
    assert isinstance(step.criterion, WithinToleranceCriterion)
    assert step.criterion.expected == 295.0
    assert step.criterion.tolerance == 0.5


@pytest.mark.unit
def test_setpoint_value_list_on_wire_coerces_to_tuple_in_process() -> None:
    body = ConductProcedureRequest.model_validate(
        {"steps": [{"kind": "setpoint", "address": "2bma:waveform", "value": [1.0, 2.0, 3.0]}]}
    )
    step = step_from_wire(body.steps[0])
    assert isinstance(step, SetpointStep)
    assert step.value == (1.0, 2.0, 3.0)
    assert isinstance(step.value, tuple)


@pytest.mark.unit
def test_equals_expected_list_on_wire_coerces_to_tuple_in_process() -> None:
    wire = _criterion_wire_from_dict({"kind": "equals", "expected": [1, 2, 3]})
    criterion = criterion_from_wire(wire)
    assert isinstance(criterion, EqualsCriterion)
    assert criterion.expected == (1, 2, 3)
    assert isinstance(criterion.expected, tuple)


def _criterion_wire_from_dict(d: dict[str, Any]) -> Any:
    """Parse a single criterion dict through the wire model union."""
    body = ConductProcedureRequest.model_validate(
        {"steps": [{"kind": "check", "address": "x", "criterion": d}]}
    )
    return body.steps[0].criterion  # type: ignore[union-attr]


@pytest.mark.unit
def test_unknown_step_kind_is_rejected_by_pydantic_at_parse_time() -> None:
    """Discriminated union catches malformed step kinds before the handler runs."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ConductProcedureRequest.model_validate(
            {"steps": [{"kind": "lifecycle", "address": "x", "value": 1.0}]}
        )


@pytest.mark.unit
def test_result_to_wire_serializes_success() -> None:
    procedure_id = uuid4()
    result = ConductProcedureResult(
        procedure_id=procedure_id, completed_count=3, succeeded=True, failure=None
    )
    wire = result_to_wire(result)
    assert wire.procedure_id == procedure_id
    assert wire.completed_count == 3
    assert wire.succeeded is True
    assert wire.failure is None


@pytest.mark.unit
def test_result_to_wire_serializes_failure() -> None:
    procedure_id = uuid4()
    failure = ConductorFailure(
        step_index=1,
        source_kind="check",
        target="2bma:rot:rbv",
        error_class="CheckFailedError",
        message="value 12.5 did not equal expected 45.0",
    )
    result = ConductProcedureResult(
        procedure_id=procedure_id, completed_count=1, succeeded=False, failure=failure
    )
    wire = result_to_wire(result)
    assert wire.succeeded is False
    assert wire.failure is not None
    assert wire.failure.step_index == 1
    assert wire.failure.source_kind == "check"
    assert wire.failure.target == "2bma:rot:rbv"
    assert wire.failure.error_class == "CheckFailedError"
    assert "did not equal" in wire.failure.message


# --- lifecycle-failure step_index=None survives the wire round-trip ----


@pytest.mark.unit
def test_result_to_wire_serializes_lifecycle_failure_with_null_step_index() -> None:
    """Lifecycle failures carry step_index=None; the wire model must accept it."""
    procedure_id = uuid4()
    failure = ConductorFailure(
        step_index=None,
        source_kind="lifecycle",
        target="start",
        error_class="RuntimeError",
        message="Procedure not in Defined",
    )
    result = ConductProcedureResult(
        procedure_id=procedure_id, completed_count=0, succeeded=False, failure=failure
    )
    wire = result_to_wire(result)
    assert wire.failure is not None
    assert wire.failure.step_index is None
    assert wire.failure.source_kind == "lifecycle"
    assert wire.failure.target == "start"


@pytest.mark.unit
def test_conduct_procedure_request_with_empty_step_list_is_valid() -> None:
    body = ConductProcedureRequest.model_validate({"steps": []})
    assert body.steps == []


@pytest.mark.unit
def test_conduct_procedure_request_default_is_empty_step_list() -> None:
    body = ConductProcedureRequest.model_validate({})
    assert body.steps == []


# ---  recipe-replay branch --------------------------------------
#
# These tests pin the recipe-driven branch of `conduct_procedure` per
# [[project-run-procedure-replay-design]]. Each test seeds a Procedure
# stream carrying both `ProcedureRegistered(recipe_id=...)` and
# `RecipeExpansionRecorded(...)`; the test-only knob is whatever payload
# field needs to drift to trigger the rejection.

import hashlib  # noqa: E402

from cora.operation._recipe_expansion import steps_to_wire  # noqa: E402
from cora.operation.aggregates.procedure import (  # noqa: E402
    ProcedureBoundCapabilityDeprecatedError,
    ProcedureNotFoundError,
    ProcedureStepsForbiddenForRecipeDrivenError,
    RecipeExpanderVersionMismatchError,
    RecipeExpansionRecorded,
    RecipeExpansionRecordNotFoundError,
    RecipeExpansionReplayMismatchError,
)
from cora.recipe.aggregates.capability import (  # noqa: E402
    CapabilityDefined,
    CapabilityDeprecated,
    ExecutorShape,
)
from cora.recipe.aggregates.capability import (  # noqa: E402
    event_type_name as capability_event_type_name,
)
from cora.recipe.aggregates.capability import (  # noqa: E402
    to_payload as capability_to_payload,
)
from cora.recipe.aggregates.recipe import (  # noqa: E402
    RecipeDefined,
    RecipeSetpointStep,
)
from cora.recipe.aggregates.recipe import event_type_name as recipe_event_type_name  # noqa: E402
from cora.recipe.aggregates.recipe import to_payload as recipe_to_payload  # noqa: E402
from cora.shared.canonical_json import canonical_json_bytes  # noqa: E402


async def _seed_capability(
    store: InMemoryEventStore,
    capability_id: UUID,
    *,
    deprecated: bool = False,
) -> None:
    """Seed a Capability stream so the conduct_procedure gate's
    `load_capability` call returns a real aggregate. When `deprecated`
    is True, a second `CapabilityDeprecated` event follows so the gate
    can verify it rejects."""
    defined = CapabilityDefined(
        capability_id=capability_id,
        code="cora.capability.test",
        name="Test",
        description=None,
        required_affordances=frozenset(),
        executor_shapes=frozenset({ExecutorShape.PROCEDURE}),
        parameters_schema=None,
        occurred_at=_NOW,
    )
    events = [
        to_new_event(
            event_type=capability_event_type_name(defined),
            payload=capability_to_payload(defined),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="seed",
            correlation_id=uuid4(),
            causation_id=None,
            principal_id=uuid4(),
        )
    ]
    if deprecated:
        deprecated_event = CapabilityDeprecated(
            capability_id=capability_id,
            replaced_by_capability_id=None,
            occurred_at=_NOW,
        )
        events.append(
            to_new_event(
                event_type=capability_event_type_name(deprecated_event),
                payload=capability_to_payload(deprecated_event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            )
        )
    await store.append(
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        events=events,
    )


async def _seed_recipe_driven_procedure(
    store: InMemoryEventStore,
    procedure_id: UUID,
    recipe_id: UUID,
    *,
    bindings: dict[str, object] | None = None,
    recipe_steps: tuple[RecipeSetpointStep, ...] | None = None,
    expansion_port_version: str = "v2-pseudoaxis-aware",
    bindings_hash_override: str | None = None,
    steps_hash_override: str | None = None,
    omit_recipe_expansion_recorded: bool = False,
) -> UUID:
    """Seed both events of the 2-event genesis block emitted by
    register_procedure_from_recipe, optionally drifting one of the pins.

    Returns the `capability_id` so callers can additionally seed a
    Capability stream with `_seed_capability(store, capability_id, ...)`
    when the conduct-time Capability-deprecation gate must be exercised.
    """
    capability_id = uuid4()
    binds = bindings if bindings is not None else {"angle": 30.0}
    rsteps = (
        recipe_steps
        if recipe_steps is not None
        else (RecipeSetpointStep(address="dev:x", value=1.0),)
    )
    # Also seed the Recipe stream so load_recipe_at_version succeeds.
    recipe_event = RecipeDefined(
        recipe_id=recipe_id,
        name="R",
        capability_id=capability_id,
        steps=rsteps,
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
    # Compute the expected hashes via the SAME canonicalizer the at-write
    # decider uses; tests can override either to trigger drift assertions.
    expected_bindings_hash = hashlib.sha256(canonical_json_bytes(dict(binds))).hexdigest()
    # Tests in this file use only literal values (no BindingRef), so the
    # cast to Conductor's narrower Step.value union is safe; the recipe-
    # expansion bridge does the same translation at run time.
    expanded_for_hash: tuple[Step, ...] = tuple(
        SetpointStep(address=s.address, value=s.value)  # type: ignore[arg-type]
        for s in rsteps
    )
    expected_steps_hash = hashlib.sha256(
        canonical_json_bytes(steps_to_wire(expanded_for_hash))
    ).hexdigest()
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="P",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        capability_id=capability_id,
        recipe_id=recipe_id,
        occurred_at=_NOW,
    )
    procedure_events = [registered]
    if not omit_recipe_expansion_recorded:
        recorded = RecipeExpansionRecorded(
            procedure_id=procedure_id,
            recipe_id=recipe_id,
            recipe_version=None,
            capability_id=capability_id,
            capability_version=None,
            bindings=binds,
            expansion_port_version=expansion_port_version,
            steps_hash=steps_hash_override or expected_steps_hash,
            bindings_hash=bindings_hash_override or expected_bindings_hash,
            step_count=len(rsteps),
            occurred_at=_NOW,
        )
        procedure_events.append(recorded)  # type: ignore[arg-type]
    new_events = [
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
        for event in procedure_events
    ]
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=new_events,
    )
    return capability_id


def _bind_handler(
    store: InMemoryEventStore,
    conductor: "_FakeConductor",
    *,
    expansion_port: InMemoryRecipeExpander | None = None,
) -> Any:
    return bind(
        _deps(_FakeAuthz(), store),  # type: ignore[arg-type]
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=expansion_port or InMemoryRecipeExpander(),
    )


@pytest.mark.unit
async def test_conduct_procedure_legacy_procedure_uses_caller_supplied_steps_unchanged() -> None:
    procedure_id = uuid4()
    store = InMemoryEventStore()
    await _seed_procedure(store, procedure_id)  # recipe_id is None
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=1))
    handler = _bind_handler(store, conductor)
    steps = (SetpointStep(address="dev:caller", value=99.0),)
    await handler(
        ConductProcedure(procedure_id=procedure_id, steps=steps),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert conductor.calls[0].steps == steps


@pytest.mark.unit
async def test_conduct_procedure_recipe_driven_procedure_uses_re_expanded_steps() -> None:
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    await _seed_recipe_driven_procedure(store, procedure_id, recipe_id)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=1))
    handler = _bind_handler(store, conductor)
    await handler(
        ConductProcedure(procedure_id=procedure_id, steps=()),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert conductor.calls[0].steps == (SetpointStep(address="dev:x", value=1.0),)


@pytest.mark.unit
async def test_recipe_driven_handler_with_non_empty_caller_steps_raises_forbidden() -> None:
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    await _seed_recipe_driven_procedure(store, procedure_id, recipe_id)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = _bind_handler(store, conductor)
    with pytest.raises(ProcedureStepsForbiddenForRecipeDrivenError) as exc:
        await handler(
            ConductProcedure(
                procedure_id=procedure_id,
                steps=(SetpointStep(address="dev:caller", value=99.0),),
            ),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert exc.value.procedure_id == procedure_id
    assert conductor.calls == []


@pytest.mark.unit
async def test_recipe_driven_handler_with_missing_expansion_record_raises_not_found() -> None:
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    await _seed_recipe_driven_procedure(
        store, procedure_id, recipe_id, omit_recipe_expansion_recorded=True
    )
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = _bind_handler(store, conductor)
    with pytest.raises(RecipeExpansionRecordNotFoundError) as exc:
        await handler(
            ConductProcedure(procedure_id=procedure_id, steps=()),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert exc.value.procedure_id == procedure_id


@pytest.mark.unit
async def test_recipe_driven_handler_with_port_version_mismatch_raises_port_error() -> None:
    """Dataclass `version` field supports `InMemoryRecipeExpander(version='v3')`
    so we can stage a drifted port against a `v2-pseudoaxis-aware`-pinned event
    without inventing a second adapter."""
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    # Pinned at the current default version; the port below reports v3.
    await _seed_recipe_driven_procedure(store, procedure_id, recipe_id)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = _bind_handler(store, conductor, expansion_port=InMemoryRecipeExpander(version="v3"))
    with pytest.raises(RecipeExpanderVersionMismatchError) as exc:
        await handler(
            ConductProcedure(procedure_id=procedure_id, steps=()),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert exc.value.procedure_id == procedure_id
    assert exc.value.recorded_version == "v2-pseudoaxis-aware"
    assert exc.value.current_version == "v3"


@pytest.mark.unit
async def test_recipe_driven_handler_with_bindings_drift_raises_bindings_mismatch() -> None:
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    await _seed_recipe_driven_procedure(
        store, procedure_id, recipe_id, bindings_hash_override="0" * 64
    )
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = _bind_handler(store, conductor)
    with pytest.raises(RecipeExpansionReplayMismatchError) as exc:
        await handler(
            ConductProcedure(procedure_id=procedure_id, steps=()),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert exc.value.procedure_id == procedure_id
    assert exc.value.mismatch_field == "bindings"


@pytest.mark.unit
async def test_recipe_driven_handler_with_steps_drift_raises_steps_mismatch() -> None:
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    await _seed_recipe_driven_procedure(
        store, procedure_id, recipe_id, steps_hash_override="0" * 64
    )
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = _bind_handler(store, conductor)
    with pytest.raises(RecipeExpansionReplayMismatchError) as exc:
        await handler(
            ConductProcedure(procedure_id=procedure_id, steps=()),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert exc.value.procedure_id == procedure_id
    assert exc.value.mismatch_field == "steps"


@pytest.mark.unit
async def test_conduct_procedure_with_unregistered_procedure_raises_procedure_not_found_error() -> (
    None
):
    """Added `load_procedure_with_events` at handler entry; the
    handler raises ProcedureNotFoundError before hitting the Conductor.
    Aligns with the route-tier 404 mapping (was: 200 + lifecycle-failure)."""
    store = InMemoryEventStore()
    conductor = _FakeConductor(result=ConductorResult(procedure_id=uuid4(), completed_count=0))
    handler = _bind_handler(store, conductor)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            ConductProcedure(procedure_id=uuid4(), steps=()),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert conductor.calls == []


@pytest.mark.unit
async def test_recipe_driven_handler_with_active_capability_passes_replay_gate() -> None:
    """Sanity: the new conduct-time Capability-deprecation gate does
    NOT fire when the bound Capability is in `Defined` state. Procedure
    replay completes and the Conductor receives the re-expanded steps."""
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    capability_id = await _seed_recipe_driven_procedure(store, procedure_id, recipe_id)
    await _seed_capability(store, capability_id, deprecated=False)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=1))
    handler = _bind_handler(store, conductor)
    await handler(
        ConductProcedure(procedure_id=procedure_id, steps=()),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert len(conductor.calls) == 1


@pytest.mark.unit
async def test_recipe_driven_handler_with_deprecated_capability_raises_capability_deprecated() -> (
    None
):
    """Symmetric to start_run's RunBoundPlanDeprecatedError: when the
    Capability bound by the Recipe pinned on a recipe-driven Procedure
    is Deprecated at conduct time, raise rather than re-expand against
    a tombstoned contract. Mapped to HTTP 409. Closes the deprecation-
    at-execution-time gap surfaced by the 2026-06-04 domain harmony audit."""
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    capability_id = await _seed_recipe_driven_procedure(store, procedure_id, recipe_id)
    await _seed_capability(store, capability_id, deprecated=True)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=0))
    handler = _bind_handler(store, conductor)
    with pytest.raises(ProcedureBoundCapabilityDeprecatedError) as exc:
        await handler(
            ConductProcedure(procedure_id=procedure_id, steps=()),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    assert exc.value.procedure_id == procedure_id
    assert exc.value.capability_id == capability_id
    assert conductor.calls == []
