"""REPRODUCTION: Procedure holds have the same order-dependent contention fault
that cause-scoped claims fixed for Run.

Same three conditions as the Run fault (see the hold-claim design note):

  1. `ProcedureStatus.HELD` is one bit. `ProcedureHeld` carries a REQUIRED free-text
     `reason`, which explains a hold but does not OWN one: a releaser cannot read it
     to learn whether the hold is its own.
  2. `hold_procedure`'s decider admits `RUNNING` only, so a second concern arriving
     at an already-held Procedure cannot record its intent.
  3. `resume_procedure` has no notion of who placed the hold. Its only cross-concern
     guard is the hand-patched `parent_run_held` flag, one bespoke case rather than a
     general rule.

Two independent concerns can hold a Procedure, which is what turns the shape into a
fault:

  - an operator, via `hold_procedure`;
  - the Conductor, via `conduct_or_hold`, which pauses to Held on a recoverable step
    failure so the conduct stays resumable.

## Severity: LOWER than the Run fault, and the tests say why

The shape is the same but the exposure is not, which is worth recording precisely
because the structural condition alone would predict otherwise.

`append_activities` admits `RUNNING` only, so once a Procedure is held mid-conduct
the next step's activity append is refused outright. The conduct cannot quietly
carry on past a hold it did not see, and by that route it never reaches its own
pause attempt. So while the Conductor's hold does sit inside
`contextlib.suppress(Exception)`, getting it silently dropped needs a narrow race
between a step's failure and the pause call, not the wide human-response window
that made the Run fault dangerous.

What DOES bite without any race is condition 3. An operator resume clears the
Conductor's pause outright, because nothing on the Procedure records whose hold it
is. The release still speaks for a concern that never authorised it.

And condition 2 holds but fails LOUDLY: an operator who needs a Conductor-held
Procedure held for their own reason gets `ProcedureCannotHoldError` rather than a
silent drop. They learn about it; there is still nowhere to put their intent.

These tests assert CURRENT behaviour. The two that pin the fault invert when the
fix lands; the `append_activities` one documents a mitigation and should keep
passing.
"""

# white-box reproduction: mirrors the posture of test_conduct_or_hold_procedure_handler
# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.aggregates.procedure import (
    InMemoryActivityStore,
    Procedure,
    ProcedureCannotHoldError,
    ProcedureName,
    ProcedureRegistered,
    ProcedureStatus,
    ProcedureStepsLogbookClosedError,
    event_type_name,
    load_procedure,
    to_payload,
)
from cora.operation.conductor import Conductor, SetpointStep, Step
from cora.operation.features import (
    abort_procedure,
    append_activities,
    complete_procedure,
    conduct_or_hold_procedure,
    hold_procedure,
    resume_procedure,
    start_procedure,
)
from cora.operation.features.conduct_or_hold_procedure import (
    ConductOrHoldProcedure,
    ConductOrHoldProcedureResult,
)
from cora.operation.features.conduct_or_hold_procedure import (
    Handler as ConductOrHoldHandler,
)
from cora.operation.features.hold_procedure.command import HoldProcedure
from cora.operation.features.hold_procedure.decider import decide as hold_decide
from cora.operation.features.resume_procedure.command import ResumeProcedure
from cora.operation.features.resume_procedure.decider import decide as resume_decide
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000d0b01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OPERATOR_ID = UUID("01900000-0000-7000-8000-0000000000f1")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_CONNECTED = "2bma:reachable"
_UNREACHABLE = "2bma:unreachable"  # never connected -> recoverable write failure


@dataclass
class _LenientIds:
    """Conductor id_generator that never exhausts."""

    def new_id(self) -> UUID:
        return uuid4()


def _deps(store: InMemoryEventStore) -> Kernel:
    return _build_deps_shared(ids=[uuid4() for _ in range(60)], now=_NOW, event_store=store)


