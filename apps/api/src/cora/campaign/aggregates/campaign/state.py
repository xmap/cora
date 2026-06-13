"""Campaign aggregate state, VOs, enums, and domain errors.

`Campaign` is the operator-declared coordinated container above Run:
a series of measurements over time on shared resources, a parametric
sweep, a coordinated multi-modal or multi-Subject acquisition, or a
scheduling block (proposal / beamtime / cycle). It is distinct from
Recipe BC
(pre-execution template ladder; design surface for recipe authors)
by audience-and-vocabulary separation: Campaign is a post-execution
coordination layer (study surface for operators / PIs after Plans
exist). Per `[[project_campaign_design]]`.

Per the design memo the 5-state FSM is locked day one (BC-map line
94, corpus-validated as light-but-sufficient; PackML's 17-state is
the documented over-engineering counter-example):

  Planned -> Active     (operator starts the campaign)
  Active  <-> Held      (pause / resume cycle; unlimited)
  Active | Held -> Closed     (normal terminal; members locked)
  Planned | Active | Held -> Abandoned  (early terminal w/ reason)

The aggregate is intentionally slim per
`[[project_fold_cost_principles]]`: identity + name + intent +
lead actor + optional subject + description + tags + external refs +
optional external_id + run_ids (forward-compat empty at BC genesis;
mutated when membership slices land) + status + last_status_reason.

## VO pattern reuse (17th / 18th / 19th bounded-text instances)

`CampaignName`, `CampaignDescription`, and `CampaignTag` are
trimmed-bounded-text VOs following the shared
`cora.shared.bounded_text.validate_bounded_text` pattern.

Reason fields on `hold_campaign` and `abandon_campaign` slices are
bare `str` validated 1-500 chars at the decider, mirroring
`RunAbortReason` / `RunStopReason` / `ClearanceRejectReason`
precedent (free-form audit breadcrumb, no shared semantics across
slices that would justify a typed VO).

## Intent enum (4 values closed) + free tags

`CampaignIntent` is closed at 4 abstract intent-shape values: Series /
Sweep / Coordination / Block. It describes what KIND of coordination
the Campaign carries, NOT the scientific technique. Technique-specific
tagging (in-situ, operando, tomography, EDD, etc.) lives on the free
`tags: frozenset[CampaignTag]` field. Closed enum + free tags yields
a reportable shape vocabulary alongside a flexible domain-vocabulary
surface. Day-1 lock is intentionally narrow: adding intents is cheap
(additive StrEnum), pruning is expensive.

## Identifier (anti-corruption for proposal / btr / visit / cycle)

`Campaign.external_refs: frozenset[Identifier]` reuses the shared
`cora.shared.identifier.Identifier` VO (open-scheme anti-
corruption-ref axis per `[[project_identifier_vo_design]]`). Day-1
schemes: `proposal` / `btr` / `visit` / `cycle`. Mirrors
`Run.external_refs` exactly.

## Lazy-mint `external_id` for facility-assigned / DataCite Project DOI

`external_id: str | None` is the same internal-opaque + lazy-external-
mint pattern Clearance uses (per `[[project_pid_landscape]]`). Set
lazily once a Campaign is significant enough to publish (DataCite 4.6
added `Project` as `resourceTypeGeneral`; clean fit). Field on
aggregate today; no slice mints it (deferred to a watch item).
"""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text
from cora.shared.identifier import Identifier
from cora.shared.text_bounds import REASON_MAX_LENGTH

CAMPAIGN_NAME_MAX_LENGTH = 200
CAMPAIGN_DESCRIPTION_MAX_LENGTH = 2000
CAMPAIGN_TAG_MAX_LENGTH = 50
CAMPAIGN_EXTERNAL_ID_MAX_LENGTH = 100


class CampaignStatus(StrEnum):
    """The Campaign's lifecycle state.

    Five values locked day one per `[[project_campaign_design]]`:

      - `Planned`   -- registered; not yet started; members addable
      - `Active`    -- in progress; members addable; Runs may execute
      - `Held`      -- paused (operator decision); members addable
      - `Closed`    -- normal terminal; members locked
      - `Abandoned` -- early terminal with reason; members locked

    5-state lifecycle is the BC-map locked shape (line 94), corpus-
    validated as light-but-sufficient: no standard has a tighter
    Campaign FSM, and PackML's 17-state cascade is the documented
    over-engineering counter-example. UPPER_SNAKE_CASE identifier +
    PascalCase value per cross-BC convention.
    """

    PLANNED = "Planned"
    ACTIVE = "Active"
    HELD = "Held"
    CLOSED = "Closed"
    ABANDONED = "Abandoned"


