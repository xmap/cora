"""Decision aggregate state, value objects, and domain errors.

`Decision` is the structured-audit record for every consequential
choice in CORA: human approval, AI inference, agent action,
operator override. The aggregate is unified across deciders, so
the same shape captures human approvers and LLM inferences alike.
Distinguishing AI from human deciders today happens at the
projection layer (the Decision is a record, not a typed sum); a
future Actor.role discriminator (deferred-with-trigger: first
audit-policy demanding role-based filtering) will let consumers
type-narrow at query time. Optional `parent_id` chains carry the
AI-recommends-then-human-overrides flow.

## What a Decision is NOT

  - Not a Run / Subject / Dataset event. Decisions are the WHY
    behind a state change; the state change itself lives on the
    target aggregate's stream.
  - Not a free-form audit log. Reasoning text is captured but
    `rule` + `confidence_source` + `override_kind` etc.
    keep the structure scannable.
  - Not a place for token-by-token AI traces. Those go to a
    `reasoning` logbook on the Decision aggregate (cross-BC
    precedent; carries OpenTelemetry `gen_ai.*` semantic-
    convention attributes).


Genesis aggregate: id + decided_by + context + choice + reasoning +
confidence + confidence_source + parent_id + rule +
inputs + alternatives + override_kind + reasoning_signature
+ occurred_at. Single event (DecisionRegistered); read side; REST +
MCP. Cross-aggregate validation in the handler (Actor exists; if
parent_id set, parent Decision exists).

## Standards alignment (gate-review locks; 2026 survey + validation pass)

  - **PROV-AGENT (eScience 2025)**: field naming aligns with
    `prov:wasAssociatedWith.agent` (`decided_by`),
    `prov:wasInformedBy` (`parent_id`), `prov:atTime`
    (`occurred_at`). PROV-O export at API boundaries lands when
    first consumer asks; in-domain stays on these primitives.
  - **NIST AI RMF + ISO/IEC 42001 + EU AI Act Article 12**: event
    sourcing on INSERT-only Postgres satisfies the automatic
    immutable record-keeping mandate for free.
  - **ISO 17025 Clause 7.1.3**: `rule` field carries the
    documented rule; `inputs` carries the measured value
    + uncertainty that fed the rule (per ILAC-G8:09/2019).
  - **OPA Decision Logs**: the `PolicyGrant` context's payload is
    isomorphic to OPA's `{decision_id, input, result, timestamp,
    metrics}` shape (`alternatives` carries the determining
    policy IDs for that context, Cedar-style).
  - **Anthropic extended thinking signature pattern**:
    `reasoning_signature` is an optional opaque blob (typically
    sha256 of the full reasoning trace, or a vendor-supplied
    encrypted summary) for tamper-evidence beyond the row-level
    INSERT-only guarantee.

## `decided_by` vs envelope `principal_id`

These are distinct fields with overlapping but non-identical
semantics. They will TYPICALLY hold the same UUID but can
legitimately differ:

  - `Decision.decided_by` is the WHO of the decision: the human or
    AI that made the choice. PROV-O `prov:wasAssociatedWith.agent`.
    Lives on the Decision aggregate's state and is captured in the
    DecisionRegistered event payload.
  - `events.principal_id` (envelope-level ReBAC hook) is the WHO of
    the COMMAND: the authenticated caller that triggered the
    register_decision command. Lives on the persistence envelope,
    independent of payload.

Today they're always the same UUID (the Actor that made the
decision is the same Actor whose credentials called the API).
Future cases where they differ:

  - Admin records a decision made by another Actor (audit-policy
    feature; admin's principal_id, decided-by Actor's decided_by).
  - Saga emits register_decision on behalf of an originating
    principal (saga's machine principal_id, original-decider's
    decided_by).

Convention when sagas land: the saga passes-through the
originating principal_id to downstream commands; the saga's own
identity goes in event metadata, not the principal_id field.
See [[project_authz_future]] for the saga-propagation pattern.

## Aggregate is atomic-immutable; chains carry corrections

Decisions' decision facts are append-only and never updated in
place. Corrections, exceptions, appeals, supersessions, and
invalidations land as NEW Decisions with `parent_id` pointing at
the original and `override_kind` explaining the transition. The
"current" Decision in a chain is the latest entry; consumers use
the `latest-in-chain
wins` projection rule (documented in this BC's `__init__.py`).

See `Decision.ratings` for the additive operator-rating annotation
channel; rating accrual does NOT change decision
facts and is folded latest-per-actor wins into the aggregate
state. The atomic-immutability stance applies to the choice /
reasoning / confidence / inputs fields; ratings are an
orthogonal additive annotation.

## Thirteenth bounded-name VO

`DecisionChoice` and the `Decision.reasoning` field use the shared
`validate_bounded_text` helper hoisted at the rule-of-three trigger, with a higher max-length
cap (reasoning text is naturally longer than display names).
`DecisionContext` is intentionally an open string with documented
well-known constants, new contexts arrive without schema
migration.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal
from uuid import UUID

from cora.shared.bounded_text import validate_bounded_text
from cora.shared.identity import ActorId

DECISION_CHOICE_MAX_LENGTH = 500
DECISION_REASONING_MAX_LENGTH = 5000
DECISION_CONTEXT_MAX_LENGTH = 100
DECISION_RULE_MAX_LENGTH = 500
DECISION_ALTERNATIVES_MAX_ENTRIES = 32
DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH = 500
DECISION_INPUTS_MAX_ENTRIES = 64
DECISION_INPUTS_KEY_MAX_LENGTH = 100
DECISION_REASONING_SIGNATURE_MAX_LENGTH = 4096

# Confidence-band boundaries (8b derived field). Stored confidence
# is a float in [0, 1]; the derived band is a UX/triage layer
# computed at read time. Boundaries match the 2025-2026 LLM
# calibration literature: ECE <0.05 = "well-calibrated", and
# >=0.95 / <=0.05 is the high-stakes auto-accept/auto-reject
# threshold cited across KDD 2025 + JMIR 2025 + MICCAI 2025. The
# band is never stored (one source of truth = the float).
CONFIDENCE_BAND_MEDIUM_MIN = 0.3
CONFIDENCE_BAND_HIGH_MIN = 0.7
CONFIDENCE_BAND_CERTAIN_MIN = 0.95

# Logbook kind for AI-decider reasoning traces (8c). When an AI
# decider produces a Decision, the producer opens a logbook of
# this kind on the Decision aggregate and appends per-trace
# entries (one per LLM call / tool invocation / agent span)
# carrying OpenTelemetry GenAI semantic-convention attributes
# (gen_ai.*). Mirrors `LOGBOOK_KIND_VERDICT` in Conduit BC
# (6f-5a precedent).
LOGBOOK_KIND_INFERENCE: Final = "inference"

# Well-known context discriminators per BC map. Open-ended: new
# contexts arrive without schema migration. Validated at
# projection time, not at write time.
DECISION_CONTEXT_RECIPE_APPROVAL = "RecipeApproval"
DECISION_CONTEXT_RUN_ABORT = "RunAbort"
DECISION_CONTEXT_RUN_STOP = "RunStop"
DECISION_CONTEXT_RUN_TRUNCATE = "RunTruncate"
DECISION_CONTEXT_RESOURCE_ALLOCATION = "ResourceAllocation"
DECISION_CONTEXT_POLICY_GRANT = "PolicyGrant"
DECISION_CONTEXT_PROCEDURE_EXECUTION = "ProcedureExecution"
DECISION_CONTEXT_DATASET_DISCARD = "DatasetDiscard"
# RunDebriefer agent writes one Decision per terminal Run
# event. Open-ended convention; the choice value lives in the
# `RunDebriefChoice` Literal below.
DECISION_CONTEXT_RUN_DEBRIEF = "RunDebrief"


# Closed `choice` value set for `context = "RunDebrief"` Decisions.
# Projection-validated, not domain-enforced (the open-string
# `DecisionContext` + `DecisionChoice` shape is preserved so future
# agent kinds can add their own choice vocabularies without churn).
# `DebriefDeferred` is the audit-fallback value emitted by the
# subscriber when the LLM call fails after 3 retries; preserves the
# exactly-one-Decision-per-terminal-Run audit invariant.
# `DebriefConflicted` is the audit-only value emitted by a losing
# agent when it lost the cross-agent lease race on the Run stream
# (per [[project-run-debriefer-lease-design]]). The losing agent
# writes the Decision on its own Decision stream citing the winning
# `debriefer_agent_id` so concurrent-debrief races stay visible in
# the Decision projection without polluting the Run stream further.
RunDebriefChoice = Literal[
    "NominalCompletion",
    "DegradedCompletion",
    "OperatorAbort",
    "EquipmentAbort",
    "DataSuspect",
    "DebriefDeferred",
    "DebriefConflicted",
]
RUN_DEBRIEF_CHOICES: Final = frozenset(
    {
        "NominalCompletion",
        "DegradedCompletion",
        "OperatorAbort",
        "EquipmentAbort",
        "DataSuspect",
        "DebriefDeferred",
        "DebriefConflicted",
    }
)


# CautionDrafter agent writes one Decision per
# terminal Run event proposing (or refusing to propose) a Caution.
# Open-ended convention identical to `DECISION_CONTEXT_RUN_DEBRIEF`;
# the closed choice vocabulary lives in the `CautionProposalChoice`
# Literal below. See [[project-caution-drafter-design]] for the full
# grounding.
DECISION_CONTEXT_CAUTION_PROPOSAL = "CautionProposal"


# Closed `choice` value set for `context = "CautionProposal"` Decisions.
# Five values:
#
#   - `NoAction`         -- Run signals do NOT warrant a Caution.
#                           Target 65-75% of all proposals (Epic Sepsis
#                           refuse-aggressively lesson). Audit-only
#                           outcome: Decision still written for
#                           telemetry + future-training signal.
#   - `ProposeNotice`    -- Awareness-only Caution; no required next
#                           operator step. FDA CDS Criterion 3
#                           "contextually relevant reference information."
#                           Tier-quota target <= 80% of non-NoAction.
#   - `ProposeCaution`   -- Operator should adjust HOW they execute
#                           the next Plan. FDA "matching reference
#                           guidelines." Tier-quota target <= 15%.
#   - `ProposeWarning`   -- Potential harm or expensive loss if
#                           ignored. Bound by FDA's device line
#                           (always advisory, never directive).
#                           Tier-quota target <= 5%.
#   - `ProposeSupersede` -- Matches an existing Active Caution on
#                           the same target; propose superseding with
#                           refined narrative. Counts in the tier
#                           quota at the severity of the proposed
#                           superseding Caution.
#
# Quota is telemetry-only today (per design lock Anti-hook #12;
# Epic Sepsis lesson: don't enforce a rate you haven't measured
# baselines for).
CautionProposalChoice = Literal[
    "NoAction",
    "ProposeNotice",
    "ProposeCaution",
    "ProposeWarning",
    "ProposeSupersede",
]
CAUTION_PROPOSAL_CHOICES: Final = frozenset(
    {
        "NoAction",
        "ProposeNotice",
        "ProposeCaution",
        "ProposeWarning",
        "ProposeSupersede",
        # Audit-only value emitted by a losing CautionDrafter agent
        # when it lost the cross-agent lease race on the Run stream
        # (per [[project-run-debriefer-lease-design]]). Parallel to
        # RUN_DEBRIEF_CHOICES.DebriefConflicted. The losing agent
        # writes the Decision on its own Decision stream citing the
        # winning `caution_drafter_agent_id` so concurrent-debrief
        # races stay visible in the Decision projection without
        # polluting the Run stream further.
        "CautionDraftConflicted",
    }
)


# Operator-authored Decision emitted when dismissing a poison event
# from a Reaction's subscriber bookmark. The Decision is the audit
# record of the dismissal; the `dismiss_event_in_reaction` slice
# atomically pairs it with a `projection_bookmarks` advance so the
# operator action is recorded in the same place as every other
# operator judgment call. Open-ended convention identical to the
# RunDebrief / CautionProposal patterns above.
DECISION_CONTEXT_REACTION_DISMISSAL = "ReactionDismissal"


# Closed `choice` value set for `context = "ReactionDismissal"`
# Decisions. Single value today (the slice is purely "operator
# acknowledged this event is poison and advances the bookmark past
# it"); the Literal exists for symmetry with RunDebriefChoice /
# CautionProposalChoice and so a future "OperatorReplayed" or
# "OperatorQuarantined" choice can land additively without breaking
# downstream parsers.
ReactionDismissalChoice = Literal["EventDismissed"]
REACTION_DISMISSAL_CHOICES: Final = frozenset({"EventDismissed"})


# RunSupervisor agent writes one Decision per supervision disposition on
# an in-flight Run. Open-ended convention identical to RunDebrief /
# CautionProposal; the closed choice vocabulary lives in the
# `RunSupervisionChoice` Literal below. See
# [[project-run-supervisor-design]] for the full grounding.
DECISION_CONTEXT_RUN_SUPERVISION = "RunSupervision"


# Closed `choice` value set for `context = "RunSupervision"` Decisions.
# Projection-validated, not domain-enforced (the open-string
# `DecisionContext` + `DecisionChoice` shape is preserved). Ten values:
# five beam-Hold/Resume + two audit-fallback + three advise-rung
# observe->advise dispositions (Quieted / Stalled / Breached), the last
# three Decision-only (one per breach edge, never a command).
#
#   - `Continue`              -- no wind-down trigger met; no command
#                               issued (the NoAction-bias default).
#   - `Hold`                  -- issues HoldRun (pause, resumable).
#   - `Resume`                -- issues ResumeRun (the gated wind-up: only
#                               for a Run the supervisor itself held, only
#                               when the full start-safety envelope is good
#                               again; mirror of Hold).
#   - `Stop`                  -- issues StopRun (controlled early exit).
#   - `Abort`                 -- issues AbortRun (data-unusable exit).
#   - `SupervisionDeferred`   -- audit-fallback: signal stale / absent /
#                               unevaluable, OR a state race made the
#                               command a no-op; no wind-down taken.
#                               Qualified with the agent work-noun
#                               (parallel to DebriefDeferred) so it does
#                               not collide in the shared, globally-
#                               filtered DecisionChoice projection.
#   - `SupervisionConflicted` -- audit-only: lost the per-Run lease race
#                               to another supervisor evaluator (parallel
#                               to DebriefConflicted / CautionDraftConflicted).
#   - `SupervisionQuieted`    -- advise-rung: the run-age run-liveness
#                               backstop fired (a Run has been Running
#                               implausibly long). Decision-only, no command.
#   - `SupervisionStalled`    -- advise-rung: a live observation channel's
#                               arrivals stopped (Rule R rate-dropout) while
#                               beam up + feeder alive. Decision-only.
#   - `SupervisionBreached`   -- advise-rung: a quality channel's latest
#                               value crossed below the operator-set limit
#                               (Rule Q). Decision-only. (Named by naming-r3:
#                               the limit was breached, an objective edge,
#                               not the supervisor's epistemic state.)
RunSupervisionChoice = Literal[
    "Continue",
    "Hold",
    "Resume",
    "Stop",
    "Abort",
    "SupervisionDeferred",
    "SupervisionConflicted",
    "SupervisionQuieted",
    "SupervisionStalled",
    "SupervisionBreached",
]
RUN_SUPERVISION_CHOICES: Final = frozenset(
    {
        "Continue",
        "Hold",
        "Resume",
        "Stop",
        "Abort",
        "SupervisionDeferred",
        "SupervisionConflicted",
        "SupervisionQuieted",
        "SupervisionStalled",
        "SupervisionBreached",
    }
)


# CautionPromoter agent writes one Decision per CautionProposal it
# evaluates. Open-ended convention identical to CautionProposal; the
# closed choice vocabulary lives in the `CautionPromotionChoice` Literal
# below. See [[project-caution-promoter-design]] for the full grounding.
DECISION_CONTEXT_CAUTION_PROMOTION = "CautionPromotion"


# Closed `choice` value set for `context = "CautionPromotion"` Decisions.
# Projection-validated, not domain-enforced. Three values:
#
#   - `Promote`              -- the proposal met the auto-promote gate; a
#                              live Caution was registered.
#   - `PromotionDeferred`    -- gate not met (severity above Notice, low
#                              confidence, invalid target, or a Notice the
#                              operator already retired). Carries the
#                              Promotion work-noun (parallel to
#                              SupervisionDeferred / DebriefDeferred) so it
#                              does not collide in the shared, globally-
#                              filtered DecisionChoice projection.
#   - `PromotionConflicted`  -- an active Caution already covers the target;
#                              no duplicate registered.
CautionPromotionChoice = Literal[
    "Promote",
    "PromotionDeferred",
    "PromotionConflicted",
]
CAUTION_PROMOTION_CHOICES: Final = frozenset(
    {
        "Promote",
        "PromotionDeferred",
        "PromotionConflicted",
    }
)


# ClearanceExpirer agent writes one Decision per safety Clearance it
# auto-expires. Open-ended convention identical to RunSupervision /
# CautionPromotion; the closed choice vocabulary lives in the
# `ClearanceExpiryChoice` Literal below. The agent is purely positive: it
# records a Decision only when it expires a clearance (a not-yet-elapsed
# clearance is simply not selected, so there is no Deferred/Conflicted
# disposition). The context noun is `ClearanceExpiry` (abstract
# action-noun, family-clean with RunSupervision / CautionPromotion); the
# agent kind is `ClearanceExpirer` (the doer) -- a deliberate Expiry-vs-
# Expirer asymmetry across the context-naming and R5 doer axes, not drift.
# See [[project-clearance-window-expirer-design]] for the full grounding.
DECISION_CONTEXT_CLEARANCE_EXPIRY = "ClearanceExpiry"


# Closed `choice` value set for `context = "ClearanceExpiry"` Decisions.
# Projection-validated, not domain-enforced. Single value today (the agent
# only ever acts to expire); the Literal exists for symmetry with the
# sibling agent choices and so a future qualified disposition can land
# additively. `Expire` is unique in the shared, globally-filtered
# DecisionChoice projection column.
ClearanceExpiryChoice = Literal["Expire"]
CLEARANCE_EXPIRY_CHOICES: Final = frozenset({"Expire"})


# ClearanceWatcher agent writes one Decision per stalled front-of-lifecycle
# Clearance it surfaces. Open-ended convention identical to ClearanceExpiry /
# RunSupervision; the closed choice vocabulary lives in the
# `ClearanceProgressChoice` Literal below. The agent is FLAG-ONLY: it records a
# Decision only when it surfaces a stalled clearance (one per stall episode) and
# issues NO command. The context noun is `ClearanceProgress` (abstract
# action-noun, family-clean with ClearanceExpiry / CautionPromotion); the agent
# kind is `ClearanceWatcher` (the doer) -- a deliberate Progress-vs-Watcher
# asymmetry across the context-naming and R5 doer axes, not drift. See
# [[project-clearance-watcher-design]] for the full grounding.
DECISION_CONTEXT_CLEARANCE_PROGRESS = "ClearanceProgress"


# Closed `choice` value set for `context = "ClearanceProgress"` Decisions.
# Projection-validated, not domain-enforced. Single value today (the agent only
# ever flags); the Literal exists for symmetry with the sibling agent choices
# and so a future qualified disposition can land additively. `Flag` is unique in
# the shared, globally-filtered DecisionChoice projection column.
ClearanceProgressChoice = Literal["Flag"]
CLEARANCE_PROGRESS_CHOICES: Final = frozenset({"Flag"})


# acceptance-signal capture: closed 3-value rating set on
# the new `DecisionRated` event. `useful` and `misleading` are
# operator-affirmative; `ignored` is a positive marker ("operator saw
# it and chose not to act"), distinct from no-rating ("never seen").
# Latest-per-actor wins in the projection; audit trail keeps all
# ratings. See [[project-run-debrief-design]] Locks for the
# `ConfidenceCalibrator` adoption trigger that consumes the (rating,
# context, confidence_at_rating) corpus this event accrues.
class DecisionRating(StrEnum):
    """How an operator rates a Decision after the fact."""

    USEFUL = "useful"
    MISLEADING = "misleading"
    IGNORED = "ignored"


DECISION_RATING_COMMENT_MAX_LENGTH = 2000


class DecisionConfidenceSource(StrEnum):
    """How the `confidence` value was computed.

    ISO 42001 audit asks 'how was this confidence derived?'; this
    enum is the answer. Stored alongside the float so consumers can
    distinguish calibrated probabilistic estimates from
    self-reported model claims.

    Values:
      - `self_reported`: AI decider's own confidence claim, as a
        learned linguistic pattern. NOT a posterior probability.
        Lowest audit weight.
      - `logprob`: derived from token log-probabilities. Closer to
        a calibrated estimate but still model-internal.
      - `ensemble`: aggregated over multiple deciders / runs /
        models. Higher audit weight; carries the implicit promise
        of uncertainty quantification.
      - `human`: subjective human confidence rating. Audit-weight
        is operator-dependent; treat as direction-of-confidence,
        not a probability.
    """

    SELF_REPORTED = "self_reported"
    LOGPROB = "logprob"
    ENSEMBLE = "ensemble"
    HUMAN = "human"


class ConfidenceBand(StrEnum):
    """Triage band derived from the stored `confidence` float (8b).

    Computed at read time via `confidence_band()`; never stored
    (one source of truth = the float). Boundaries:

      - Low:     confidence < 0.3
      - Medium:  0.3 <= confidence < 0.7
      - High:    0.7 <= confidence < 0.95
      - Certain: confidence >= 0.95

    Operators reason about bands more naturally than raw floats;
    the >=0.95 cut matches the high-stakes auto-accept/auto-reject
    threshold cited across 2025-2026 LLM calibration literature.
    A `confidence` of None yields no band (returns None from
    `confidence_band()`); the field stays None in projections
    rather than mapping to a misleading "Low".
    """

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CERTAIN = "Certain"


# `override_kind` discriminator. When `parent_id` is set, this
# field says WHY the new Decision overrides the old one.
#
# Values (closed Literal; each is an English noun describing the
# *kind* of override):
#   - `correction`: the parent Decision was wrong; this is the
#     correct one.
#   - `exception`: the parent Decision's rule still applies, but
#     this Decision grants an exception.
#   - `appeal`: the parent Decision is being reviewed via appeal.
#   - `supersession`: the parent Decision is being replaced by a
#     newer/improved version of the same conceptual choice.
#   - `invalidation`: this Decision's authorized action UNDOES the
#     effect of the parent Decision (additive compensation, never
#     in-place mutation of the parent). Maps to PROV-O
#     `wasInvalidatedBy` on the activity side; `parent_id` itself
#     always carries the `wasInformedBy` semantic (informed-by the
#     parent — same chain whether the relationship is correction,
#     supersession, or invalidation). First concrete consumer:
#     paired with `demote_dataset` slice writes per
#     [[project-dataset-demote-design]] / Q4 compensation primitive.
DecisionOverrideKind = Literal["correction", "exception", "appeal", "supersession", "invalidation"]


class InvalidDecisionChoiceError(ValueError):
    """The supplied choice is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision choice must be 1-{DECISION_CHOICE_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidDecisionContextError(ValueError):
    """The supplied context is empty, whitespace-only, or too long.

    Validated for shape only; the well-known-values check is a
    projection-time concern (the field is intentionally an open
    string per gate-review Q5).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision context must be 1-{DECISION_CONTEXT_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidDecisionReasoningError(ValueError):
    """The supplied reasoning text is empty or too long.

    Whitespace-only IS allowed (becomes None after trim); this
    differs from the bounded-name pattern because reasoning is
    naturally optional and an explicit empty string from a UI
    should fold to None rather than raise.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision reasoning must be at most {DECISION_REASONING_MAX_LENGTH} chars after "
            f"trimming (got length: {len(value)})"
        )
        self.value = value


