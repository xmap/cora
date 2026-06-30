"""Shared signing for proactive agent runtimes that compose Decisions directly.

The reactive agent subscribers (RunDebriefer, CautionDrafter) sign each
agent-authored `DecisionRegistered` via their own `_maybe_sign` before appending,
per the signing design lock: `DecisionRegistered` is in `SIGNED_EVENT_TYPES`, so
an AI-agent row is signed at write time (an unsigned agent row would trip the
strict audit sweep, `signing.verify_stream(strict=True)` raising
`SignatureMissingError`). Human-actor rows from the operator-driven
`register_decision` slice stay unsigned by design.

The proactive agent runtimes hosted at the composition root (`_run_initiator`,
`_run_supervisor`) also compose `DecisionRegistered` directly (they cannot use
`register_decision`, whose decider rejects AGENT principals), so they need the
same signing step. This module hoists it to one helper both import, rather than
each re-declaring a private `_maybe_sign`. Mirrors
`RunDebrieferSubscriber._maybe_sign` exactly.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from cora.infrastructure.signing import SIGNED_EVENT_TYPES

if TYPE_CHECKING:
    from uuid import UUID

    from cora.infrastructure.ports.event_store import NewEvent
    from cora.infrastructure.ports.signer import Signer


async def maybe_sign_agent_event(
    signer: Signer | None,
    new_event: NewEvent,
    *,
    actor_id: UUID,
) -> NewEvent:
    """Attach a signature when a Signer is wired AND the event type must be signed.

    No-op when no Signer is configured (a deployment that wires none) or the event
    type is not in `SIGNED_EVENT_TYPES`. Otherwise signs as `actor_id` (the agent's
    id) and returns a copy carrying signature / signature_kid / signature_version.
    The caller passes the agent's id because these runtimes emit agent-actor events
    exclusively, so no actor-kind discrimination is needed here.
    """
    if signer is None or new_event.event_type not in SIGNED_EVENT_TYPES:
        return new_event
    signature, kid, signing_version = await signer.sign(
        event_type=new_event.event_type,
        payload=new_event.payload,
        actor_id=actor_id,
    )
    return replace(
        new_event,
        signature=signature,
        signature_kid=kid,
        signature_version=signing_version,
    )


__all__ = ["maybe_sign_agent_event"]
