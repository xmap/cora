"""Helper for Subject downstream tests that need an Active Asset to mount onto.

`mount_subject` cross-aggregate-validates the Asset; downstream Subject
slice tests (measure / remove / return / store / discard / get_subject)
that mount as setup all need an Active Asset in the in-memory event
store. This module provides the canonical seed helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cora.equipment.aggregates.asset import (
    AssetActivated,
    AssetRegistered,
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from datetime import datetime

    from cora.infrastructure.ports.event_store import EventStore

DEFAULT_ASSET_ID = UUID("01900000-0000-7000-8000-00000000a55e")


async def seed_active_asset(
    store: EventStore,
    *,
    asset_id: UUID = DEFAULT_ASSET_ID,
    now: datetime,
    correlation_id: UUID,
    activated: bool = True,
) -> UUID:
    """Seed an Asset stream with AssetRegistered (+ optional AssetActivated).

    Defaults to fully Activated. Set `activated=False` to leave the
    Asset in `Commissioned` (useful for negative tests that exercise
    SubjectMountTargetUnavailableError).
    """
    registered = AssetRegistered(
        asset_id=asset_id,
        name="Goniometer-1",
        tier="Unit",
        parent_id=None,
        occurred_at=now,
        commissioned_by=ActorId(uuid4()),
    )
    events = [
        to_new_event(
            event_type=event_type_name(registered),
            payload=to_payload(registered),
            occurred_at=now,
            event_id=uuid4(),
            command_name="RegisterAsset",
            correlation_id=correlation_id,
            principal_id=uuid4(),
        )
    ]
    if activated:
        activated_evt = AssetActivated(asset_id=asset_id, occurred_at=now)
        events.append(
            to_new_event(
                event_type=event_type_name(activated_evt),
                payload=to_payload(activated_evt),
                occurred_at=now,
                event_id=uuid4(),
                command_name="ActivateAsset",
                correlation_id=correlation_id,
                principal_id=uuid4(),
            )
        )
    await store.append(stream_type="Asset", stream_id=asset_id, expected_version=0, events=events)
    return asset_id


__all__ = ["DEFAULT_ASSET_ID", "seed_active_asset"]