class InvalidDecisionRuleError(ValueError):
    """The supplied rule is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision rule must be 1-{DECISION_RULE_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidDecisionConfidenceError(ValueError):
    """The supplied confidence is outside [0.0, 1.0] or NaN.

    Confidence is a float in [0, 1] when present. Source is
    captured separately via `confidence_source` so consumers can
    audit the provenance of the value.
    """

    def __init__(self, value: float) -> None:
        super().__init__(f"Decision confidence must be a float in [0.0, 1.0] (got: {value!r})")
        self.value = value


class InvalidDecisionAlternativesError(ValueError):
    """The supplied alternatives tuple has too many entries, or
    an entry is empty / whitespace-only / too long.

    Cap is documented (not arbitrary): 32 entries covers the
    expected use ('operator considered Hold + Stop + Abort, chose
    Hold') plus headroom for AI top-k lists. When an AI decider
    needs more, switch to a `reasoning` logbook on the Decision
    aggregate (8c).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Decision alternatives invalid: {reason}")
        self.reason = reason


class InvalidDecisionInputsError(ValueError):
    """The supplied inputs dict is too large, has an
    invalid key, or carries a non-JSON-roundtrippable value.

    Optional dict for the `rule`'s input values (per ISO
    17025 Clause 7.1.3 + ILAC-G8:09/2019: a rule without its
    inputs is unauditable). Each key must be 1-100 chars after
    trim; values must be JSON-roundtrippable. Cap is 64 entries.

    JSON-roundtrip is enforced at the BC boundary via
    `json.dumps(value)`: a `datetime`, `set`, or other
    non-JSON-native value raises here rather than failing deep
    at jsonb serialization time.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Decision inputs invalid: {reason}")
        self.reason = reason


class InvalidReasoningSignatureError(ValueError):
    """The supplied reasoning_signature is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision reasoning_signature must be 1-{DECISION_REASONING_SIGNATURE_MAX_LENGTH} "
            f"chars after trimming (got length: {len(value)})"
        )
        self.value = value


