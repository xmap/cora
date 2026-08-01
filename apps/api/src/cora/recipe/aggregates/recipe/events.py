"""Domain events emitted by the Recipe aggregate, plus the discriminated union.

New aggregate (no rename history -> no dual-match arms). Events:

  - RecipeDefined (genesis; carries name + capability_id + steps)
  - RecipeVersioned (declarative replacement: new version_tag + new
                     steps; name and capability_id PRESERVED across
                     versions per the immutable-capability_id lock)
  - RecipeDeprecated (terminal state; carries optional replaced_by
                      pointer per LOINC `MAP_TO`)

Status is NOT carried in event payloads; the event type itself
encodes the state change. Same precedent as `CapabilityStatus` /
`FamilyStatus`.

## Replacement semantics

A new version IS a new declaration: `RecipeVersioned` carries the
FULL replacement step sequence. No diff/merge semantics. Matches the
replace-on-version precedent across the Family/Method/Plan/Practice/
Capability family.

## Re-attestation emits

Re-versioning with identical `(version_tag, steps)` SUCCEEDS and emits
the event. The duplicate is the audit signal, not a bug. Mirrors
`version_capability` / `version_method` deciders which both emit on
byte-equal re-call.

## Payload field ordering

Steps serialize via `body.to_dict` (canonical wire format with
`__binding__` sentinel for BindingRef). `replaced_by_recipe_id`
serializes as string-or-None.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.recipe.body import InvalidRecipeStepShapeError, RecipeStep
from cora.recipe.aggregates.recipe.body import from_dict as steps_from_dict
from cora.recipe.aggregates.recipe.body import to_dict as steps_to_dict

# ValueError covers UUID() / datetime.fromisoformat() parse failures;
# InvalidRecipeStepShapeError covers steps_from_dict unknown-kind / missing-key
# paths. Both must wrap into the canonical Malformed <event_type> payload
# envelope per [[project-from-stored-wrap-convention]] so audit dispatch
# groups them uniformly with the default KeyError / TypeError / AttributeError
# cases that deserialize_or_raise already catches.
_PAYLOAD_PARSE_EXTRA: tuple[type[BaseException], ...] = (
    ValueError,
    InvalidRecipeStepShapeError,
)


@dataclass(frozen=True)
class RecipeDefined:
    """A new Recipe was defined against a Capability.

    Status is implicit (`Defined`); the evolver sets it. All
    declarative fields are present in the genesis payload.
    """

    recipe_id: UUID
    name: str
    capability_id: UUID
    steps: tuple[RecipeStep, ...]
    occurred_at: datetime


@dataclass(frozen=True)
class RecipeVersioned:
    """A Recipe's step sequence was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    full step sequence REPLACES wholesale (a new version IS a new
    declaration). `name` and `capability_id` are PRESERVED across
    versions; re-binding to a different Capability requires a new
    Recipe.
    """

    recipe_id: UUID
    version_tag: str
    steps: tuple[RecipeStep, ...]
    occurred_at: datetime


@dataclass(frozen=True)
class RecipeDeprecated:
    """A Recipe was marked as no longer recommended for new bindings.

    Multi-source transition: `Defined | Versioned -> Deprecated`.
    `replaced_by_recipe_id` is an optional pointer to a successor
    Recipe (LOINC `MAP_TO` precedent); None means deprecated-
    without-replacement. Existing Procedures already expanded from
    this Recipe are NOT automatically invalidated (advisory at BC
    layer).
    """

    recipe_id: UUID
    reason: str
    occurred_at: datetime
    replaced_by_recipe_id: UUID | None = None


RecipeEvent = RecipeDefined | RecipeVersioned | RecipeDeprecated


def event_type_name(event: RecipeEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: RecipeEvent) -> dict[str, Any]:
    """Serialize a Recipe event to a JSON-friendly dict for jsonb storage.

    UUIDs become strings; datetimes ISO-8601; step sequences serialize
    via `body.to_dict` so the wire-format `__binding__` sentinel
    survives the round-trip.
    """
    match event:
        case RecipeDefined(
            recipe_id=recipe_id,
            name=name,
            capability_id=capability_id,
            steps=steps,
            occurred_at=occurred_at,
        ):
            return {
                "recipe_id": str(recipe_id),
                "name": name,
                "capability_id": str(capability_id),
                "steps": steps_to_dict(steps),
                "occurred_at": occurred_at.isoformat(),
            }
        case RecipeVersioned(
            recipe_id=recipe_id,
            version_tag=version_tag,
            steps=steps,
            occurred_at=occurred_at,
        ):
            return {
                "recipe_id": str(recipe_id),
                "version_tag": version_tag,
                "steps": steps_to_dict(steps),
                "occurred_at": occurred_at.isoformat(),
            }
        case RecipeDeprecated(
            recipe_id=recipe_id,
            reason=reason,
            replaced_by_recipe_id=replaced_by_recipe_id,
            occurred_at=occurred_at,
        ):
            return {
                "recipe_id": str(recipe_id),
                "reason": reason,
                "replaced_by_recipe_id": (
                    str(replaced_by_recipe_id) if replaced_by_recipe_id is not None else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> RecipeEvent:
    """Rebuild a Recipe event from a StoredEvent loaded from the event store.

    Single-match arms; no legacy / dual-match (this aggregate is new,
    not a rename of a prior aggregate). Step-sequence payloads round-
    trip through `body.from_dict`, which raises
    `InvalidRecipeStepShapeError` on malformed shapes; the
    `deserialize_or_raise` wrapper translates any exception during
    rebuild into a `Malformed Recipe<X>` error per the
    `from_stored` wrap convention.
    """
    payload = stored.payload
    match stored.event_type:
        case "RecipeDefined":
            return deserialize_or_raise(
                "RecipeDefined",
                lambda: RecipeDefined(
                    recipe_id=UUID(payload["recipe_id"]),
                    name=payload["name"],
                    capability_id=UUID(payload["capability_id"]),
                    steps=steps_from_dict(payload["steps"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=_PAYLOAD_PARSE_EXTRA,
            )
        case "RecipeVersioned":
            return deserialize_or_raise(
                "RecipeVersioned",
                lambda: RecipeVersioned(
                    recipe_id=UUID(payload["recipe_id"]),
                    version_tag=payload["version_tag"],
                    steps=steps_from_dict(payload["steps"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=_PAYLOAD_PARSE_EXTRA,
            )
        case "RecipeDeprecated":

            def _build_recipe_deprecated() -> RecipeDeprecated:
                replaced_raw = payload.get("replaced_by_recipe_id")
                return RecipeDeprecated(
                    recipe_id=UUID(payload["recipe_id"]),
                    reason=payload["reason"],
                    replaced_by_recipe_id=(
                        UUID(replaced_raw) if replaced_raw is not None else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise(
                "RecipeDeprecated",
                _build_recipe_deprecated,
                extra=_PAYLOAD_PARSE_EXTRA,
            )
        case _:
            msg = f"Unknown RecipeEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "RecipeDefined",
    "RecipeDeprecated",
    "RecipeEvent",
    "RecipeVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
