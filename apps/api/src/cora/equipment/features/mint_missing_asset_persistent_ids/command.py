"""The `MintMissingAssetPersistentIds` command + result: bulk retrospective mint.

Orchestration entry, not a single-aggregate command. The handler enumerates
Assets that lack a persistent identifier and delegates each to the existing
`assign_asset_persistent_id` handler, encoding every per-asset outcome in the
result rather than raising. Mirrors `operation.conduct_procedure`'s
result-carries-failures shape so one response covers every outcome.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme

DEFAULT_BATCH_LIMIT = 100
"""Cap on Assets minted per call. Bounds the external mint calls a single
invocation makes; re-run to continue (the sweep is re-run-safe)."""


@dataclass(frozen=True)
class MintMissingAssetPersistentIds:
    """Mint a persistent identifier for every Asset that lacks one.

    `scheme` applies to every mint in the batch. `facility_code` optionally
    scopes the sweep to one facility (None sweeps all). `limit` caps the
    batch so a single call bounds its external mint calls.
    """

    scheme: PersistentIdentifierScheme = PersistentIdentifierScheme.DOI
    facility_code: str | None = None
    limit: int = DEFAULT_BATCH_LIMIT


@dataclass(frozen=True)
class MintedAsset:
    """An Asset that received a freshly-minted persistent identifier."""

    asset_id: UUID
    persistent_id: PersistentIdentifier


@dataclass(frozen=True)
class SkippedAsset:
    """An Asset the sweep declined to mint (already assigned, decommissioned,
    or vanished between enumeration and mint: an expected, retryable outcome)."""

    asset_id: UUID
    reason: str


@dataclass(frozen=True)
class FailedAsset:
    """An Asset whose mint raised (external authority failure or unexpected
    error). Retryable on the next sweep."""

    asset_id: UUID
    error_class: str
    message: str


@dataclass(frozen=True)
class MintMissingAssetPersistentIdsResult:
    """Summary of one bulk-mint sweep.

    `scanned` is the number of Assets enumerated as missing a persistent id
    (capped by `limit`). Every per-asset outcome lands in exactly one of
    `minted` / `skipped` / `failed`; the handler raises only on auth or
    protocol faults, never per asset.
    """

    scanned: int
    minted: tuple[MintedAsset, ...] = ()
    skipped: tuple[SkippedAsset, ...] = ()
    failed: tuple[FailedAsset, ...] = ()
