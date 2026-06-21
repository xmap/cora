"""MCP tool for the `register_distribution` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. The MCP tool flattens the nested `checksum`
and `encoding` objects into discrete arguments because FastMCP's
tool-arg JSON Schema is easier for LLM consumers to fill correctly
when fields are flat; the REST route preserves the nested shape
for typed clients. Mirrors `register_dataset_tool` precedent.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_CONFORMS_TO_MAX_ENTRIES,
    DATASET_MEDIA_TYPE_MAX_LENGTH,
)
from cora.data.aggregates.distribution import (
    DISTRIBUTION_URI_MAX_LENGTH,
    AccessProtocol,
)
from cora.data.features.register_distribution.command import RegisterDistribution
from cora.data.features.register_distribution.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RegisterDistributionOutput(BaseModel):
    """Structured output of the `register_distribution` MCP tool."""

    distribution_id: UUID = Field(description="Identifier of the newly registered Distribution.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_distribution` tool on the given MCP server."""

    @mcp.tool(
        name="register_distribution",
        description=(
            "Register a new Distribution (materialized byte-copy of a logical "
            "Dataset at a storage Supply). The Data BC stores only metadata; "
            "bytes live at the URI inside the Supply. checksum_algorithm is "
            "'sha256' (single file) or 'sha256-tree' (directory tree-hash) and "
            "must equal the parent Dataset's; checksum_value and byte_size must "
            "match it too (byte-identical-copy invariant). The Supply must have "
            "kind='Storage'."
        ),
    )
    async def register_distribution_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        dataset_id: Annotated[
            UUID,
            Field(description="Identifier of the parent logical Dataset."),
        ],
        supply_id: Annotated[
            UUID,
            Field(description=("Identifier of the storage-kind Supply hosting the bytes.")),
        ],
        uri: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DISTRIBUTION_URI_MAX_LENGTH,
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
                    "(directory tree-hash). Must equal the parent Dataset's."
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
            Field(
                ge=0,
                description=(
                    "Bulk content size in bytes. Must match the parent Dataset's byte_size."
                ),
            ),
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
        access_protocol: Annotated[
            AccessProtocol,
            Field(
                description=(
                    "Transport family of the URI. Closed enum: HTTPS, "
                    "Globus, S3, POSIX, NFS, OAI_PMH."
                )
            ),
        ],
        conforms_to: Annotated[
            list[str] | None,
            Field(
                default=None,
                max_length=DATASET_CONFORMS_TO_MAX_ENTRIES,
                description=(
                    "Profile URIs the Distribution claims to conform to "
                    "(NeXus, OME-Zarr, CIF, etc.). Defaults to empty."
                ),
            ),
        ] = None,
    ) -> RegisterDistributionOutput:
        handler = get_handler()
        distribution_id = await handler(
            RegisterDistribution(
                dataset_id=dataset_id,
                supply_id=supply_id,
                uri=uri,
                checksum_algorithm=checksum_algorithm,
                checksum_value=checksum_value,
                byte_size=byte_size,
                media_type=media_type,
                conforms_to=frozenset(conforms_to or []),
                access_protocol=access_protocol.value,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterDistributionOutput(distribution_id=distribution_id)
