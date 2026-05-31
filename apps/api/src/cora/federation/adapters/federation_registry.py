"""FederationRegistry: composite PublishPort + PullPort dispatcher.

Per project_federation_port_design.md: handlers see ONE port; the
routing table is configuration not code. The registry implements
both PublishPort and PullPort by routing each call to the matching
backing adapter via longest-prefix-match on the artifact's
`source_facility_id` UUID-prefix string.

Modelled after `cora.operation.adapters.control_port_registry.ControlPortRegistry`:
construct empty, call `register(prefix, port)` for each peer
facility at app startup, then hand the registry to the Federation
BC handlers as a single PublishPort + PullPort.

`aclose()` fan-out in registration order with `contextlib.suppress(Exception)`
and a `_closed` idempotency flag so one flaky peer adapter cannot
strand its siblings.

Routing rule: longest-prefix-match by the source_facility_id's
hex-string representation. A more specific prefix wins over a
shorter one. No regex, no glob. Matches the
NoAdapterForAddressError analog in ControlPort with
NoAdapterForFacilityError here.
"""

import contextlib

from cora.infrastructure.ports.federation import (
    ArtifactReference,
    NoAdapterForFacilityError,
    PublishedArtifact,
    PublishPort,
    PublishReceipt,
    PulledArtifact,
    PullPort,
)


class FederationRegistry:
    """Composite PublishPort + PullPort with prefix-routed dispatch.

    Construct empty, call `register(prefix, port)` for each peer
    facility, then hand the registry to handlers as a single port.
    The routing table is the only configuration that varies between
    deployments; the handler tier sees a stable port surface.
    """

    def __init__(self) -> None:
        self._routes: list[tuple[str, PublishPort | PullPort]] = []
        self._closed = False

    def register(self, prefix: str, port: PublishPort | PullPort) -> None:
        """Add a route. Re-registering a prefix REPLACES the prior entry.

        Replacement is intentional: hot-swapping a peer-facility
        adapter during integration tests should not require dropping
        and reconstructing the registry. Matches the
        ControlPortRegistry precedent verbatim.
        """
        self._routes = [(p, a) for (p, a) in self._routes if p != prefix]
        self._routes.append((prefix, port))

    def route_publish(self, artifact: PublishedArtifact) -> PublishPort:
        """Return the PublishPort adapter for `artifact`'s source facility."""
        adapter = self._route_by_facility_hex(artifact.source_facility_id.hex)
        if not isinstance(adapter, PublishPort):
            raise NoAdapterForFacilityError(source_facility_id=artifact.source_facility_id)
        return adapter

    def route_pull(self, reference: ArtifactReference) -> PullPort:
        """Return the PullPort adapter for `reference`'s source facility."""
        adapter = self._route_by_facility_hex(reference.source_facility_id.hex)
        if not isinstance(adapter, PullPort):
            raise NoAdapterForFacilityError(source_facility_id=reference.source_facility_id)
        return adapter

    def _route_by_facility_hex(self, facility_hex: str) -> PublishPort | PullPort:
        for prefix, adapter in sorted(self._routes, key=lambda r: -len(r[0])):
            if facility_hex.startswith(prefix):
                return adapter
        raise NoAdapterForFacilityError(source_facility_id=None)  # type: ignore[arg-type]

    async def publish(self, artifact: PublishedArtifact) -> PublishReceipt:
        return await self.route_publish(artifact).publish(artifact)

    async def fetch(self, reference: ArtifactReference) -> PulledArtifact:
        return await self.route_pull(reference).fetch(reference)

    def registered_prefixes(self) -> tuple[str, ...]:
        """Return the registered prefixes in registration order."""
        return tuple(p for p, _ in self._routes)

    async def aclose(self) -> None:
        """Close every registered adapter; idempotent.

        Suppresses per-adapter close errors so one flaky adapter
        cannot strand siblings. Production deployments call this
        from the FastAPI lifespan exit handler.
        """
        if self._closed:
            return
        self._closed = True
        for _, adapter in self._routes:
            close = getattr(adapter, "aclose", None)
            if close is None:
                continue
            with contextlib.suppress(Exception):
                await close()


__all__ = ["FederationRegistry"]
