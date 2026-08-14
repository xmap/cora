"""Generate the record-export redaction disposition table.

The record exporter decides what to publish from a field's DECLARED TYPE
(see the F5 section of `project_record_export_v3.md`). Answering "is this
annotation a StrEnum, a str alias, or a value object" needs the defining
module imported, and the exporter lives at `cora.infrastructure`, where
`tach.toml` allows `cora.shared` and nothing else. So the question is
answered HERE, at build time, by a tool that may import every bounded
context, and the answer is committed as inert data the exporter reads.

This mirrors `make openapi-snapshot`: a generated artifact in the tree,
a drift test that fails until it is regenerated, and a diff a reviewer
can read. Living OUTSIDE `src/` is deliberate and structural, not
cosmetic: nothing the application ships can import this module, so the
exporter cannot acquire the BC dependency the design forbids it.

Run it with:

    make record-dispositions

Resolution happens on real type objects rather than on annotation
strings, which is the point. A plain alias (`ActorId = UUID`) collapses
to its target for free; only `NewType` and genuine value objects need
handling. An annotation this tool cannot classify ABORTS the run: an
unrecognized type is a question about the design, not a row to skip.
"""

from __future__ import annotations

import dataclasses
import enum
import importlib
import inspect
import json
import subprocess
import sys
import types
import typing
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, NewType, Union, get_args, get_origin
from uuid import UUID

from cora.shared.closed_value import ClosedValueObject

_API_ROOT = Path(__file__).resolve().parents[1]
_SRC = _API_ROOT / "src"
_OUT = _SRC / "cora" / "infrastructure" / "record_export" / "_dispositions.py"

KEEP_CLOSED = "keep:closed"
KEEP_ENUM = "keep:enum"
KEEP_NUMBER = "keep:number"
KEEP_TIME = "keep:time"
TOKEN_UUID = "token:uuid"
DROP_TEXT = "drop:text"
DROP_OPAQUE = "drop:opaque"
BY_VALUE = "by-value"

# A field's dataclass name occasionally differs, DELIBERATELY, from the
# key `to_payload` actually writes it under. Every entry here is a
# documented design decision in the event module itself, not a typo:
# `to_payload` and `from_stored` already agree with EACH OTHER on the
# wire key, so nothing about the stored bytes changes; only the
# generated table's lookup key does, so redaction can find the field it
# already knows the wire calls something else. Renaming the dataclass
# field instead was rejected for the Seal events specifically because
# the wire key is under a cryptographic-chain immutability lock (Seal
# events.py's own module docstring, `project_slice6_design` L7); the
# other two follow the same convention for consistency across
# Federation's identity-bearing events.
_OVERRIDE_WIRE_KEYS: dict[tuple[str, str], str] = {
    ("CredentialRegistered", "facility_code"): "facility_id",
    ("PermitDefined", "peer_facility_code"): "peer_facility_id",
    ("SealInitialized", "facility_code"): "facility_id",
    ("SealPointerSigned", "facility_code"): "facility_id",
    ("SealOnlineKeyRotated", "facility_code"): "facility_id",
    ("SealRepublishingStarted", "facility_code"): "facility_id",
    ("SealRepublishingCompleted", "facility_code"): "facility_id",
}

# A field's TYPE-DRIVEN disposition is occasionally the wrong call for
# what the field actually names, not what it happens to be declared as.
# Every entry here is a documented design decision, not a generic
# catch-all: `bool` defaults to `keep:number` (see `_SCALAR_KEEP`) because
# most booleans are operator-facing flags safe to publish whole, but
# `SafetyEnvelopeVerdict.enclosure_permitted` / `.beam_available` are a
# point-in-time reading of live PSS/interlock and beam-shutter facility
# state -- the same class of fact `EnclosurePermitObserved.from_status` /
# `.to_status` already treat as `drop:text` (dropped entirely), not
# `keep:*`. Gate-review finding (record/publishing lens, watched-genesis
# review): the two events described the same category of fact but got
# opposite export treatment purely because one used `str` and the other
# `bool`. Keeping the fields genuinely typed `bool` (correct domain
# modeling; no `str` coercion) while overriding their export disposition
# to match the precedent this table already sets for the same class of
# reading.
_OVERRIDE_DISPOSITIONS: dict[tuple[str, str], str] = {
    ("SafetyEnvelopeVerdict", "enclosure_permitted"): DROP_TEXT,
    ("SafetyEnvelopeVerdict", "beam_available"): DROP_TEXT,
}

