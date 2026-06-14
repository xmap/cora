"""Domain events emitted by the Asset aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes,
discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

Event catalog: `AssetRegistered` (genesis), the lifecycle transitions
(`AssetActivated`, `AssetDecommissioned`, `AssetMaintenanceEntered`,
`AssetMaintenanceExited`), the hierarchy mutation
(`AssetRelocated` — the first event whose payload carries source
AND target state, `from_parent_id` + `to_parent_id`, since `parent_id`
is mutable and the audit log should record both sides without
forcing readers to walk the prior event), and the incremental
family-set mutations (`AssetFamilyAdded` / `AssetFamilyRemoved`,
each carrying a single `family_id` that the evolver folds into the
`family_ids` frozenset as new techniques are commissioned or retired).

`AssetDecommissioned`'s source set accepts both ACTIVE and
MAINTENANCE so a faulted asset can be retired without first being
restored.

## Payload conventions for Asset

`tier` IS carried in the payload (set at registration, never
changes; no `AssetTierChanged` event in scope). The evolver
reconstructs via `AssetTier(payload["tier"])`.

`parent_id` IS carried in the AssetRegistered payload (sets the
initial value). For mutations, AssetRelocated carries BOTH
`from_parent_id` and `to_parent_id` — the only event in the
codebase to date with source-state in the payload (most
transitions encode the source via the event TYPE; this one needs
explicit source because parent_id is a value with many possible
prior states, not a discrete state-machine state). Serialized as
`str(parent_id)` or `None` (Optional fits naturally into JSON).

`reason` on AssetRelocated is free-text (validated at the API
boundary, not by a domain VO) — operators include why the move
happened (commissioning move, maintenance reorganization,
decommissioning to storage, etc).

`lifecycle` is NOT carried in the payload — the event TYPE
encodes the state change (`AssetRegistered → COMMISSIONED`).
Same precedent as Subject / Family / Actor.

`drawing` on AssetRegistered uses the omit-when-None convention:
the payload key is absent when no Drawing was supplied (rather
than written as JSON null). `from_stored` uses `payload.get(...)`
so legacy events written before the drawing field landed fold
cleanly to `drawing=None`. Mount took the opposite convention
(always-present-with-null) because MountRegistered carried
drawing from genesis; Asset's omit-when-None is the strict
additive-evolution shape and matches the `AssetSettingsUpdated`
precedent (also payload.get-based).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates._partition_rule import (
    PartitionRule,
    partition_rule_from_payload,
    partition_rule_to_payload,
)
from cora.equipment.aggregates.asset.state import (
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
)
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.facility_code import FacilityCode, InvalidFacilityCodeError
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    MalformedPersistentIdentifierError,
    PersistentIdentifierScheme,
)
from cora.shared.identity import ActorId


def _owner_to_payload(owner: AssetOwner) -> dict[str, Any]:
    """Serialize an `AssetOwner` VO to a stable-shape dict for jsonb.

    Always emits the same key order (`name`, `contact`, `identifier`,
    `identifier_type`) regardless of the VO's defaulted fields. Each
    optional value is rendered as `None` when absent so the wire shape
    of an `AssetOwner` block stays uniform across rows; the
    projection's JSONB sort key reads `name` consistently.
    """
    return {
        "name": owner.name.value,
        "contact": owner.contact.value if owner.contact is not None else None,
        "identifier": owner.identifier.value if owner.identifier is not None else None,
        "identifier_type": (
            owner.identifier_type.value if owner.identifier_type is not None else None
        ),
    }


def _owner_from_payload(entry: dict[str, Any]) -> AssetOwner:
    """Rebuild an `AssetOwner` VO from a stored-event payload dict.

    Returns the VO; any `ValueError` raised by the VOs is caught by
    the surrounding `deserialize_or_raise(extra=(ValueError,))` wrap.
    """
    raw_contact = entry.get("contact")
    raw_identifier = entry.get("identifier")
    raw_identifier_type = entry.get("identifier_type")
    return AssetOwner(
        name=AssetOwnerName(entry["name"]),
        contact=AssetOwnerContact(raw_contact) if raw_contact is not None else None,
        identifier=(AssetOwnerIdentifier(raw_identifier) if raw_identifier is not None else None),
        identifier_type=(
            AssetOwnerIdentifierType(raw_identifier_type)
            if raw_identifier_type is not None
            else None
        ),
    )


@dataclass(frozen=True)
class AssetRegistered:
    """A new asset was registered with the facility.

    Lifecycle is implicit (`Commissioned`) — the evolver sets it.
    `parent_id` is optional: a root Asset has a null parent and binds
    `facility_code` instead; a non-root carries `parent_id`. The
    `{parent_id, facility_code}` XOR rule is enforced at the decider.

    `drawing` is an optional Drawing VO captured at registration:
    the engineering build-to spec for the physical specimen. Defaults
    to None so legacy AssetRegistered streams (no drawing in the
    payload) fold cleanly via the additive-payload pattern.

    `model_id` is an optional reference to the Model catalog entry
    this Asset is an instance of (Family -> Model -> Assembly ->
    Asset ladder). Set at registration per the model-binding design
    memo (Lock A); rebind path is decommission + re-register.
    Defaults to None so legacy AssetRegistered streams (no model_id
    in the payload) fold cleanly via the additive-payload pattern;
    `to_payload` uses the omit-when-None convention (key absent
    rather than serialized as JSON null) to mirror the `drawing`
    precedent.

    `alternate_identifiers` is an optional frozenset of PIDINST
    Property 13 alternate identifiers seeded at registration. The
    field defaults to an empty frozenset so legacy AssetRegistered
    streams (no `alternate_identifiers` key in the payload) fold
    cleanly via the additive-payload pattern; `to_payload` uses the
    omit-when-empty convention (key absent rather than serialized as
    `[]`) to mirror the `drawing` / `model_id` precedents. See
    [[project-asset-alternate-identifiers-design]] Locks A and D.

    `owners` is an optional frozenset of PIDINST v1.0 Property 5
    owner blocks (institutional bodies owning or curating the
    instrument) seeded at registration. Defaults to an empty
    frozenset so legacy AssetRegistered streams (no `owners` key in
    the payload) fold cleanly via the additive-payload pattern;
    `to_payload` uses the omit-when-empty convention mirroring the
    `alternate_identifiers` precedent. The aggregate allows 0-n
    owners; PIDINST 1-n MANDATORY cardinality is enforced at the
    serializer boundary, not here. See
    [[project-asset-owner-design]] Locks 1, 7, 11.

    `controller_id` is an optional reference to the controller Asset
    (a sibling Device carrying the MotionController Family) that
    drives this Asset. Set at registration per the
    [[project-controller-as-asset-stage1-design]] memo (Lock A
    precedent from model_id); rebind path is decommission + re-
    register. Defaults to None so legacy AssetRegistered streams
    without the field fold cleanly via the additive-payload pattern;
    `to_payload` uses the omit-when-None convention (key absent
    rather than serialized as JSON null) to mirror the `drawing` /
    `model_id` precedents.

    `located_in_enclosure_id` is an optional bare cross-BC opaque
    pointer to the Enclosure (the operational access-gated volume)
    this Asset is located in (its OPERATIONAL where, distinct from
    `facility_code`, its INSTITUTIONAL where). Set at registration per
    the Lock A precedent (mirrors `controller_id`); rebind path is
    decommission + re-register. Defaults to None so legacy
    AssetRegistered streams without the field fold cleanly via the
    additive-payload pattern; `to_payload` uses the omit-when-None
    convention (key absent rather than serialized as JSON null) to
    mirror the `controller_id` / `model_id` precedents. Kept a bare
    `UUID` so the Equipment BC takes on no module dependency on the
    Enclosure BC.

    `facility_code` is an optional cross-BC reference to the
    Federation Facility that owns this Asset, keyed on the
    cross-deployment convergent slug (`FacilityCode`) per
    [[project-slice8-design]] L1. The typed VO carries through the
    aggregate state; the payload key serializes as the bare-str
    `.value` (matching the Permit / Credential / Seal wire convention
    of bare-str disk payloads + typed `FacilityCode` VO on aggregate
    state). `from_stored` wraps `FacilityCode(payload["facility_code"])`
    with `extra=(InvalidFacilityCodeError,)` so malformed slugs in
    stored events surface as `Malformed AssetRegistered payload`
    rather than silently passing the VO's
    `InvalidFacilityCodeError` upstream. Defaults to None so legacy
    AssetRegistered streams (no `facility_code` key in the payload)
    fold cleanly via the additive-payload pattern; `to_payload`
    OMITS the key when None per the Supply Slice 7A
    `containing_asset_id` precedent.
    """

    asset_id: UUID
    name: str
    tier: str  # AssetTier.value; carried as primitive in the payload
    parent_id: UUID | None
    occurred_at: datetime
    commissioned_by: ActorId
    drawing: Drawing | None = None
    model_id: UUID | None = None
    # Parametrized default_factory for the empty frozenset trick used
    # across Asset / Method / Mount: the empty frozenset has no
    # element type for pyright to infer under strict, so the
    # parametrized callable is supplied as the factory.
    alternate_identifiers: frozenset[AlternateIdentifier] = field(
        default_factory=frozenset[AlternateIdentifier]
    )
    owners: frozenset[AssetOwner] = field(default_factory=frozenset[AssetOwner])
    controller_id: UUID | None = None
    located_in_enclosure_id: UUID | None = None
    facility_code: FacilityCode | None = None


@dataclass(frozen=True)
class AssetActivated:
    """An asset transitioned into service.

    Lifecycle transition: `Commissioned -> Active`. The evolver
    sets the new lifecycle; no lifecycle field in the payload.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetDecommissioned:
    """An asset was retired from service.

    Lifecycle transition: `Commissioned | Active -> Decommissioned`
    (multi-source; widens to include Maintenance). The
    evolver sets the new lifecycle regardless of which source state
    the asset came from; the decider's source-state guard is what
    enforces the multi-source restriction at command time.

    `decommissioned_by` records the principal that issued the
    decommission_asset command; folded onto `Asset.decommissioned_by`
    by the evolver per [[project-fold-symmetry-design]].
    """

    asset_id: UUID
    occurred_at: datetime
    decommissioned_by: ActorId


