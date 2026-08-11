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

_API_ROOT = Path(__file__).resolve().parents[1]
_SRC = _API_ROOT / "src"
_OUT = _SRC / "cora" / "infrastructure" / "record_export" / "_dispositions.py"

KEEP_ENUM = "keep:enum"
KEEP_NUMBER = "keep:number"
KEEP_TIME = "keep:time"
TOKEN_UUID = "token:uuid"
DROP_TEXT = "drop:text"
DROP_OPAQUE = "drop:opaque"
BY_VALUE = "by-value"

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
    """Disposition per field of one dataclass, recursing into value objects."""
    hints = typing.get_type_hints(cls)
    out: dict[str, Any] = {}
    for spec in dataclasses.fields(cls):
        out[spec.name] = _classify(hints[spec.name], cls.__name__, spec.name)
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
            if cls.__name__ in table:
                raise RuntimeError(
                    f"Duplicate event class name {cls.__name__!r}; the table is "
                    "keyed on the bare name because that is what `events.event_type` "
                    "stores. Rename one, or key on the qualified name."
                )
            if not survey:
                table[cls.__name__] = _resolve_fields(cls)
                continue
            try:
                table[cls.__name__] = _resolve_fields(cls)
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

    keep:enum:<Name>  closed value set, provably reviewable. The enum is
                      NAMED because a human signs off the value set, and
                      swapping one enum for another must read as drift.
    keep:number       int / float / bool
    keep:time         datetime
    token:uuid        replaced with a per-export random surrogate
    drop:text         free text, no finite range, dropped by default
    drop:opaque       a dict with no declared keys, nothing to allowlist
    by-value          the slot is polymorphic across scalars and objects,
                      so no static answer exists. Apply the tier-2 leaf
                      rule at export time: numbers and booleans keep,
                      UUID-shaped strings token, other strings drop.

A nested mapping is a value object recursed into. A mapping whose sole
key is `[]` is a fixed-length heterogeneous tuple, and its value lists
one disposition per position.

Redaction iterates the STORED payload's keys and looks each up here. A
key absent from its event's entry is dropped; an event type absent from
this table aborts the export. The canonical hash of this mapping is the
redaction profile hash recorded in the export manifest.
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
