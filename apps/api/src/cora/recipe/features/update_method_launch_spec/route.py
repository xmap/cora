"""HTTP route for the `update_method_launch_spec` slice.

Action endpoint at `POST /methods/{method_id}/launch-spec`. Body
carries the launch_spec (or null to clear). 204 No Content on success.
Same action-endpoint pattern as `update_method_parameters_schema`.

The wire shape is a typed Pydantic mirror of the `LaunchSpec` VO; the
decider re-validates well-formedness + the schema cross-check.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.aggregates.method import ArgStyle, LaunchArg, LaunchSpec
from cora.recipe.features.update_method_launch_spec.command import UpdateMethodLaunchSpec
from cora.recipe.features.update_method_launch_spec.handler import Handler


class LaunchArgRequest(BaseModel):
    """JSON wire shape for a `LaunchArg`."""

    name: str = Field(..., min_length=1, description="A parameters_schema property key.")
    flag: str | None = Field(default=None, description="Option flag (XOR with position).")
    position: int | None = Field(
        default=None, ge=0, description="Positional index (XOR with flag)."
    )
    required: bool = False
    style: ArgStyle = ArgStyle.VALUE

    model_config = {"extra": "forbid"}


class LaunchSpecRequest(BaseModel):
    """JSON wire shape for a `LaunchSpec`."""

    base_command: list[str] = Field(..., min_length=1, description="Literal argv prefix.")
    args: list[LaunchArgRequest] = Field(default_factory=list[LaunchArgRequest])
    input_arg: str | None = Field(default=None, description="Flag before each input URI.")
    output_arg: str | None = Field(default=None, description="Flag before the output URI.")

    model_config = {"extra": "forbid"}


class UpdateMethodLaunchSpecRequest(BaseModel):
    """Body for `POST /methods/{method_id}/launch-spec`."""

    launch_spec: LaunchSpecRequest | None = Field(
        ...,
        description="The vetted launch recipe, or null to clear an existing one.",
    )


def launch_spec_from_request(request: LaunchSpecRequest | None) -> LaunchSpec | None:
    """Build a `LaunchSpec` VO from its wire shape (None passes through).

    Public because `tool.py` reuses it (MCP + REST share the wire schema).
    """
    if request is None:
        return None
    return LaunchSpec(
        base_command=tuple(request.base_command),
        args=tuple(
            LaunchArg(
                name=a.name,
                flag=a.flag,
                position=a.position,
                required=a.required,
                style=a.style,
            )
            for a in request.args
        ),
        input_arg=request.input_arg,
        output_arg=request.output_arg,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.update_method_launch_spec
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/methods/{method_id}/launch-spec",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Launch spec rejected: malformed (bad flag, flag/position both, "
                "position gap), names an unknown parameters_schema key, or binds "
                "a flag_only arg to a non-boolean key."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No method exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Concurrent write to the same method stream conflicted.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Set, replace, or clear a Method's launch_spec",
)
async def post_methods_launch_spec(
    method_id: Annotated[UUID, Path(description="Target method's id.")],
    body: UpdateMethodLaunchSpecRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UpdateMethodLaunchSpec(
            method_id=method_id,
            launch_spec=launch_spec_from_request(body.launch_spec),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