_SCALAR_KEEP: Mapping[type, str] = {
    bool: KEEP_NUMBER,
    int: KEEP_NUMBER,
    float: KEEP_NUMBER,
    datetime: KEEP_TIME,
}

_CONTAINER_ORIGINS = (tuple, frozenset, set, list)


class UnclassifiedAnnotationError(Exception):
    """An annotation no rule in F5 covers. Aborts the run by design."""

    def __init__(self, event: str, field: str, annotation: object) -> None:
        super().__init__(
            f"{event}.{field}: cannot classify {annotation!r}. "
            "Add a rule to gen_record_dispositions.py, or change the "
            "declared type. Do NOT silently drop it."
        )


def _union_variants(annotation: Any) -> list[Any] | None:
    """Non-None members of a union, or None if this is not a union."""
    origin = get_origin(annotation)
    if origin is not Union and origin is not types.UnionType:
        return None
    return [a for a in get_args(annotation) if a is not type(None)]


def _merge(
    variants: Sequence[str | dict[str, Any]], event: str, field: str, ann: Any
) -> str | dict[str, Any]:
    """Fold the dispositions of a union's variants into one.

    Scalars must agree. Value objects are MERGED, because a discriminated
    union stores whichever arm's keys, so the published rule has to cover
    every arm. A key two arms disagree on is a real ambiguity and aborts.
    """
    if all(isinstance(v, str) for v in variants):
        if len({typing.cast("str", v) for v in variants}) == 1:
            return typing.cast("str", variants[0])
        return BY_VALUE
    if not all(isinstance(v, dict) for v in variants):
        # A slot spanning scalars AND value objects (a Recipe setpoint is
        # a number, a channel string, or a binding reference) cannot be
        # decided statically. Defer to the same leaf rule the tier-2 jsonb
        # columns already use, which is fail-closed on strings.
        return BY_VALUE
    merged: dict[str, Any] = {}
    for variant in variants:
        for key, disposition in typing.cast("dict[str, Any]", variant).items():
            if key in merged and merged[key] != disposition:
                raise UnclassifiedAnnotationError(event, field, ann)
            merged[key] = disposition
    return merged


def _is_value_object(annotation: Any) -> bool:
    """True for a frozen dataclass, which has declared fields to recurse into."""
    if not inspect.isclass(annotation) or not dataclasses.is_dataclass(annotation):
        return False
    params: Any = getattr(annotation, "__dataclass_params__", None)
    return bool(params is not None and params.frozen)


def _classify(annotation: Any, event: str, field: str) -> str | dict[str, Any]:
    """Map one resolved annotation to a disposition, per the F5 table."""
    if isinstance(annotation, typing.TypeAliasType):
        return _classify(annotation.__value__, event, field)

    variants = _union_variants(annotation)
    if variants is not None:
        if len(variants) == 1:
            return _classify(variants[0], event, field)
        return _merge([_classify(v, event, field) for v in variants], event, field, annotation)

    if annotation is Any:
        return DROP_OPAQUE

    if isinstance(annotation, NewType):
        return _classify(annotation.__supertype__, event, field)

    if get_origin(annotation) is Literal:
        args = get_args(annotation)
        if all(isinstance(a, str) for a in args):
            return KEEP_ENUM
        if all(isinstance(a, bool | int | float) for a in args):
            return KEEP_NUMBER
        raise UnclassifiedAnnotationError(event, field, annotation)

    if inspect.isclass(annotation):
        if issubclass(annotation, enum.Enum):
            # Name the enum. The value set is what a human signs off, so
            # the disposition has to say WHICH set, and swapping one enum
            # for another must show up as drift rather than as no change.
            return f"{KEEP_ENUM}:{annotation.__name__}"
        if annotation is UUID:
            return TOKEN_UUID
        if annotation is str:
            return DROP_TEXT
        for scalar, disposition in _SCALAR_KEEP.items():
            if annotation is scalar:
                return disposition
        if _is_value_object(annotation):
            if issubclass(annotation, ClosedValueObject):
                # The whole VO closes its own range by construction (see
                # `ClosedValueObject`'s docstring for the criterion); KEEP
                # it whole rather than resolving field by field, so a
                # bare `str` field inside it (a hex digest) does not fall
                # through the generic drop-by-default rule that field
                # would otherwise get on its own.
                return f"{KEEP_CLOSED}:{annotation.__name__}"
            return _resolve_fields(annotation)

    origin = get_origin(annotation)
    if origin in _CONTAINER_ORIGINS:
        raw = get_args(annotation)
        args = [a for a in raw if a is not Ellipsis]
        if not args:
            raise UnclassifiedAnnotationError(event, field, annotation)
        inner = [_classify(a, event, field) for a in args]
        if origin is tuple and Ellipsis not in raw and len(inner) > 1:
            # A fixed-length heterogeneous tuple is a positional record,
            # not a collection: `tuple[str, float]` is (name, value) and
            # its two slots get different answers. Emit one per position.
            return {"[]": inner}
        if any(candidate != inner[0] for candidate in inner[1:]):
            raise UnclassifiedAnnotationError(event, field, annotation)
        return inner[0]
    if origin in (dict, Mapping, MutableMapping):
        return DROP_OPAQUE

    raise UnclassifiedAnnotationError(event, field, annotation)


