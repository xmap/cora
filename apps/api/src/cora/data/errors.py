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

from enum import StrEnum


class ScanFileInvalidReason(StrEnum):
    """Why `InvalidScanFileError` refused a scan file, discriminated from
    the message text so a caller can branch on cause without parsing a
    string or ever touching the path the message may (redacted or not)
    embed.

    One member per raise site in `ingest_scan.handler`; none merged.
    Every pair considered kept a real diagnostic distinction: the two
    `captured_at` members have opposite remedies (drop the supplied
    value versus supply one); `UNREADABLE` and `DIGEST_UNREACHABLE` are
    distinct pipeline stages behind distinct ports, and collapsing them
    would lose which pass failed; `LOCATOR_UNRESOLVED` and
    `LOCATOR_MISSING_FILENAME` fail for different reasons at different
    call sites.

    `is_transient` is the machine-readable permanent/transient split:
    true when retrying the SAME command unmodified could plausibly
    succeed once the file's writer finishes; false when nothing about
    the file changing can help, because the fix requires the caller to
    change the request, the file, or the configuration. Each
    classification below is cited from the code that justifies it, not
    from intuition.

      - `LOCATOR_UNRESOLVED` (permanent): `resolve_capture_path_locator`
        returns `None` only for "malformed locator; no vault row at
        all; a row that exists but not at the location the locator
        names; filename mismatch" (its own docstring). The sweep's
        candidate query only selects vault rows that already exist, so
        a failure here is drift or misconfiguration, not a file still
        arriving.
      - `UNREADABLE` (transient): `ScanReader`'s port docstring: "may be
        transient: a half-transferred file on the analysis tier is an
        expected observable, and the caller decides whether to retry."
      - `UNRECOGNIZED` (permanent): the same `ScanReader` docstring
        pointedly withholds the "may be transient" language from this
        variant; it fires only when the layout's one mandatory dataset
        is entirely absent, a layout verdict rather than an I/O timing
        issue.
      - `STRUCTURALLY_INCOMPLETE` (permanent): `DataExchangeScanReader`
        documents the absent rotation-angle dataset as meaning
        post-processing "has not completed (not yet run, failed
        permanently... or a scan that produced zero projections)". The
        sweep only ever considers terminal runs (`status IN
        ('Completed', 'Aborted')`), which narrows but does not fully
        eliminate the "not yet run" sub-case this member bundles
        together with the two permanent ones; whoever builds the
        finality-axis work the port docstring defers should revisit
        this member first.
      - `DIGEST_UNREACHABLE` (transient): reuses `ChecksumVerifier`'s
        `Unreachable`, whose docstring says outright "(transient)".
      - `CHANGED_WHILE_READING` (transient): fires only when size or
        mtime moved between two stat snapshots taken moments apart,
        which by construction means a writer touched the file during
        the read window.
      - `CAPTURED_AT_AMBIGUOUS` (permanent): the remedy is to drop the
        supplied value; the CALLER's request must change, not the file.
      - `CAPTURED_AT_MISSING` (permanent): the remedy requires an
        operator to supply `captured_at` manually. `CaptureScanIngestor`
        (the only automated caller) never passes `captured_at`, so this
        can never self-resolve through automated retry.
      - `LOCATOR_MISSING_FILENAME` (permanent): the locator names a
        directory, not a file; a caller/configuration defect, not a
        file-readiness one.

    Member name SCREAMING_SNAKE; string value PascalCase, matching
    `AttestationKind`'s house style. Values are plain enum labels only
    and must never embed, interpolate, or derive from a filesystem
    path, so they stay safe to log and persist forever.
    """

    LOCATOR_UNRESOLVED = "LocatorUnresolved"
    UNREADABLE = "Unreadable"
    UNRECOGNIZED = "Unrecognized"
    STRUCTURALLY_INCOMPLETE = "StructurallyIncomplete"
    DIGEST_UNREACHABLE = "DigestUnreachable"
    CHANGED_WHILE_READING = "ChangedWhileReading"
    CAPTURED_AT_AMBIGUOUS = "CapturedAtAmbiguous"
    CAPTURED_AT_MISSING = "CapturedAtMissing"
    LOCATOR_MISSING_FILENAME = "LocatorMissingFilename"

    @property
    def is_transient(self) -> bool:
        """See the class docstring for the per-member citation backing
        this split; kept as a property (not a bare frozenset check
        inline at each call site) so the transient/permanent verdict
        has exactly one place to change."""
        return self in _TRANSIENT_SCAN_FILE_INVALID_REASONS


_TRANSIENT_SCAN_FILE_INVALID_REASONS = frozenset(
    {
        ScanFileInvalidReason.UNREADABLE,
        ScanFileInvalidReason.DIGEST_UNREACHABLE,
        ScanFileInvalidReason.CHANGED_WHILE_READING,
    }
)


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

    `reason` carries the same cause as a closed, non-PII
    `ScanFileInvalidReason` a caller can branch on (whether to keep
    retrying, for instance) without parsing `message` or risking a path
    it may embed; see that enum for the permanent/transient split.
    `message` remains the sole content of `str(exc)`, unchanged, so
    every existing catcher that ignores `reason` behaves identically.

    Subclasses ValueError so the shared schema validator can raise it
    directly for the declared evidence shape.
    """

    def __init__(self, message: str, *, reason: ScanFileInvalidReason) -> None:
        super().__init__(message)
        self.reason = reason


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
