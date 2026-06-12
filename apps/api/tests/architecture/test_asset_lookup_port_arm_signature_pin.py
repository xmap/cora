"""Pin the `AssetLookup.ancestors_of` signature flat (chain-walk Anti-hook 1).

`ancestors_of` is deliberately a flat positional walk:
`(asset_ids: frozenset[UUID]) -> frozenset[AssetLookupResult]`. No
keyword-only filter / depth / edge-type parameters are allowed -- the
moment the arm grows a `stop_at_facility_boundary=` or `depth=` or
`edge_kind=` flag it has started down the query-DSL path that the
locked design forbids (OPC UA QueryFirst is the cautionary precedent).
A federation-spanning walk is a SEPARATE sibling method
(`ancestors_of_across_facilities`); a down-chain walk is a separate
`descendants_of` method; neither is a parameter here.

The keyword-only allowlist starts EMPTY. Widening it is a deliberate
design conversation (gate review), not an incidental edit. If you are
here because this test failed, you almost certainly want a new sibling
method, not a new parameter on `ancestors_of`.
"""

import inspect
import typing
from uuid import UUID

import pytest

from cora.infrastructure.ports.asset_lookup import AssetLookup, AssetLookupResult

# Keyword-only parameters permitted on `ancestors_of`. Intentionally
# empty; extend only at gate review with a one-line rationale.
_KEYWORD_ONLY_ALLOWLIST: frozenset[str] = frozenset()


@pytest.mark.architecture
def test_ancestors_of_signature_is_flat_positional() -> None:
    sig = inspect.signature(AssetLookup.ancestors_of)
    params = [p for name, p in sig.parameters.items() if name != "self"]

    positional = [
        p
        for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    keyword_only = [p for p in params if p.kind is inspect.Parameter.KEYWORD_ONLY]
    var_params = [
        p
        for p in params
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]

    assert [p.name for p in positional] == ["asset_ids"], (
        "ancestors_of must take exactly one positional parameter `asset_ids`; "
        f"got {[p.name for p in positional]}"
    )
    assert not var_params, "ancestors_of must not take *args / **kwargs"

    unexpected_kwonly = {p.name for p in keyword_only} - _KEYWORD_ONLY_ALLOWLIST
    assert not unexpected_kwonly, (
        "ancestors_of grew a keyword-only parameter "
        f"{sorted(unexpected_kwonly)} not on the (empty) allowlist. A filter / "
        "depth / edge-type flag belongs in a separate sibling method "
        "(ancestors_of_across_facilities, descendants_of), not here. Widen "
        "_KEYWORD_ONLY_ALLOWLIST only at gate review."
    )


@pytest.mark.architecture
def test_ancestors_of_annotations_are_frozenset_in_and_out() -> None:
    sig = inspect.signature(AssetLookup.ancestors_of)
    asset_ids_ann = sig.parameters["asset_ids"].annotation
    assert typing.get_origin(asset_ids_ann) is frozenset, (
        f"ancestors_of asset_ids must be a frozenset; got {asset_ids_ann}"
    )
    assert typing.get_args(asset_ids_ann) == (UUID,), (
        f"ancestors_of asset_ids must be frozenset[UUID]; got {asset_ids_ann}"
    )
    ret = sig.return_annotation
    assert typing.get_origin(ret) is frozenset, f"ancestors_of must return a frozenset; got {ret}"
    assert typing.get_args(ret) == (AssetLookupResult,), (
        "ancestors_of must return frozenset[AssetLookupResult] (lifecycle-bearing "
        f"rows so consumers partition); got {ret}"
    )
