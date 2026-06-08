"""The `RegisterCampaign` command -- intent dataclass for this slice.

Carries the caller-controlled fields: `name`, `intent` (closed enum),
REQUIRED `lead_actor_id`, optional `subject_id` (loose policy), optional
`description`, optional `tags` (empty set allowed), optional
`external_refs` (empty set allowed), optional `external_id` (lazy-
mint pattern).

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports / the request envelope, matching the cross-BC
create-style command shape locked in Access / Trust / Subject /
Equipment / Supply / Safety / Caution.

## `lead_actor_id` stays on the command (intentionally different from Caution)

Caution closed its author-spoofing surface by deriving
`author_actor_id` from the envelope `principal_id` and omitting it
from the command. Campaign INTENTIONALLY keeps `lead_actor_id` on
the command: a Campaign lead (PI) is OPERATOR-ASSIGNED and may
differ from the registering principal (an admin acting on behalf of
a visiting PI). This mirrors LIMS Study Director / GLP Study
Director Identity precedent. Per design memo lock + Anti-hooks.

## Bounded-text validation

`name` length is validated at the API boundary via Pydantic
(`min_length=1, max_length=200`) AND at the decider via the
`CampaignName` VO (trims + re-checks). Same dual-validation pattern
as every other create-style slice. `description` follows the same
pattern when provided (None is the supported "no description" path).
`external_id` is bare-str validated at the decider (1-100 chars
after trim) when provided.
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.shared.identifier import Identifier


@dataclass(frozen=True)
class RegisterCampaign:
    """Register a new Campaign (lands in Planned)."""

    name: str
    intent: CampaignIntent
    lead_actor_id: UUID
    subject_id: UUID | None = None
    description: str | None = None
    tags: frozenset[str] = field(default_factory=frozenset[str])
    external_refs: frozenset[Identifier] = field(default_factory=frozenset[Identifier])
    external_id: str | None = None