class DecisionAlreadyExistsError(Exception):
    """Attempted to register a Decision whose stream already has events."""

    def __init__(self, decision_id: UUID) -> None:
        super().__init__(f"Decision {decision_id} already exists")
        self.decision_id = decision_id


class DecisionNotFoundError(Exception):
    """Attempted an operation on a Decision whose stream has no events."""

    def __init__(self, decision_id: UUID) -> None:
        super().__init__(f"Decision {decision_id} not found")
        self.decision_id = decision_id


class DeciderActorNotFoundError(Exception):
    """The Actor referenced by `decided_by` does not exist.

    Cross-aggregate validation at registration: the handler pre-
    loads the Actor and confirms its stream is non-empty. No
    status check (a Decision can be made by an Actor in any
    lifecycle state, including Deactivated, because the historical
    fact still holds). Mapped to HTTP 409.
    """

    def __init__(self, decided_by: UUID) -> None:
        super().__init__(f"Cannot register Decision: decided_by {decided_by} does not exist")
        self.decided_by = decided_by


class DecisionParentNotFoundError(Exception):
    """The parent Decision referenced by `parent_id` does not exist.

    Cross-aggregate validation at registration: when `parent_id` is
    set, the handler pre-loads the parent Decision and confirms
    its stream is non-empty. Mapped to HTTP 409.
    """

    def __init__(self, parent_id: UUID) -> None:
        super().__init__(f"Cannot register Decision: parent_id {parent_id} does not exist")
        self.parent_id = parent_id


