"""Facility aggregate state, enums, value objects, and domain errors.

A `Facility` is a per-code singleton record naming a containment /
authority entity that other CORA aggregates bind to (Asset.facility_id
in slice 8, Supply.facility_id in slice 7, Seal/Permit/Credential
facility_id binding in slice 6, ClearanceTemplate.facility_id in slice
9). Per [[project_structural_scope_design]] the aggregate resolves the
upper Asset tiers / SupplyScope.Facility / Federation.facility_id
masquerade family in one promotion.

Two-tier identity per locked design:

  - `Facility.id: FacilityId` is the internal-opaque PK for spine
    references within ONE deployment.
  - `Facility.code: FacilityCode` is the cross-deployment convergent
    identity. Cross-BC and cross-deployment references MUST use
    `Facility.code`; the architecture fitness test
    `test_cross_bc_refs_facility_code_not_id` enforces this.

Day-one `FacilityKind` is closed at `{Site, Area}`:

  - `Site` (ISA-95 Site): the physical research facility (APS, MAX IV).
    Only kind that holds `trust_anchor_credential_ids` and that may
    have `parent_id = None`.
  - `Area` (ISA-95 Area): an experimental hall or building within a
    Site. Always has a non-null parent; trust anchors stay empty
    (Area inherits the parent Site's trust posture).

`Institution` (ISA-95 Enterprise / PROV-O Organization / ROR) is
DEFERRED; when promoted it becomes a separate `Organization` aggregate,
NOT a `FacilityKind` member, to avoid the ISA-95 Enterprise/Site
conflation.

`Sector` is DEFERRED; APS-local concept whose canonical home is an
Asset row at the Area tier (per [[project_supply_sector_disposition]]).
Map APS Sector to `kind=Area` with a documented operational convention
until MAX IV / DLS bring a second intermediate vocabulary that doesn't
fit Area.

Two-state FSM per locked design:

  - `Active` (genesis from `register_facility`).
  - `Decommissioned` (terminal, via `decommission_facility`; no further
    transitions).

Fold-symmetric attribution pairs per [[project_fold_symmetry_design]]:
`registered_at + registered_by` at genesis; `decommissioned_at +
decommissioned_by` at terminal transition. Both `_by` fields are
typed `ActorId` so the fold-symmetry fitness test detects them
structurally.

PIDINST day-one carriage per locked design:

  - `alternate_identifiers: frozenset[AlternateIdentifier]` is accepted
    as an optional seed in `register_facility` (defaults to empty).
    Mirrors the Asset register-time seed; add/remove slices are
    deferred per Asset precedent.
  - `persistent_id: PersistentIdentifier | None` ships on state only
    (default None). The `assign_facility_persistent_id` slice is
    deferred (mirrors Asset's separate `assign_asset_persistent_id`
    slice; trigger is first Facility-tier DOI mint).

Trust-anchor binding per locked design:

  - `trust_anchor_credential_ids: frozenset[CredentialId]` carries the
    set of Credential ids the Facility trusts as Seal anchors;
    populated only when `kind=Site`. The Seal decider checks set-
    membership against this field (initialize_seal +
    rotate_seal_online_key) to enforce the structural cross-tenant
    defense, raising `SealCredentialNotTrustAnchorError` on miss.
    Mutated via `add_facility_trust_anchor_credential` and
    `remove_facility_trust_anchor_credential`.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.shared.bounded_text import bounded_name
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import AlternateIdentifier, PersistentIdentifier
from cora.shared.identity import ActorId

FACILITY_NAME_MAX_LENGTH = 200


class InvalidFacilityNameError(ValueError):
    """The supplied `Facility.display_name` is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Facility name must be 1-{FACILITY_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


@bounded_name(max_length=FACILITY_NAME_MAX_LENGTH, error_class=InvalidFacilityNameError)
@dataclass(frozen=True)
class FacilityName:
    """Operator-supplied display name for a Facility.

    Trimmed and length-bounded 1-200 chars via the `bounded_name`
    decorator. Matches `ActorName` / `PolicyName` / `CapabilityName`
    precedent for free-Unicode title-like names.
    """

    value: str


class FacilityKind(StrEnum):
    """The structural tier of a Facility row.

    Day-one closed at two arms per [[project_structural_scope_design]]:

      - `Site`: ISA-95 Site (the physical research facility). Only kind
        that holds `trust_anchor_credential_ids`; only kind whose
        `parent_id` may be None.
      - `Area`: ISA-95 Area (an experimental hall or building within a
        Site). Always has a non-null `parent_id`; trust
        anchors stay empty (Area inherits via parent chain).

    Widening triggers (deferred per locked design):

      - `Institution` (ISA-95 Enterprise): promote to a SEPARATE
        `Organization` aggregate with ROR-identifier semantics when
        Argonne-owns-APS-and-CNM becomes operationally relevant. Do
        NOT widen `FacilityKind` to add Institution.
      - `Sector`: APS-local; map to `kind=Area` until a second facility
        brings an intermediate vocabulary that doesn't fit Area.
    """

    SITE = "Site"
    AREA = "Area"


class FacilityStatus(StrEnum):
    """Lifecycle status of a Facility.

    Two-state FSM per [[project_facility_aggregate_design]] L3:

      - `Active`: genesis state set by `register_facility`.
      - `Decommissioned`: terminal. The facility is no longer in
        service; no further transitions are valid.

    Expansion is deferred to rule-of-three (e.g. `Suspended` for a
    temporarily offline facility under maintenance; not designed today).
    """

    ACTIVE = "Active"
    DECOMMISSIONED = "Decommissioned"


class FacilityAlreadyExistsError(Exception):
    """Attempted to register a Facility whose stream already has events.

    Surfaces from `ConcurrencyError` translation in the
    `register_facility` handler when two operators race the same code
    (live-path uniqueness via deterministic stream_id derivation per
    [[project_facility_aggregate_design]] L1) OR when a deregistered
    facility's code is re-used (memo anti-hook: code is immutable
    post-creation; deregister-and-re-register with the same code is
    forbidden).

    Per [[project_genesis_error_classes]] this class stays un-hoisted;
    per-BC isinstance routing in the federation BC's exception handler
    outweighs the small saving from a generic alias.
    """

    def __init__(self, code: FacilityCode) -> None:
        super().__init__(f"Facility {code.value!r} already exists")
        self.code = code


class FacilityNotFoundError(Exception):
    """Attempted an operation on a Facility whose stream has no events."""

    def __init__(self, facility_id: FacilityId) -> None:
        super().__init__(f"Facility {facility_id} not found")
        self.facility_id = facility_id


class FacilityCannotDecommissionError(Exception):
    """Decommission was attempted on an already-decommissioned Facility.

    Strict-not-idempotent per the `revoke_credential` precedent: a loud
    error surfaces operator intent mismatches (two operators racing to
    decommission the same facility) rather than silently absorbing the
    second call.
    """

    def __init__(self, facility_id: FacilityId) -> None:
        super().__init__(f"Facility {facility_id} is already decommissioned")
        self.facility_id = facility_id


class FacilitySiteCannotHaveParentError(Exception):
    """A `kind=Site` Facility was constructed with a non-null `parent_id`.

    Site is the ISA-95 root tier; its `parent_id` MUST be
    None. Cross-tier nesting (Site under Site) is a future concern when
    a hypothetical `Institution` widens the hierarchy; today the
    invariant is structural.
    """

    def __init__(self, code: FacilityCode, parent_id: FacilityId) -> None:
        super().__init__(
            f"Facility {code.value!r} has kind=Site but parent_id={parent_id}; "
            "Site-tier facilities must have null parent"
        )
        self.code = code
        self.parent_id = parent_id


class FacilityAreaMustHaveParentError(Exception):
    """A `kind=Area` Facility was constructed without a `parent_id`.

    Area-tier facilities live within a Site; the parent reference is
    structural. Cross-stream parent existence + parent-kind=Site checks
    land in slice 6 (FacilityLookup port surface); slice 5 enforces
    only the null/non-null invariant.
    """

    def __init__(self, code: FacilityCode) -> None:
        super().__init__(
            f"Facility {code.value!r} has kind=Area but parent_id is null; "
            "Area-tier facilities must have a non-null parent"
        )
        self.code = code


class FacilityAreaCannotHaveTrustAnchorsError(Exception):
    """A `kind=Area` Facility was constructed with non-empty `trust_anchor_credential_ids`.

    Trust anchors bind credentials to the Site root, NOT to its Area
    children; Area facilities inherit the parent Site's trust posture.
    The Seal decider's set-membership check against
    `trust_anchor_credential_ids` is therefore Site-only.
    """

    def __init__(self, code: FacilityCode) -> None:
        super().__init__(
            f"Facility {code.value!r} has kind=Area but non-empty trust_anchor_credential_ids; "
            "trust anchors bind to Site-tier facilities only"
        )
        self.code = code


class FacilityParentNotFoundError(Exception):
    """An `Area` Facility was registered with a `parent_id` that resolves to no
    existing Facility row.

    Raised by `register_facility` decider in Sub-Slice A of Slice 6 when
    the FacilityLookup port returns None for the supplied parent_id.
    Mirrors the cross-aggregate not-found shape of `AssetNotFoundError`
    / `CredentialNotFoundError`. HTTP 404 at the route.
    """

    def __init__(self, code: FacilityCode, parent_id: FacilityId) -> None:
        super().__init__(
            f"Facility {code.value!r} parent_id={parent_id} resolves to no existing Facility"
        )
        self.code = code
        self.parent_id = parent_id


class FacilityTrustAnchorCredentialAlreadyPresentError(Exception):
    """Attempted to add a credential id that is already a trust anchor.

    Strict-not-idempotent: mirrors `AssetAlternateIdentifierAlreadyPresentError`.
    Re-add raises rather than no-ops so operator intent mismatches surface
    (two operators racing to bind the same credential). HTTP 409 at the
    route.
    """

    def __init__(self, facility_id: FacilityId, credential_id: CredentialId) -> None:
        super().__init__(
            f"Facility {facility_id} already has credential {credential_id} as a trust anchor"
        )
        self.facility_id = facility_id
        self.credential_id = credential_id


class FacilityTrustAnchorCredentialNotPresentError(Exception):
    """Attempted to remove a credential id that is not a trust anchor.

    Mirror of `FacilityTrustAnchorCredentialAlreadyPresentError`.
    Strict-not-idempotent: the decider rejects rather than no-ops on
    a missing credential. Same shape as
    `AssetAlternateIdentifierNotPresentError`. HTTP 409 at the route.
    """

    def __init__(self, facility_id: FacilityId, credential_id: CredentialId) -> None:
        super().__init__(
            f"Facility {facility_id} does not have credential {credential_id} as a trust anchor; "
            "nothing to remove"
        )
        self.facility_id = facility_id
        self.credential_id = credential_id


class FacilityCannotAddTrustAnchorCredentialError(Exception):
    """Attempted to mutate trust_anchor_credential_ids under a disqualifying
    lifecycle / kind.

    Shared by BOTH `add_facility_trust_anchor_credential` and
    `remove_facility_trust_anchor_credential` deciders: the lifecycle
    guard fires when the Facility is Decommissioned (retired; no further
    trust-anchor changes), the kind guard fires when the Facility is
    kind=Area (Area Facilities inherit the parent Site's trust posture
    and never carry their own trust anchors). Mirrors the Asset precedent
    where `AssetCannotAddAlternateIdentifierError` is shared by add+remove
    deciders. The `reason` string surfaces in the route's 409 body.

    Naming note: the verb "Add" carries over the shared-error convention
    from the Asset precedent even though this class also fires on the
    Remove path. Splitting into a separate `Remove` class would
    duplicate the lifecycle/kind logic across two arms; the shared shape
    keeps both deciders consistent.
    """

    def __init__(
        self,
        facility_id: FacilityId,
        credential_id: CredentialId,
        *,
        reason: str,
    ) -> None:
        super().__init__(
            f"Facility {facility_id} cannot mutate trust anchor for credential "
            f"{credential_id}: {reason}"
        )
        self.facility_id = facility_id
        self.credential_id = credential_id
        self.reason = reason


class FacilityAreaParentMustBeSiteError(Exception):
    """An `Area` Facility was registered with a `parent_id` whose `kind` is not `Site`.

    Day-one `FacilityKind` is closed at `{Site, Area}` with the
    structural rule "Areas live within Sites". Cross-stream parent
    existence + parent-kind=Site checks land in Sub-Slice A of Slice 6
    via the FacilityLookup port. Declarative-constraint shape continues
    the `FacilitySiteCannotHaveParentError` / `FacilityAreaMustHaveParentError`
    sibling-error family. HTTP 422 at the route (invariant violation
    on supplied input, not a missing resource).

    When a future widening adds a third tier (Floor / Building), this
    invariant generalizes; today it is binary Site/Area only.
    """

    def __init__(
        self,
        code: FacilityCode,
        parent_id: FacilityId,
        parent_kind: str,
    ) -> None:
        super().__init__(
            f"Facility {code.value!r} parent_id={parent_id} has kind={parent_kind!r}; "
            "Area-tier facilities must have a Site-tier parent"
        )
        self.code = code
        self.parent_id = parent_id
        self.parent_kind = parent_kind


@dataclass(frozen=True)
class Facility:
    """Aggregate root: a per-code Facility singleton.

    Two-tier identity: `id` is the opaque UUID PK for spine references
    within one deployment; `code` is the cross-deployment convergent
    slug. Cross-BC and cross-deployment references MUST use `code`
    (architecture fitness test enforces this in slice 5 Sub-Slice D).

    Structural invariants enforced in `__post_init__` and re-enforced
    at the `register_facility` decider (belt-and-braces):

      - Site has no parent: `kind == Site` implies
        `parent_id is None` (else `FacilitySiteCannotHaveParentError`).
      - Area has parent: `kind == Area` implies
        `parent_id is not None` (else `FacilityAreaMustHaveParentError`).
      - Area has empty trust anchors: `kind == Area` implies
        `trust_anchor_credential_ids == frozenset()` (else
        `FacilityAreaCannotHaveTrustAnchorsError`).

    Per [[project_fold_symmetry_design]] the genesis envelope
    `occurred_at` is folded onto state as `registered_at` alongside the
    identity denorm `registered_by`. The terminal transition mirrors
    the pair: `decommissioned_at` and `decommissioned_by` are
    populated together by the `FacilityDecommissioned` evolver fold.
    Both `_by` fields are typed `ActorId` so the fold-symmetry fitness
    test detects attribution fields structurally.
    """

    id: FacilityId
    code: FacilityCode
    display_name: FacilityName
    kind: FacilityKind
    parent_id: FacilityId | None
    trust_anchor_credential_ids: frozenset[CredentialId]
    status: FacilityStatus
    persistent_id: PersistentIdentifier | None
    alternate_identifiers: frozenset[AlternateIdentifier]
    registered_at: datetime
    registered_by: ActorId
    decommissioned_at: datetime | None
    decommissioned_by: ActorId | None

    def __post_init__(self) -> None:
        if self.kind is FacilityKind.SITE and self.parent_id is not None:
            raise FacilitySiteCannotHaveParentError(self.code, self.parent_id)
        if self.kind is FacilityKind.AREA and self.parent_id is None:
            raise FacilityAreaMustHaveParentError(self.code)
        if self.kind is FacilityKind.AREA and self.trust_anchor_credential_ids:
            raise FacilityAreaCannotHaveTrustAnchorsError(self.code)


@dataclass(frozen=True)
class FacilityLifecycleTimestamps:
    """Observed wall-clock timestamps surfaced from the Facility projection.

    Placeholder for projection-tier reads; mirrors the
    `CredentialLifecycleTimestamps` shape. Slice 5 Sub-Slice A ships
    only the dataclass; `load_facility_timestamps` is implemented in
    Sub-Slice B alongside the projection writer.

    `registered_at` is NOT carried here; per [[project_fold_symmetry_design]]
    callers read it directly from `Facility.registered_at` (folded
    onto state). `decommissioned_at` likewise reads from
    `Facility.decommissioned_at` once the terminal transition lands.

    Reserved for future fields whose authority is the projection rather
    than the event stream (e.g. last-rebuild-at, observed-row-count).
    The dataclass is empty in Sub-Slice A but kept so the read-tier
    import surface stays stable across the sub-slices.
    """
