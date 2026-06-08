"""Domain events emitted by the Run aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Lifecycle events:
  - `RunStarted` — genesis. Payload + lifecycle context for the
    other transitions to depend on.
  - `RunCompleted` — happy-path terminal (Running → Completed).
    Payload is `run_id` + `occurred_at` only; substantive run
    summary (frame_count, duration, final detector positions, etc.)
    will land when DAQ-channel integration arrives. Per the
    fold-cost principles, the completion event SHOULD eventually
    carry summary state so consumers don't have to re-fold per-step
    history just to ask "what happened in Run X?" — but the
    substantive shape only crystallizes once the observation-channel
    infrastructure exists to source it.
  - `RunAborted` — emergency-exit terminal (Running | Held → Aborted).
    Payload carries `run_id` + free-form `reason: str` (1-500 chars)
    + `occurred_at`. Reason is stored as primitive string today;
    future-additive structured taxonomy is documented at
    `InvalidRunAbortReasonError` along with its re-evaluation
    triggers.
  - `RunHeld` — pause transition (Running → Held). Payload is
    `run_id` + `occurred_at` only. No reason field — matches PackML
    / Bluesky precedent (Hold / pause carries no domain reason in
    either standard). Holds are routine (alignment, brief beam
    dropout, operator break); a reason field would be friction
    without audit value at this layer. Future-additive on the same
    triggers as RunAborted's reason if vocabulary / Decision BC
    integration / compliance demand crystallize.
  - `RunResumed` — resume transition (Held → Running). Payload is
    `run_id` + `occurred_at` only. Resume is just permission to
    proceed; no reason field.
  - `RunStopped` — controlled-exit terminal (Running | Held → Stopped).
    Payload carries `run_id` + free-form `reason: str` (1-500 chars)
    + `occurred_at`. Mirrors RunAborted shape — controlled-but-early
    terminal exit deserves audit explanation. Distinct from Aborted:
    Stopped data is valid up to the stop point; Aborted data is
    flagged as potentially invalid (PackML + Bluesky semantic
    distinction at the lifecycle layer; observation-channel cleanup
    semantics materialize on the observation channel).

Hold ⇄ Resume is a bidirectional cycle with unlimited repeats; the
event stream may interleave [RunStarted, RunHeld, RunResumed, RunHeld,
RunResumed, RunCompleted] with arbitrary cycle counts. The fold
preserves only the latest status; per-cycle audit lives in the
event stream itself.

`RunTruncated` — cleanup terminal (Running | Held → Truncated).
Payload carries `run_id` + free-form `reason: str` (1-500 chars)
+ optional `interrupted_at: datetime | None` (operator's best guess
at when the actual interruption occurred, separate from
`occurred_at` which is when truncation was processed) + `occurred_at`.
Mirrors RunStopped's reason shape; adds the interrupted_at field
because Truncated is uniquely retroactive among the terminals (the
Run was already de-facto over before the operator could mark it).

Observation events (per-frame triggers, motor positions) do NOT live
on the main Run stream; they're observation-channel territory. When
the Run aggregate adds logbooks, the truncate_run decider extends to
emit RunLogbookClosed events for each open logbook before
RunTruncated (gate-review L4).

## Payload conventions

`plan_id` and `subject_id` carry as primitive UUIDs (or null for
subject_id in calibration runs). Eventual-consistency stance:
neither is verified at the persistence layer — handler pre-loads
both before reaching the decider.

Status is NOT carried in event payloads — the event type itself
encodes the state change. Same precedent as PracticeDefined /
MethodDefined / FamilyDefined / SubjectMounted /
ActorDeactivated / PlanDefined.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId
from cora.shared.logbook import LogbookSchema


@dataclass(frozen=True)
class CautionAcknowledgement:
    """One entry in `RunStarted.acknowledged_cautions`.

    Snapshot of a single Active caution that referenced the Run's
    scope (Asset / Procedure) at start time. The full caution lives
    in the Caution BC stream; this VO carries only the columns
    needed for the operator-facing banner + audit trail. Excerpt
    columns mirror the projection's `LEFT(text, 200)` truncation;
    the full text is available via `GET /cautions/{id}`.

    Per the Caution design memo anti-pattern #7 (ack tracked on the
    consumption event, never per-operator on the Caution aggregate),
    THIS VO is where the ack lives. The presence of the entry in
    the `RunStarted` payload IS the ack: operators saw the caution
    when the run started, and the snapshot proves it.

    NON-BLOCKING by construction (anti-pattern #5): the `start_run`
    decider does NOT raise any error class based on the presence,
    count, severity, or category of these entries. The list is
    purely informational + audit.
    """

    caution_id: UUID
    target_kind: str  # "Asset" | "Procedure"
    target_id: UUID
    category: str
    severity: str  # "Notice" | "Caution" | "Warning"
    text_excerpt: str
    workaround_excerpt: str


@dataclass(frozen=True)
class RunStarted:
    """A new Run was started: Plan + (optional) Subject binding established.

    Status is implicit (`Running`) — the evolver sets it.

    `plan_id` and `subject_id` are eventual-consistency refs (loaded
    at handler-load time; not re-verified at fold time). `subject_id`
    is null for dark-field / flat-field calibration runs per
    beamline-domain convention.

    `raid` is the Research Activity Identifier (ISO 23527), opaque
    string carried verbatim. Defaults to None (a Run that wasn't
    registered against a research activity). Forward-compatible
    jsonb load: `from_stored` reads the key with `.get(...)` so
    legacy events without the raid key deserialize as `raid=None`.

    `override_parameters` is the operator-supplied overrides on top
    of `Plan.default_parameters` (RFC 7396 merge semantics).
    `effective_parameters` is the resolved post-merge snapshot
    (defaults + overrides) that governs this Run; mirrors the
    Bluesky start-document / MLflow params / W&B run.config /
    ISA-88 control-recipe / RO-Crate CreateAction precedent (run
    resource carries the resolved value set, not just an audit log).
    Both default to `{}` and forward-compat: `from_stored` reads
    each key with `payload.get(..., {})` so legacy streams replay.

    `trigger_source` is operator-supplied free text
    capturing what initiated this Run (operator-manual, scheduler
    id, prior-run id, automation id). Optional (None when omitted).
    Forward-compat via `payload.get("trigger_source")`. Future
    Decision-BC integration may populate this from
    `DecisionReasoning.entries` references.
    """

    run_id: UUID
    name: str
    plan_id: UUID
    subject_id: UUID | None
    occurred_at: datetime
    raid: str | None = None
    override_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    effective_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    trigger_source: str | None = None
    # anti-corruption refs to upstream-deferred concepts
    # (proposal / btr / lab_visit / session). Each entry is a dict
    # `{"scheme": str, "value": str}` per the shared `Identifier` VO
    # wire shape. Defaults to () for legacy streams without the field;
    # the evolver reconstructs typed `Identifier` VOs.
    external_refs: tuple[dict[str, Any], ...] = ()
    # snapshot of Active cautions whose target referenced
    # this Run's scope at start time. Audit-trail proof + operator-
    # facing banner data; NON-BLOCKING by construction (anti-pattern
    # #5: the decider never partitions on this field). Lives on the
    # event payload only — NOT on Run state (anti-pattern #7: ack
    # tracked on the consumption event, never per-operator on the
    # Caution aggregate). Defaults to () for legacy streams without the field;
    # forward-compat via `payload.get("acknowledged_cautions", [])` in
    # `from_stored`.
    acknowledged_cautions: tuple[CautionAcknowledgement, ...] = ()
    # optional Campaign membership stamped at Run-start.
    # None when the Run is standalone or when membership is established
    # post-hoc (via `add_run_to_campaign` → RunAddedToCampaign). When
    # `StartRun.campaign_id` is provided the handler atomically writes
    # this event AND `CampaignRunAdded` to the Campaign stream via
    # `EventStore.append_streams` (mirrors amend_clearance shape).
    # Forward-compat via `payload.get("campaign_id")` returning None
    # for legacy streams without the field.
    campaign_id: UUID | None = None
    # Decision→Run linkage: optional Decision-causation link
    # mirroring RunAdjusted.decided_by_decision_id. Lets operators link
    # the Run's start to the Decision BC record that justified it (most
    # commonly an EnergyChange / PivotToHighResolution / similar
    # cross-Plan operator pivot). Maps to `prov:wasInformedBy` at the
    # future PROV-O export adapter, same contract as Decision.parent_id.
    # OPTIONAL: not every Run-start needs formal justification. NO
    # existence check at the decider per the cross-BC eventual-
    # consistency stance. Forward-compat via
    # `payload.get("decided_by_decision_id")` returning None for legacy
    # streams that pre-date the field.
    decided_by_decision_id: UUID | None = None
    # Calibration AsShot anchor: set of CalibrationRevision
    # ids that were live at start_run time per
    # [[project_calibration_design]]. Tuple (not frozenset) on the
    # event payload for deterministic byte ordering during replay; the
    # evolver reconstructs the frozenset. NO cross-BC existence check
    # at the decider (operator/agent supplies the pin set; symmetry
    # with adjust_run + the cross-BC eventual-consistency stance).
    # IMMUTABLE after start by aggregate-level invariant — every Run
    # transition arm preserves it verbatim. Forward-compat via
    # `payload.get("pinned_calibration_ids", [])` returning an empty list
    # for legacy streams without the field.
    pinned_calibration_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class RunAddedToCampaign:
    """A Run was added to a Campaign post-hoc.

    Written by the cross-aggregate `add_run_to_campaign` slice on the
    Campaign BC, atomically alongside `CampaignRunAdded` on the
    Campaign's stream (via `EventStore.append_streams`). Distinct from
    `RunStarted.campaign_id`, which covers the at-start membership
    path. Splitting the two paths keeps the evolver's state-derivation
    clean: RunStarted is the genesis arm; RunAddedToCampaign is a
    post-genesis transition that requires prior state.

    Invariants enforced at the cross-aggregate decider (NOT here at
    the event layer): the Run's prior `campaign_id` must be None (one-
    Campaign-per-Run lock). The evolver trusts the event log and
    simply sets `campaign_id = event.campaign_id`.
    """

    run_id: UUID
    campaign_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RunRemovedFromCampaign:
    """A Run was removed from its Campaign.

    Written by the cross-aggregate `remove_run_from_campaign` slice on
    the Campaign BC, atomically alongside `CampaignRunRemoved` on the
    Campaign's stream. The `reason` carries the operator's audit
    breadcrumb (REQUIRED at the slice, 1-500 chars after trim);
    ungrouping is a meaningful operator action.

    The evolver clears `campaign_id` back to None; the prior
    `campaign_id` is on the event payload for audit-replay queries.
    """

    run_id: UUID
    campaign_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class DecisionDebriefRequested:
    """An Agent BC subscriber leased the right to author a Decision for
    this Run's terminal event.

    Written by terminal-Run-event side-effecting subscribers
    (`RunDebriefer`, `CautionDrafter`, future agents) BEFORE invoking
    the LLM. The append uses the Run aggregate's current
    `expected_version`; first writer wins via the existing
    `UNIQUE(stream_type, stream_id, version)` optimistic-concurrency
    primitive on the events table. Losing subscribers see
    `ConcurrencyError`, emit a `DebriefConflicted` Decision on their
    own Decision stream for audit visibility, and exit without
    consuming LLM tokens.

    The lease is per `(terminal_event_id, debriefer_agent_id)` pair:
    the event_id is derived as
    `uuid5(run_id, f"lease:{terminal_event_id}:{agent_id}")` so the
    same agent's retries are idempotent (re-append fails on event_id
    UNIQUE) but different agents compete on stream version.

    Audit-only on the Run aggregate: the evolver returns prior state
    unchanged. The lease's existence on the stream IS the lease. See
    [[project-run-debriefer-lease-design]] for the full design and
    [[project-cross-bc-atomic-writes]] for the cross-BC stream-write
    precedent (Agent BC subscriber appending to Run stream).
    """

    run_id: UUID
    debriefer_agent_id: UUID
    terminal_event_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RunHeld:
    """A Run was held (Running → Held).

    Slim payload — no reason field. Matches PackML / Bluesky
    precedent: Hold / pause is a routine operation (alignment,
    brief dropout, operator break) that doesn't reify a domain
    reason. Future-additive if the same re-evaluation triggers
    documented for RunAborted's reason field crystallize.
    """

    run_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RunResumed:
    """A held Run was resumed (Held → Running).

    Slim payload by design — resume is just permission to proceed.
    """

    run_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RunCompleted:
    """A Run reached its happy-path terminal (Running → Completed).

    Slim payload by design (gate-review Q3): substantive run
    summary lands later once DAQ-channel integration is in
    place to source it. Today, downstream consumers needing
    aggregate read state should fold the Run stream — the stream
    is short for terminal-by-design Lifecycle Aggregates (a
    handful of lifecycle events, not per-frame data).
    """

    run_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RunAborted:
    """A Run reached its emergency-exit terminal (Running | Held → Aborted).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Future-additive structured
    taxonomy is parked at `InvalidRunAbortReasonError`'s docstring
    along with three concrete triggers for re-evaluation.

    The source set includes `Held` — emergencies during a hold are
    real and should not require an intervening Resume.

    `decided_by_decision_id` (mirrors RunAdjusted + RunStarted):
    optional Decision-causation link to the Decision BC
    record that justified this abort (most commonly an
    OperatorAbortDecision or EquipmentAbortDecision per
    [[project-run-debrief-design]]'s 5-value choice enum). OPTIONAL:
    not every abort needs formal justification (operator-emergency
    aborts may bypass Decision). NO existence check at the decider
    per the cross-BC eventual-consistency stance. Forward-compat via
    `payload.get("decided_by_decision_id")` returning None for legacy
    pre-Phase-1 streams.
    """

    run_id: UUID
    reason: str
    occurred_at: datetime
    decided_by_decision_id: UUID | None = None


@dataclass(frozen=True)
class RunStopped:
    """A Run reached its controlled-exit terminal (Running | Held → Stopped).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Same shape as RunAborted's
    reason; same future-additive structured-taxonomy posture.

    Distinct from Aborted at the lifecycle layer (data validity
    semantics): Stopped data is valid up to the stop point;
    Aborted data is flagged as potentially invalid. PackML +
    Bluesky precedent (Stop = controlled deceleration / clean
    exit; Abort = emergency, prioritises speed over orderly
    shutdown).
    """

    run_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class RunReadingLogbookOpened:
    """A reading logbook was attached to this Run.

    Naming note: this event carries the entry-noun (`Reading`) in its
    name, vs. Conduit/Decision's bare `<Aggregate>LogbookOpened`. Why:
    Run is planned to host MULTIPLE logbook kinds (reading now;
    hazard events and operator-action audit are likely future
    additions), so the event name needs the entry-noun discriminator
    upfront. Conduit and Decision currently host one kind each and
    use the bare form; if either grows a second kind, they would
    follow the `<Aggregate><EntryNoun>LogbookOpened` skeleton then.
    Per [[project_logbook_entry_storage]] cross-BC family table.

    Lazy open-on-first-write: emitted by the `append_run_readings`
    handler the first time a reading is appended for this Run, NOT
    by `start_run` (mirrors Decision BC's 8c-b precedent for
    `DecisionLogbookOpened`). Subsequent appends find the logbook
    already attached and skip the open-event emission.

    `kind` discriminates the logbook category. Today only
    `LOGBOOK_KIND_READING` from state.py; future per-Run logbook
    kinds (hazard events, operator-action audit) would use distinct
    constants and distinct state fields, not additional values for
    `kind` here.

    `schema` declares the row shape of `entries_run_readings`,
    documenting the polymorphic `(channel_name, value, units?,
    sampling_procedure, sampled_at, occurred_at, recorded_at)` shape
    for downstream projections. Per
    [[project_logbook_entry_storage]], the schema lives on the event
    so projections can read entry shape uniformly without per-BC
    adapters. Discriminator values today: `baseline` (6f-5b, snapshot
    at run boundary) + `monitor` (6f-5c, sub-Hz time-series during
    the run); future-additive without schema migration.

    No `RunReadingLogbookClosed` event today: Run.status terminals
    (Completed | Aborted | Stopped | Truncated) are the implicit
    close signal; `append_run_readings` rejects writes when status is
    terminal via `RunReadingLogbookClosedError`. Audit fidelity is
    preserved: the open event timestamps the logbook lifecycle start;
    the terminal RunCompleted / RunAborted / etc. event timestamps
    the lifecycle end.
    """

    run_id: UUID
    logbook_id: UUID
    kind: str
    schema: LogbookSchema
    occurred_at: datetime


@dataclass(frozen=True)
class RunAdjusted:
    """A Run had its effective parameters steered mid-flight.

    Payload carries BOTH the patch (operator intent / audit) AND the
    post-merge `effective_parameters` snapshot (replay efficiency).
    Mirrors `RunStarted.effective_parameters` precedent: every event
    that updates the resolved parameter set carries the resolved set
    so projections / read endpoints do not have to fold prior
    RunAdjusted events to surface the current value.

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim. Mirrors RunAbortReason / RunStopReason /
    RunTruncateReason shape; same future-additive structured-taxonomy
    posture (the three documented re-evaluation triggers carry over).

    `adjusted_by` is the ActorId of the principal who issued the
    adjust command. Folded onto `Run.last_adjusted_by` paired with
    `last_adjusted_at` per the fold-symmetry rule
    ([[project_fold_symmetry_design]]). Threaded from the handler's
    `principal_id` parameter; never derived inside the decider.

    `decided_by_decision_id` (optional) is the domain-meaningful
    Decision-causation link to the Decision BC record that justified
    this adjustment. Maps to `prov:wasInformedBy` at the future PROV-O
    export adapter (same export contract used by `Decision.parent_id`).
    Distinct from the technical envelope `causation_id` (previous-
    message chain). The link is OPTIONAL: operators can record ad-hoc
    adjustments without a Decision; not every steering action needs
    formal justification at MVP. No existence check at decider per the
    cross-BC eventual-consistency stance (Trust.Conduit / Asset parent /
    Procedure target / Campaign lead_actor precedent). Forward-compat
    via `payload.get("decided_by_decision_id")` returning None for
    legacy / omitted entries.

    Source-state guard `{Running, Held}` applied at the decider. The
    Run identity / Subject / Plan / Method / Asset binding /
    `trigger_source` / `external_refs` / `campaign_id` are NOT touched
    by adjust: they remain the audit identity of the scientific
    activity. Operators wanting to change those force abort + restart
    per the design lock.
    """

    run_id: UUID
    parameters_patch: dict[str, Any]
    effective_parameters: dict[str, Any]
    reason: str
    adjusted_by: ActorId
    occurred_at: datetime
    decided_by_decision_id: UUID | None = None


@dataclass(frozen=True)
class RunTruncated:
    """A Run reached its partial-data terminal (Running | Held → Truncated).

    Cleanup terminal for a Run that became de-facto dead through
    interruption (power loss, process crash, hardware fault) and is
    being closed retroactively by an operator. The Run was already
    over before the operator could mark it; truncation captures
    that fact.

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Same shape and future-
    additive structured-taxonomy posture as RunStopped's reason.

    `interrupted_at` is the operator's best guess at when the
    actual interruption occurred (None when unknown). Distinct from
    `occurred_at`, which is when the truncate command was
    processed. The two timestamps can be hours or days apart for
    weekend / overnight interruptions; the explicit field saves
    auditors from parsing the free-text reason for a date.

    Stopped vs Truncated (lifecycle-layer distinction): Stopped
    is a controlled exit while the system is responsive; Truncated
    is a cleanup mechanism for known-dead Runs. The system itself
    does not detect de-facto-dead Runs (separate liveness concern,
    out of scope for 6f-4); operators must invoke truncate
    explicitly.
    """

    run_id: UUID
    reason: str
    interrupted_at: datetime | None
    occurred_at: datetime


# Discriminated union of every event the Run aggregate emits.
RunEvent = (
    RunStarted
    | RunHeld
    | RunResumed
    | RunCompleted
    | RunAborted
    | RunStopped
    | RunTruncated
    | RunAdjusted
    | RunReadingLogbookOpened
    | RunAddedToCampaign
    | RunRemovedFromCampaign
    | DecisionDebriefRequested
)


def event_type_name(event: RunEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: RunEvent) -> dict[str, Any]:
    """Serialize a Run event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings. `subject_id` serializes as null when None (dark-field /
    calibration runs).
    """
    match event:
        case RunStarted(
            run_id=run_id,
            name=name,
            plan_id=plan_id,
            subject_id=subject_id,
            raid=raid,
            override_parameters=override_parameters,
            effective_parameters=effective_parameters,
            trigger_source=trigger_source,
            external_refs=external_refs,
            acknowledged_cautions=acknowledged_cautions,
            campaign_id=campaign_id,
            decided_by_decision_id=decided_by_decision_id,
            pinned_calibration_ids=pinned_calibration_ids,
            occurred_at=occurred_at,
        ):
            return {
                "run_id": str(run_id),
                "name": name,
                "plan_id": str(plan_id),
                "subject_id": str(subject_id) if subject_id is not None else None,
                "raid": raid,
                "override_parameters": override_parameters,
                "effective_parameters": effective_parameters,
                "trigger_source": trigger_source,
                "external_refs": list(external_refs),
                "acknowledged_cautions": [
                    {
                        "caution_id": str(ack.caution_id),
                        "target_kind": ack.target_kind,
                        "target_id": str(ack.target_id),
                        "category": ack.category,
                        "severity": ack.severity,
                        "text_excerpt": ack.text_excerpt,
                        "workaround_excerpt": ack.workaround_excerpt,
                    }
                    for ack in acknowledged_cautions
                ],
                "campaign_id": str(campaign_id) if campaign_id is not None else None,
                "decided_by_decision_id": (
                    str(decided_by_decision_id) if decided_by_decision_id is not None else None
                ),
                # CalibrationRevision ids sorted lexicographically for
                # deterministic byte ordering (the typed in-memory shape is
                # frozenset; the wire shape is a sorted list for stable bytes).
                "pinned_calibration_ids": sorted(str(pin) for pin in pinned_calibration_ids),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunHeld(run_id=run_id, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunResumed(run_id=run_id, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunCompleted(run_id=run_id, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunAborted(
            run_id=run_id,
            reason=reason,
            decided_by_decision_id=decided_by_decision_id,
            occurred_at=occurred_at,
        ):
            return {
                "run_id": str(run_id),
                "reason": reason,
                "decided_by_decision_id": (
                    str(decided_by_decision_id) if decided_by_decision_id is not None else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunStopped(run_id=run_id, reason=reason, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case RunTruncated(
            run_id=run_id,
            reason=reason,
            interrupted_at=interrupted_at,
            occurred_at=occurred_at,
        ):
            interrupted_at_iso = interrupted_at.isoformat() if interrupted_at is not None else None
            return {
                "run_id": str(run_id),
                "reason": reason,
                "interrupted_at": interrupted_at_iso,
                "occurred_at": occurred_at.isoformat(),
            }
        case RunAdjusted(
            run_id=run_id,
            parameters_patch=parameters_patch,
            effective_parameters=effective_parameters,
            reason=reason,
            adjusted_by=adjusted_by,
            decided_by_decision_id=decided_by_decision_id,
            occurred_at=occurred_at,
        ):
            return {
                "run_id": str(run_id),
                "parameters_patch": parameters_patch,
                "effective_parameters": effective_parameters,
                "reason": reason,
                "adjusted_by": str(adjusted_by),
                "decided_by_decision_id": (
                    str(decided_by_decision_id) if decided_by_decision_id is not None else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunReadingLogbookOpened(
            run_id=run_id,
            logbook_id=logbook_id,
            kind=kind,
            schema=schema,
            occurred_at=occurred_at,
        ):
            return {
                "run_id": str(run_id),
                "logbook_id": str(logbook_id),
                "kind": kind,
                "schema": schema.to_dict(),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunAddedToCampaign(
            run_id=run_id,
            campaign_id=campaign_id,
            occurred_at=occurred_at,
        ):
            return {
                "run_id": str(run_id),
                "campaign_id": str(campaign_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunRemovedFromCampaign(
            run_id=run_id,
            campaign_id=campaign_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "run_id": str(run_id),
                "campaign_id": str(campaign_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case DecisionDebriefRequested(
            run_id=run_id,
            debriefer_agent_id=debriefer_agent_id,
            terminal_event_id=terminal_event_id,
            occurred_at=occurred_at,
        ):
            return {
                "run_id": str(run_id),
                "debriefer_agent_id": str(debriefer_agent_id),
                "terminal_event_id": str(terminal_event_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> RunEvent:
    """Rebuild a Run event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "RunStarted":

            def _build_run_started() -> RunStarted:
                raw_subject = payload["subject_id"]
                # Forward-compat additive evolution: `raid`,
                # `override_parameters` / `effective_parameters` /
                # `trigger_source`, `external_refs`,
                # `acknowledged_cautions`, `campaign_id`,
                # `decided_by_decision_id` (Decision-to-Run linkage),
                # `pinned_calibration_ids` (Calibration AsShot anchor)
                # were all added additively. Each .get(...) returns
                # the field's default when the key isn't in the jsonb
                # payload, so legacy streams replay without an upcaster.
                raw_campaign_id = payload.get("campaign_id")
                raw_decided_by = payload.get("decided_by_decision_id")
                return RunStarted(
                    run_id=UUID(payload["run_id"]),
                    name=payload["name"],
                    plan_id=UUID(payload["plan_id"]),
                    subject_id=UUID(raw_subject) if raw_subject is not None else None,
                    raid=payload.get("raid"),
                    override_parameters=payload.get("override_parameters", {}),
                    effective_parameters=payload.get("effective_parameters", {}),
                    trigger_source=payload.get("trigger_source"),
                    external_refs=tuple(payload.get("external_refs", [])),
                    acknowledged_cautions=tuple(
                        CautionAcknowledgement(
                            caution_id=UUID(ack["caution_id"]),
                            target_kind=ack["target_kind"],
                            target_id=UUID(ack["target_id"]),
                            category=ack["category"],
                            severity=ack["severity"],
                            text_excerpt=ack["text_excerpt"],
                            workaround_excerpt=ack["workaround_excerpt"],
                        )
                        for ack in payload.get("acknowledged_cautions", [])
                    ),
                    campaign_id=UUID(raw_campaign_id) if raw_campaign_id is not None else None,
                    decided_by_decision_id=UUID(raw_decided_by)
                    if raw_decided_by is not None
                    else None,
                    pinned_calibration_ids=tuple(
                        UUID(p) for p in payload.get("pinned_calibration_ids", [])
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("RunStarted", _build_run_started)
        case "RunHeld":
            return deserialize_or_raise(
                "RunHeld",
                lambda: RunHeld(
                    run_id=UUID(payload["run_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RunResumed":
            return deserialize_or_raise(
                "RunResumed",
                lambda: RunResumed(
                    run_id=UUID(payload["run_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RunCompleted":
            return deserialize_or_raise(
                "RunCompleted",
                lambda: RunCompleted(
                    run_id=UUID(payload["run_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RunAborted":

            def _build_run_aborted() -> RunAborted:
                # `decided_by_decision_id` optional. Forward-compat
                # additive evolution: pre-existing streams replay without the
                # key via `.get(..., None)`.
                raw_decided_by_abort = payload.get("decided_by_decision_id")
                return RunAborted(
                    run_id=UUID(payload["run_id"]),
                    reason=payload["reason"],
                    decided_by_decision_id=(
                        UUID(raw_decided_by_abort) if raw_decided_by_abort is not None else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("RunAborted", _build_run_aborted)
        case "RunStopped":
            return deserialize_or_raise(
                "RunStopped",
                lambda: RunStopped(
                    run_id=UUID(payload["run_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RunTruncated":

            def _build_run_truncated() -> RunTruncated:
                raw_interrupted_at = payload["interrupted_at"]
                return RunTruncated(
                    run_id=UUID(payload["run_id"]),
                    reason=payload["reason"],
                    interrupted_at=(
                        datetime.fromisoformat(raw_interrupted_at)
                        if raw_interrupted_at is not None
                        else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("RunTruncated", _build_run_truncated)
        case "RunAdjusted":

            def _build_run_adjusted() -> RunAdjusted:
                # `decided_by_decision_id` is optional on the
                # event payload. Forward-compat additive: synthetic / future
                # callers omitting the key (None semantically) deserialize
                # as decided_by_decision_id=None. `parameters_patch` and
                # `effective_parameters` are always carried (never optional).
                # `adjusted_by` is REQUIRED per the fold-symmetry rule
                # (pre-pilot rename; legacy streams pre-date the field but
                # dev DBs are wiped on migration run).
                raw_decision_id = payload.get("decided_by_decision_id")
                return RunAdjusted(
                    run_id=UUID(payload["run_id"]),
                    parameters_patch=payload["parameters_patch"],
                    effective_parameters=payload["effective_parameters"],
                    reason=payload["reason"],
                    adjusted_by=ActorId(UUID(payload["adjusted_by"])),
                    decided_by_decision_id=(
                        UUID(raw_decision_id) if raw_decision_id is not None else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("RunAdjusted", _build_run_adjusted)
        case "RunReadingLogbookOpened":
            return deserialize_or_raise(
                "RunReadingLogbookOpened",
                lambda: RunReadingLogbookOpened(
                    run_id=UUID(payload["run_id"]),
                    logbook_id=UUID(payload["logbook_id"]),
                    kind=payload["kind"],
                    schema=LogbookSchema.from_dict(payload["schema"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RunAddedToCampaign":
            return deserialize_or_raise(
                "RunAddedToCampaign",
                lambda: RunAddedToCampaign(
                    run_id=UUID(payload["run_id"]),
                    campaign_id=UUID(payload["campaign_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RunRemovedFromCampaign":
            return deserialize_or_raise(
                "RunRemovedFromCampaign",
                lambda: RunRemovedFromCampaign(
                    run_id=UUID(payload["run_id"]),
                    campaign_id=UUID(payload["campaign_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "DecisionDebriefRequested":
            return deserialize_or_raise(
                "DecisionDebriefRequested",
                lambda: DecisionDebriefRequested(
                    run_id=UUID(payload["run_id"]),
                    debriefer_agent_id=UUID(payload["debriefer_agent_id"]),
                    terminal_event_id=UUID(payload["terminal_event_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown RunEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "CautionAcknowledgement",
    "DecisionDebriefRequested",
    "RunAborted",
    "RunAddedToCampaign",
    "RunAdjusted",
    "RunCompleted",
    "RunEvent",
    "RunHeld",
    "RunReadingLogbookOpened",
    "RunRemovedFromCampaign",
    "RunResumed",
    "RunStarted",
    "RunStopped",
    "RunTruncated",
    "event_type_name",
    "from_stored",
    "to_payload",
]
