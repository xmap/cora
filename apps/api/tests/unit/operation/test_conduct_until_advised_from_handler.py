"""Application-handler tests for `conduct_until_advised_from` (steered RESUME).

Orchestration handler composing the reconstruction (read the self-describing
outcome rows) + `Conductor.conduct_until_advised_from` (resume + close-dangling +
re-ask frontier + terminalize). Pins the read-path wiring, the crash scenarios,
and the guards:

  - a Held steered Procedure with recorded closed passes resumes: the brain is
    re-asked at the frontier over the recovered history, only new passes measure
  - re_establishment_boundary echoes the count of recovered observations
  - MID-PASS crash: an iteration left open is CLOSED before the loop, so the
    resume does not 409 (the headline bug this rewrite fixes)
  - crash-AFTER-measure: an outcome recorded for the crashed pass is recovered
    and re-fed (not dropped); its own start_iteration is not re-run
  - REPEATED crash: a second mid-pass crash after a resume still resumes
  - not Held -> ProcedureCannotResumeError (no resume)
  - unknown Procedure -> ProcedureNotFoundError
  - authz deny -> UnauthorizedError

The handler builds its own brain from `command.decide`. `in_memory` unseeded
advises Stop, so a resume whose frontier re-ask returns Stop COMPLETES with no
forced pass; `grid_walk` is a deterministic real brain used where the resume
must run a further pass.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.llm import FakeLLM, FakeLLMResponse, LLMUsage
from cora.operation.adapters.decide_port_config import DecidePortConfig, DecideSubstrate
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.adapters.postgres_procedure_outcome_lookup import (
    InMemoryProcedureOutcomeLookup,
)
from cora.operation.aggregates.procedure import (
    InMemoryActivityStore,
    InMemoryOutcomeStore,
    Outcome,
    ProcedureCannotResumeError,
    ProcedureEvent,
    ProcedureHeld,
    ProcedureIterationEnded,
    ProcedureIterationStarted,
    ProcedureNotFoundError,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStatus,
    ResolvedStepsRecorded,
    SteeringDesignRecorded,
    event_type_name,
    from_stored,
    load_procedure,
    to_payload,
)
from cora.operation.conductor import (
    ComputeStep,
    Conductor,
    SetpointStep,
    Step,
    step_to_payload,
)
from cora.operation.errors import (
    SteeringDesignMismatchError,
    SteeringWireMismatchError,
    UnauthorizedError,
    UnsupportedClosingStepsError,
)
from cora.operation.features import (
    abort_procedure,
    append_activities,
    complete_procedure,
    conduct_until_advised_from,
    end_iteration,
    resume_procedure,
    start_iteration,
)
from cora.operation.features.conduct_until_advised_from import (
    ConductUntilAdvisedFrom,
)
from cora.operation.features.conduct_until_advised_from import (
    Handler as ReconductHandler,
)
from cora.operation.ports.control_port import ControlPort
from cora.operation.ports.decide_port import (
    SteeringAxis,
    SteeringBudget,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe.body import CaptureRef
from cora.shared.steering import SteeringDesignSource, SteeringSubstrate
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 7, 2, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000e0a01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_MOTOR_ADDR = "motor"
_OBJECTIVE_NAME = "offset"


@dataclass
class _LenientIds:
    """Conductor id_generator that never exhausts (markers double appends)."""

    def new_id(self) -> UUID:
        return uuid4()


def _deps(store: InMemoryEventStore, *, deny: bool = False, llm: FakeLLM | None = None) -> Kernel:
    return _build_deps_shared(
        ids=[uuid4() for _ in range(40)], now=_NOW, event_store=store, deny=deny, llm=llm
    )


def _steered_block() -> tuple[Step, ...]:
    """One steered pass: deposit the objective, then move the seeded axis."""
    return (
        ComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
        SetpointStep(address=_MOTOR_ADDR, value=CaptureRef(capture_name=_MOTOR_ADDR)),
    )


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name=_MOTOR_ADDR, lower=0.0, upper=10.0),))


def _objective() -> SteeringObjective:
    return SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name=_OBJECTIVE_NAME,
        target_value=0.0,
    )


def _measurement(value: float) -> Measurement:
    return Measurement(
        value=value,
        kind="Scalar",
        quality="Good",
        produced_at=_PRIOR,
        name=_OBJECTIVE_NAME,
        units="pixel",
    )


def _make_conduct_from(
    deps: Kernel,
    port: ControlPort,
    compute: InMemoryComputePort,
    outcome_store: InMemoryOutcomeStore,
) -> ReconductHandler:
    conductor = Conductor(
        control_port=port,
        append_step=append_activities.bind(deps, step_store=InMemoryActivityStore()),
        clock=deps.clock,
        id_generator=_LenientIds(),
        compute_port=compute,
        resume_procedure=resume_procedure.bind(deps),
        complete_procedure=complete_procedure.bind(deps),
        abort_procedure=abort_procedure.bind(deps),
        start_iteration=start_iteration.bind(deps),
        end_iteration=end_iteration.bind(deps),
    )
    return conduct_until_advised_from.bind(
        deps,
        conductor=conductor,
        expansion_port=InMemoryRecipeExpander(),
        outcome_lookup=InMemoryProcedureOutcomeLookup(outcome_store),
    )


def _outcome_row(
    procedure_id: UUID, *, iteration_index: int, coordinate: float, value: float
) -> Outcome:
    """A self-describing recorded outcome (point x + measured y) for one pass."""
    return Outcome(
        event_id=uuid4(),
        procedure_id=procedure_id,
        logbook_id=uuid4(),
        iteration_index=iteration_index,
        point={_MOTOR_ADDR: coordinate},
        measurements=[
            {
                "name": _OBJECTIVE_NAME,
                "value": value,
                "kind": "Scalar",
                "quality": "Good",
                "produced_at": _PRIOR.isoformat(),
                "units": "pixel",
            }
        ],
        succeeded=True,
        actuation_kind="Physical",
        sampled_at=_PRIOR,
        occurred_at=_PRIOR,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
    )


async def _seed_held_steered(
    store: InMemoryEventStore,
    outcome_store: InMemoryOutcomeStore,
    *,
    closed: Sequence[tuple[float, float]],
    open_pass: bool = False,
    extra_outcome: tuple[int, float, float] | None = None,
    procedure_id: UUID = _PROCEDURE_ID,
    resolved_closing_steps: tuple[Step, ...] = (),
    design_pinned: bool = True,
) -> None:
    """Land a conducted-then-Held steered Procedure with recorded closed passes.

    `closed` is one (measured_coordinate, measured_value) per cleanly-closed
    pass, in order. Each seeds an IterationStarted + IterationEnded pair AND a
    self-describing Outcome row (0-based index).

    `open_pass=True` models a MID-PASS crash: after the closed passes, one more
    iteration is Started but NOT Ended (current_iteration_index stays set), so
    the aggregate's iteration_count exceeds the recovered observation count.

    `extra_outcome=(index, coordinate, value)` models a crash AFTER the pass
    wrote its outcome but before end_iteration: an Outcome row exists for the
    open pass. It is recovered + re-fed by the resume.

    `design_pinned=False` models a stream conducted BEFORE the design pin
    existed:
    steps pinned, design absent. The resume's continuity check has nothing to
    compare against and must stay silent rather than refuse, so this is the
    legacy arm, not a variant of the normal case.
    """
    resolved = tuple(step_to_payload(s) for s in _steered_block())
    resolved_closing = tuple(step_to_payload(s) for s in resolved_closing_steps)
    events: list[ProcedureEvent] = [
        ProcedureRegistered(
            procedure_id=procedure_id,
            name="steered align",
            kind="rotation_center_characterization",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_PRIOR,
        ),
        ResolvedStepsRecorded(
            procedure_id=procedure_id,
            resolved_steps=resolved,
            resolved_closing_steps=resolved_closing,
            step_count=len(resolved) + len(resolved_closing),
            occurred_at=_PRIOR,
        ),
    ]
    if design_pinned:
        events.append(
            SteeringDesignRecorded(
                procedure_id=procedure_id,
                objective=_objective(),
                objective_capture_name=_OBJECTIVE_NAME,
                space=_space(),
                budget_iterations_remaining=None,
                budget_wall_clock_seconds_remaining=None,
                substrate=SteeringSubstrate.IN_MEMORY,
                points_per_axis=5,
                min_observations=5,
                num_restarts=10,
                raw_samples=256,
                seed=0,
                staged_threshold=5,
                spend_agent_id=None,
                design_source=SteeringDesignSource.REQUEST,
                occurred_at=_PRIOR,
            )
        )
    events.append(ProcedureStarted(procedure_id=procedure_id, occurred_at=_PRIOR))
    for k, _pass in enumerate(closed):
        one_based = k + 1
        events.append(
            ProcedureIterationStarted(
                procedure_id=procedure_id, iteration_index=one_based, occurred_at=_PRIOR
            )
        )
        events.append(
            ProcedureIterationEnded(
                procedure_id=procedure_id,
                iteration_index=one_based,
                converged=None,
                reason=None,
                advised_stop=False,
                advised_next_point=None,
                occurred_at=_PRIOR,
            )
        )
    if open_pass:
        # A mid-crash pass: Started, never Ended. Its index is len(closed)+1.
        events.append(
            ProcedureIterationStarted(
                procedure_id=procedure_id,
                iteration_index=len(closed) + 1,
                occurred_at=_PRIOR,
            )
        )
    events.append(
        ProcedureHeld(
            procedure_id=procedure_id,
            reason="beam dropped",
            occurred_at=_PRIOR,
            actuation_kind="Physical",
        )
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(e),
                payload=to_payload(e),
                occurred_at=e.occurred_at,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
            for e in events
        ],
    )
    rows = [
        _outcome_row(procedure_id, iteration_index=k, coordinate=coord, value=value)
        for k, (coord, value) in enumerate(closed)
    ]
    if extra_outcome is not None:
        idx, coord, value = extra_outcome
        rows.append(_outcome_row(procedure_id, iteration_index=idx, coordinate=coord, value=value))
    await outcome_store.append(rows)


async def _status(store: InMemoryEventStore) -> ProcedureStatus:
    state = await load_procedure(store, _PROCEDURE_ID)
    assert state is not None
    return state.status


async def _current_open_iteration(store: InMemoryEventStore) -> int | None:
    state = await load_procedure(store, _PROCEDURE_ID)
    assert state is not None
    return state.current_iteration_index


def _call(
    handler: ReconductHandler,
    *,
    substrate: DecideSubstrate = "in_memory",
    objective: SteeringObjective | None = None,
    space: SteeringSpace | None = None,
    objective_capture_name: str = _OBJECTIVE_NAME,
    budget: SteeringBudget | None = None,
) -> Any:
    return handler(
        ConductUntilAdvisedFrom(
            procedure_id=_PROCEDURE_ID,
            objective=objective or _objective(),
            space=space or _space(),
            objective_capture_name=objective_capture_name,
            decide=DecidePortConfig(substrate=substrate),
            budget=budget,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_resume_re_asks_frontier_and_completes_on_stop() -> None:
    """The brain is re-asked at the frontier; an in_memory Stop completes, no new pass."""
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()  # nothing queued: no pass may run
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0), (4.0, 0.5)])
    deps = _deps(store)

    result = await _call(_make_conduct_from(deps, port, compute, outcome_store))

    assert result.succeeded is True
    assert result.re_establishment_boundary == 2
    assert await _status(store) is ProcedureStatus.COMPLETED


@pytest.mark.unit
async def test_resume_with_a_real_brain_runs_a_further_pass_and_measures() -> None:
    """A grid_walk brain not yet satisfied runs one more pass on resume."""
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_measurement(0.2),),))  # one further pass
    outcome_store = InMemoryOutcomeStore()
    # One recovered pass; grid_walk (points_per_axis default) still has lattice
    # left, so the frontier re-ask returns Measure and one more pass runs.
    await _seed_held_steered(store, outcome_store, closed=[(0.0, 2.0)])
    deps = _deps(store)

    result = await _call(
        _make_conduct_from(deps, port, compute, outcome_store), substrate="grid_walk"
    )

    assert result.re_establishment_boundary == 1
    # A further pass measured (the frontier re-ask returned Measure).
    assert (await port.read(_MOTOR_ADDR)).value is not None


@pytest.mark.unit
async def test_resume_after_mid_pass_crash_closes_open_iteration_and_resumes() -> None:
    """A pass left open by a mid-crash hold is closed; the resume does NOT 409.

    This is the headline bug the rewrite fixes: iteration_count (passes started)
    exceeds the recovered observation count, and the dangling open iteration
    would collide with the loop's start_iteration. The handler passes the open
    index to the conductor, which ends it before the frontier.
    """
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()  # frontier re-ask says Stop (in_memory) -> no pass
    outcome_store = InMemoryOutcomeStore()
    # One cleanly-closed pass + one open (crashed mid-pass, no outcome).
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)], open_pass=True)
    deps = _deps(store)
    # Precondition: the aggregate really has an open iteration (index 2).
    assert await _current_open_iteration(store) == 2

    result = await _call(_make_conduct_from(deps, port, compute, outcome_store))

    assert result.succeeded is True
    assert result.re_establishment_boundary == 1  # only the ONE recovered outcome
    assert await _status(store) is ProcedureStatus.COMPLETED


@pytest.mark.unit
async def test_resume_after_crash_that_recorded_its_outcome_refeeds_it() -> None:
    """A crash after the outcome write (before end_iteration) re-feeds that outcome.

    The open pass (index 2, 1-based) wrote its Outcome row (0-based index 1)
    before crashing. That outcome is recovered, so the brain sees BOTH passes;
    the dangling iteration is still closed. Nothing is re-measured.
    """
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()  # in_memory frontier Stop -> no re-measure
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(
        store,
        outcome_store,
        closed=[(3.0, 2.0)],
        open_pass=True,
        extra_outcome=(1, 4.0, 0.5),  # the crashed pass's recorded outcome
    )
    deps = _deps(store)

    result = await _call(_make_conduct_from(deps, port, compute, outcome_store))

    assert result.succeeded is True
    # BOTH outcomes were recovered (the closed one + the crashed pass's).
    assert result.re_establishment_boundary == 2
    assert await _status(store) is ProcedureStatus.COMPLETED


async def _seed_twice_crashed(
    store: InMemoryEventStore,
    outcome_store: InMemoryOutcomeStore,
    *,
    procedure_id: UUID = _PROCEDURE_ID,
) -> None:
    """Land a Procedure that already resumed once and then crashed again.

    Models the state AFTER a first mid-pass crash was resumed and a further pass
    ran, then a SECOND mid-pass crash:

      - iteration 1, 2: closed cleanly (outcomes idx 0, 1)
      - iteration 3: ABANDONED by the first resume (end_iteration, advised_stop=None,
        NO outcome row) -> leaves a GAP in the outcome index sequence
      - iteration 4: the first resume's frontier pass, closed (outcome idx 3)
      - iteration 5: STARTED then crashed mid-pass (open, no outcome)

    So iteration_count=5, current_iteration_index=5, and the outcome rows are the
    GAPPED sequence {0, 1, 3}. A correct second resume must close iteration 5,
    reconstruct from the gapped rows (sort tolerates the gap), and continue at
    start_iteration(6).
    """
    resolved = tuple(step_to_payload(s) for s in _steered_block())
    events: list[ProcedureEvent] = [
        ProcedureRegistered(
            procedure_id=procedure_id,
            name="steered align",
            kind="rotation_center_characterization",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_PRIOR,
        ),
        ResolvedStepsRecorded(
            procedure_id=procedure_id,
            resolved_steps=resolved,
            step_count=len(resolved),
            occurred_at=_PRIOR,
        ),
        ProcedureStarted(procedure_id=procedure_id, occurred_at=_PRIOR),
    ]

    def _started(index: int) -> ProcedureIterationStarted:
        return ProcedureIterationStarted(
            procedure_id=procedure_id, iteration_index=index, occurred_at=_PRIOR
        )

    def _ended(index: int, *, abandoned: bool) -> ProcedureIterationEnded:
        return ProcedureIterationEnded(
            procedure_id=procedure_id,
            iteration_index=index,
            converged=None,
            reason="resume abandoned an incomplete pass" if abandoned else None,
            advised_stop=None if abandoned else False,
            advised_next_point=None,
            occurred_at=_PRIOR,
        )

    events += [_started(1), _ended(1, abandoned=False)]
    events += [_started(2), _ended(2, abandoned=False)]
    events += [_started(3), _ended(3, abandoned=True)]  # first resume abandoned this
    events += [_started(4), _ended(4, abandoned=False)]  # first resume's frontier pass
    events += [_started(5)]  # second crash: open, never ended
    events.append(
        ProcedureHeld(
            procedure_id=procedure_id,
            reason="beam dropped again",
            occurred_at=_PRIOR,
            actuation_kind="Physical",
        )
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(e),
                payload=to_payload(e),
                occurred_at=e.occurred_at,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
            for e in events
        ],
    )
    # Gapped outcome sequence: 0, 1, 3 (iteration 3 abandoned -> no row).
    await outcome_store.append(
        [
            _outcome_row(procedure_id, iteration_index=0, coordinate=1.0, value=2.0),
            _outcome_row(procedure_id, iteration_index=1, coordinate=3.0, value=0.5),
            _outcome_row(procedure_id, iteration_index=3, coordinate=5.0, value=0.3),
        ]
    )


@pytest.mark.unit
async def test_resume_after_a_second_mid_pass_crash_still_resumes() -> None:
    """A second mid-pass crash (gapped outcomes + dangling iter) still resumes.

    The reviewer's key trace: after one resume abandoned iteration 3 and ran iteration 4,
    a crash mid-pass-5 leaves iteration_count=5, current_iteration_index=5, and
    a GAPPED outcome sequence {0,1,3}. The second resume must close iteration 5 and
    reconstruct the three observations from the gapped rows without mis-ordering
    or double-counting.
    """
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()  # in_memory frontier Stop -> no forced pass
    outcome_store = InMemoryOutcomeStore()
    await _seed_twice_crashed(store, outcome_store)
    deps = _deps(store)
    # Precondition: the second crash left iteration 5 open.
    assert await _current_open_iteration(store) == 5

    result = await _call(_make_conduct_from(deps, port, compute, outcome_store))

    assert result.succeeded is True
    # Three observations recovered from the gapped {0,1,3} sequence.
    assert result.re_establishment_boundary == 3
    assert await _status(store) is ProcedureStatus.COMPLETED


@pytest.mark.unit
async def test_resume_of_non_held_procedure_raises_cannot_resume() -> None:
    """A Defined (never-conducted) Procedure cannot be steered-resumed."""
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    compute = InMemoryComputePort()
    outcome_store = InMemoryOutcomeStore()
    event = ProcedureRegistered(
        procedure_id=_PROCEDURE_ID,
        name="steered align",
        kind="rotation_center_characterization",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_PRIOR,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = _deps(store)

    with pytest.raises(ProcedureCannotResumeError):
        await _call(_make_conduct_from(deps, port, compute, outcome_store))


@pytest.mark.unit
async def test_resume_unknown_procedure_raises_not_found() -> None:
    """An unregistered Procedure raises ProcedureNotFoundError."""
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    compute = InMemoryComputePort()
    outcome_store = InMemoryOutcomeStore()
    deps = _deps(store)

    with pytest.raises(ProcedureNotFoundError):
        await _call(_make_conduct_from(deps, port, compute, outcome_store))


@pytest.mark.unit
async def test_resume_authz_deny_raises_unauthorized() -> None:
    """A denied principal never touches the Procedure."""
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)])
    deps = _deps(store, deny=True)

    with pytest.raises(UnauthorizedError):
        await _call(_make_conduct_from(deps, port, compute, outcome_store))


@pytest.mark.unit
async def test_resume_refuses_a_closing_bearing_pinned_record() -> None:
    """v1 scope, mirroring conduct_until_advised's forward-direction refusal:
    the pinned record already carries resolved_closing_steps when the bound
    Recipe has any, so no fresh Recipe load is needed to reject here."""
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(
        store,
        outcome_store,
        closed=[(3.0, 2.0)],
        resolved_closing_steps=(SetpointStep(address="2bma:shutter", value=0.0),),
    )
    deps = _deps(store)

    with pytest.raises(UnsupportedClosingStepsError):
        await _call(_make_conduct_from(deps, port, compute, outcome_store))
    assert await _status(store) is ProcedureStatus.HELD


@pytest.mark.unit
async def test_resume_with_an_llm_brain_surfaces_its_calls_on_the_result() -> None:
    """The handler wires the usage sink into the brain and the collected
    calls onto the result; dropping either silently unmeters the llm
    substrate while every adapter-level test stays green."""
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()  # nothing queued: Stop completes, no pass
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0), (4.0, 0.5)])
    llm = FakeLLM(
        [
            FakeLLMResponse(
                parsed={"verdict": "Stop", "rationale": "target met"},
                usage=LLMUsage(input_tokens=700, output_tokens=40),
            )
        ]
    )
    deps = _deps(store, llm=llm)

    result = await _call(_make_conduct_from(deps, port, compute, outcome_store), substrate="llm")

    assert result.succeeded is True
    assert len(result.llm_calls) == 1
    assert result.llm_calls[0].usage.input_tokens == 700
    assert result.llm_calls[0].request_model == "claude-sonnet-4-5"


# --- steering design continuity + the resumed segment's own pin ---


async def _design_pins(store: InMemoryEventStore) -> list[SteeringDesignRecorded]:
    stored, _version = await store.load(stream_type="Procedure", stream_id=_PROCEDURE_ID)
    pins = [from_stored(e) for e in stored if e.event_type == "SteeringDesignRecorded"]
    return [pin for pin in pins if isinstance(pin, SteeringDesignRecorded)]


async def _resume_once(
    store: InMemoryEventStore, outcome_store: InMemoryOutcomeStore, **call_kwargs: Any
) -> Any:
    port = InMemoryControlPort()
    port.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    deps = _deps(store)
    return await _call(_make_conduct_from(deps, port, compute, outcome_store), **call_kwargs)


@pytest.mark.unit
async def test_resume_pins_its_own_design_for_the_resumed_segment() -> None:
    """A resume records the design it ran under, not just the one it inherited.

    Without this the Procedure ends its life carrying a single pin that
    describes only the segment before the hold, while the passes after it were
    driven by whatever the resume request happened to carry.
    """
    store = InMemoryEventStore()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)])

    await _resume_once(store, outcome_store, substrate="grid_walk")

    pins = await _design_pins(store)
    assert len(pins) == 2
    assert pins[0].substrate is SteeringSubstrate.IN_MEMORY
    assert pins[1].substrate is SteeringSubstrate.GRID_WALK


@pytest.mark.unit
async def test_resume_pins_the_design_before_the_procedure_leaves_held() -> None:
    """The RESUMED segment's pin, specifically, precedes ProcedureResumed.

    The fixture already seeds a pin from the earlier segment, and that one sits
    before this resume no matter what, so asserting "some pin precedes
    ProcedureResumed" would hold even if the resume pinned nothing at all. The
    count has to be part of the claim, and the substrate has to differ from the
    seeded one or the duplicate guard correctly writes nothing.
    """
    store = InMemoryEventStore()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)])

    await _resume_once(store, outcome_store, substrate="grid_walk")

    stored, _version = await store.load(stream_type="Procedure", stream_id=_PROCEDURE_ID)
    event_types = [e.event_type for e in stored]
    resumed_index = event_types.index("ProcedureResumed")
    design_indices = [i for i, name in enumerate(event_types) if name == "SteeringDesignRecorded"]

    assert len(design_indices) == 2
    assert design_indices[1] < resumed_index


@pytest.mark.unit
async def test_resume_under_an_unchanged_design_adds_no_second_pin() -> None:
    """Two segments under one design need one pin, and the guard leaves one.

    The pin answers what design the observations were drawn under, and when a
    resume changes nothing that answer is already on the stream. The hold and
    resume are recorded by the FSM events either way, so a duplicate would add
    a row without adding a fact. This is the same guard the forward path relies
    on after a failed attempt, reached by a different route.
    """
    store = InMemoryEventStore()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)])

    await _resume_once(store, outcome_store)

    assert len(await _design_pins(store)) == 1


@pytest.mark.unit
async def test_resume_dropping_a_recorded_axis_refuses_and_leaves_the_procedure_held() -> None:
    """A recorded pass carries a coordinate the new space cannot hold.

    Asserting only that the call raises would leave the "fires before any FSM
    event" claim untested, and a guard that refuses AFTER resuming has already
    done the damage it exists to prevent.
    """
    store = InMemoryEventStore()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)])
    renamed = SteeringSpace(axes=(SteeringAxis(name="a_different_axis", lower=0.0, upper=10.0),))

    with pytest.raises(SteeringDesignMismatchError) as excinfo:
        await _resume_once(store, outcome_store, space=renamed)

    assert excinfo.value.differing_fields == (
        f"space.axes.{_MOTOR_ADDR}.missing",
        "space.axes.a_different_axis.unrecorded",
    )
    assert await _status(store) is ProcedureStatus.HELD
    assert len(await _design_pins(store)) == 1


@pytest.mark.unit
async def test_resume_with_moved_bounds_is_recorded_not_refused() -> None:
    """Narrowing or widening the bounds strands nothing, so it is allowed.

    The whole run stays resumable and the new bounds land on the resumed
    segment's own pin, which is what lets a reader see that the search was
    tightened partway through.
    """
    store = InMemoryEventStore()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)])
    narrowed = SteeringSpace(axes=(SteeringAxis(name=_MOTOR_ADDR, lower=2.0, upper=4.0),))

    result = await _resume_once(store, outcome_store, space=narrowed)

    assert result.succeeded is True
    assert (await _design_pins(store))[-1].space == narrowed


@pytest.mark.unit
async def test_resume_with_a_changed_budget_and_substrate_is_recorded_not_refused() -> None:
    """Budget and brain config legitimately change across a hold.

    `iterations_remaining` decrements by construction, so comparing it would
    refuse every ordinary resume. Both are recorded on the new pin instead,
    which is the only reason the record can say the two segments differed.
    """
    store = InMemoryEventStore()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)])
    budget = SteeringBudget(iterations_remaining=3, wall_clock_seconds_remaining=45.0)

    await _resume_once(store, outcome_store, substrate="grid_walk", budget=budget)

    resumed = (await _design_pins(store))[-1]
    assert resumed.budget_iterations_remaining == 3
    assert resumed.budget_wall_clock_seconds_remaining == 45.0
    assert resumed.substrate is SteeringSubstrate.GRID_WALK


@pytest.mark.unit
async def test_resume_of_a_stream_pinned_before_the_design_existed_is_not_refused() -> None:
    """Absence is not a mismatch.

    Every Procedure conducted before this event existed carries steps and no
    design. Refusing those would make a record-keeping improvement retroactively
    break resumes that were fine, so the check stays silent and the resume's own
    pin closes the gap from its next segment on.
    """
    store = InMemoryEventStore()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)], design_pinned=False)

    result = await _resume_once(store, outcome_store)

    assert result.succeeded is True
    assert len(await _design_pins(store)) == 1


@pytest.mark.unit
async def test_a_refused_first_resume_does_not_lock_a_legacy_stream_out_of_resuming() -> None:
    """A pin left by a resume that never ran must not become the thing to match.

    On a stream with no pin the continuity check has nothing to compare, so the
    first attempt pins whatever was typed, and the pin outlives the refusal that
    follows it. If the check then measured against that pin, the only design it
    would accept is the one the Conductor's wire guard just rejected, and the
    Procedure could never be resumed again: every remedy the error offers is
    either the rejected design or discarding the accumulated observations.

    A pin that no segment ever started under governed nothing, so it is not what
    a later resume has to be continuous with.
    """
    store = InMemoryEventStore()
    outcome_store = InMemoryOutcomeStore()
    await _seed_held_steered(store, outcome_store, closed=[(3.0, 2.0)], design_pinned=False)
    mistyped = SteeringSpace(axes=(SteeringAxis(name="thteta", lower=0.0, upper=10.0),))

    with pytest.raises(SteeringWireMismatchError):
        await _resume_once(store, outcome_store, space=mistyped)
    assert await _status(store) is ProcedureStatus.HELD

    result = await _resume_once(store, outcome_store)

    assert result.succeeded is True