class DecisionParentRunMismatchError(Exception):
    """The supplied parent Decision references a different `run_id`
    than the new Decision's command. Prevents accidental cross-Run
    chains in operator-triggered re-invocations of
    `debrief_run`.

    Hoisted to Decision aggregate state.py per cross-BC convention:
    cross-aggregate-load-state errors live with the relevant
    aggregate (mirrors `DeciderActorNotFoundError` precedent above).
    """

    def __init__(self, parent_decision_id: UUID, parent_run_id: UUID | None) -> None:
        super().__init__(
            f"parent decision {parent_decision_id} references "
            f"run_id={parent_run_id!r}; expected the command's run_id"
        )
        self.parent_decision_id = parent_decision_id
        self.parent_run_id = parent_run_id


class DecisionParentAgentMismatchError(Exception):
    """The supplied parent Decision was authored by a different agent
    (or by a non-`RunDebrief`-context decider). Prevents accidental
    cross-agent chains in operator-triggered re-invocations.

    Pinned by architecture gate-review: the parent-chain validator
    should check `parent.context` matches the expected RunDebrief
    context.
    """

    def __init__(self, parent_decision_id: UUID, parent_context: str) -> None:
        super().__init__(
            f"parent decision {parent_decision_id} has context "
            f"{parent_context!r}; expected 'RunDebrief'"
        )
        self.parent_decision_id = parent_decision_id
        self.parent_context = parent_context


