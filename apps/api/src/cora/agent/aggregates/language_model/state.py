"""LanguageModel aggregate state, VOs, enums, and domain errors.

`LanguageModel` is the facility's catalog entry for one approved LLM:
the object that binds a governance decision (this model is approved for
this class of data) to the infrastructure that serves it (a provider
endpoint, the Argo gateway, or an in-house pool). Homed in the agent BC
beside the fleet whose `Agent.model_ref` it governs; the equipment BC
already owns the `Model` stream type (vendor equipment), which is why
this aggregate carries the longer name. Design lock:
[[project_model_catalog_design]].

Per [[project_lifecycle_status_naming]] the FSM is a single axis,
`LanguageModelStatus`:

  Defined -> Approved -> RetirementAnnounced -> Retired
                     \\-> Retired (unannounced provider removal)
  {Defined, Approved, RetirementAnnounced} -> Deprecated

Approval is the facility's governance act: a Defined entry is
registered but unusable by the define_agent gate until approved. The
seed precedent is Safety's clearance-template seed, which writes
Defined + Activated in one append; the agent-fleet seeds are NOT the
analogy (they land Defined and are gated at runtime by `Actor.active`,
not by `AgentStatus`). `RetirementAnnounced` models the VENDOR's lifecycle event
(the paper's governance-event claim: a provider announcing retirement
becomes an appended fact the at-risk-results projection reads), while
`Deprecated` models the FACILITY withdrawing its own approval; the two
terminals stay distinct because they answer different audit questions
(who ended this model's service life, the vendor or us?).

## Identity and serving

`model_ref` reuses the Agent aggregate's `ModelRef` VO (same BC, same
invariants), so an agent's declared model and a catalog entry compare
field-for-field. `served_via` names the serving route: `Direct` (CORA's
own adapter holds provider credentials), `Argo` (the facility gateway
is the choke point; ANL deployments), `InHouse` (facility GPU pool).
Credentials, quotas, and per-user grants never live here: the serving
layer owns credentials and the Trust BC owns grants (anti-hooks in the
design memo).

## Cost basis (discriminated union)

`TokenPricing` (per-million-token USD, the four-field shape of
`cora.infrastructure.observability.gen_ai.ModelPricing`, which the
pricing bridge feeds from Approved entries) or `GpuHourPricing`
(facility-set rate for in-house pools). Argo-served entries carry
facility-set vendor-equivalent token prices (shadow pricing: Argo is
centrally funded, but allocation math still needs a rate, the
administratively-set internal conversion of the design).

## Tiers

`DataSensitivityTier` is the R3 axis (which data classes may reach this
model), a deliberately small v1 enum mirroring facility practice
(public / prudent-to-protect and pre-publication / approved-plan data).
`ArchivabilityTier` is the orthogonal reproducibility axis: `Pinned`
means the facility holds the weights and can serve them indefinitely
(results stay re-executable); `Alias` means the provider may move or
retire the identity (results degrade to attributable-only when it
does). The at-risk-results projection grades by this axis.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from cora.agent.aggregates.agent import ModelRef
from cora.shared.bounded_text import bounded_name, validate_bounded_text
from cora.shared.text_bounds import REASON_MAX_LENGTH

LANGUAGE_MODEL_NAME_MAX_LENGTH = 120
ENDPOINT_NOTE_MAX_LENGTH = 500


class LanguageModelStatus(StrEnum):
    """The catalog entry's lifecycle state.

    - `Defined`              -- registered as config; NOT yet approved for
                                use (the define_agent gate requires
                                Approved).
    - `Approved`             -- the facility's governance act: usable for
                                the entry's declared data tier.
    - `RetirementAnnounced`  -- the VENDOR announced this model will cease
                                to exist; still servable until retired,
                                and the at-risk-results projection is
                                live from this moment.
    - `Retired`              -- the model is no longer servable (vendor
                                removed it, or the facility decommissioned
                                the pool). Terminal.
    - `Deprecated`           -- the FACILITY withdrew approval (policy,
                                security, cost), independent of the
                                vendor's lifecycle. Terminal.
    """

    DEFINED = "Defined"
    APPROVED = "Approved"
    RETIREMENT_ANNOUNCED = "RetirementAnnounced"
    RETIRED = "Retired"
    DEPRECATED = "Deprecated"


class ServingRoute(StrEnum):
    """Where calls to this model are served.

    - `Direct`  -- CORA's own LLM adapter against the provider API
                   (credentials live with the deployment's serving
                   layer, never on this entry).
    - `Argo`    -- the facility gateway (ANL's Argo) is the choke
                   point; CORA holds no provider credentials at all.
    - `InHouse` -- a facility GPU pool serves held weights.
    """

    DIRECT = "Direct"
    ARGO = "Argo"
    IN_HOUSE = "InHouse"


class DataSensitivityTier(StrEnum):
    """Which class of data may reach this model (the R3 axis).

    Small on purpose: the facility's existing data-handling vocabulary
    maps onto three rungs at v1, and adding rungs is an additive enum
    change while pruning is expensive (the Caution category precedent).

      - `Open`      -- public or publishable-now data only.
      - `Internal`  -- non-public working data (prudent-to-protect,
                       pre-publication).
      - `Sensitive` -- data requiring an approved handling plan.
    """

    OPEN = "Open"
    INTERNAL = "Internal"
    SENSITIVE = "Sensitive"


class ArchivabilityTier(StrEnum):
    """Whether this model's identity outlives the vendor's lifecycle.

    - `Pinned` -- weights the facility holds and can serve
                  indefinitely; results stay re-executable.
    - `Alias`  -- an identity the provider may move onto new weights
                  or retire; results degrade to attributable-only
                  when it does.
    """

    PINNED = "Pinned"
    ALIAS = "Alias"


# ---------------------------------------------------------------------------
# Domain validation errors (raised by VO __post_init__ + deciders)
# ---------------------------------------------------------------------------


class InvalidLanguageModelNameError(ValueError):
    """The supplied display name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"LanguageModel name must be 1-{LANGUAGE_MODEL_NAME_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidEndpointNoteError(ValueError):
    """The supplied endpoint note is empty, whitespace-only, or too long.

    Callers pass None to omit; an empty string is a mistake, not an
    omission (the ModelRef.snapshot_pin convention).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"LanguageModel endpoint note must be 1-{ENDPOINT_NOTE_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidLanguageModelReasonError(ValueError):
    """A supplied retirement or deprecation reason is empty or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"LanguageModel reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidCostBasisError(ValueError):
    """A pricing figure is negative or not finite.

    One negative or infinite rate would poison every projection the
    pricing bridge feeds, the same reason the ledger's migration CHECK
    rejects them at the row level.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found / cannot-transition)
# ---------------------------------------------------------------------------


class LanguageModelAlreadyExistsError(Exception):
    """Attempted to define a catalog entry whose stream already has events.

    Per [[project_genesis_error_classes]] this stays un-hoisted.
    """

    def __init__(self, language_model_id: UUID) -> None:
        super().__init__(f"LanguageModel {language_model_id} already exists")
        self.language_model_id = language_model_id


class LanguageModelNotFoundError(Exception):
    """Attempted an operation on an entry whose stream has no events."""

    def __init__(self, language_model_id: UUID) -> None:
        super().__init__(f"LanguageModel {language_model_id} not found")
        self.language_model_id = language_model_id


class LanguageModelCannotApproveError(Exception):
    """Attempted `approve_language_model` from a disqualifying status.

    Source set is `{Defined}` only: approval is the one-way promotion
    out of the registered-but-unusable state, and re-approving a
    retiring or terminal entry would resurrect it silently.
    """

    def __init__(self, language_model_id: UUID, current_status: "LanguageModelStatus") -> None:
        super().__init__(
            f"LanguageModel {language_model_id} cannot be approved: currently in "
            f"status {current_status.value}, approve_language_model requires "
            f"{LanguageModelStatus.DEFINED.value}"
        )
        self.language_model_id = language_model_id
        self.current_status = current_status


class LanguageModelCannotAnnounceRetirementError(Exception):
    """Attempted `announce_language_model_retirement` from a disqualifying status.

    Source set is `{Approved}`: the announcement is meaningful only for
    an entry the facility currently serves. A Defined entry the vendor
    retires simply never gets approved; a terminal entry is past
    caring.
    """

    def __init__(self, language_model_id: UUID, current_status: "LanguageModelStatus") -> None:
        super().__init__(
            f"LanguageModel {language_model_id} cannot announce retirement: currently "
            f"in status {current_status.value}, announce_language_model_retirement "
            f"requires {LanguageModelStatus.APPROVED.value}"
        )
        self.language_model_id = language_model_id
        self.current_status = current_status


class LanguageModelCannotRetireError(Exception):
    """Attempted `retire_language_model` from a disqualifying status.

    Source set is `{Approved, RetirementAnnounced}`: providers remove
    models both with and without notice, so retirement is reachable
    directly from Approved (the unannounced case keeps its honesty; the
    projection simply had no warning window).
    """

    def __init__(self, language_model_id: UUID, current_status: "LanguageModelStatus") -> None:
        super().__init__(
            f"LanguageModel {language_model_id} cannot be retired: currently in "
            f"status {current_status.value}, retire_language_model requires "
            f"{LanguageModelStatus.APPROVED.value} or "
            f"{LanguageModelStatus.RETIREMENT_ANNOUNCED.value}"
        )
        self.language_model_id = language_model_id
        self.current_status = current_status


class LanguageModelNotApprovedError(Exception):
    """An agent cannot be registered on a model the facility has not approved.

    Raised by the `define_agent` gate when the command's model identity
    resolves to no catalog entry, or to an entry whose status is not
    Approved. The kernel's default lookup approves everything, so the
    gate arms only when a deployment stands up a real catalog. `status`
    is None when the identity is absent from the catalog entirely.
    """

    # Gate refusal must finalize the idempotency claim as a 400 like
    # every sibling validation error, not strand it Claimed (the name
    # matches none of classify_error_status's class-name patterns).
    idempotency_http_status: ClassVar[int] = 400

    def __init__(self, provider: str, model: str, status: str | None) -> None:
        detail = f"catalog status {status}" if status is not None else "not in the catalog"
        super().__init__(
            f"LanguageModel {provider}/{model} is not approved for agent registration ({detail})"
        )
        self.provider = provider
        self.model = model
        self.status = status


class LanguageModelCannotDeprecateError(Exception):
    """Attempted `deprecate_language_model` from a disqualifying status.

    Source set is `{Defined, Approved, RetirementAnnounced}`: the
    facility can withdraw at any pre-terminal point, but a Retired or
    Deprecated entry is already terminal and re-terminating it would
    blur which end the audit trail records.
    """

    def __init__(self, language_model_id: UUID, current_status: "LanguageModelStatus") -> None:
        super().__init__(
            f"LanguageModel {language_model_id} cannot be deprecated: currently in "
            f"status {current_status.value}, deprecate_language_model requires a "
            f"non-terminal status"
        )
        self.language_model_id = language_model_id
        self.current_status = current_status


# ---------------------------------------------------------------------------
# Bounded-text value objects
# ---------------------------------------------------------------------------


@bounded_name(max_length=LANGUAGE_MODEL_NAME_MAX_LENGTH, error_class=InvalidLanguageModelNameError)
@dataclass(frozen=True)
class LanguageModelName:
    """Display name for the catalog entry. Trimmed; 1-120 chars."""

    value: str


@dataclass(frozen=True)
class EndpointNote:
    """Optional serving detail (pool name, broker route). Trimmed; 1-500 chars.

    A note, not an address: connection configuration and credentials
    live with the serving layer, and putting a URL here would tempt a
    caller to treat the catalog as a router (anti-hook).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ENDPOINT_NOTE_MAX_LENGTH,
            error_class=InvalidEndpointNoteError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class LanguageModelReason:
    """Operator- or vendor-sourced reason text. Trimmed; 1-500 chars.

    One VO for both the retirement announcement's reason and the
    facility's deprecation reason, sharing the fleet-wide
    REASON_MAX_LENGTH bound per [[project_reason_max_length]].
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidLanguageModelReasonError,
        )
        object.__setattr__(self, "value", trimmed)


# ---------------------------------------------------------------------------
# Cost basis: discriminated union (token-priced or GPU-hour-priced)
# ---------------------------------------------------------------------------


def _require_finite_non_negative(name: str, value: float) -> None:
    if not (value >= 0.0) or value == float("inf"):
        raise InvalidCostBasisError(f"{name} must be finite and non-negative (got {value!r})")


@dataclass(frozen=True)
class TokenPricing:
    """Per-million-token USD prices; the bought-model cost basis.

    Field-for-field the shape of the observability `ModelPricing` so
    the pricing bridge can feed `compute_cost_usd` from Approved
    entries without translation. For Argo-served entries these are the
    facility's vendor-equivalent shadow prices.
    """

    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float

    def __post_init__(self) -> None:
        for field_name in (
            "input_per_mtok",
            "output_per_mtok",
            "cache_write_per_mtok",
            "cache_read_per_mtok",
        ):
            _require_finite_non_negative(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class GpuHourPricing:
    """Facility-set USD per GPU-hour; the built-model cost basis.

    The administratively-set internal conversion of the design: the
    rate the facility already implicitly chooses when it decides how
    much GPU to stand up versus how much external contract to buy.
    """

    usd_per_gpu_hour: float

    def __post_init__(self) -> None:
        _require_finite_non_negative("usd_per_gpu_hour", self.usd_per_gpu_hour)


type CostBasis = TokenPricing | GpuHourPricing
"""How consumption of this model converts to the accounting unit."""


# ---------------------------------------------------------------------------
# LanguageModel aggregate state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LanguageModel:
    """Aggregate root: one facility-approved LLM catalog entry.

    Slim per [[project_fold_cost_principles]]: identity + serving +
    pricing + the two tier axes + status + end-of-life metadata.
    `retirement_effective_at` is the vendor's announced cutoff (None
    until announced, and None on an unannounced retirement);
    `end_reason` carries whichever reason ended or is ending the
    entry's service life (the announcement's, the retirement's, or the
    deprecation's; the events distinguish which, the fold keeps the
    latest).
    """

    id: UUID
    name: LanguageModelName
    model_ref: ModelRef
    served_via: ServingRoute
    cost_basis: CostBasis
    data_tier: DataSensitivityTier
    archivability: ArchivabilityTier
    endpoint_note: EndpointNote | None = None
    status: LanguageModelStatus = LanguageModelStatus.DEFINED
    retirement_effective_at: datetime | None = None
    end_reason: LanguageModelReason | None = None
