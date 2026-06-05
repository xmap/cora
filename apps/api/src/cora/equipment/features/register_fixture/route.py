"""HTTP route for the `register_fixture` slice.

POST /assemblies/{assembly_id}/fixtures: register a new Fixture
against an Assembly blueprint (materialize the template into a
concrete cluster of pre-existing Assets). Returns the new
fixture_id.

The body carries the slot-to-asset bindings as a list (Pydantic
cannot hash BaseModel; the route handler converts each to its
domain VO before constructing the command, and duplicate bindings
collapse when the frozenset is built).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.features.register_fixture.command import RegisterFixture
from cora.equipment.features.register_fixture.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class SlotAssetBindingBody(BaseModel):
    """A single slot-to-asset binding within the body."""

    slot_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "Name of the TemplateSlot in the Assembly's required_slots this binding fills."
        ),
    )
    asset_id: UUID = Field(
        ...,
        description="Asset.id of the pre-existing Asset that fills the slot.",
    )

    def to_domain(self) -> SlotAssetBinding:
        return SlotAssetBinding(slot_name=self.slot_name, asset_id=self.asset_id)


class RegisterFixtureRequest(BaseModel):
    """Body for `POST /assemblies/{assembly_id}/fixtures`."""

    slot_asset_bindings: list[SlotAssetBindingBody] = Field(
        default_factory=list[SlotAssetBindingBody],
        description=(
            "Bindings of slot_name to pre-existing Asset.id. Each "
            "binding's slot_name must reference a TemplateSlot in "
            "the Assembly's required_slots; each asset_id must "
            "resolve to a registered Asset whose family_ids intersect "
            "the slot's required_family_ids. Cardinality of each slot "
            "must be satisfied by the count of bindings carrying its "
            "slot_name. Wire shape is a list; duplicates collapse "
            "when the route handler converts to the domain frozenset."
        ),
    )
    parameter_overrides: dict[str, Any] = Field(
        default_factory=dict[str, Any],
        description=(
            "Operator-supplied parameter overrides validated against "
            "the Assembly's parameter_overrides_schema. STRICT posture: "
            "non-empty overrides on an Assembly with no schema rejects."
        ),
    )


class RegisterFixtureResponse(BaseModel):
    """Response body for `POST /assemblies/{assembly_id}/fixtures`."""

    fixture_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.register_fixture
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assemblies/{assembly_id}/fixtures",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterFixtureResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Slot cardinality not satisfied, a mapped Asset's "
                "family_ids do not intersect the slot's "
                "required_family_ids, OR parameter_overrides fail "
                "the Assembly's schema (STRICT: non-empty overrides "
                "on a schema-less Assembly)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Assembly does not exist, OR a referenced asset_id "
                "does not resolve to a registered Asset."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Assembly is Deprecated (cannot instantiate), OR a "
                "referenced Asset is Decommissioned (lifecycle disallows "
                "attachment), OR a referenced Asset is not currently "
                "installed in any Mount (install_asset first), OR a "
                "concurrent write to the new Fixture stream conflicted "
                "(optimistic concurrency; essentially impossible with "
                "UUIDv7 ids)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR "
                "Idempotency-Key was reused with a different request body."
            ),
        },
    },
    summary="Register a new Fixture against an Assembly blueprint",
)
async def post_assemblies_fixtures(
    assembly_id: Annotated[UUID, Path(description="Target Assembly's id.")],
    body: RegisterFixtureRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied key for idempotent retry: "
                "replaying the same key returns the original "
                "fixture_id without creating a new Fixture."
            ),
        ),
    ] = None,
) -> RegisterFixtureResponse:
    fixture_id = await handler(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(b.to_domain() for b in body.slot_asset_bindings),
            parameter_overrides=body.parameter_overrides,
            surface_id=surface_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterFixtureResponse(fixture_id=fixture_id)
