"""Shared types for observation-logbook declaration.

A **logbook** is a header on an aggregate's main event stream that
declares an attached observation logbook — a parallel, append-only
sequence of fine-grained entries (per-frame triggers, motor positions,
authz traversals, etc.) that does NOT fold into the parent aggregate's
state.

The pattern is borrowed from Bluesky's `EventDescriptor` document:
the descriptor (here: `<Aggregate>LogbookOpened` event) declares the
schema and lifecycle of a logbook; the per-row entries (here: rows in
an `entries_<kind>` table) live elsewhere keyed by `logbook_id`.

The Conduit aggregate is the first use site (traversals logbook).
Run / Decision / Asset adopt the same pattern when their first
observation kind ships.

## Why these types live in shared infrastructure

Logbook declarations are a cross-aggregate pattern. Run, Conduit,
Decision, Asset will all declare logbooks with the same shape (kind +
schema + lifecycle). The `LogbookSchema` representation needs to be
identical so observation projections can read schemas uniformly
across aggregates without per-BC adapters.

## Why the schema representation is documentation-grade today

The locked 6f-5 design (gate-review G8) keeps the schema
representation deliberately simple: a `dict[str, LogbookFieldSpec]`
with type/units/description per column. This satisfies the audit /
regulatory requirement (instrument config at time of measurement; 21
CFR Part 11, ISO 17025) without committing to a specific validator
stack. When schema validation actually matters (multi-version
logbooks, contract testing, schema-driven UI), this representation
can grow into a fuller model. Don't reach for JSON Schema or Pydantic
yet.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

LogbookFieldType = Literal["string", "uuid", "datetime", "int", "float", "bool"]


@dataclass(frozen=True)
class LogbookFieldSpec:
    """Declaration of one column in a logbook's entries.

    `type` names the on-the-wire primitive type (the entry payload's
    column type); `units` is for numeric measurements (temperature,
    angle, etc.; the actual unit is a UDUNITS/UCUM code, see
    [[project-units-design]]); `description` is free-text audit context.
    """

    type: LogbookFieldType
    units: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict for event payload storage."""
        out: dict[str, Any] = {"type": self.type}
        if self.units is not None:
            out["units"] = self.units
        if self.description is not None:
            out["description"] = self.description
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LogbookFieldSpec":
        """Rebuild from a stored dict. Defensive on missing optionals."""
        return cls(
            type=raw["type"],
            units=raw.get("units"),
            description=raw.get("description"),
        )


@dataclass(frozen=True)
class LogbookSchema:
    """Declaration of the entry-row shape a logbook produces.

    `fields` maps column name to spec. Field-name uniqueness is
    enforced by the dict; ordering is irrelevant (entries are keyed
    by their own `event_id`, not by column position).

    `description` is free-text audit context for the logbook as a
    whole (for example: "Eiger-9M frame trigger metadata, 21 keV,
    fly-scan tomography").
    """

    fields: dict[str, LogbookFieldSpec] = field(default_factory=dict[str, LogbookFieldSpec])
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict for event payload storage."""
        out: dict[str, Any] = {
            "fields": {name: spec.to_dict() for name, spec in self.fields.items()},
        }
        if self.description is not None:
            out["description"] = self.description
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LogbookSchema":
        """Rebuild from a stored dict."""
        raw_fields = raw.get("fields", {})
        return cls(
            fields={name: LogbookFieldSpec.from_dict(spec) for name, spec in raw_fields.items()},
            description=raw.get("description"),
        )


__all__ = [
    "LogbookFieldSpec",
    "LogbookFieldType",
    "LogbookSchema",
]
