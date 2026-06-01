"""BC-application-layer errors for the Calibration BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/calibration/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/calibration/state.py`.

Distinct class from each other BC's `UnauthorizedError`: each BC
owns its own application-error namespace so a Calibration 403 is
distinguishable from other BCs' 403s in logs / aggregator filters
(documented in CONTRIBUTING.md "BC-application-layer errors").
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PublishPortNotWiredError(RuntimeError):
    """The publish-time Kernel deps (publish_port + signature_port + permit_lookup)
    are not all wired.

    Raised by the publish_revision handler's bind() at startup so a
    misconfigured deployment surfaces immediately instead of failing
    silently mid-request. BC-application-layer error (lives here, not
    on the aggregate kernel) because the failure mode is wiring, not
    a domain invariant.
    """

    def __init__(self, missing: tuple[str, ...]) -> None:
        super().__init__(
            f"publish_revision handler requires Kernel deps {missing!r} to be non-None"
        )
        self.missing = missing