class DecisionLogbookAlreadyOpenError(Exception):
    """Attempted to open a second logbook of the same kind on a Decision.

    The at-most-one-open-per-kind invariant: each Decision carries
    `logbooks: dict[str, UUID]` keyed by kind. Opening a second
    logbook of the same kind would silently shadow the first
    (losing the reference to its entries); the evolver raises
    instead. The existing logbook id is carried on the error so
    operators can resolve via close-then-reopen if intentional.

    Mapped to HTTP 409.
    """

    def __init__(self, decision_id: UUID, kind: str, existing_logbook_id: UUID) -> None:
        super().__init__(
            f"Decision {decision_id} already has an open logbook of kind {kind!r} "
            f"(existing logbook_id={existing_logbook_id})"
        )
        self.decision_id = decision_id
        self.kind = kind
        self.existing_logbook_id = existing_logbook_id


class DecisionLogbookNotOpenError(Exception):
    """Attempted to close a logbook that isn't currently open on the Decision.

    Either the logbook id was never opened (typo / wrong id), or it
    was already closed (re-close after close). Strict-not-idempotent
    for the same reason every other terminal-style transition is.

    Mapped to HTTP 409.
    """

    def __init__(self, decision_id: UUID, logbook_id: UUID) -> None:
        super().__init__(f"Decision {decision_id} has no open logbook with id {logbook_id}")
        self.decision_id = decision_id
        self.logbook_id = logbook_id


