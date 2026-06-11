"""The `RegisterAsset` command, intent dataclass for this slice.

Carries the caller-controlled fields: the asset's display name,
its operational tier, its parent_id (None only for facility-rooted
Assets, enforced by the decider), an optional Drawing reference, and
an optional `model_id` Model-binding ref. Server-side concerns (new
aggregate id, wall-clock timestamp, correlation id, per-event ids)
are injected by the handler from infrastructure ports, matching the
cross-BC create-style command shape locked in Access / Trust /
Subject / Equipment.

`tier` is typed as `AssetTier` (the StrEnum) so callers cannot
pass an invalid value; the route's Pydantic body and the MCP
tool's argument schema both enforce this at the API boundary.

`parent_id` is `UUID | None`. Per the `{parent_id, facility_code}`
XOR rule, a root Asset has `parent_id=None` and binds
`facility_code`; a non-root carries `parent_id` and no
`facility_code`. Eventual-consistency stance for the parent ref:
the decider does NOT verify the referenced parent Asset exists in
the event store (same precedent as Trust's Conduit zone refs).

`model_id` is `UUID | None`, optional reference to the Model
catalog entry this Asset is an instance of. Set ONCE at
registration per the model-binding design memo (Lock A); rebind
path is decommission + re-register. The handler verifies the
referenced Model stream exists before invoking the decider
(`ModelNotFoundError` -> 404); the decider does NOT need a Model
snapshot because the genesis Asset's families set is empty so the
subset invariant is vacuously satisfied at registration (Lock B).

`alternate_identifiers` is a `frozenset[AlternateIdentifier]`,
defaulted to empty. Seeds the Asset's initial set of PIDINST v1.0
Property 13 alternate identifiers (operator-supplied serial
numbers, inventory tags, vendor-specific schemes) in a single
registration transaction; the targeted-mutation slices
`add_asset_alternate_identifier` /
`remove_asset_alternate_identifier` mutate the set post-genesis.
Identifiers are operator-supplied opaque strings: the decider
does NOT cross-validate `(kind, value)` uniqueness across Assets
in v1 (per [[project-asset-alternate-identifiers-design]] Lock F);
no cross-BC IO either (per Lock I), so the handler does not load
any external stream on this field's behalf.

`controller_id` is `UUID | None`, optional reference to the
controller Asset (a sibling Device carrying the MotionController
Family) that drives this Asset. Set ONCE at registration per
[[project-controller-as-asset-stage1-design]] (Lock A precedent
from model_id); rebind path is decommission + re-register.
Eventual-consistency: the decider does NOT verify the referenced
controller Asset exists (mirrors `parent_id`, `model_id`,
`fixture_id`). The handler does not load any external stream on
this field's behalf.

`facility_code` is `str | None`, optional cross-BC reference to
the Federation Facility that owns this Asset, keyed on the
cross-deployment convergent slug (`FacilityCode`) per
[[project-slice8-design]] L1. Set ONCE at registration per the
Asset.model_id Lock A precedent; rebind path is decommission +
re-register. The handler resolves the slug via
`FacilityLookup.lookup_by_code` before invoking the decider; the
decider rejects unknown slugs with `AssetFacilityNotFoundError`
(HTTP 404) and skips validation entirely when the field is None.
Bare `str` on the command (matches the Permit / Credential / Seal
wire convention of bare-str slugs on commands + typed
`FacilityCode` VO on aggregate state); route + tool Pydantic
regex enforces the `[a-z0-9-]{1,32}` codepoint contract at the
API boundary.
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing
from cora.equipment.aggregates.asset import (
    AssetOwner,
    AssetTier,
)
from cora.shared.identifier import AlternateIdentifier


@dataclass(frozen=True)
class RegisterAsset:
    """Register a new asset.

    Carries the display name, operational tier, parent_id, optional
    Drawing reference, optional `model_id` Model-binding ref, optional
    `alternate_identifiers` seed set, and optional `owners` seed set.
    """

    name: str
    tier: AssetTier
    parent_id: UUID | None
    drawing: Drawing | None = None
    model_id: UUID | None = None
    # frozenset[AlternateIdentifier] for PIDINST v1.0 Property 13
    # alternate-identifier tuples seeded at registration. Same
    # parametrized-callable trick as Asset.alternate_identifiers in
    # state.py: empty frozenset has no element type for pyright to
    # infer under strict, so the parametrized callable is supplied as
    # the factory.
    alternate_identifiers: frozenset[AlternateIdentifier] = field(
        default_factory=frozenset[AlternateIdentifier]
    )
    # frozenset[AssetOwner] for PIDINST v1.0 Property 5 owner blocks
    # seeded at registration. The decider enforces owner_name
    # uniqueness within the payload (Lock 6); identifier/identifier_type
    # pairing is enforced by the AssetOwner VO.
    owners: frozenset[AssetOwner] = field(default_factory=frozenset[AssetOwner])
    controller_id: UUID | None = None
    facility_code: str | None = None
