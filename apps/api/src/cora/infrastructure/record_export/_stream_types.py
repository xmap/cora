"""The closed set of `events.stream_type` values.

No such set exists anywhere else in the code: each BC's aggregate/slice
declares its own `_STREAM_TYPE = "X"` module constant (42 distinct
literals across 211 declarations at last count), and `stream_type` on
`events` is a bare `text` column with no DB or Python enum closing it.

The exporter needs one anyway: per `project_record_export_build_brief.md`
step 2's acceptance criteria, "an unknown `stream_type` refuses rather
than skips ... silently skipping is pass-while-differing." So this
module declares the closed set explicitly, the same shape as
`_registry.py`'s `kind` registry, and
`test_record_export_stream_types_completeness.py` AST-discovers every
`_STREAM_TYPE` literal under `src/cora` and pins it against
`KNOWN_STREAM_TYPES` in both directions so a new BC cannot silently fall
through `ensure_stream_type_known` as "skip" instead of "refuse".
"""

KNOWN_STREAM_TYPES: frozenset[str] = frozenset(
    {
        "Acquisition",
        "Actor",
        "Agent",
        "Allocation",
        "Assembly",
        "Asset",
        "Attestation",
        "Calibration",
        "Campaign",
        "Capability",
        "Caution",
        "Clearance",
        "ClearanceTemplate",
        "Conduit",
        "Credential",
        "Dataset",
        "Decision",
        "Distribution",
        "Edition",
        "Enclosure",
        "Facility",
        "Family",
        "Fixture",
        "Frame",
        "LanguageModel",
        "Method",
        "Model",
        "Mount",
        "Permit",
        "Plan",
        "Policy",
        "Practice",
        "Procedure",
        "Ratification",
        "Recipe",
        "Role",
        "Run",
        "Seal",
        "Subject",
        "Supply",
        "Surface",
        "Visit",
        "Zone",
    }
)


class UnknownStreamTypeError(LookupError):
    """A `stream_type` with no entry in `KNOWN_STREAM_TYPES`.

    Refuses loudly rather than being silently skipped: skipping an
    unrecognised stream is "pass while differing" per the build brief's
    trap list, not a safe default.
    """

    def __init__(self, stream_type: str) -> None:
        super().__init__(
            f"unknown events.stream_type {stream_type!r}; not in "
            "KNOWN_STREAM_TYPES. A new BC's stream_type must be added "
            "here before its streams can be exported."
        )
        self.stream_type = stream_type


def ensure_stream_type_known(stream_type: str) -> None:
    """Raise `UnknownStreamTypeError` unless `stream_type` is declared."""
    if stream_type not in KNOWN_STREAM_TYPES:
        raise UnknownStreamTypeError(stream_type)
