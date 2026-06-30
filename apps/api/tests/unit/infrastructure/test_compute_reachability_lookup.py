"""Behavioural tests for the `ComputeReachabilityLookup` test stubs."""

from uuid import uuid4

import pytest

from cora.infrastructure.ports.compute_reachability_lookup import (
    NoComputeReachabilityLookup,
    SeededComputeReachabilityLookup,
)


@pytest.mark.unit
async def test_no_reachability_stub_returns_none_for_any_code() -> None:
    lookup = NoComputeReachabilityLookup()
    assert await lookup.reachable_storage_supply_ids("polaris") is None


@pytest.mark.unit
async def test_seeded_stub_returns_the_mapped_set_for_a_known_code() -> None:
    tier = uuid4()
    lookup = SeededComputeReachabilityLookup({"polaris": frozenset({tier})})
    assert await lookup.reachable_storage_supply_ids("polaris") == frozenset({tier})


@pytest.mark.unit
async def test_seeded_stub_returns_none_for_an_unmapped_code() -> None:
    lookup = SeededComputeReachabilityLookup({"polaris": frozenset({uuid4()})})
    assert await lookup.reachable_storage_supply_ids("unconfigured") is None


@pytest.mark.unit
async def test_seeded_stub_returns_empty_set_for_a_reads_nothing_code() -> None:
    """An empty frozenset is a valid configured answer, distinct from None."""
    lookup = SeededComputeReachabilityLookup({"isolated": frozenset()})
    assert await lookup.reachable_storage_supply_ids("isolated") == frozenset()
