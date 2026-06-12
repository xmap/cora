"""Data BC adapters: concrete implementations of Data ports.

`RoCrate12Adapter`: implements `EditionSerializer` for
`EditionKind.ROCRATE` producing JSON-LD per the RO-Crate 1.2 +
Workflow Run Crate profiles.

`PostgresDistributionLookup` + `InMemoryDistributionLookup`:
`DistributionLookup` adapters reading `proj_data_distribution_summary`
or an in-process dict for the canonical Distribution row per Dataset.

`HttpRangeChecksumAdapter`: implements `ChecksumVerifier` over
HTTP / HTTPS via range-read in 1 MiB chunks.

Test-only stub adapters live alongside the production adapters for
reuse across unit + contract + integration tests:

  - `StubEditionSerializer`: returns a pre-configured `SerializedEdition`
  - `FailingEditionSerializer`: raises a pre-configured exception
  - `PerKindEditionSerializer`: dispatches to per-kind serializers

Per [[project_adapter_naming_design]]: class name ``<Tech><Port>``;
module placement at ``cora.<bc>.adapters/`` for single-BC adapters,
or ``cora.<bc>.infrastructure.adapters/`` for cross-BC adapters.
"""

from cora.data.adapters.http_range_checksum import HttpRangeChecksumAdapter
from cora.data.adapters.in_memory_distribution_lookup import (
    InMemoryDistributionLookup,
)
from cora.data.adapters.postgres_distribution_lookup import (
    PostgresDistributionLookup,
)
from cora.data.adapters.rocrate12_serializer import RoCrate12Adapter
from cora.data.adapters.stub_edition_serializer import (
    FailingEditionSerializer,
    PerKindEditionSerializer,
    StubEditionSerializer,
)

__all__ = [
    "FailingEditionSerializer",
    "HttpRangeChecksumAdapter",
    "InMemoryDistributionLookup",
    "PerKindEditionSerializer",
    "PostgresDistributionLookup",
    "RoCrate12Adapter",
    "StubEditionSerializer",
]
