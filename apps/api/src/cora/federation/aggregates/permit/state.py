"""Permit aggregate state, lifecycle status, directional terms VOs, and domain errors.

A `Permit` authorizes a federation flow between this facility and a
named peer facility. The single aggregate carries both directions of
the publish-pull relationship through a discriminated `terms` field
(`OutboundTerms | InboundTerms`); the `direction` enum on the
aggregate root is a query-convenience discriminator that mirrors
`type(state.terms)` for read-side filters and projection indexing.

Polymorphism precedent: `RunReading` carries a tagged-union payload
discriminated by SOSA `sampling_procedure`. Permit follows the same
shape: identity and lifecycle fields live on the root, direction-
specific contractual fields ride on the `terms` arm.

The 4-state FSM is shared across directions:

    Defined -> Active -> Suspended (resumable) -> Revoked (terminal)

with `Active <-> Suspended` reversible until `Revoked` closes the
lifecycle.

## Direction-specific term shapes

`OutboundTerms` (this facility publishes to the peer):

  - `scopes` is the bounded set of publishable scopes the peer may
    pull under this permit.
  - `read_scope` and `onward_action_scope` are orthogonal axes.
    Combinations that collapse the matrix (for example onward
    `MayExportOffPlatform` with read `ListMetadataOnly` has no carrier
    to export) raise `PermitScopeCollapseError`.

`InboundTerms` (this facility pulls from the peer):

  - `accepted_canonicalization_versions` carries the canonicalization
    schemes this side will accept (default `frozenset({"cora/v1"})`).
  - `required_receipt_kinds` is the set of `ReceiptKind` values the
    inbound side demands; default `frozenset()` (no receipt required).
  - `publisher_grant_correlation_handle` is the opaque string the peer
    minted at publish-time for cross-facility audit linkage; NOT a
    UUID foreign key.
  - `inbound_allowed_artifact_kinds` is the free-form string set the
    peer is authorized to publish for this permit. The `inbound_*`
    prefix disambiguates from the Permit root's own
    `allowed_artifact_kinds` field; same instance carries both.

The tagged-union shape of `terms` structurally enforces direction-
specific field ownership: an outbound payload cannot smuggle
`accepted_canonicalization_versions` because that field does not
exist on `OutboundTerms`. The prior
`AcceptedCanonicalizationVersionsForbiddenOnOutboundError` is DROPPED;
the type system enforces it now.

## ABI tier floor

`AbiTier` lives here as its canonical home: shared with the seal
aggregate (and any future federation symbol). Hoist to a federation-
level `_value_types.py` helper once a second symbol fires rule-of-three.

## Path C lifecycle bookkeeping

Per [[project_template_aggregate_timestamps]] the transition
lifecycle timestamps (`activated_at`, `suspended_at`, `resumed_at`,
`revoked_at`) do NOT live on aggregate state; they are derived at
projection-apply time from each event's envelope `occurred_at`.
`expires_at` STAYS on state: it is a contractual upper bound,
domain-meaningful, and not envelope-derivable. `defined_at` also
STAYS on state per the fold-symmetry rule
[[project_fold_symmetry_design]]: the `PermitDefined.occurred_at`
fold pairs with the `defined_by` attribution fold on the genesis
arm. `defined_by` is type-annotated as `ActorId` so the
fold-symmetry fitness test detects attribution fields structurally.

## Errors

Inlined per the unanimous instance-aggregate precedent
(Calibration / Caution / Supply / Clearance all keep error classes
alongside state). Per [[project_genesis_error_classes]] the
`*AlreadyExistsError` and `*NotFoundError` pair stays un-hoisted: each
BC routes its own per-class isinstance check in the BC exception
handler.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.shared.identity import ActorId


class AbiTier(StrEnum):
    """ABI-tier floor used by permits and the seal.

    - `Testing`:  pre-stable; SHOULD NOT be relied on for production.
    - `Stable`:   supported and recommended for production consumers.
    - `Obsolete`: still served, MAY be removed; consumers should migrate.
    - `Removed`:  no longer served; included as a closed enum arm so
                  historical event payloads remain decodable.
    """

    TESTING = "Testing"
    STABLE = "Stable"
    OBSOLETE = "Obsolete"
    REMOVED = "Removed"


class ReadScope(StrEnum):
    """How much the peer may read under an outbound permit.

    - `ListMetadataOnly`:     index entries (titles, ids, tags) only;
                              no artifact bodies.
    - `ReadAllArtifacts`:     full artifact bytes for every entry
                              in scope.
    - `ReadByABITierMinimum`: artifact bytes only for entries at or
                              above `abi_tier_floor`.
    """

    LIST_METADATA_ONLY = "ListMetadataOnly"
    READ_ALL_ARTIFACTS = "ReadAllArtifacts"
    READ_BY_ABI_TIER_MINIMUM = "ReadByABITierMinimum"


class OnwardActionScope(StrEnum):
    """What the peer may do with the data after reading under an outbound permit.

    - `ReadOnly`:               read-and-display; no persistence.
    - `MayCacheLocally`:        local caching permitted; not exposed
                                to the peer's own peers.
    - `MayRePublishToOwnPeers`: the peer may federate the data
                                onward to its own subscribers.
    - `MayExportOffPlatform`:   the peer may export the data out of
                                the federation entirely.
    """

    READ_ONLY = "ReadOnly"
    MAY_CACHE_LOCALLY = "MayCacheLocally"
    MAY_REPUBLISH_TO_OWN_PEERS = "MayRePublishToOwnPeers"
    MAY_EXPORT_OFF_PLATFORM = "MayExportOffPlatform"


class ReceiptKind(StrEnum):
    """Receipt schemes an inbound permit requires for accepted artifacts.

      - `scitt`:        transparency-log receipt arm
      - `rekor_sct`:    certificate-transparency receipt arm
      - `ts_authority`: timestamp-authority token arm

    The inbound side decides which receipt kinds it requires; an
    inbound pull refuses an artifact lacking every required kind.
    Defaulting to empty frozenset means "no receipt required" (initial
    deployment posture; tighten via update slice as ecosystem matures).

    See [[project_federation_adapter_design]] for the wire-tier per-arm
    format vocabulary.
    """

    SCITT = "scitt"
    REKOR_SCT = "rekor_sct"
    TS_AUTHORITY = "ts_authority"


class Direction(StrEnum):
    """Query-convenience discriminator mirroring `type(state.terms)`.

    Lives on the aggregate root so projections and read-side filters
    can index by direction without crossing the polymorphic terms
    boundary. Decider enforces `direction == Outbound iff
    isinstance(terms, OutboundTerms)`.
    """

    OUTBOUND = "Outbound"
    INBOUND = "Inbound"


class PermitStatus(StrEnum):
    """FSM positions for a Permit (shared across directions).

    - `Defined`:   created but not yet active; the flow is closed.
    - `Active`:    in force; pulls / publishes are permitted under terms.
    - `Suspended`: temporarily paused; resumable back to Active.
    - `Revoked`:   terminal; the permit is closed and cannot be revived.
    """

    DEFINED = "Defined"
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    REVOKED = "Revoked"


@dataclass(frozen=True, slots=True)
class ScopeRef:
    """Opaque reference to a publishable scope inside the publisher facility.

    Deviation from Identifier VO: 3-tuple per
    project-federation-port-design L37.

    Carried verbatim through the permit; the publisher's pull-side
    adapter resolves a `ScopeRef` to a concrete set of artifact
    streams at request time. Kept as a structural triple of strings so
    payloads stay JSON-friendly and free of cross-BC types.
    """

    kind: str
    name: str
    qualifier: str | None = None


@dataclass(frozen=True, slots=True)
class OutboundTerms:
    """Direction-specific contractual fields when this facility publishes."""

    scopes: frozenset[ScopeRef]
    read_scope: ReadScope
    onward_action_scope: OnwardActionScope


@dataclass(frozen=True, slots=True)
class InboundTerms:
    """Direction-specific contractual fields when this facility pulls.

    `inbound_allowed_artifact_kinds` carries the artifact-kind strings
    the peer is authorized to publish to this side. The `inbound_`
    prefix disambiguates from `Permit.allowed_artifact_kinds` on the
    aggregate root (which narrows artifact kinds across BOTH
    directions); same Permit instance carries both fields.
    """

    inbound_allowed_artifact_kinds: frozenset[str]
    accepted_canonicalization_versions: frozenset[str] = field(
        default_factory=lambda: frozenset({"cora/v1"})
    )
    required_receipt_kinds: frozenset[ReceiptKind] = field(default_factory=frozenset[ReceiptKind])
    publisher_grant_correlation_handle: str | None = None


@dataclass(frozen=True, slots=True)
class Permit:
    """Aggregate root: federation-flow authorization for one peer + direction.

    `peer_facility_id` is the opaque string identifier of the peer
    facility. String-typed (not UUID) because federation peers are
    external entities; CORA does NOT mint their ids.

    `direction` mirrors `type(terms)` and is the read-side query
    discriminator; the decider enforces the invariant on every
    transition.

    `allowed_credential_ids`, `allowed_payload_types`, and
    `allowed_artifact_kinds` narrow the permit across both
    directions: only the named Credential ids, payload-type strings,
    and artifact kinds are valid under this permit. Each MUST be
    non-empty; the decider rejects empty frozensets with
    `InvalidPermitScopeError`. There is no wildcard or implicit
    "no restriction" fallback. (Distinct from
    `InboundTerms.inbound_allowed_artifact_kinds`, which scopes the
    inbound arm specifically.)

    `abi_tier_floor` is the lowest tier the permit will honor on
    either side of the relationship.

    `expires_at` is the contractual upper bound; not envelope-
    derivable, stays on state. `defined_by` denorms the genesis
    principal and pairs with `defined_at` (folded from the
    `PermitDefined` envelope) per fold-symmetry.
    """

    id: UUID
    peer_facility_id: str
    direction: Direction
    allowed_credential_ids: frozenset[UUID]
    allowed_payload_types: frozenset[str]
    allowed_artifact_kinds: frozenset[str]
    abi_tier_floor: AbiTier
    expires_at: datetime
    defined_by: ActorId
    defined_at: datetime
    status: PermitStatus
    terms: OutboundTerms | InboundTerms


# ---------------------------------------------------------------------------
# Domain validation errors
# ---------------------------------------------------------------------------


class InvalidPermitScopeError(ValueError):
    """The supplied scope dimension is structurally invalid.

    Fires when a scope dimension fails its structural contract:
    empty string in `allowed_artifact_kinds` /
    `inbound_allowed_artifact_kinds` / `allowed_payload_types`,
    inverted validity window, or any other shape problem the decider
    catches before evolution.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Permit scope invalid: {reason}")
        self.reason = reason


