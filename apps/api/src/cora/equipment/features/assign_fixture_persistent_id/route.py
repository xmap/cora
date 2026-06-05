"""HTTP route for the `assign_fixture_persistent_id` slice.

Action endpoint at `POST /fixtures/{fixture_id}/assign-persistent-identifier`.
Thin wire layer: forwards `(fixture_id, scheme, suffix)` to the handler,
which resolves the `DoiMinter` call and runs the pure decider. The
route itself does NOT depend on the `DoiMinter` port (server-mint
posture per Lock 5 of [[project-fixture-pidinst-design]] keeps
non-determinism in the handler closure only).

201 Created on success with `AssignFixturePersistentIdResponse(scheme,
value)` in the body so the operator learns the server-minted
identifier without a follow-up GET (Section 6.5 deviation from the
empty-201 convention for Fixture mutations).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment._fixture_persistent_identifier_body import (
    AssignFixturePersistentIdRequest,
    AssignFixturePersistentIdResponse,
)
from cora.equipment.features.assign_fixture_persistent_id.command import (
    AssignFixturePersistentId,
)
from cora.equipment.features.assign_fixture_persistent_id.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.assign_fixture_persistent_id
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/fixtures/{fixture_id}/assign-persistent-identifier",
    status_code=status.HTTP_201_CREATED,
    response_model=AssignFixturePersistentIdResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "PersistentIdentifier VO validation failed: empty or "
                "whitespace-only value, or value over the max-length "
                "bound (InvalidPersistentIdentifierValueError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No fixture exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Fixture cannot accept the persistent identifier: the "
                "fixture already carries a persistent_id (set-once: "
                "FixturePersistentIdAlreadyAssignedError), OR a "
                "concurrent write to the same fixture stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": (
                "The external mint authority (DataCite or Handle.net) "
                "failed to assign a persistent identifier "
                "(PersistentIdentifierMintError)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, malformed UUID, scheme "
                "outside the closed enum, suffix length out of bounds "
                "at the wire layer)."
            ),
        },
    },
    summary="Assign a PIDINST persistent identifier to an existing Fixture",
)
async def post_fixtures_assign_persistent_identifier(
    fixture_id: Annotated[UUID, Path(description="Target fixture's id.")],
    body: AssignFixturePersistentIdRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AssignFixturePersistentIdResponse:
    persistent_id = await handler(
        AssignFixturePersistentId(
            fixture_id=fixture_id,
            scheme=body.scheme,
            suffix=body.suffix,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return AssignFixturePersistentIdResponse(
        scheme=persistent_id.scheme.value,
        value=persistent_id.value,
    )
