"""The `StartRun` command — intent dataclass for this slice.

Carries the caller-controlled inputs:
  - `name` — display name for the new Run (for example "32-ID
    FlyScan morning session" or "Dark field calibration 2026-05-11")
  - `plan_id` — the Plan being executed (eventual-consistency ref;
    existence verified at handler-load time)
  - `subject_id` — the Subject being measured, or None for
    calibration / dark-field runs
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
