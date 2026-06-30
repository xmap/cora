"""ComputeReachabilityLookup port: which Storage Supply tiers a compute resource can read.

Used by the Run BC start_run gate to extend the genesis input-data check.
The present-and-Verified gate (leg C) confirms each input Dataset has a
Verified Distribution somewhere; reconstruction now sometimes runs on a
remote compute resource (for example ALCF Polaris) that can only READ
certain Storage tiers, so "Verified anywhere" is insufficient. This port
resolves the named compute resource to the set of Storage Supply ids it
can read, so the decider can require the Verified copy to sit on a
reachable tier.

The port models a deployment-config map (compute resource -> readable
Storage Supply ids), resolved by Supply name at the composition root. It
is NOT event-sourced: the readable-tier topology is operations
configuration, not domain state. Returning None when the code is unknown
(not configured) distinguishes a config typo (`RunComputeResourceUnknownError`,
fixable by the operator) from a genuinely-unreachable input
(`RunInputNotReachableError`, a data problem). An empty frozenset is a
valid configured answer: the resource can read NO tier, so every input is
unreachable.

`compute_resource_code` is the plain string the caller put on
`StartRun.compute_resource_code`; the production adapter (deferred) maps
it to the readable Storage Supply id set via the deployment config.
"""

from typing import Protocol
from uuid import UUID


class ComputeReachabilityLookup(Protocol):
    """Cross-BC-style port: resolve a compute resource to its readable Storage tiers."""

    async def reachable_storage_supply_ids(
        self, compute_resource_code: str
    ) -> frozenset[UUID] | None:
        """Return the Storage Supply ids the named compute resource can read.

        Returns None when `compute_resource_code` is UNKNOWN (the
        deployment config does not map it to any readable-storage set);
        the handler turns that into `RunComputeResourceUnknownError`, a
        config-typo signal distinct from a genuinely-unreachable input.

        Returns a (possibly empty) frozenset when the code IS configured.
        An empty frozenset means the resource can read no Storage tier, so
        every input is unreachable (fail-closed at the decider).
        """
        ...


class NoComputeReachabilityLookup:
    """Test stub: every code is UNKNOWN (returns None), the conservative default.

    The default for tests that do not seed reachability: a Run naming any
    compute_resource_code fails with `RunComputeResourceUnknownError`. A
    Run that names no compute resource never calls the port, so the gate
    stays dormant.
    """

    async def reachable_storage_supply_ids(
        self, compute_resource_code: str
    ) -> frozenset[UUID] | None:
        _ = compute_resource_code
        return None


class SeededComputeReachabilityLookup:
    """Test stub: returns the readable Storage tiers configured per code.

    Construct with a mapping `{compute_resource_code: frozenset(supply_ids)}`;
    an unmapped code returns None (UNKNOWN). Lets a gate test seed a
    reachable tier set, an empty (reads-nothing) set, or an unmapped code
    to exercise each branch.
    """

    def __init__(self, by_code: dict[str, frozenset[UUID]]) -> None:
        self._by_code = dict(by_code)

    async def reachable_storage_supply_ids(
        self, compute_resource_code: str
    ) -> frozenset[UUID] | None:
        return self._by_code.get(compute_resource_code)


__all__ = [
    "ComputeReachabilityLookup",
    "NoComputeReachabilityLookup",
    "SeededComputeReachabilityLookup",
]
