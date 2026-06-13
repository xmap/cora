"""HTTP route for the `dismiss_event_in_reaction` slice.

Operator action endpoint:
`POST /agent/reactions/{subscriber_name}/dismiss-event` body
`{event_id, reason}`. Returns the new decision_id (201 Created so the
caller has the audit handle to follow up with `rate_decision` etc.).

The 503 response covers the in-memory configuration; production
deployments never see it.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.dismiss_event_in_reaction.command import (
    DismissEventInReaction,
)
from cora.agent.features.dismiss_event_in_reaction.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH

# The Pydantic schema short-circuits oversize bodies before the handler
# acquires a pool connection; the decider's check defends against
# direct in-process callers (tests, future sagas).
_REASON_MIN_LENGTH = 1


class DismissEventInReactionRequest(BaseModel):
    """Body for `POST /agent/reactions/{subscriber_name}/dismiss-event`."""

    event_id: UUID = Field(
        ...,
        description=(
            "The event_id the operator wants the subscriber's bookmark "
            "advanced past. Read from the operator dashboard's wedged-"
            "bookmark surface (last_error_message + last_event_recorded_at "
            "on projection_bookmarks); pasting an arbitrary event_id risks "
            "rewinding the bookmark, which the decider catches via the "
            "lexicographic (transaction_id, position) check."
        ),
    )
    reason: str = Field(
        ...,
        min_length=_REASON_MIN_LENGTH,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason the operator gives for the dismissal "
            "(1-500 chars after trimming). Captured verbatim into "
            "DecisionRegistered.reasoning for audit. Operationally: "
            "'cannot deserialize this event_type since the rename, "
            "advancing past' / 'LLM returned hallucinated context, "
            "manual retry tomorrow' etc."
        ),
    )


class DismissEventInReactionResponse(BaseModel):
    """Body returned on successful dismissal."""

    decision_id: UUID = Field(
        ...,
        description="The Decision audit record's id.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.dismiss_event_in_reaction
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agent/reactions/{subscriber_name}/dismiss-event",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: empty / oversize reason (InvalidDismissalReasonError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No projection_bookmarks row for the named subscriber "
                "(SubscriberBookmarkNotFoundError) OR no event row for "
                "the supplied event_id (DismissalEventNotFoundError)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The bookmark is already at or past the target event "
                "(EventAlreadyDismissedError); refresh the dashboard "
                "and re-evaluate before retrying."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": (
                "The deployment has no Postgres pool "
                "(DismissalRequiresPostgresError); the slice is a no-op "
                "without projection_bookmarks. Production deployments "
                "never see this."
            ),
        },
    },
    summary="Dismiss a poison event on a Reaction's bookmark",
)
async def post_agent_reactions_dismiss_event(
    subscriber_name: Annotated[
        str,
        Path(
            min_length=1,
            max_length=200,
            description="Name of the subscriber (matches `Reaction.name`).",
        ),
    ],
    body: DismissEventInReactionRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> DismissEventInReactionResponse:
    decision_id = await handler(
        DismissEventInReaction(
            subscriber_name=subscriber_name,
            event_id=body.event_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return DismissEventInReactionResponse(decision_id=decision_id)
