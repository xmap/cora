"""Federation BC bootstrap: seeds the self-Facility row at lifespan startup.

Per [[project_facility_aggregate_design]] Sub-Slice D and the
self-Facility bootstrap order locked in [[project_structural_scope_design]]
"Migration / federation coordination notes": every CORA deployment
seeds ITS OWN Facility row at lifespan startup BEFORE any Federation
slice can run. The self-Facility row is the deployment's identity in
the cross-deployment convergent code namespace; downstream slices
(slice 6 onward) bind Seal / Permit / Credential / Asset / Supply rows
to it via Facility.code.

Idempotency follows the `seed_agent` precedent: the function tries an
`append(expected_version=0)` and swallows `ConcurrencyError` as the
"already seeded" signal. Safe to call on every app boot.

The self-Facility identity comes from `settings.self_facility_code`
(loaded from the `SELF_FACILITY_CODE` env var; default "cora").
FacilityCode construction at startup catches misconfiguration (typos,
wrong-case slugs, codepoints outside the alphanumeric+dash pattern) as
`InvalidFacilityCodeError` and fails the lifespan fast.

The seeded row:
  - `kind = Site` (the deployment's own facility is the root of its
    structural hierarchy)
  - `parent_id = None` (Site invariant)
  - `display_name` defaults to `Facility.code` (operators rename via a
    future update_facility_display_name slice; not in slice 5)
  - `trust_anchor_credential_ids = frozenset()` (slice 6 binding
    populates this; empty default per L4 lock)
  - `alternate_identifiers = frozenset()` (genesis seed empty; add via
    future add_facility_alternate_identifier slice)
  - `persistent_id = None` (state-only; assign via future
    assign_facility_persistent_id slice)
  - `registered_by = ActorId(SYSTEM_PRINCIPAL_ID)` (system-driven seed,
    not operator action)

NO Decision-stream audit cross-write: matches the register_facility
+ decommission_facility pattern (Facility lifecycle is structural-
scaffolding metadata, not authorization-decision-bearing).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    FacilityKind,
    FacilityRegistered,
    event_type_name,
    facility_stream_id,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel

_FACILITY_STREAM_TYPE = "Facility"
_COMMAND_NAME = "bootstrap_federation"

_log = get_logger(__name__)


async def bootstrap_federation(kernel: Kernel) -> None:
    """Seed the self-Facility row from `settings.self_facility_code` (idempotent).

    No-op if the self-Facility is already seeded; logs the outcome
    either way. Safe to call on every app boot.
    """
    code = FacilityCode(kernel.settings.self_facility_code)
    facility_id = FacilityId(facility_stream_id(code))
    now = kernel.clock.now()

    registered_event = FacilityRegistered(
        facility_id=facility_id,
        code=code,
        display_name=code.value,
        kind=FacilityKind.SITE,
        parent_id=None,
        registered_by=ActorId(SYSTEM_PRINCIPAL_ID),
        occurred_at=now,
    )

    new_event = to_new_event(
        event_type=event_type_name(registered_event),
        payload=to_payload(registered_event),
        occurred_at=now,
        event_id=kernel.id_generator.new_id(),
        command_name=_COMMAND_NAME,
        correlation_id=kernel.id_generator.new_id(),
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )

    try:
        await kernel.event_store.append(
            stream_type=_FACILITY_STREAM_TYPE,
            stream_id=facility_id,
            expected_version=0,
            events=[new_event],
        )
    except ConcurrencyError:
        _log.info(
            "facility_seed.already_present",
            facility_id=str(facility_id),
            facility_code=code.value,
        )
        return

    _log.info(
        "facility_seed.created",
        facility_id=str(facility_id),
        facility_code=code.value,
    )


__all__ = ["bootstrap_federation"]