def _resolve_fields(cls: type) -> dict[str, Any]:
    """Disposition per field of one dataclass, recursing into value objects.

    The table is keyed on the STORED key, per `_OVERRIDE_WIRE_KEYS`, when
    a field's dataclass name deliberately differs from what `to_payload`
    writes it under; every other field's key is just its own name. Only
    ever consulted with `cls.__name__` as the class actually being
    resolved, so an override keyed on an EVENT class name (e.g.
    `("CredentialRegistered", "facility_code")`) cannot accidentally
    apply while recursing into an unrelated nested value object that
    happens to share a field name. `_OVERRIDE_DISPOSITIONS` replaces the
    type-driven classification outright, under the same recursion-safety
    guarantee, for the rarer case where the type's default answer is
    wrong for what the field actually names (see that dict's docstring).
    """
    hints = typing.get_type_hints(cls)
    out: dict[str, Any] = {}
    for spec in dataclasses.fields(cls):
        wire_key = _OVERRIDE_WIRE_KEYS.get((cls.__name__, spec.name), spec.name)
        override = _OVERRIDE_DISPOSITIONS.get((cls.__name__, spec.name))
        out[wire_key] = (
            override
            if override is not None
            else _classify(hints[spec.name], cls.__name__, spec.name)
        )
    return out


def _event_modules() -> list[str]:
    """Dotted names of every `events.py` under the cora package."""
    names: list[str] = []
    for path in sorted((_SRC / "cora").rglob("events.py")):
        names.append(".".join(path.relative_to(_SRC).with_suffix("").parts))
    return names


def _event_classes(module_name: str) -> Iterable[type]:
    """Frozen dataclasses DEFINED in this module, deduplicated by identity.

    A single-member union alias (`AcquisitionEvent = AcquisitionRecorded`)
    binds one class under two module-level names, so `getmembers` yields
    it twice. Dedupe on identity, not on name.
    """
    module = importlib.import_module(module_name)
    seen: set[int] = set()
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module_name or not _is_value_object(obj):
            continue
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        yield obj


def _wire_name(module_name: str, cls: type) -> str:
    """The string this class is STORED under, asked of the real writer.

    The table is keyed on `events.event_type`, and that is not reliably
    the class name: `ActorRegistered` writes `"ActorRegisteredV2"`. A
    generator that assumes the two agree produces a table the exporter
    cannot look up, which is not a degraded export but no export at all,
    since redaction refuses an unknown event type. Every real database
    holds an Actor registration from bootstrap, so the redacted export
    path was unreachable for every real record until this was fixed.

    So the name is taken from each module's own `event_type_name`, the
    same function the append path calls, rather than re-derived here.
    Those functions discriminate on type alone, so an instance that was
    never `__init__`ed answers correctly and no field values have to be
    invented. If one ever reads a field, this raises and the run ABORTS,
    matching how the tool treats an annotation it cannot classify: an
    unanswerable question about the model, not a row to skip.
    """
    module = importlib.import_module(module_name)
    resolve = getattr(module, "event_type_name", None)
    if resolve is None:
        raise RuntimeError(
            f"{module_name} defines event classes but no `event_type_name`, so "
            "the string they are stored under cannot be established. Add the "
            "function, or the export table will key on a name that may not be "
            "what the append path writes."
        )
    try:
        name = resolve(object.__new__(cls))
    except Exception as exc:
        raise RuntimeError(
            f"{module_name}.event_type_name failed on an uninitialised "
            f"{cls.__name__} ({exc!r}). It reads a field rather than "
            "discriminating on type, so this tool can no longer establish the "
            "stored name without inventing values. Teach the tool about it "
            "deliberately rather than falling back to the class name."
        ) from exc
    if not isinstance(name, str) or not name:
        raise RuntimeError(
            f"{module_name}.event_type_name returned {name!r} for "
            f"{cls.__name__}; expected the non-empty string it is stored under."
        )
    return name