class PermitScopeCollapseError(ValueError):
    """OutboundTerms read_scope and onward_action_scope collapse the matrix.

    Only applicable to OutboundTerms. Example: `onward_action_scope =
    MayExportOffPlatform` with `read_scope = ListMetadataOnly` has no
    artifact carrier to export.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedCanonicalizationVersionError(ValueError):
    """An accepted_canonicalization_versions member is not a recognized scheme.

    The inbound side has to map each accepted version to a concrete
    canonicalization implementation; an unknown string would mean
    every artifact under that version is unverifiable. Recognized
    versions are owned by the canonicalization port; v1 (`cora/v1`)
    is the day-one default per
    [[project_canonicalization_port_design]].
    """

    def __init__(self, version: str) -> None:
        super().__init__(
            f"Unsupported canonicalization version {version!r}; the inbound side has "
            f"no verifier registered for this version"
        )
        self.version = version


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision, not-found, FSM rejects)
# ---------------------------------------------------------------------------


class PermitAlreadyExistsError(Exception):
    def __init__(self, permit_id: UUID) -> None:
        super().__init__(f"Permit {permit_id} already exists")
        self.permit_id = permit_id


class PermitNotFoundError(Exception):
    def __init__(self, permit_id: UUID) -> None:
        super().__init__(f"Permit {permit_id} not found")
        self.permit_id = permit_id


class PermitCannotActivateError(Exception):
    def __init__(self, permit_id: UUID, current_status: PermitStatus) -> None:
        super().__init__(
            f"Permit {permit_id} cannot be activated: currently in status "
            f"{current_status.value}, activate_permit requires "
            f"{PermitStatus.DEFINED.value}"
        )
        self.permit_id = permit_id
        self.current_status = current_status


class PermitCannotSuspendError(Exception):
    def __init__(self, permit_id: UUID, current_status: PermitStatus) -> None:
        super().__init__(
            f"Permit {permit_id} cannot be suspended: currently in status "
            f"{current_status.value}, suspend_permit requires "
            f"{PermitStatus.ACTIVE.value}"
        )
        self.permit_id = permit_id
        self.current_status = current_status


class PermitCannotResumeError(Exception):
    def __init__(self, permit_id: UUID, current_status: PermitStatus) -> None:
        super().__init__(
            f"Permit {permit_id} cannot be resumed: currently in status "
            f"{current_status.value}, resume_permit requires "
            f"{PermitStatus.SUSPENDED.value}"
        )
        self.permit_id = permit_id
        self.current_status = current_status


class PermitCannotRevokeError(Exception):
    def __init__(self, permit_id: UUID, current_status: PermitStatus) -> None:
        super().__init__(
            f"Permit {permit_id} cannot be revoked: currently in status "
            f"{current_status.value}, revoke_permit rejects terminal status "
            f"{PermitStatus.REVOKED.value}"
        )
        self.permit_id = permit_id
        self.current_status = current_status