@dataclass(frozen=True)
class AssetMaintenanceEntered:
    """An asset was taken out of service for maintenance.

    Lifecycle transition: `Active -> Maintenance` (single-source).
    The evolver sets the new lifecycle; no lifecycle field in the
    payload (event TYPE encodes the change). Same convention as
    AssetActivated.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetMaintenanceExited:
    """An asset was returned to active service after maintenance.

    Lifecycle transition: `Maintenance -> Active` (single-source).
    The evolver sets the new lifecycle; no lifecycle field in the
    payload (event TYPE encodes the change). Mirrors
    `AssetMaintenanceEntered` shape exactly with symmetric
    enter/exit preposition.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetFamilyAdded:
    """A Family was added to an asset's family set.

    Single-family event (not bulk-update). Capabilities accumulate
    as operators commission new techniques on the asset; each event
    captures a single addition for clean audit trails ("when did this
    asset gain XRF Mapping?"). The evolver inserts the family_id
    into `state.family_ids` (frozenset semantics → no-op on
    duplicate at the evolver layer; the decider's strict-not-idempotent
    guard is what enforces "must not already be present" at command
    time).

    Eventual-consistency: `family_id` is NOT verified against the
    Family stream. Same precedent as Conduit zone refs (3b),
    Asset parent refs (5b), Method.needed_family_ids (6a).
    """

    asset_id: UUID
    family_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetFamilyRemoved:
    """A Family was removed from an asset's family set.

    Mirror of `AssetFamilyAdded`. Single-family event; the
    evolver removes the family_id from `state.family_ids`. The
    decider's strict-not-idempotent guard enforces "must currently be
    present" at command time.
    """

    asset_id: UUID
    family_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetDegraded:
    """An asset's condition transitioned to `Degraded`.

    Condition transition: any condition -> Degraded (target-state
    semantics, mirrors `enter_asset_maintenance`'s lifecycle target). The
    evolver sets the new condition; no condition field in the
    payload (event TYPE encodes the change).

    `reason` is operator-supplied free text (for example "hot pixel detected
    at (12, 42)"); validated 1-500 chars at the API boundary, the
    decider trusts the input. Same precedent as `AssetRelocated.reason`.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetFaulted:
    """An asset's condition transitioned to `Faulted`.

    Condition transition: any condition -> Faulted. Mirror of
    `AssetDegraded`. Operationally: device is down, requires repair
    before any further use.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetRestored:
    """An asset's condition transitioned to `Nominal`.

    Condition transition: any condition -> Nominal. Mirror of
    `AssetDegraded`. Operationally: device fully repaired and back
    to normal operating specs. Partial repairs (Faulted -> Degraded)
    use `degrade_asset`, NOT `restore_asset` with a target arg —
    each slice has a fixed target.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetPortAdded:
    """A typed port was added to an Asset's port set (5h).

    Single-port event (not bulk-add), mirrors `AssetFamilyAdded`.
    Audit value: "when did this Asset gain a `sync_clock` port?"

    `port_name`, `direction`, and `signal_type` are the three
    components of the AssetPort VO; carried as primitives in the
    event payload so the from_stored reconstruction can rebuild the
    VO without reading the state.
    """

    asset_id: UUID
    port_name: str
    direction: str  # PortDirection.value (StrEnum)
    signal_type: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetPortRemoved:
    """A typed port was removed from an Asset's port set (5h).

    Mirror of `AssetPortAdded`. Carries only `port_name` because
    that is the unique key on Asset.ports — the decider's evolver
    pre-image gives the removed port's full shape if a future reader
    needs it. Symmetric with `AssetFamilyRemoved`.
    """

    asset_id: UUID
    port_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetAlternateIdentifierAdded:
    """An alternate identifier (PIDINST Property 13) was added to an Asset.

    Single-identifier event mirroring `AssetPortAdded` /
    `AssetFamilyAdded`. Audit value: "when did this Asset gain the
    `InventoryNumber=APS-2BM-CAM-001` tag?"

    The full `AlternateIdentifier` VO (kind + value) travels in the
    payload as two primitives — `kind` is the StrEnum value, `value`
    is the trimmed string — so `from_stored` reconstructs the VO
    without reading prior state. Mirrors `AssetPortAdded`'s
    (port_name, direction, signal_type) primitive carry. The decider
    enforces strict-not-idempotent semantics at command time per
    [[project-asset-alternate-identifiers-design]] Lock E.
    """

    asset_id: UUID
    alternate_identifier: AlternateIdentifier
    occurred_at: datetime


@dataclass(frozen=True)
class AssetAlternateIdentifierRemoved:
    """An alternate identifier (PIDINST Property 13) was removed from an Asset.

    Mirror of `AssetAlternateIdentifierAdded`. The full
    `AlternateIdentifier` VO (kind + value) travels in the payload so
    the audit reader can see exactly which identifier was removed
    without folding back through prior events; symmetric with the
    Added event (the Port mirror carries only `port_name` because
    `name` is the unique key on `AssetPort`, whereas here uniqueness
    keys on the full `(kind, value)` tuple).
    """

    asset_id: UUID
    alternate_identifier: AlternateIdentifier
    occurred_at: datetime


@dataclass(frozen=True)
class AssetOwnerAdded:
    """An institutional owner block (PIDINST Property 5) was added to an Asset.

    Single-owner event mirroring `AssetAlternateIdentifierAdded`. Audit
    value: "when did this Asset first gain HZB as an owner?"

    The full `AssetOwner` VO (name + optional contact + paired
    identifier/identifier_type) travels in the payload so `from_stored`
    reconstructs the VO without reading prior state. The decider
    enforces uniqueness on `name` at command time per
    [[project-asset-owner-design]] Locks 5 and 6.
    """

    asset_id: UUID
    owner: AssetOwner
    occurred_at: datetime


@dataclass(frozen=True)
class AssetOwnerRemoved:
    """An institutional owner block was removed from an Asset.

    Mirror of `AssetOwnerAdded` but keyed on `owner_name` only per
    [[project-asset-owner-design]] Lock 5: operator commands say
    "remove HZB", not "remove HZB with contact X and identifier Y".
    The smaller payload also keeps the audit log readable when an
    operator scans the event stream after a long curation gap. The
    decider rejects an unknown name at command time
    (`AssetOwnerNotPresentError`) per Lock 6's name-key uniqueness.
    """

    asset_id: UUID
    owner_name: AssetOwnerName
    occurred_at: datetime


@dataclass(frozen=True)
class AssetFacilityCodeAssigned:
    """A facility_code (cross-BC binding to a Federation Facility) was
    assigned to an Asset post-genesis via the bind_asset_to_facility
    slice.

    Set-once at the aggregate level: the decider's
    `AssetFacilityCodeAlreadyAssignedError` enforces "must currently be
    absent" at command time, so the stream can contain AT MOST ONE
    `AssetFacilityCodeAssigned` event per Asset (the `register_asset`
    genesis path can also pre-assign via `AssetRegistered.facility_code`;
    in that case `bind_asset_to_facility` is rejected as already-set).

    The typed `FacilityCode` VO travels in the payload as the bare
    `.value` string on disk per the Permit / Credential / Seal wire
    convention; `from_stored` re-wraps with `FacilityCode(...)` inside
    `deserialize_or_raise` with
    `extra=(InvalidFacilityCodeError, ValueError)` so malformed slugs
    in stored events surface as `Malformed AssetFacilityCodeAssigned
    payload` rather than silently passing the VO's
    `InvalidFacilityCodeError` upstream.

    `occurred_at` + `assigned_by` carry the fold-symmetry attribution
    pair: every transversal-time fact is paired with a transversal-
    attribution fact (`assigned_by: ActorId`).
    """

    asset_id: UUID
    facility_code: FacilityCode
    occurred_at: datetime
    assigned_by: ActorId


@dataclass(frozen=True)
class AssetPersistentIdAssigned:
    """A persistent identifier (PIDINST v1.0 Property 1) was assigned to an Asset.

    Single-assign event. Set-once at the aggregate level: the
    decider's `AssetPersistentIdAlreadyAssignedError` enforces "must
    currently be absent" at command time, so the stream can contain
    AT MOST ONE `AssetPersistentIdAssigned` event per Asset.

    The full `PersistentIdentifier` VO (scheme + value) travels in the
    payload as two primitives, mirroring `AssetPortAdded`'s
    (port_name, direction, signal_type) primitive carry: scheme is the
    StrEnum value, value is the trimmed string. This lets `from_stored`
    rebuild the VO without reading prior state.

    No `withdrawn_at` / `withdrawal_reason` on this event: F.1 does not
    model withdrawal. A future slice G adds a sibling
    `AssetPersistentIdWithdrawn` event when operator demand fires.
    """

    asset_id: UUID
    persistent_id_scheme: str
    persistent_id_value: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetSettingsUpdated:
    """An asset's settings dict was set / replaced via the
    update_asset_settings slice (5g-c).

    The payload carries the FULL post-merge dict (`settings`), NOT
    the patch (`settings_patch`) that was submitted. Readers
    reconstruct current state without folding back through prior
    events; the audit log answers "what is true at time T", not
    "what changed between T and T-1". Trade-off: payloads are
    slightly larger than carrying the diff, but for typical settings
    dicts (5-30 keys) it's a non-issue.

    The handler validates the post-merge dict against the union of
    currently-assigned Capabilities' settings_schemas BEFORE
    emitting; an event in the stream means validation passed at the
    moment of write. Family schemas changing later does NOT
    auto-revalidate existing settings (locked design; see the 5g-c
    memo).
    """

    asset_id: UUID
    settings: dict[str, Any]
    occurred_at: datetime


@dataclass(frozen=True)
class AssetPartitionRuleUpdated:
    """A PseudoAxis Asset's partition rule was set, changed, or cleared
    via the update_asset_partition_rule slice.

    Single event covers genesis (None -> rule), mutation (rule -> rule'),
    and removal (rule -> None). Mirrors the AssetSettingsUpdated precedent
    (one event covers set + update + clear).

    Payload `partition_rule` is None when the operator cleared the rule;
    otherwise it is the serialized typed-VO with the `kind` discriminator
    plus per-kind fields. The discriminated union codec lives at
    `cora.equipment.aggregates._partition_rule.partition_rule_to_payload`
    and `partition_rule_from_payload`; from_stored re-runs the per-shape
    `__post_init__` validators, so a malformed event payload fails loud
    rather than folding into invalid state.

    Genesis detection (was-the-prior-rule-None) is reconstructable from
    the event stream by replay: the first AssetPartitionRuleUpdated
    payload with non-None partition_rule on a stream is the genesis.
    No separate AssetPartitionRuleSet event ships (matches
    AssetSettingsUpdated precedent; rejected as overspecification in
    the round-2 gate review).
    """

    asset_id: UUID
    partition_rule: PartitionRule | None
    occurred_at: datetime


@dataclass(frozen=True)
class AssetRelocated:
    """An asset's parent in the hierarchy tree changed.

    Hierarchy mutation: `parent_id: from_parent_id -> to_parent_id`.
    Lifecycle is unchanged. Carries BOTH source and target parent
    in the payload — the audit log should record both sides without
    requiring readers to walk the prior event. `reason` is operator-
    supplied free text (for example "moved from storage to BL2-IBP", "site
    reorganization 2026-Q3").

    Per BC map: `from_parent_id` is the prior parent, `to_parent_id`
    is the new parent. Both non-null for any non-root asset
    (a root can't relocate per the decider's anchoring guard).
    """

    asset_id: UUID
    from_parent_id: UUID
    to_parent_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetAttachedToFixture:
    """The Asset was bound into a Fixture (registered Assembly materialization).

    Sets the Asset's `fixture_id` back-reference. The Fixture side
    carries the slot_name in its `slot_asset_bindings`; this event
    only records the back-pointer so the conformance projection can
    answer "what Fixture is this Asset in?" in O(1).
    """

    asset_id: UUID
    fixture_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetDetachedFromFixture:
    """The Asset was unbound from a Fixture (clears fixture_id back-reference).

    Payload carries the prior fixture_id for audit trail. After this
    event, Asset.fixture_id is None and the Asset is free to attach
    to another Fixture (or stand alone). The Fixture's own
    slot_asset_bindings stays unchanged (single-event-stream invariant);
    the conformance projection notices the gap and reports the
    Fixture as having a missing Asset binding.
    """

    asset_id: UUID
    fixture_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Asset aggregate emits.
# Add new event classes above and extend this alias when new
# slices land.
AssetEvent = (
    AssetRegistered
    | AssetActivated
    | AssetDecommissioned
    | AssetRelocated
    | AssetMaintenanceEntered
    | AssetMaintenanceExited
    | AssetFamilyAdded
    | AssetFamilyRemoved
    | AssetDegraded
    | AssetFaulted
    | AssetRestored
    | AssetSettingsUpdated
    | AssetPartitionRuleUpdated
    | AssetPortAdded
    | AssetPortRemoved
    | AssetAlternateIdentifierAdded
    | AssetAlternateIdentifierRemoved
    | AssetOwnerAdded
    | AssetOwnerRemoved
    | AssetPersistentIdAssigned
    | AssetAttachedToFixture
    | AssetDetachedFromFixture
    | AssetFacilityCodeAssigned
)


def event_type_name(event: AssetEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: AssetEvent) -> dict[str, Any]:
    """Serialize an Asset event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, optional UUIDs become string-or-None.
    """
    match event:
        case AssetRegistered(
            asset_id=asset_id,
            name=name,
            tier=tier,
            parent_id=parent_id,
            occurred_at=occurred_at,
            commissioned_by=commissioned_by,
            drawing=drawing,
            model_id=model_id,
            alternate_identifiers=alternate_identifiers,
            owners=owners,
            controller_id=controller_id,
            located_in_enclosure_id=located_in_enclosure_id,
            facility_code=facility_code,
        ):
            payload: dict[str, Any] = {
                "asset_id": str(asset_id),
                "name": name,
                "tier": tier,
                "parent_id": str(parent_id) if parent_id is not None else None,
                "occurred_at": occurred_at.isoformat(),
                "commissioned_by": str(commissioned_by),
            }
            if drawing is not None:
                payload["drawing"] = {
                    "system": drawing.system.value,
                    "number": drawing.number,
                    "revision": drawing.revision,
                }
            if model_id is not None:
                payload["model_id"] = str(model_id)
            if controller_id is not None:
                # Omit-when-None mirroring the model_id / drawing
                # precedent: legacy AssetRegistered streams (pre-
                # controller-as-Asset slice) had no `controller_id`
                # key; preserve that wire shape so existing readers
                # cannot observe a JSON null where the key was
                # previously absent.
                payload["controller_id"] = str(controller_id)
            if located_in_enclosure_id is not None:
                # Omit-when-None mirroring the controller_id / model_id
                # precedent: legacy AssetRegistered streams (pre-
                # enclosure-location slice) had no `located_in_enclosure_id`
                # key; preserve that wire shape so existing readers
                # cannot observe a JSON null where the key was previously
                # absent. Bare opaque UUID string on disk.
                payload["located_in_enclosure_id"] = str(located_in_enclosure_id)
            if facility_code is not None:
                # Omit-when-None mirroring the controller_id / model_id
                # precedent (and the Supply facility_code precedent on
                # SupplyRegistered's payload): legacy AssetRegistered
                # streams had no `facility_code` key; preserve that wire
                # shape so existing readers cannot observe a JSON null
                # where the key was previously absent. Bare `.value` on
                # disk per the Permit / Credential / Seal wire convention.
                payload["facility_code"] = facility_code.value
            if alternate_identifiers:
                # Omit-when-empty: legacy AssetRegistered shape had no
                # `alternate_identifiers` key; preserve that wire shape
                # so existing stream readers can't accidentally observe
                # an empty list where the key was previously absent.
                # Sorted by (kind, value) so payload bytes are stable
                # under the equivalent VO set (frozenset iteration is
                # nondeterministic; canonical bytes matter for any
                # future signing/hashing slice).
                payload["alternate_identifiers"] = [
                    {"kind": identifier.kind.value, "value": identifier.value}
                    for identifier in sorted(
                        alternate_identifiers,
                        key=lambda ident: (ident.kind.value, ident.value),
                    )
                ]
            if owners:
                # Omit-when-empty mirroring the alternate_identifiers
                # precedent. Sorted by `name` so payload bytes are
                # stable under the equivalent VO set; the projection
                # writer re-sorts defensively at insert time too.
                payload["owners"] = [
                    _owner_to_payload(owner) for owner in sorted(owners, key=lambda o: o.name.value)
                ]
            return payload
        case AssetActivated(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetDecommissioned(
            asset_id=asset_id,
            occurred_at=occurred_at,
            decommissioned_by=decommissioned_by,
        ):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
                "decommissioned_by": str(decommissioned_by),
            }
        case AssetRelocated(
            asset_id=asset_id,
            from_parent_id=from_parent_id,
            to_parent_id=to_parent_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "from_parent_id": str(from_parent_id),
                "to_parent_id": str(to_parent_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetMaintenanceEntered(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetMaintenanceExited(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetFamilyAdded(
            asset_id=asset_id,
            family_id=family_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "family_id": str(family_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetFamilyRemoved(
            asset_id=asset_id,
            family_id=family_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "family_id": str(family_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetDegraded(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetFaulted(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetRestored(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetSettingsUpdated(asset_id=asset_id, settings=settings, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "settings": settings,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetPartitionRuleUpdated(
            asset_id=asset_id,
            partition_rule=partition_rule,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "partition_rule": (
                    partition_rule_to_payload(partition_rule)
                    if partition_rule is not None
                    else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetPortAdded(
            asset_id=asset_id,
            port_name=port_name,
            direction=direction,
            signal_type=signal_type,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "port_name": port_name,
                "direction": direction,
                "signal_type": signal_type,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetPortRemoved(asset_id=asset_id, port_name=port_name, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "port_name": port_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetAlternateIdentifierAdded(
            asset_id=asset_id,
            alternate_identifier=identifier,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "alternate_identifier": {
                    "kind": identifier.kind.value,
                    "value": identifier.value,
                },
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetAlternateIdentifierRemoved(
            asset_id=asset_id,
            alternate_identifier=identifier,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "alternate_identifier": {
                    "kind": identifier.kind.value,
                    "value": identifier.value,
                },
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetOwnerAdded(
            asset_id=asset_id,
            owner=owner,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "owner": _owner_to_payload(owner),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetOwnerRemoved(
            asset_id=asset_id,
            owner_name=owner_name,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "owner_name": owner_name.value,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetPersistentIdAssigned(
            asset_id=asset_id,
            persistent_id_scheme=scheme,
            persistent_id_value=value,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "persistent_id_scheme": scheme,
                "persistent_id_value": value,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetAttachedToFixture(
            asset_id=asset_id,
            fixture_id=fixture_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "fixture_id": str(fixture_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetDetachedFromFixture(
            asset_id=asset_id,
            fixture_id=fixture_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "fixture_id": str(fixture_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetFacilityCodeAssigned(
            asset_id=asset_id,
            facility_code=facility_code,
            occurred_at=occurred_at,
            assigned_by=assigned_by,
        ):
            return {
                "asset_id": str(asset_id),
                "facility_code": facility_code.value,
                "occurred_at": occurred_at.isoformat(),
                "assigned_by": str(assigned_by),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> AssetEvent:
    """Rebuild an Asset event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "AssetRegistered":

            def _build_registered() -> AssetRegistered:
                raw_parent = payload["parent_id"]
                raw_drawing = payload.get("drawing")
                drawing = (
                    Drawing(
                        system=DrawingSystem(raw_drawing["system"]),
                        number=raw_drawing["number"],
                        revision=raw_drawing.get("revision"),
                    )
                    if raw_drawing is not None
                    else None
                )
                raw_model_id = payload.get("model_id")
                model_id = UUID(raw_model_id) if raw_model_id is not None else None
                raw_controller_id = payload.get("controller_id")
                controller_id = UUID(raw_controller_id) if raw_controller_id is not None else None
                raw_located_in_enclosure_id = payload.get("located_in_enclosure_id")
                located_in_enclosure_id = (
                    UUID(raw_located_in_enclosure_id)
                    if raw_located_in_enclosure_id is not None
                    else None
                )
                raw_facility_code = payload.get("facility_code")
                facility_code = (
                    FacilityCode(raw_facility_code) if raw_facility_code is not None else None
                )
                raw_alt_ids = payload.get("alternate_identifiers", [])
                alternate_identifiers = frozenset(
                    AlternateIdentifier(
                        kind=AlternateIdentifierKind(entry["kind"]),
                        value=entry["value"],
                    )
                    for entry in raw_alt_ids
                )
                raw_owners = payload.get("owners", [])
                owners = frozenset(_owner_from_payload(entry) for entry in raw_owners)
                return AssetRegistered(
                    asset_id=UUID(payload["asset_id"]),
                    name=payload["name"],
                    tier=payload["tier"],
                    parent_id=UUID(raw_parent) if raw_parent is not None else None,
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    commissioned_by=ActorId(UUID(payload["commissioned_by"])),
                    drawing=drawing,
                    model_id=model_id,
                    alternate_identifiers=alternate_identifiers,
                    owners=owners,
                    controller_id=controller_id,
                    located_in_enclosure_id=located_in_enclosure_id,
                    facility_code=facility_code,
                )

            return deserialize_or_raise(
                "AssetRegistered",
                _build_registered,
                extra=(InvalidFacilityCodeError, ValueError),
            )
        case "AssetActivated":
            return deserialize_or_raise(
                "AssetActivated",
                lambda: AssetActivated(
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetDecommissioned":
            return deserialize_or_raise(
                "AssetDecommissioned",
                lambda: AssetDecommissioned(
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    decommissioned_by=ActorId(UUID(payload["decommissioned_by"])),
                ),
            )
        case "AssetRelocated":
            return deserialize_or_raise(
                "AssetRelocated",
                lambda: AssetRelocated(
                    asset_id=UUID(payload["asset_id"]),
                    from_parent_id=UUID(payload["from_parent_id"]),
                    to_parent_id=UUID(payload["to_parent_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetMaintenanceEntered":
            return deserialize_or_raise(
                "AssetMaintenanceEntered",
                lambda: AssetMaintenanceEntered(
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetMaintenanceExited":
            return deserialize_or_raise(
                "AssetMaintenanceExited",
                lambda: AssetMaintenanceExited(
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetFamilyAdded":
            return deserialize_or_raise(
                "AssetFamilyAdded",
                lambda: AssetFamilyAdded(
                    asset_id=UUID(payload["asset_id"]),
                    family_id=UUID(payload["family_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetFamilyRemoved":
            return deserialize_or_raise(
                "AssetFamilyRemoved",
                lambda: AssetFamilyRemoved(
                    asset_id=UUID(payload["asset_id"]),
                    family_id=UUID(payload["family_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetDegraded":
            return deserialize_or_raise(
                "AssetDegraded",
                lambda: AssetDegraded(
                    asset_id=UUID(payload["asset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetFaulted":
            return deserialize_or_raise(
                "AssetFaulted",
                lambda: AssetFaulted(
                    asset_id=UUID(payload["asset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetRestored":
            return deserialize_or_raise(
                "AssetRestored",
                lambda: AssetRestored(
                    asset_id=UUID(payload["asset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetSettingsUpdated":
            return deserialize_or_raise(
                "AssetSettingsUpdated",
                lambda: AssetSettingsUpdated(
                    asset_id=UUID(payload["asset_id"]),
                    settings=payload.get("settings", {}),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetPartitionRuleUpdated":
            return deserialize_or_raise(
                "AssetPartitionRuleUpdated",
                lambda: AssetPartitionRuleUpdated(
                    asset_id=UUID(payload["asset_id"]),
                    partition_rule=(
                        partition_rule_from_payload(payload["partition_rule"])
                        if payload.get("partition_rule") is not None
                        else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetPortAdded":
            return deserialize_or_raise(
                "AssetPortAdded",
                lambda: AssetPortAdded(
                    asset_id=UUID(payload["asset_id"]),
                    port_name=payload["port_name"],
                    direction=payload["direction"],
                    signal_type=payload["signal_type"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetPortRemoved":
            return deserialize_or_raise(
                "AssetPortRemoved",
                lambda: AssetPortRemoved(
                    asset_id=UUID(payload["asset_id"]),
                    port_name=payload["port_name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetAlternateIdentifierAdded":
            return deserialize_or_raise(
                "AssetAlternateIdentifierAdded",
                lambda: AssetAlternateIdentifierAdded(
                    asset_id=UUID(payload["asset_id"]),
                    alternate_identifier=AlternateIdentifier(
                        kind=AlternateIdentifierKind(
                            payload["alternate_identifier"]["kind"],
                        ),
                        value=payload["alternate_identifier"]["value"],
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "AssetAlternateIdentifierRemoved":
            return deserialize_or_raise(
                "AssetAlternateIdentifierRemoved",
                lambda: AssetAlternateIdentifierRemoved(
                    asset_id=UUID(payload["asset_id"]),
                    alternate_identifier=AlternateIdentifier(
                        kind=AlternateIdentifierKind(
                            payload["alternate_identifier"]["kind"],
                        ),
                        value=payload["alternate_identifier"]["value"],
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "AssetOwnerAdded":
            return deserialize_or_raise(
                "AssetOwnerAdded",
                lambda: AssetOwnerAdded(
                    asset_id=UUID(payload["asset_id"]),
                    owner=_owner_from_payload(payload["owner"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "AssetOwnerRemoved":
            return deserialize_or_raise(
                "AssetOwnerRemoved",
                lambda: AssetOwnerRemoved(
                    asset_id=UUID(payload["asset_id"]),
                    owner_name=AssetOwnerName(payload["owner_name"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "AssetPersistentIdAssigned":

            def _build_persistent_id_assigned() -> AssetPersistentIdAssigned:
                scheme = PersistentIdentifierScheme(payload["persistent_id_scheme"])
                value = payload["persistent_id_value"]
                if not isinstance(value, str) or not value.strip():
                    raise MalformedPersistentIdentifierError(
                        f"persistent_id_value must be a non-empty string (got: {value!r})"
                    )
                return AssetPersistentIdAssigned(
                    asset_id=UUID(payload["asset_id"]),
                    persistent_id_scheme=scheme.value,
                    persistent_id_value=value,
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise(
                "AssetPersistentIdAssigned",
                _build_persistent_id_assigned,
                extra=(ValueError, MalformedPersistentIdentifierError),
            )
        case "AssetAttachedToFixture":
            return deserialize_or_raise(
                "AssetAttachedToFixture",
                lambda: AssetAttachedToFixture(
                    asset_id=UUID(payload["asset_id"]),
                    fixture_id=UUID(payload["fixture_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetDetachedFromFixture":
            return deserialize_or_raise(
                "AssetDetachedFromFixture",
                lambda: AssetDetachedFromFixture(
                    asset_id=UUID(payload["asset_id"]),
                    fixture_id=UUID(payload["fixture_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetFacilityCodeAssigned":
            return deserialize_or_raise(
                "AssetFacilityCodeAssigned",
                lambda: AssetFacilityCodeAssigned(
                    asset_id=UUID(payload["asset_id"]),
                    facility_code=FacilityCode(payload["facility_code"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    assigned_by=ActorId(UUID(payload["assigned_by"])),
                ),
                extra=(InvalidFacilityCodeError, ValueError),
            )
        case _:
            msg = f"Unknown AssetEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AssetActivated",
    "AssetAlternateIdentifierAdded",
    "AssetAlternateIdentifierRemoved",
    "AssetAttachedToFixture",
    "AssetDecommissioned",
    "AssetDegraded",
    "AssetDetachedFromFixture",
    "AssetEvent",
    "AssetFacilityCodeAssigned",
    "AssetFamilyAdded",
    "AssetFamilyRemoved",
    "AssetFaulted",
    "AssetMaintenanceEntered",
    "AssetMaintenanceExited",
    "AssetOwnerAdded",
    "AssetOwnerRemoved",
    "AssetPartitionRuleUpdated",
    "AssetPersistentIdAssigned",
    "AssetPortAdded",
    "AssetPortRemoved",
    "AssetRegistered",
    "AssetRelocated",
    "AssetRestored",
    "AssetSettingsUpdated",
    "event_type_name",
    "from_stored",
    "to_payload",
]