class InvalidDecisionRatingCommentError(ValueError):
    """The supplied rating comment is empty (after trim) or too long.

    Per [[project-run-debrief-design]] the `rate_decision` slice
    accepts an OPTIONAL free-form comment. None means "no comment";
    an empty / whitespace-only string is rejected (callers pass
    None to omit). Over 2000 chars after trim raises.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision rating comment must be 1-{DECISION_RATING_COMMENT_MAX_LENGTH} "
            f"chars after trimming (got length: {len(value)})"
        )
        self.value = value


@dataclass(frozen=True)
class DecisionChoice:
    """The choice that was made. Trimmed; 1-500 chars.

    Free-form string per gate-review Q5 (same posture as
    RunStopped reason). When a structured taxonomy crystallizes
    for a specific `context`, the conventions land as projection-
    time validation, not write-time enforcement.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=DECISION_CHOICE_MAX_LENGTH,
            error_class=InvalidDecisionChoiceError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class DecisionContext:
    """The decision discriminator. Trimmed; 1-100 chars.

    Open string with documented well-known values (see module-
    level constants `DECISION_CONTEXT_*`). Projection-time
    validation enforces the well-known set; the BC accepts any
    non-empty string.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=DECISION_CONTEXT_MAX_LENGTH,
            error_class=InvalidDecisionContextError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class DecisionRule:
    """The documented rule that governed the decision. Trimmed; 1-500 chars.

    Per ISO 17025 Clause 7.1.3, the decision rule must be
    documented and agreed before the test/calibration; reports
    must cite it. The BC accepts `rule = None` for any
    context: context-conditional requiredness ("ProcedureExecution
    must carry a rule", "RecipeApproval must carry one") is a
    projection-time audit-policy concern, not a domain invariant.
    Different facilities have different rules about which contexts
    require a citation. The deferred-with-trigger is "first audit
    demand for context-strict enforcement".

    Format is free-form but the convention encourages prefixed
    identifiers like `iso17025:7.1.3:simple_acceptance` or
    `cora:policy:recipe_approval:v1`.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=DECISION_RULE_MAX_LENGTH,
            error_class=InvalidDecisionRuleError,
        )
        object.__setattr__(self, "value", trimmed)


