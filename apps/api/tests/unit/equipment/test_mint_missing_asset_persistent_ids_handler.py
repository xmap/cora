"""Unit tests for the `mint_missing_asset_persistent_ids` orchestration slice.

`mint_for_asset_ids` is the loop core; tested with a fake assign delegate so
partial-failure partitioning is covered without Postgres. The bound handler is
tested for the pool-None short-circuit (in-memory mode enumerates nothing) and
the authz-deny path.
"""

from collections.abc import Mapping
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    AssetNotFoundError,
    AssetPersistentIdAlreadyAssignedError,
    AssetPersistentIdAssignmentForbiddenError,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.mint_missing_asset_persistent_ids import (
    MintMissingAssetPersistentIds,
    MintMissingAssetPersistentIdsResult,
    bind,
    mint_for_asset_ids,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme
from cora.shared.ports.doi_minter import PersistentIdentifierMintError
from tests.unit._helpers import build_deps

pytestmark = pytest.mark.timeout(60, method="thread")

_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000099")
_CID = UUID("01900000-0000-7000-8000-0000000000aa")


def _pid(value: str) -> PersistentIdentifier:
    return PersistentIdentifier(scheme=PersistentIdentifierScheme.DOI, value=value)


class _FakeMintOne:
    """Per-asset scripted mint delegate (MintOne shape): returns a PID or raises."""

    def __init__(self, outcomes: Mapping[UUID, PersistentIdentifier | Exception]) -> None:
        self._outcomes = outcomes
        self.calls: list[UUID] = []

    async def __call__(
        self,
        asset_id: UUID,
        *,
        scheme: PersistentIdentifierScheme,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
        surface_id: UUID,
    ) -> PersistentIdentifier:
        self.calls.append(asset_id)
        outcome = self._outcomes[asset_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def _run(
    asset_ids: list[UUID], mint_one: _FakeMintOne
) -> MintMissingAssetPersistentIdsResult:
    return await mint_for_asset_ids(
        asset_ids,
        mint_one=mint_one,
        scheme=PersistentIdentifierScheme.DOI,
        principal_id=_PRINCIPAL,
        correlation_id=_CID,
        causation_id=None,
        surface_id=NIL_SENTINEL_ID,
    )


async def test_mint_for_asset_ids_all_succeed_returns_all_minted() -> None:
    a, b = uuid4(), uuid4()
    fake = _FakeMintOne({a: _pid("10.x/a"), b: _pid("10.x/b")})
    result = await _run([a, b], fake)
    assert result.scanned == 2
    assert {m.asset_id for m in result.minted} == {a, b}
    assert result.skipped == ()
    assert result.failed == ()
    assert fake.calls == [a, b]


async def test_mint_for_asset_ids_partitions_skip_fail_and_mint() -> None:
    ok, already, decom, gone, mint_err = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    fake = _FakeMintOne(
        {
            ok: _pid("10.x/ok"),
            already: AssetPersistentIdAlreadyAssignedError(
                already, current=_pid("10.x/old"), attempted=_pid("10.x/new")
            ),
            decom: AssetPersistentIdAssignmentForbiddenError(
                decom, _pid("10.x/d"), reason="decommissioned"
            ),
            gone: AssetNotFoundError(gone),
            mint_err: PersistentIdentifierMintError(
                scheme=PersistentIdentifierScheme.DOI, reason="authority unreachable"
            ),
        }
    )
    result = await _run([ok, already, decom, gone, mint_err], fake)

    assert result.scanned == 5
    assert {m.asset_id for m in result.minted} == {ok}
    assert {s.asset_id for s in result.skipped} == {already, decom, gone}
    assert {s.reason for s in result.skipped} == {
        "AssetPersistentIdAlreadyAssignedError",
        "AssetPersistentIdAssignmentForbiddenError",
        "AssetNotFoundError",
    }
    assert {f.asset_id for f in result.failed} == {mint_err}
    failed = result.failed[0]
    assert failed.error_class == "PersistentIdentifierMintError"
    assert "authority unreachable" in failed.message


async def test_mint_for_asset_ids_one_failure_does_not_abort_batch() -> None:
    a, boom, c = uuid4(), uuid4(), uuid4()
    fake = _FakeMintOne(
        {
            a: _pid("10.x/a"),
            boom: PersistentIdentifierMintError(
                scheme=PersistentIdentifierScheme.DOI, reason="boom"
            ),
            c: _pid("10.x/c"),
        }
    )
    result = await _run([a, boom, c], fake)
    assert {m.asset_id for m in result.minted} == {a, c}
    assert {f.asset_id for f in result.failed} == {boom}
    assert fake.calls == [a, boom, c]


async def test_mint_for_asset_ids_empty_scan_returns_empty_result() -> None:
    fake = _FakeMintOne({})
    result = await _run([], fake)
    assert result.scanned == 0
    assert result.minted == ()
    assert result.skipped == ()
    assert result.failed == ()
    assert fake.calls == []


async def test_handler_short_circuits_when_pool_is_none() -> None:
    """In-memory mode (pool=None) enumerates nothing: scanned 0, no assign calls."""
    deps = build_deps()
    fake = _FakeMintOne({})
    handler = bind(deps, mint_one=fake)
    result = await handler(
        MintMissingAssetPersistentIds(),
        principal_id=_PRINCIPAL,
        correlation_id=_CID,
    )
    assert result.scanned == 0
    assert result.minted == ()
    assert fake.calls == []


async def test_handler_raises_unauthorized_when_authz_denies() -> None:
    deps = build_deps(deny=True)
    fake = _FakeMintOne({})
    handler = bind(deps, mint_one=fake)
    with pytest.raises(UnauthorizedError):
        await handler(
            MintMissingAssetPersistentIds(),
            principal_id=_PRINCIPAL,
            correlation_id=_CID,
        )
    assert fake.calls == []
