"""Design-intent markers for fields that masquerade as structural-scope refs.

Three marker classes, attached via `typing.Annotated`, that record an
explicit design-intent stance on bare-str / closed-enum fields the
axes-foundation structural-scope audit (Refactor #4) flagged as
"masquerading as references to a missing aggregate". Each marker
records a different stance:

  - `NamedFor(target_name=...)`: the field references conceptually-real
    entity X by name/key today, BUT X has no aggregate. Promote to a
    typed `<X>Id` relational ref when the X aggregate ships. Use when
    the deferral is "aggregate doesn't exist yet but will."

  - `DeferredVocabulary(target_name=..., trigger_doc=...)`: the bare
    string is conceptually closed enum X; the vocabulary is not yet
    earned. Graduates to typed `X(StrEnum)` when the documented trigger
    fires. Use when the deferral is "vocabulary will tighten on an
    existing aggregate's classifier."

  - `SubsumedBy(subsumed_target_name=..., subsuming_aggregate_names=...)`:
    the field looks like it might want aggregate X, BUT the template /
    scope role is already filled by aggregates Y, Z, ... so X must NOT
    be promoted independently. PERMANENT marker. Stronger than
    `DeferredVocabulary` because future contributors reading a deferral
    would otherwise reasonably create a duplicate template layer.

Markers are recognised at runtime via `typing.get_type_hints(..., include_extras=True)`
and statically via `tests/architecture/test_scope_markers.py` (AST walk).
Per the design lock at `project_structural_scope_design.md` §"Marker
convention", these three instantiated-not-parameterised dataclasses are
deliberately preferred over `Generic[X]` parameterisation because
AST-walk fitness detection is simpler against instantiated metadata.

Zero runtime behaviour change: the markers carry no validators, no
post-init hooks, and produce identical mypy / pyright types via
`Annotated[T, ...]` (the metadata tuple is erased at the type-checker
level).
"""

from dataclasses import dataclass
from typing import Annotated


@dataclass(frozen=True, slots=True)
class NamedFor:
    """The field references an entity-by-name whose aggregate does not yet exist.

    Migrates to a typed relational ref (e.g. `target_id: TargetId`) when
    the aggregate ships. `target_name` is the prospective aggregate's
    PascalCase class name (e.g. "Facility", "ProcedureTemplate").
    """

    target_name: str


@dataclass(frozen=True, slots=True)
class DeferredVocabulary:
    """The bare string is conceptually a closed enum; vocabulary not yet earned.

    Graduates to a typed enum (e.g. `SupplyKind(StrEnum)`) on the documented
    trigger. `target_name` is the prospective enum's class name;
    `trigger_doc` references the design memo + section that records the
    promotion trigger (e.g. "Supply.kind Watch item 4 trigger per
    project-structural-scope-design").
    """

    target_name: str
    trigger_doc: str


@dataclass(frozen=True, slots=True)
class SubsumedBy:
    """The field looks like it wants an aggregate, BUT the role is already filled.

    PERMANENT marker. Do NOT promote `subsumed_target_name` as an
    independent aggregate; its template / scope role is already covered
    by the aggregates named in `subsuming_aggregate_names`. Reach for
    this marker rather than `DeferredVocabulary` whenever a future
    contributor reading the deferral might reasonably create a duplicate
    template layer.
    """

    subsumed_target_name: str
    subsuming_aggregate_names: tuple[str, ...]


__all__ = ["Annotated", "DeferredVocabulary", "NamedFor", "SubsumedBy"]
