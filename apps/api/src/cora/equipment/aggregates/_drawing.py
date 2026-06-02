"""Drawing value object: a typed reference to an engineering drawing.

A `Drawing` is a structured pointer to a document in some external
document-management system, not the document itself. Engineering
drawings travel as a triple of `(system, number, revision)` per ISO
7200 title-block convention, CFIHOS handover specs, and every PLM /
EDMS in the corpus (Teamcenter Dataset, Documentum, ICMS, ...).

Storing the system separately from the number means CORA can hold
references across facilities without assuming a single document
registry: APS uses ICMS; MAX IV will use something else; PIDINST
mints DOIs.

Revision is optional. `revision = None` means "resolves to latest"
(ISO 7200 / DOI / EDMS default-resolution semantics). When present,
the Drawing references a specific snapshot. Whether a facility's
adapter actually exposes latest-resolution is a per-adapter contract
(Watch item: ICMS latest-resolution semantics need adapter
confirmation before the first revision-less Drawing is registered).

`Drawing` is a closed-shape frozen dataclass. NOT
`json_schema_validation` (that pattern is for declarer-owns-schema /
carrier-owns-dict); validation lives in field shape + enum
membership + `validate_bounded_text` from
`cora.infrastructure.bounded_text` (the 22nd hoisting site for the
trim + length-check + raise pattern; AssetPort precedent uses
per-field error classes).

`DrawingSystem` is an extensible StrEnum (registry of accepted
systems enforced per-facility at the adapter boundary, NOT in the
VO).

Used as an optional field on both `Mount` (where the slot is in the
beamline) and `Asset` (what the specimen was built to). The two are
different documents; do NOT collapse them.

Promote to a full `Document` BC only when drawings need their own
lifecycle (review status, supersedes-chain, ECO propagation per
MIL-HDBK-61A 5.4 / CMII, ACL).
"""

from dataclasses import dataclass
from enum import StrEnum

from cora.infrastructure.bounded_text import validate_bounded_text

DRAWING_NUMBER_MAX_LENGTH = 200
DRAWING_REVISION_MAX_LENGTH = 100


class InvalidDrawingError(ValueError):
    """Base class for Drawing VO validation failures.

    Tests catch the specific subclasses (`InvalidDrawingNumberError`,
    `InvalidDrawingRevisionError`) when they need to distinguish the
    failing field. The route layer's `_handle_validation_error`
    catches the base class and surfaces `str(exc)` into the 400
    body, so the formatted message is the user-facing surface;
    subclass-specific routing is not required today.

    Lives in this module (an aggregate-scoped private VO module) so
    aggregate state.py / events.py can import without violating the
    aggregates-don't-depend-on-BC-root tach layering rule.
    """


class InvalidDrawingNumberError(InvalidDrawingError):
    """`Drawing.number` failed bounded-text validation.

    Raised by `validate_bounded_text` when the trimmed number is
    empty / whitespace-only or exceeds `DRAWING_NUMBER_MAX_LENGTH`.
    `value` carries the original untrimmed input for diagnostics
    (mirrors the `InvalidAssetPortNameError` shape).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Invalid Drawing number (must be 1-{DRAWING_NUMBER_MAX_LENGTH} "
            f"chars after trimming, got: {value!r})"
        )
        self.value = value


class InvalidDrawingRevisionError(InvalidDrawingError):
    """`Drawing.revision` failed bounded-text validation.

    Raised by `validate_bounded_text` when the revision is present
    but trimmed empty or exceeds `DRAWING_REVISION_MAX_LENGTH`. To
    indicate 'latest' (resolves at the adapter), pass `revision=None`
    instead of an empty string. `value` carries the original
    untrimmed input.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Invalid Drawing revision (must be 1-{DRAWING_REVISION_MAX_LENGTH} "
            f"chars after trimming, or None for 'latest'; got: {value!r})"
        )
        self.value = value


class DrawingSystem(StrEnum):
    """The external document-management system a Drawing lives in.

    Closed StrEnum: v1 ships with three systems. Adding a new value
    is a paired change: extend this enum AND ship a migration that
    drops + re-adds the CHECK constraint on `drawing_system` in any
    projection that materializes drawings (today: `proj_equipment_
    asset_summary`). Whether a given system value is actually wired
    to an adapter is enforced per-facility at the adapter boundary,
    NOT here.

      - `ICMS`: APS Information Content Management System (Documentum-
        backed).
      - `EDMS`: generic Engineering Document Management System
        (CERN EDMS and similar).
      - `DOI`: DataCite Digital Object Identifier (used by PIDINST
        for instrument-level identifiers).
    """

    ICMS = "ICMS"
    EDMS = "EDMS"
    DOI = "DOI"


@dataclass(frozen=True)
class Drawing:
    """A typed reference to an engineering drawing in an external system.

    `system` says which document registry; `number` is the document
    identifier within that registry; `revision` is the optional
    snapshot pin (None means "latest").

    Equality and hash are structural across the three fields, so two
    Drawing instances referring to the same `(system, number, revision)`
    triple collapse in a set.
    """

    system: DrawingSystem
    number: str
    revision: str | None = None

    def __post_init__(self) -> None:
        trimmed_number = validate_bounded_text(
            self.number,
            max_length=DRAWING_NUMBER_MAX_LENGTH,
            error_class=InvalidDrawingNumberError,
        )
        object.__setattr__(self, "number", trimmed_number)

        if self.revision is not None:
            trimmed_revision = validate_bounded_text(
                self.revision,
                max_length=DRAWING_REVISION_MAX_LENGTH,
                error_class=InvalidDrawingRevisionError,
            )
            object.__setattr__(self, "revision", trimmed_revision)


def drawing_to_payload(drawing: Drawing) -> dict[str, object]:
    """Serialize a Drawing VO to a JSON-friendly dict for jsonb storage.

    Canonical codec shared by every aggregate event that carries a
    Drawing (Mount, Asset, Assembly). Sibling rebuilder is
    `drawing_from_payload`. Hoisted to the VO module to close the
    duplication anti-hook flagged in `project_mount_frame_design`
    Watch items.
    """
    return {
        "system": drawing.system.value,
        "number": drawing.number,
        "revision": drawing.revision,
    }


def drawing_from_payload(payload: dict[str, object]) -> Drawing:
    """Reconstruct a Drawing VO from its JSON payload.

    Sibling of `drawing_to_payload`. Round-trips losslessly with it.
    Re-runs Drawing.__post_init__ validation.
    """
    return Drawing(
        system=DrawingSystem(str(payload["system"])),
        number=str(payload["number"]),
        revision=(str(payload["revision"]) if payload.get("revision") is not None else None),
    )


__all__ = [
    "DRAWING_NUMBER_MAX_LENGTH",
    "DRAWING_REVISION_MAX_LENGTH",
    "Drawing",
    "DrawingSystem",
    "drawing_from_payload",
    "drawing_to_payload",
]