class CampaignIntent(StrEnum):
    """Intent-shape vocabulary; what KIND of coordination this Campaign carries.

    Four abstract shape categories: what the operator is coordinating,
    not the scientific technique. Technique-specific tagging (in-situ,
    operando, tomography, EDD, etc.) goes on the free
    `tags: frozenset[CampaignTag]` field. Closed enum + free tags
    yields a reportable shape vocabulary plus a flexible domain-
    vocabulary surface.

      - `Series`       -- multiple measurements coordinated over time on
                          shared resources
      - `Sweep`        -- parametric exploration (axes swept across runs)
      - `Coordination` -- multi-modal or multi-Subject coordinated
                          acquisition
      - `Block`        -- scheduling envelope (proposal / beamtime block /
                          cycle)
    """

    SERIES = "Series"
    SWEEP = "Sweep"
    COORDINATION = "Coordination"
    BLOCK = "Block"


# ---------------------------------------------------------------------------
# Domain validation errors (raised by VO __post_init__ + deciders)
# ---------------------------------------------------------------------------


class InvalidCampaignNameError(ValueError):
    """The supplied campaign name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Campaign name must be 1-{CAMPAIGN_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidCampaignDescriptionError(ValueError):
    """The supplied campaign description is empty, whitespace-only, or too long.

    The VO is only constructed when the operator-supplied value is non-None;
    omitting `description` entirely is the supported path for the
    "no description" case.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Campaign description must be 1-{CAMPAIGN_DESCRIPTION_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidCampaignTagError(ValueError):
    """A supplied tag is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Campaign tag must be 1-{CAMPAIGN_TAG_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidCampaignHoldReasonError(ValueError):
    """The supplied hold reason is empty, whitespace-only, or too long.

    Bare-str validated at the `hold_campaign` decider (mirrors the
    `RunAbortReason` / `RunStopReason` / `ClearanceRejectReason`
    free-form audit-breadcrumb precedent).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Campaign hold reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidCampaignAbandonReasonError(ValueError):
    """The supplied abandon reason is empty, whitespace-only, or too long.

    Bare-str validated at the `abandon_campaign` decider. REQUIRED at
    the abandon path (an abandoned Campaign must say why, mirroring
    `RunAbortReason` REQUIRED-on-abort precedent).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Campaign abandon reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidCampaignExternalIdError(ValueError):
    """The supplied external_id is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Campaign external_id must be 1-{CAMPAIGN_EXTERNAL_ID_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found / cannot-transition)
# ---------------------------------------------------------------------------


class CampaignAlreadyExistsError(Exception):
    """Attempted to register a Campaign whose stream already has events.

    Per `[[project_genesis_error_classes]]` this class stays un-hoisted:
    per-BC isinstance routing in the BC's exception handler outweighs
    the ~80 LOC saved by hoisting to a generic `AggregateAlreadyExists`
    error.
    """

    def __init__(self, campaign_id: UUID) -> None:
        super().__init__(f"Campaign {campaign_id} already exists")
        self.campaign_id = campaign_id


class CampaignNotFoundError(Exception):
    """Attempted an operation on a Campaign whose stream has no events."""

    def __init__(self, campaign_id: UUID) -> None:
        super().__init__(f"Campaign {campaign_id} not found")
        self.campaign_id = campaign_id


class CampaignCannotStartError(Exception):
    """Attempted `start_campaign` from a disqualifying status.

    Single-source guard: source set is `{Planned}` only. Cannot start
    an already-Active / Held / Closed / Abandoned Campaign.
    """

    def __init__(self, campaign_id: UUID, current_status: "CampaignStatus") -> None:
        super().__init__(
            f"Campaign {campaign_id} cannot be started: currently in status "
            f"{current_status.value}, start_campaign requires "
            f"{CampaignStatus.PLANNED.value}"
        )
        self.campaign_id = campaign_id
        self.current_status = current_status


class CampaignCannotHoldError(Exception):
    """Attempted `hold_campaign` from a disqualifying status.

    Single-source guard: source set is `{Active}` only.
    """

    def __init__(self, campaign_id: UUID, current_status: "CampaignStatus") -> None:
        super().__init__(
            f"Campaign {campaign_id} cannot be held: currently in status "
            f"{current_status.value}, hold_campaign requires "
            f"{CampaignStatus.ACTIVE.value}"
        )
        self.campaign_id = campaign_id
        self.current_status = current_status


class CampaignCannotResumeError(Exception):
    """Attempted `resume_campaign` from a disqualifying status.

    Single-source guard: source set is `{Held}` only.
    """

    def __init__(self, campaign_id: UUID, current_status: "CampaignStatus") -> None:
        super().__init__(
            f"Campaign {campaign_id} cannot be resumed: currently in status "
            f"{current_status.value}, resume_campaign requires "
            f"{CampaignStatus.HELD.value}"
        )
        self.campaign_id = campaign_id
        self.current_status = current_status


class CampaignCannotCloseError(Exception):
    """Attempted `close_campaign` from a disqualifying status.

    Multi-source guard: source set is `{Active, Held}` (terminals
    refuse re-closing; Planned refuses since work never started).
    """

    def __init__(self, campaign_id: UUID, current_status: "CampaignStatus") -> None:
        super().__init__(
            f"Campaign {campaign_id} cannot be closed: currently in status "
            f"{current_status.value}, close_campaign requires one of "
            f"{CampaignStatus.ACTIVE.value} | {CampaignStatus.HELD.value}"
        )
        self.campaign_id = campaign_id
        self.current_status = current_status


class CampaignCannotAbandonError(Exception):
    """Attempted `abandon_campaign` from a disqualifying status.

    Multi-source guard: source set is `{Planned, Active, Held}`
    (terminals refuse re-abandoning).
    """

    def __init__(self, campaign_id: UUID, current_status: "CampaignStatus") -> None:
        super().__init__(
            f"Campaign {campaign_id} cannot be abandoned: currently in status "
            f"{current_status.value}, abandon_campaign requires one of "
            f"{CampaignStatus.PLANNED.value} | {CampaignStatus.ACTIVE.value} | "
            f"{CampaignStatus.HELD.value}"
        )
        self.campaign_id = campaign_id
        self.current_status = current_status


class CampaignCannotAddRunError(Exception):
    """Attempted `add_run_to_campaign` from a disqualifying status.

    Multi-source guard: source set is `{Planned, Active, Held}`. Terminal
    Campaigns (Closed / Abandoned) refuse new members per the design memo
    membership lock.
    """

    def __init__(self, campaign_id: UUID, current_status: "CampaignStatus") -> None:
        super().__init__(
            f"Campaign {campaign_id} cannot add a Run: currently in status "
            f"{current_status.value}, add_run_to_campaign requires one of "
            f"{CampaignStatus.PLANNED.value} | {CampaignStatus.ACTIVE.value} | "
            f"{CampaignStatus.HELD.value}"
        )
        self.campaign_id = campaign_id
        self.current_status = current_status


class CampaignRunAlreadyMemberError(Exception):
    """Attempted to add a Run already in the Campaign's run_ids set.

    Membership idempotency violation: `add_run_to_campaign` rejects when
    the Run is already a member of THIS Campaign. (A Run already member
    of a DIFFERENT Campaign raises `RunAlreadyAssignedToCampaignError`
    from the Run BC instead.)
    """

    def __init__(self, campaign_id: UUID, run_id: UUID) -> None:
        super().__init__(f"Run {run_id} is already a member of Campaign {campaign_id}.")
        self.campaign_id = campaign_id
        self.run_id = run_id


class CampaignCannotRemoveRunError(Exception):
    """Attempted `remove_run_from_campaign` from a disqualifying status.

    Multi-source guard: source set is `{Planned, Active, Held}`. Terminal
    Campaigns refuse membership mutation (membership frozen at Closed /
    Abandoned per the design memo lock).
    """

    def __init__(self, campaign_id: UUID, current_status: "CampaignStatus") -> None:
        super().__init__(
            f"Campaign {campaign_id} cannot remove a Run: currently in status "
            f"{current_status.value}, remove_run_from_campaign requires one of "
            f"{CampaignStatus.PLANNED.value} | {CampaignStatus.ACTIVE.value} | "
            f"{CampaignStatus.HELD.value}"
        )
        self.campaign_id = campaign_id
        self.current_status = current_status


class CampaignRunNotMemberError(Exception):
    """Attempted to remove a Run that is not in the Campaign's run_ids set.

    `remove_run_from_campaign` rejects when the supplied run_id is not
    a current member.
    """

    def __init__(self, campaign_id: UUID, run_id: UUID) -> None:
        super().__init__(f"Run {run_id} is not a member of Campaign {campaign_id}.")
        self.campaign_id = campaign_id
        self.run_id = run_id


class InvalidCampaignRunRemoveReasonError(ValueError):
    """The supplied remove-run reason is empty, whitespace-only, or too long.

    Bare-str validated at the `remove_run_from_campaign` decider. REQUIRED
    on the remove path: an operator must say WHY they ungroup a Run
    (ungrouping is meaningful).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Campaign run remove reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


# ---------------------------------------------------------------------------
# Bounded-text value objects (17th, 18th, 19th instances of the pattern)
# ---------------------------------------------------------------------------


@bounded_name(max_length=CAMPAIGN_NAME_MAX_LENGTH, error_class=InvalidCampaignNameError)
@dataclass(frozen=True)
class CampaignName:
    """Operator-meaningful Campaign name. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class CampaignDescription:
    """Optional free-form description. Trimmed; 1-2000 chars.

    The VO is constructed only when the operator-supplied value is
    non-None; omitting `description` entirely is the supported path
    for "no description" (`Campaign.description` defaults to None).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=CAMPAIGN_DESCRIPTION_MAX_LENGTH,
            error_class=InvalidCampaignDescriptionError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class CampaignTag:
    """One free-form tag. Trimmed; 1-50 chars per tag.

    The aggregate carries `frozenset[CampaignTag]`; an empty set is
    allowed (the closed `intent` enum carries the discriminator weight).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=CAMPAIGN_TAG_MAX_LENGTH,
            error_class=InvalidCampaignTagError,
        )
        object.__setattr__(self, "value", trimmed)


