"""BC-application-layer errors for the Data BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/data/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate at `aggregates/dataset/state.py`.

Distinct class from other BCs' `UnauthorizedError` namespaces
(per-BC log-distinguishability convention; see CONTRIBUTING.md
"BC-application-layer errors").
"""


class InvalidScanFileError(ValueError):
    """The file at the ingest locator cannot be ingested as commanded.

    Validation family (`Invalid<X>` -> 400), homed here rather than in
    an aggregate's `state.py` because no aggregate's state gates it: the
    subject is the FILE, judged before any command composes. Same
    handler-tier posture as `ChecksumVerifierUnsupportedSchemeError`.

    Covers: the reader refusing the bytes (unreadable, unrecognized
    layout, structurally incomplete), the digest pass failing, the file
    changing while being read, a missing acquisition timestamp with no
    operator-supplied one, and a supplied timestamp alongside a
    parseable file value (ambiguous). The message always names the
    remedy, because the operator holding it is the only one who can act.

    Subclasses ValueError so the shared schema validator can raise it
    directly for the declared evidence shape.
    """


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
