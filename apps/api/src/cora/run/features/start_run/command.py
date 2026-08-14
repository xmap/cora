"""The `StartRun` command — intent dataclass for this slice.

Carries the caller-controlled inputs:
  - `name` — display name for the new Run (for example "32-ID
    FlyScan morning session" or "Dark field calibration 2026-05-11")
  - `plan_id` — the Plan being executed (eventual-consistency ref;
    existence verified at handler-load time)
  - `subject_id` — the Subject being measured, or None for
    calibration / dark-field runs
  - `conduct_mode`: who drove this act, CORA's own Conductor
    (`Conducted`) or an external tool CORA only observes
    (`Recorded`). Defaults to `Conducted`, true of every caller
    today; see the field's own comment for the RECORDED-mode plan.
  - `raid` — Research Activity Identifier (ISO 23527) of the
    research activity this Run belongs to. Optional; opaque string
    carried verbatim. RAiD is project/activity scoped: one RAiD is
    shared across the many Runs of an activity, never minted per Run
    (the per-run identity is the Run id). Supports cross-facility
    provenance export (DataCite / RAiD ecosystem); legacy Runs have
    raid=None and stay valid via the forward-compatible payload load.
  - `override_parameters` — operator-supplied overrides on top of
    `Plan.default_parameters`. Applied via RFC 7396 merge by the
    handler before the decider validates against the owning Method's
    `parameters_schema`. Default `{}`.
  - `trigger_source`: operator-supplied free text capturing what
    initiated this Run (operator-manual, scheduler, prior-run,
    automation). Optional. Future Decision-BC integration may
    populate this.

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports.

Status is implicit at start (`Running`) and not part of the
command — see Run aggregate's `state.py` docstring for the
enum-in-state, derived-from-event-type-in-evolver convention.

The handler additionally pre-loads Plan + Subject (if given) +
each bound Asset (from `plan.asset_ids`) to build a
`RunStartContext` for the decider (gate-review Q2 / Q5 pattern),
AND resolves the Method's parameters_schema for 6g-c validation.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from cora.run.aggregates.run.state import ConductMode
from cora.shared.identifier import Identifier


@dataclass(frozen=True)
class StartRun:
    """Start a new Run: bind a Plan + (optional) Subject.

    Optional `external_refs` (anti-corruption refs to
    upstream-deferred concepts like proposal / btr / lab_visit /
    session). Forward-compat additive field; legacy callers omitting
    it get an empty frozenset.

    Optional `campaign_id`: when supplied, the handler pre-loads
    the Campaign, the decider verifies it's in `{Planned,
    Active, Held}` (else `RunCannotJoinCampaignError`), and the
    cross-aggregate atomic write via `EventStore.append_streams`
    persists `RunStarted` (carrying `campaign_id` on its payload) on
    the Run stream AND `CampaignRunAdded` on the Campaign stream.
    When omitted, behaviour is unchanged (single-stream Run write).
    """

    name: str
    plan_id: UUID
    subject_id: UUID | None
    # who drove this act: CORA's own Conductor, or an external tool CORA
    # only observes. Defaults to CONDUCTED: the only production caller
    # today (`cora.api._run_initiator`) is always Conducted, so the
    # default declares the closed, currently-total set of reality rather
    # than guessing a live signal. A future RECORDED-mode genesis (the
    # not-yet-built shadow-to-real promotion, see `cora.api._run_watcher`)
    # is new code passing this explicitly, never an old caller inheriting
    # the default silently. See `ConductMode`'s own docstring.
    conduct_mode: ConductMode = ConductMode.CONDUCTED
    raid: str | None = None
    override_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    trigger_source: str | None = None
    external_refs: frozenset[Identifier] = field(default_factory=frozenset[Identifier])
    campaign_id: UUID | None = None
    # Decision→Run linkage: optional Decision-causation link
    # mirroring `AdjustRun.decided_by_decision_id`. Lets the operator
    # link a Run's start to the Decision BC record that justified it
    # (most commonly a cross-Plan operator pivot — EnergyChange,
    # PivotToHighResolution, etc.). Operators can start ad-hoc Runs
    # without a Decision; not every start needs formal justification.
    # NO existence check at the decider per the cross-BC eventual-
    # consistency stance (Trust.Conduit / Asset parent / Procedure
    # target / Campaign lead_actor / Run.subject_id precedent).
    decided_by_decision_id: UUID | None = None
    # Calibration AsShot anchor: set of CalibrationRevision
    # ids that should be recorded as live at this Run's start per
    # [[project_calibration_design]]. Operator-supplied (or, in the
    # autonomous-CT future, agent-supplied). IMMUTABLE on the Run
    # aggregate after start_run — every transition arm preserves the
    # field verbatim per the DNG AsShot precedent. NO cross-BC
    # existence check at the decider (cross-BC eventual-consistency
    # stance); a downstream consumer that needs to read the pinned
    # CalibrationRevision still goes through the Calibration BC.
    pinned_calibration_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    # input Dataset references (PROV `used`): the set of
    # Dataset ids a reconstruction Run consumes. Each reference targets
    # the Dataset, not a Distribution. Operator-supplied (or, in the
    # autonomous-CT future, agent-supplied). IMMUTABLE on the Run
    # aggregate after start_run, like pinned_calibration_ids. NO cross-
    # BC existence check at the decider (cross-BC eventual-consistency
    # stance); the start_run gate that reads each input Dataset's
    # Verified Distribution goes through the Data BC.
    input_dataset_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    # names the compute resource the reconstruction will run on
    # (for example a remote resource like ALCF Polaris that can only read
    # certain Storage tiers). Bare string carried verbatim. NO cross-BC
    # existence check at the decider (same eventual-consistency stance as
    # input_dataset_ids); the composition root resolves it against
    # deployment config to the set of Storage tiers that resource can
    # read, and the start_run gate then requires each input's Verified
    # Distribution to sit on a reachable tier. None means no remote-compute
    # target is declared, so the reachability check is skipped (the gate
    # stays present-and-Verified only). Consumed only by the gate, not
    # persisted on RunStarted (mirrors the beam reading).
    compute_resource_code: str | None = None