# ---------------------------------------------------------------------------
# Campaign aggregate state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Campaign:
    """Aggregate root: an operator-declared coordinated study container.

    Slim aggregate per `[[project_fold_cost_principles]]`. Identity
    is a stable opaque `id: UUID`. Optional `external_id: str | None`
    is the facility-minted or DataCite Project DOI assigned lazily;
    no slice mints it today (deferred per design memo Watch items).

    `lead_actor_id: UUID` is REQUIRED at register, mirroring LIMS
    Study Director / GLP Study Director Identity (required for
    compliance). Separate from `StoredEvent.principal_id`: the
    registering principal (an admin acting on behalf of a visiting
    PI) may differ from the campaign lead. Per design memo lock.

    `subject_id: UUID | None` is INFORMATIONAL (LOOSE policy day-1):
    Block and Sweep-across-samples use cases need multi-Subject
    Campaigns. Aggregate does NOT enforce coherence against member
    Run subjects (anti-hook).

    `run_ids: frozenset[UUID]` is the bidirectional composition set.
    At BC genesis it stays empty; the evolver does NOT mutate it.
    Membership mutation slices land later (add_run_to_campaign /
    remove_run_from_campaign + Run.campaign_id additive field). The
    field is on the aggregate today for forward-compat so those
    slices can add evolver arms without changing the state shape.

    `last_status_reason: str | None` is populated by Held and
    Abandoned events. Resume preserves the value (audit breadcrumb:
    "why was it held before the resume?" stays readable).

    No actor field beyond `lead_actor_id`. Audit truth ("who started /
    held / closed / abandoned") lives on `StoredEvent.principal_id`
    envelope. Future projection denormalises for query-time access.
    """

    id: UUID
    name: CampaignName
    intent: CampaignIntent
    lead_actor_id: UUID
    subject_id: UUID | None = None
    description: CampaignDescription | None = None
    tags: frozenset[CampaignTag] = field(default_factory=frozenset[CampaignTag])
    external_refs: frozenset[Identifier] = field(default_factory=frozenset[Identifier])
    external_id: str | None = None
    run_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    status: CampaignStatus = CampaignStatus.PLANNED
    last_status_reason: str | None = None
