"""MCP tool for the `register_dataset` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Uses
The MCP tool flattens the nested `checksum` and `encoding` objects
into discrete arguments because FastMCP's tool-arg JSON Schema is
easier for LLM consumers to fill correctly when fields are flat;
the REST route preserves the nested shape for typed clients.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_CONFORMS_TO_MAX_ENTRIES,
    DATASET_DERIVED_FROM_MAX_ENTRIES,
    DATASET_MEDIA_TYPE_MAX_LENGTH,
    DATASET_NAME_MAX_LENGTH,
    DATASET_URI_MAX_LENGTH,
    DATASET_USED_CALIBRATIONS_MAX_ENTRIES,
)
from cora.data.features.register_dataset.command import RegisterDataset
from cora.data.features.register_dataset.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RegisterDatasetOutput(BaseModel):
    """Structured output of the `register_dataset` MCP tool."""

    dataset_id: UUID = Field(description="Identifier of the newly registered Dataset.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_dataset` tool on the given MCP server."""

    @mcp.tool(
        name="register_dataset",
        description=(
            "Register a new Dataset (logical research data product) with the "
            "given metadata. The Data BC stores only metadata; bytes live at "
            "the URI. checksum_algorithm is 'sha256' for a single file or "
            "'sha256-tree' for a directory of files (a tree-hash over the "
            "whole directory); both carry a 64-hex value. Optional "
            "cross-refs (producing_run_id, subject_id, derived_from) are "
            "validated for existence at registration. Idempotency-Key is "
        ),
    )
    async def register_dataset_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DATASET_NAME_MAX_LENGTH,
                description="Display name for the new Dataset.",
            ),
        ],
        uri: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DATASET_URI_MAX_LENGTH,
                description=(
                    "Opaque URI string pointing at the bulk content "
                    "(s3://, file://, https://, globus://, etc.)."
                ),
            ),
        ],
        checksum_algorithm: Annotated[
            str,
            Field(
                description=(
                    "Checksum algorithm: 'sha256' (single file) or 'sha256-tree' "
                    "(directory tree-hash). Both carry a 64-hex value."
                )
            ),
        ],
        checksum_value: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
                description="Canonical checksum value. For sha256: 64 lowercase hex chars.",
            ),
        ],
        byte_size: Annotated[
            int,
            Field(ge=0, description="Bulk content size in bytes. Zero allowed."),
        ],
        media_type: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DATASET_MEDIA_TYPE_MAX_LENGTH,
                description=(
                    "Loose MIME-type-ish string ('application/x-hdf5', 'application/x-zarr', etc.)."
                ),
            ),
        ],
        conforms_to: Annotated[
            list[str] | None,
            Field(
                default=None,
                max_length=DATASET_CONFORMS_TO_MAX_ENTRIES,
                description=(
                    "Profile URIs the Dataset claims to conform to (NeXus, "
                    "OME-Zarr, CIF, etc.). Defaults to empty."
                ),
            ),
        ] = None,
        producing_run_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=("Optional id of the Run that produced this Dataset."),
            ),
        ] = None,
        producing_procedure_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional id of the conducted Procedure that produced this "
                    "Dataset. The server derives the actuation-kind provenance "
                    "from it to gate promotion; the kind itself is never a "
                    "caller input. None for non-conducted / external data."
                ),
            ),
        ] = None,
        subject_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=("Optional id of the Subject the Dataset is about."),
            ),
        ] = None,
        derived_from: Annotated[
            list[UUID] | None,
            Field(
                default=None,
                max_length=DATASET_DERIVED_FROM_MAX_ENTRIES,
                description=("Optional lineage edges to upstream Datasets. Defaults to empty."),
            ),
        ] = None,
        used_calibration_ids: Annotated[
            list[UUID] | None,
            Field(
                default=None,
                max_length=DATASET_USED_CALIBRATIONS_MAX_ENTRIES,
                description=(
                    "Optional CalibrationRevision ids the reconstruction "
                    "actually used (Calibration BC AsShot citation per "
                    "AsShot citation set). Symmetric to Run.pinned_calibration_ids on "
                    "the acquired-from Run; reconstruction may legitimately "
                    "cite refined revisions not in the producing Run's "
                    "pin set. NOT verified at the write path. Omit or "
                    "null for an empty citation set."
                ),
            ),
        ] = None,
    ) -> RegisterDatasetOutput:
        handler = get_handler()
        dataset_id = await handler(
            RegisterDataset(
                name=name,
                uri=uri,
                checksum_algorithm=checksum_algorithm,
                checksum_value=checksum_value,
                byte_size=byte_size,
                media_type=media_type,
                conforms_to=frozenset(conforms_to or []),
                producing_run_id=producing_run_id,
                producing_procedure_id=producing_procedure_id,
                subject_id=subject_id,
                derived_from=frozenset(derived_from or []),
                used_calibration_ids=frozenset(used_calibration_ids or []),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterDatasetOutput(dataset_id=dataset_id)
