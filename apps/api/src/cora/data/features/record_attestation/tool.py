"""MCP tool for the ``record_attestation`` slice.

Surfaces the same handler the REST route uses, exposed as a Model Context
Protocol tool. The tool is slim: ``dataset_id`` + ``distribution_id`` +
``kind``. CORA reads the Distribution's bytes itself and computes the
checksum, so the caller does not assert an outcome or any evidence.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.aggregates.attestation import AttestationKind
from cora.data.features.record_attestation.command import RecordAttestation
from cora.data.features.record_attestation.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RecordAttestationOutput(BaseModel):
    """Structured output of the ``record_attestation`` MCP tool."""

    attestation_id: UUID = Field(description="Identifier of the newly recorded Attestation.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the ``record_attestation`` tool on the given MCP server."""

    @mcp.tool(
        name="record_attestation",
        description=(
            "Verify a Distribution's bytes and record an Attestation fact about "
            "a Dataset (always) and a specific Distribution byte-copy. CORA reads "
            "the bytes via its checksum verifier (HTTP/HTTPS, or local file:// when "
            "configured) and computes the digest itself; you do not supply an "
            "outcome or checksum. Today only kind='ChecksumVerified' is implemented; "
            "the other three kinds are reserved. A Distribution stored on a scheme "
            "with no configured verifier is rejected."
        ),
    )
    async def record_attestation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        dataset_id: Annotated[
            UUID,
            Field(description="Identifier of the Dataset the Attestation is about."),
        ],
        kind: Annotated[
            AttestationKind,
            Field(
                description=(
                    "What to attest. Closed enum: ChecksumVerified, "
                    "FormatValidated, ConformsToValidated, BitRotChecked."
                )
            ),
        ],
        distribution_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Identifier of the bound Distribution byte-copy whose bytes "
                    "CORA reads and checksums. Required for byte-level kinds; "
                    "null only for ConformsToValidated."
                ),
            ),
        ] = None,
    ) -> RecordAttestationOutput:
        handler = get_handler()
        attestation_id = await handler(
            RecordAttestation(
                dataset_id=dataset_id,
                distribution_id=distribution_id,
                kind=kind.value,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RecordAttestationOutput(attestation_id=attestation_id)
