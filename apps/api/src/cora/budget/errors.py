"""BC-application-layer errors for the budget BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/budget/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/allocation/state.py`.

Distinct class from each other BC's `UnauthorizedError`: each BC
owns its own application-error namespace so a budget 403 is
distinguishable from other BCs' 403s in logs / aggregator filters
(documented in CONTRIBUTING.md "BC-application-layer errors").
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