def validate_reasoning(value: str | None) -> str | None:
    """Trim + bound-check the optional reasoning text.

    Returns None for None, empty string, or whitespace-only input
    (operator UIs commonly send empty strings for unset optional
    fields). Raises `InvalidDecisionReasoningError` for over-cap
    text after trim.

    **Public to sibling BCs** (cross-BC gate-review convention):
    callable from `cora.agent.subscribers.run_debriefer` which
    composes `DecisionRegistered` inline because it needs a
    deterministic decision_id that the slice handler cannot provide.
    Sibling-BC callers depend on this helper's stability; treat
    rename / signature changes as cross-BC breaking.
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > DECISION_REASONING_MAX_LENGTH:
        raise InvalidDecisionReasoningError(value)
    return trimmed


def validate_confidence(value: float | None) -> float | None:
    """Bound-check the optional confidence float to [0.0, 1.0].

    **Public to sibling BCs** (cross-BC gate-review convention):
    same callable-by-Agent-BC contract as `validate_reasoning`.
    """
    if value is None:
        return None
    if value != value:  # NaN check (NaN != NaN)
        raise InvalidDecisionConfidenceError(value)
    if not (0.0 <= value <= 1.0):
        raise InvalidDecisionConfidenceError(value)
    return value


def validate_alternatives(value: tuple[str, ...]) -> tuple[str, ...]:
    """Validate the alternatives tuple shape + per-entry trim/length.

    Order is preserved (AI deciders need top-k ordering; Cedar /
    OPA both preserve it). Returns the trimmed tuple.
    """
    if len(value) > DECISION_ALTERNATIVES_MAX_ENTRIES:
        raise InvalidDecisionAlternativesError(
            f"too many entries (max {DECISION_ALTERNATIVES_MAX_ENTRIES}, got {len(value)})"
        )
    trimmed: list[str] = []
    for entry in value:
        entry_trimmed = entry.strip()
        if not entry_trimmed:
            raise InvalidDecisionAlternativesError("entry is empty or whitespace-only")
        if len(entry_trimmed) > DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH:
            raise InvalidDecisionAlternativesError(
                f"entry exceeds {DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH} chars: {entry!r}"
            )
        trimmed.append(entry_trimmed)
    return tuple(trimmed)


def validate_inputs(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate optional inputs dict.

    Three checks: cardinality (max 64 keys), per-key shape (1-100
    chars after trim, non-empty), per-value JSON-roundtrippability.
    The JSON check uses `json.dumps(value)` so a single
    non-roundtrippable value (datetime, set, custom object) raises
    here at the BC boundary rather than failing deep at jsonb
    serialization time.

    **Public to sibling BCs** (cross-BC gate-review convention):
    same callable-by-Agent-BC contract as `validate_reasoning` /
    `validate_confidence`.
    """
    if value is None:
        return None
    if len(value) > DECISION_INPUTS_MAX_ENTRIES:
        raise InvalidDecisionInputsError(
            f"too many entries (max {DECISION_INPUTS_MAX_ENTRIES}, got {len(value)})"
        )
    for key in value:
        key_trimmed = key.strip()
        if not key_trimmed:
            raise InvalidDecisionInputsError("key is empty or whitespace-only")
        if len(key_trimmed) > DECISION_INPUTS_KEY_MAX_LENGTH:
            raise InvalidDecisionInputsError(
                f"key exceeds {DECISION_INPUTS_KEY_MAX_LENGTH} chars: {key!r}"
            )
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise InvalidDecisionInputsError(f"value is not JSON-roundtrippable: {exc}") from exc
    return value


def validate_reasoning_signature(value: str | None) -> str | None:
    """Trim + bound-check the optional reasoning_signature."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > DECISION_REASONING_SIGNATURE_MAX_LENGTH:
        raise InvalidReasoningSignatureError(value)
    return trimmed


def validate_decision_rating_comment(value: str | None) -> str | None:
    """Trim + bound-check the optional rating comment.

    Returns None for None input (operator omitted the comment).
    Raises `InvalidDecisionRatingCommentError` for empty /
    whitespace-only / over-cap strings (callers pass None to omit;
    explicit empty strings indicate UI bugs and surface as 400).
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        raise InvalidDecisionRatingCommentError(value)
    if len(trimmed) > DECISION_RATING_COMMENT_MAX_LENGTH:
        raise InvalidDecisionRatingCommentError(value)
    return trimmed