def build_table(survey: bool = False) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Disposition per (event type, field) across every bounded context.

    With `survey`, collect every unclassified annotation instead of
    aborting on the first. The generator still refuses to write a table
    while any remain; the flag exists so the tail can be read in one
    pass rather than one exception at a time.
    """
    table: dict[str, dict[str, Any]] = {}
    unclassified: list[str] = []
    for module_name in _event_modules():
        for cls in _event_classes(module_name):
            wire_name = _wire_name(module_name, cls)
            if wire_name in table:
                raise RuntimeError(
                    f"Duplicate stored event type {wire_name!r} (from class "
                    f"{cls.__name__}); the table is keyed on what "
                    "`events.event_type` stores. Rename one, or key on the "
                    "qualified name."
                )
            if not survey:
                table[wire_name] = _resolve_fields(cls)
                continue
            try:
                table[wire_name] = _resolve_fields(cls)
            except UnclassifiedAnnotationError as exc:
                unclassified.append(str(exc).split(".", 1)[0] + ": " + str(exc))
    return dict(sorted(table.items())), unclassified


def render(table: Mapping[str, Mapping[str, Any]]) -> str:
    """Render the table as a committed Python module."""
    body = json.dumps(table, indent=4, sort_keys=True)
    return f'''"""Generated redaction dispositions. DO NOT EDIT BY HAND.

Regenerate with `make record-dispositions`;
`tests/architecture/test_record_dispositions_drift.py` fails until you do.

One entry per event type, one disposition per declared field, resolved
from the field's real type by `tools/gen_record_dispositions.py`. The
vocabulary:

    keep:enum:<Name>       closed value set, provably reviewable. The
                           enum is NAMED because a human signs off the
                           value set, and swapping one enum for another
                           must read as drift.
    keep:closed:<Name>       a value object every one of whose fields is
                           closed by construction (a fixed charset and
                           length, a closed literal set), kept WHOLE
                           rather than resolved field by field. See
                           `cora.shared.closed_value.ClosedValueObject`.
    keep:number            int / float / bool
    keep:time              datetime
    token:uuid             replaced with a per-export random surrogate
    drop:text              free text, no finite range, dropped by default
    drop:opaque            a dict with no declared keys, nothing to
                           allowlist
    by-value               the slot is polymorphic across scalars and
                           objects, so no static answer exists. Apply the
                           tier-2 leaf rule at export time: numbers and
                           booleans keep, UUID-shaped strings token,
                           other strings drop.

A nested mapping is a value object recursed into. A mapping whose sole
key is `[]` is a fixed-length heterogeneous tuple, and its value lists
one disposition per position.

Redaction iterates the STORED payload's keys and looks each up here. A
key absent from its event's entry is dropped; an event type absent from
this table aborts the export. The canonical hash of this mapping is the
redaction profile hash recorded in the export manifest.

A handful of entries are keyed on the WIRE key a field is actually
stored under rather than its dataclass field name, per
`gen_record_dispositions.py`'s `_OVERRIDE_WIRE_KEYS`: the two never
disagree about what ships, only about which name this table's lookup
uses to find it.
"""

from typing import Any

DISPOSITIONS: dict[str, dict[str, Any]] = {body}
'''


def main() -> int:
    survey = "--survey" in sys.argv
    table, unclassified = build_table(survey=survey)
    if unclassified:
        print(f"{len(unclassified)} unclassified annotations:", file=sys.stderr)
        for line in unclassified:
            print(f"  {line}", file=sys.stderr)
        return 1
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(render(table), encoding="utf-8")
    # Format in place so the committed artifact is what `make lint`
    # expects. Without this the generator and the formatter disagree and
    # the drift test can never be green at the same time as lint.
    formatted = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--quiet", str(_OUT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if formatted.returncode != 0:
        print(formatted.stderr, file=sys.stderr)
        return 1
    fields = sum(len(v) for v in table.values())
    print(f"{len(table)} event types, {fields} fields -> {_OUT.relative_to(_API_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
