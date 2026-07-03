"""Run bounded context.

Owns the actual-execution layer of CORA. Per the BC map's recipe
ladder, Run is the keystone — Method (≈ ISA-88 General Recipe) →
Practice (≈ Site Recipe) → Plan (≈ Master/Control Recipe) → **Run**
(actual batch execution; immutable, has FSM, audit trail, references
to Subject(s)).

A Run binds a `Plan` (which itself binds a Practice + Asset set)
and an optional `Subject` (sample being measured; null for dark-
field / flat-field calibration runs per beamline-domain convention,
where calibration data is consumed alongside sample data within the
same analysis pipeline).

Track A BC. Depends on:
  - `Recipe.Plan` (referenced by `Run.plan_id`; loaded at Run-start
    for re-validation of capability superset against current Asset
    state)
  - `Equipment.Asset` (transitive via Plan; loaded at Run-start to
    re-check that no bound Asset has been Decommissioned)
  - `Subject.Subject` (referenced by `Run.subject_id` if non-null;
    must be in Mounted or Measured state)


Full lifecycle FSM closed:
  - `id` + `name` (RunName: 11th bounded-name VO)
  - `plan_id: UUID`, eventual-consistency ref; existence verified
    at handler-load time
  - `subject_id: UUID | None`, null for calibration / dark-field
    runs; if non-null, Subject must be in Mounted | Measured
  - `status: RunStatus` (`Running | Held | Completed | Aborted |
    Stopped | Truncated`)

Cross-aggregate validation at Run-start (gate-review Q2 / Q5
locked answers): handler pre-loads Plan + Subject (if subject_id)
+ each bound Asset (from `plan.asset_ids`); decider receives
`RunStartContext` and validates as opaque domain inputs (same
canonical pattern as Plan's PlanBindingContext). Per
gate-review Q5: Run-start re-validates capability superset
against CURRENT Asset state (Plan-bind validated against then-
current; drift is real, Run is the last gate).

Active-phase transitions (6f-2 + 6f-3):
  - `complete_run` (Running → Completed): single-source. Completion
    claims active achievement, so requires the Run to be actively
    running; an operator wanting to complete a held Run must
    Resume → Complete. Slim payload by design.
  - `abort_run` (Running | Held → Aborted): multi-source. Carries
    free-form `reason: str` (1-500 chars). Emergencies during a
    hold are real and should not require an intervening Resume.
  - `hold_run` (Running → Held): single-source pause. No reason
    field — matches PackML / Bluesky precedent that pause is a
    routine operation.
  - `resume_run` (Held → Running): single-source un-pause. Hold ⇄
    Resume is bidirectional and unlimited-cycle (PackML + Bluesky
    precedent).
  - `stop_run` (Running | Held → Stopped): multi-source controlled
    exit. Carries free-form `reason: str` (1-500 chars). Distinct
    from abort: stop = data valid up to the stop point; abort =
    data flagged as potentially invalid (PackML + Bluesky lifecycle-
    layer distinction; observation-channel cleanup semantics materialize in
    6f-5+).
  - `truncate_run` (Running | Held → Truncated): multi-source
    cleanup terminal for a Run that became de-facto dead through
    interruption (power loss, process crash, hardware fault) and
    is being closed retroactively. Carries free-form `reason: str`
    (1-500 chars) plus optional `interrupted_at: datetime | None`
    (operator's best guess at when the actual interruption happened;
    distinct from `occurred_at` which is when truncation was
    processed). The system itself does not detect de-facto-dead
    Runs; operators must call truncate explicitly. Stale-RUNNING
    detection is a separate liveness concern (out of scope).

Why complete_run is single-source while abort/stop are multi-
source (gate-review 6f-3 Q1 lock): completion claims achievement,
which requires active work. Exits don't require active work, only
any non-terminal state. The asymmetry isn't arbitrary — it
reflects the semantic difference between positive achievement and
controlled / emergency termination.

Phase history:
  - 6f-1: Run + start_run + get_run (the keystone slice) ✅
  - 6f-2: complete_run + abort_run (terminal happy + emergency
    exit) ✅
  - 6f-3: hold_run + resume_run + stop_run (pause cycle +
    controlled-exit terminal) ✅
  - 6f-4: truncate_run (partial-data terminal for known-dead Runs
    being closed retroactively; closes the lifecycle FSM) ✅
  - 6f-5 (deferred): Additional observation channels + per-frame
    trigger channel (high-cardinality telemetry); when Run gains
    logbooks, truncate_run extends to auto-close them per gate-
    review L4.

Known gaps (early sequencing decisions, accepted by design):
  - **Supply availability check** (Track B Supply BC not shipped):
    Run-start does NOT verify beam / power / gas availability today.
    Operator-trusted; documented as gap. Lands when Supply BC ships.
  - **Decision approval check** (Decision BC not shipped):
    Run-start does NOT require an Approved Decision referencing
    the Plan today. Operator-trusted; documented as gap. Lands
    when Decision BC ships.

Layout (mirrors Recipe / Equipment / Trust / Subject):
    aggregates/run/           -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                   -- RunHandlers bundle + wire_run(deps)
    routes.py                 -- register_run_routes(app)
    tools.py                  -- register_run_tools(mcp, *, get_handlers)
"""

from cora.run._projections import register_run_projections
from cora.run._subscribers import register_run_subscribers
from cora.run.errors import UnauthorizedError
from cora.run.routes import register_run_routes
from cora.run.tools import register_run_tools
from cora.run.wire import RunHandlers, wire_run

__all__ = [
    "RunHandlers",
    "UnauthorizedError",
    "register_run_projections",
    "register_run_routes",
    "register_run_subscribers",
    "register_run_tools",
    "wire_run",
]