def confidence_band(confidence: float | None) -> ConfidenceBand | None:
    """Map a stored `confidence` float to its triage band.

    Returns None when confidence is None (preserves the
    not-set distinction; never silently maps to "Low"). For
    floats in [0, 1], returns the band per the documented
    boundaries (CONFIDENCE_BAND_MEDIUM_MIN / HIGH_MIN /
    CERTAIN_MIN). Floats outside [0, 1] should never reach this
    function (`validate_confidence` rejects them at the BC
    boundary), but if they do (stale projection input), this
    function still returns a band by clamping to the nearest
    segment (>=1.0 to Certain, <0.0 to Low) so consumers don't
    crash on bad data.

    NaN handling: returns None. NaN means the value is
    meaningless; silently mapping it to any band would
    misrepresent it. Without an explicit check, NaN would fall
    through to Certain because all NaN comparisons are False.
    Same posture as None: "we can't classify this."
    """
    if confidence is None:
        return None
    if confidence != confidence:  # NaN check (NaN != NaN)
        return None
    if confidence < CONFIDENCE_BAND_MEDIUM_MIN:
        return ConfidenceBand.LOW
    if confidence < CONFIDENCE_BAND_HIGH_MIN:
        return ConfidenceBand.MEDIUM
    if confidence < CONFIDENCE_BAND_CERTAIN_MIN:
        return ConfidenceBand.HIGH
    return ConfidenceBand.CERTAIN


def has_determining_policies(decision: "Decision") -> bool:
    """Predicate: this Decision has determining-policy IDs recorded.

    True iff `context == "PolicyGrant"` AND `alternatives` is
    non-empty. Mirrors Cedar's `determining_policies` response
    field (the canonical noun for "policy IDs that produced this
    decision"). For non-PolicyGrant contexts, returns False
    because the Cedar-style determining-policies convention
    doesn't apply to those Decisions; callers asking 'is this
    audit-complete for PolicyGrant purposes?' use this predicate
    directly. Callers asking the inverse ('PolicyGrant decisions
    missing their determining policies') compose:

        decision.context.value == DECISION_CONTEXT_POLICY_GRANT
        and not has_determining_policies(decision)

    Use case: projection-time auditors flagging incomplete
    PolicyGrant records.
    """
    return (
        decision.context.value == DECISION_CONTEXT_POLICY_GRANT and len(decision.alternatives) > 0
    )


@dataclass(frozen=True)
class DecisionRatingRecord:
    """One operator's latest rating of a Decision.

    Held in `Decision.ratings: dict[UUID, DecisionRatingRecord]`
    keyed by the rater Actor's id (per the fold-symmetry dict-
    keyed special case: when attribution is the dict KEY, the
    per-value record need not repeat it). Multiple `DecisionRated`
    events per (decision, actor) pair are allowed; the evolver
    keeps only the latest (greatest `rated_at`) per actor in the
    aggregate state. The audit trail (every rating ever submitted)
    lives in the event log; this is the read-side latest-wins
    snapshot.

    `comment` is optional (None = no comment).
    """

    rating: "DecisionRating"
    comment: str | None
    rated_at: datetime


@dataclass(frozen=True)
class Decision:
    """Aggregate root: one structured-audit record of a consequential choice.

    Atomic-immutable for its decision facts: corrections / appeals /
    supersessions of the DECISION itself land as NEW Decisions with
    `parent_id` pointing at the original and `override_kind`
    explaining the transition. The 'current' Decision in a chain is
    the latest entry (latest-in-chain wins).

    Operator ratings are an ADDITIVE annotation channel:
    they do NOT change the decision facts; they accrue alongside in
    `ratings` for downstream calibration consumption. Latest-per-
    actor wins (the audit trail keeps all rating events).
    """

    id: UUID
    decided_by: ActorId
    decided_at: datetime
    context: DecisionContext
    choice: DecisionChoice
    parent_id: UUID | None = None
    override_kind: DecisionOverrideKind | None = None
    rule: DecisionRule | None = None
    reasoning: str | None = None
    confidence: float | None = None
    confidence_source: DecisionConfidenceSource | None = None
    alternatives: tuple[str, ...] = field(default_factory=tuple[str, ...])
    inputs: dict[str, Any] | None = None
    reasoning_signature: str | None = None
    # 8c: logbooks attached to this Decision, keyed by kind. Today
    # the only kind is `LOGBOOK_KIND_INFERENCE` (AI-decider trace
    # entries with OTel gen_ai.* attrs). Future kinds (evidence
    # chains, evaluator votes, etc.) follow the same shape.
    # At-most-one-open-per-kind enforced by the evolver.
    logbooks: dict[str, UUID] = field(default_factory=dict[str, UUID])
    # 8f-b: operator ratings, keyed by the rater Actor's id (the
    # fold-symmetry dict-keyed attribution special case). Latest
    # per actor wins; audit trail in the event log. Empty dict at
    # genesis; populated as `DecisionRated` events fold.
    ratings: dict[UUID, DecisionRatingRecord] = field(
        default_factory=dict[UUID, DecisionRatingRecord]
    )