async def _seed_defined(store: InMemoryEventStore) -> None:
    event = ProcedureRegistered(
        procedure_id=_PROCEDURE_ID,
        name="alignment",
        kind="alignment",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
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


def _make_conduct_or_hold(
    deps: Kernel,
    port: InMemoryControlPort,
    *,
    hold_after_first_step: bool = False,
) -> ConductOrHoldHandler:
    """Wire a real Conductor with the REAL lifecycle handlers.

    `hold_after_first_step` injects an OPERATOR hold partway through the conduct, by
    hooking the per-step append. That is the interleaving the fault needs: the
    Procedure must be Running when the conduct starts (start_procedure admits Defined
    only) and already Held by the time the Conductor tries to pause.
    """
    real_append = append_activities.bind(deps, step_store=InMemoryActivityStore())
    operator_hold = hold_procedure.bind(deps)
    state = {"held": False}

    async def append_then_maybe_hold(*args: object, **kwargs: object) -> object:
        result = await real_append(*args, **kwargs)  # type: ignore[arg-type]
        if hold_after_first_step and not state["held"]:
            state["held"] = True
            await operator_hold(
                HoldProcedure(procedure_id=_PROCEDURE_ID, reason="operator took the hutch"),
                principal_id=_OPERATOR_ID,
                correlation_id=_CORRELATION_ID,
            )
        return result

    conductor = Conductor(
        control_port=port,
        append_step=append_then_maybe_hold,  # type: ignore[arg-type]
        clock=deps.clock,
        id_generator=_LenientIds(),
        start_procedure=start_procedure.bind(deps),
        complete_procedure=complete_procedure.bind(deps),
        abort_procedure=abort_procedure.bind(deps),
        hold_procedure=operator_hold,
    )
    return conduct_or_hold_procedure.bind(
        deps, conductor=conductor, expansion_port=InMemoryRecipeExpander()
    )


async def _call(
    handler: ConductOrHoldHandler, steps: Sequence[Step]
) -> ConductOrHoldProcedureResult:
    return await handler(
        ConductOrHoldProcedure(procedure_id=_PROCEDURE_ID, steps=steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _state(store: InMemoryEventStore) -> Procedure:
    state = await load_procedure(store, _PROCEDURE_ID)
    assert state is not None
    return state


async def _event_types(store: InMemoryEventStore) -> list[str]:
    events, _ = await store.load("Procedure", _PROCEDURE_ID)
    return [e.event_type for e in events]


# --------------------------------------------------------------------------
# Condition 2: a second concern cannot record its hold.
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_hold_decider_refuses_a_second_concern_on_a_held_procedure() -> None:
    """`RUNNING`-only guard: the Conductor cannot register a pause on a Procedure an
    operator already holds, so its intent is never written down anywhere."""
    state = Procedure(
        id=_PROCEDURE_ID,
        name=ProcedureName("alignment"),
        kind="alignment",
        status=ProcedureStatus.HELD,
    )
    with pytest.raises(ProcedureCannotHoldError) as excinfo:
        hold_decide(
            state,
            HoldProcedure(procedure_id=_PROCEDURE_ID, reason="recoverable setpoint failure"),
            now=_NOW,
        )
    assert excinfo.value.current_status is ProcedureStatus.HELD


# --------------------------------------------------------------------------
# Condition 3: the release has no notion of ownership.
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_resume_decider_clears_a_hold_it_did_not_place() -> None:
    """`resume_procedure` reads only `status is HELD`. Nothing on the Procedure says
    whose hold it is, so any resume clears whatever hold exists. The one cross-concern
    guard, `parent_run_held`, is a bespoke case rather than a general rule."""
    state = Procedure(
        id=_PROCEDURE_ID,
        name=ProcedureName("alignment"),
        kind="alignment",
        status=ProcedureStatus.HELD,
    )
    events = resume_decide(
        state,
        ResumeProcedure(procedure_id=_PROCEDURE_ID, re_establishment_boundary=0),
        now=_NOW,
    )
    assert [type(e).__name__ for e in events] == ["ProcedureResumed"]


# --------------------------------------------------------------------------
# What is actually reachable end to end.
# --------------------------------------------------------------------------


@pytest.mark.unit
async def test_operator_hold_mid_conduct_closes_the_activity_logbook() -> None:
    """A partial mitigation the Run path had no analogue for, and the reason this
    instance is less severe than the Run one.

    `append_activities` admits `RUNNING` only, so once an operator holds a Procedure
    mid-conduct the next step's activity append is REFUSED rather than silently
    written. The conduct cannot quietly carry on past a hold it did not see, and it
    cannot reach its own pause attempt by this route.

    So the silent-drop window here is a narrow race between a step's failure and the
    Conductor's pause call, not the wide human-response window that made the Run fault
    dangerous. Documented as a test so the mitigation is not mistaken for the absence
    of the shape.
    """
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect(_CONNECTED)
    await _seed_defined(store)

    with pytest.raises(ProcedureStepsLogbookClosedError):
        await _call(
            _make_conduct_or_hold(_deps(store), port, hold_after_first_step=True),
            (
                SetpointStep(address=_CONNECTED, value=1.0),
                SetpointStep(address=_UNREACHABLE, value=2.0),
            ),
        )

    types = await _event_types(store)
    assert types.count("ProcedureHeld") == 1  # the operator's only
    assert (await _state(store)).status is ProcedureStatus.HELD


@pytest.mark.unit
async def test_operator_cannot_record_a_hold_on_a_conductor_held_procedure() -> None:
    """The reachable half of condition 2, over the real store.

    The Conductor pauses to Held on a recoverable failure. An operator who now needs
    the Procedure held for an unrelated reason (hutch access, a survey) cannot record
    that: `hold_procedure` refuses. Unlike the Run case this refusal is LOUD, so the
    operator learns of it, but there is still nowhere to put their intent.
    """
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    await _seed_defined(store)
    deps = _deps(store)

    result = await _call(
        _make_conduct_or_hold(deps, port),
        (SetpointStep(address=_UNREACHABLE, value=1.0),),
    )
    assert result.held is True
    assert (await _state(store)).status is ProcedureStatus.HELD

    with pytest.raises(ProcedureCannotHoldError):
        await hold_procedure.bind(deps)(
            HoldProcedure(procedure_id=_PROCEDURE_ID, reason="hutch access for a survey"),
            principal_id=_OPERATOR_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_operator_resume_clears_the_conductors_hold_over_the_real_store() -> None:
    """Condition 3 end to end, and the part that still bites.

    The Conductor pauses to Held with a recoverable failure outstanding. An operator
    resume clears it with no ownership check at all: nothing on the Procedure records
    that the hold was the Conductor's, so `resume_procedure` cannot decline. The
    Procedure returns to Running with the failure unaddressed.

    This is the Run fault transposed, minus the silent drop: the release still speaks
    for a concern that never authorised it.
    """
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    await _seed_defined(store)
    deps = _deps(store)

    result = await _call(
        _make_conduct_or_hold(deps, port),
        (SetpointStep(address=_UNREACHABLE, value=1.0),),
    )
    assert result.held is True

    await resume_procedure.bind(deps)(
        ResumeProcedure(procedure_id=_PROCEDURE_ID, re_establishment_boundary=0),
        principal_id=_OPERATOR_ID,
        correlation_id=_CORRELATION_ID,
    )

    state = await _state(store)
    assert state.status is ProcedureStatus.RUNNING, (
        "current behaviour: an operator resume clears the Conductor's pause outright"
    )
    types = await _event_types(store)
    assert types.count("ProcedureHeld") == 1
    assert types.count("ProcedureResumed") == 1
