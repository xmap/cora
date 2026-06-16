# Modeling

*Event sourcing, value objects, field grouping.*

Events are immutable; everything else evolves. The rules below exist to keep that asymmetry honest: schema evolution that doesn't lie about old events, value objects that re-validate on read, primitives at the wire and VOs at the boundaries.

## Event sourcing

**Routing key: `(stream_type, event_type)`, never `event_type` alone.** `events.event_type` stores the unqualified class name; a cross-BC name collision is plausible.

**Schema evolution: weak schema first; new event type for breaking changes.**

1. **Default**: weak schema, additive only. Add optional fields; evolver supplies a default for old events.
2. **Breaking changes** (rename, type change, semantic change): new event type. Stop emitting the old one; evolver handles both forever. A future `ActorRenamed` is a new event class on the union, not a `name` field on `ActorRegistered`.
3. **Upcasters only when warranted.** Once ≥2 breaking changes hit the same logical event, a `from_stored` dispatch table is fine. The `schema_version` field is the trigger.

Why: events are immutable; VOs evolve. The evolver re-validates payloads on read by reconstructing VOs (`Actor(name=ActorName(event.name))`). New event types are explicit at the union; pyright's exhaustiveness check forces handling.

**`event_id` is the dedup key.** Producers generate one fresh UUIDv7 per event via the IdGenerator port; the events table has UNIQUE on `event_id`. Subscribers dedupe by `event_id` against their checkpoint. Polling by `position` must also handle the bigserial sequence-rollback hazard documented in `cora/infrastructure/ports/event_store.py`.

**Collection fields on event payloads use immutable types**: `tuple[X, ...]` instead of `list[X]`, `frozenset[X]` instead of `set[X]`. The fold step shares the payload's collection reference into the new aggregate state; a mutable collection invites alias bugs where mutating the state silently mutates the (frozen) event dict that built it, or vice-versa. Pinned by `test_event_payload_immutability.py`.

**`from_stored` wraps go through the canonical helper** at `cora.infrastructure.event_payload.deserialize_or_raise(event_type, builder, *, extra=(), message_suffix='')` for event-arm wraps and the sibling `deserialize_vo_or_raise(vo_type, builder, *, extra=(), raise_as=ValueError)` for nested-VO deserializers. Both raise `ValueError("Malformed <type>")` with no payload echo, to avoid leaking PII-vault-correlatable identifiers through exception logs after PII vault shipped 2026-05-23. The `extra` parameter accepts additional exception classes that an inner `Enum(...)` constructor or typed deserializer might raise; `raise_as` (sibling only) preserves typed exception subclasses such as `InvalidCalibrationSourceError`.

**Dict fields on event payloads** are not pinned by the fitness (JSON-schema-shaped payloads are intrinsically freeform). The companion defence is **shallow-copy on fold** at the evolver: `field=dict(payload_field)` (or `dict(payload_field) if payload_field is not None else None` for Optional dicts). Today applied at every site where a dict-typed payload field maps into aggregate state: Asset.settings, Run.effective_parameters and .override_parameters, Decision.decision_inputs, Calibration.operating_point and CalibrationRevision.value, Method.parameters_schema, Capability.parameters_schema, Family.settings_schema, Plan.default_parameters. Extend on each new dict-payload event.

## Value objects

Live at the smallest scope owning the invariants:

| Scope | Home | Example |
| --- | --- | --- |
| One aggregate | `aggregates/<aggregate>/state.py` (split when >~200 lines) | `ActorName` |
| Across aggregates in one BC | `<bc>/value_objects.py` or `<bc>/_shared/` | `ConduitName` |
| Across multiple BCs (pure: zero `cora.*` imports) | `cora/shared/` (e.g. `bounded_text.py`, `identifier.py`) | shared value objects + validation helpers |
| Across multiple BCs (depends on ports / kernel / adapters) | `cora/infrastructure/` (e.g. `event_payload.py`, `update_handler.py`) | composition root + ES machinery |

Promote up only after ≥3 real usages with identical, stable invariants.

**Trimmed-bounded-text VOs share a validation helper, not a base class.** The bounded-text VOs (`ActorName`, `MethodName`, reason fields on Run / Subject / Dataset, choice / context / rule on Decision, ...) call `cora.shared.bounded_text.validate_bounded_text`:

```python
@dataclass(frozen=True)
class ActorName:
    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ACTOR_NAME_MAX_LENGTH,
            error_class=InvalidActorNameError,
        )
        object.__setattr__(self, "value", trimmed)
```

Each VO keeps its own frozen dataclass type, per-aggregate error class, and `MAX_LENGTH`. A shared base class would couple aggregates; a class factory would weaken `isinstance`. A free function avoids both.

**Primitives in events, VOs at state and decider boundaries.** Events carry primitives (str, int, UUID, datetime, dict), never VOs. Decider unwraps: `ActorRegistered(name=actor_name.value)`. Evolver re-validates: `Actor(name=ActorName(event.name))`. The round-trip test at `tests/unit/<bc>/test_evolver.py` verifies this per aggregate.

## Field grouping

Default to **flat fields** until ≥3 members of a group exist. Then hoist into a value-object holder.

```python
# 1 member: flat
@dataclass(frozen=True)
class Method:
    needed_family_ids: frozenset[UUID]

# 2 members: still flat
@dataclass(frozen=True)
class Method:
    needed_family_ids: frozenset[UUID]
    needed_supplies: frozenset[str]

# 3+ members: hoist
@dataclass(frozen=True)
class Needs:
    family_ids: frozenset[UUID]
    supplies: frozenset[str]
    assembly_ids: frozenset[UUID]

@dataclass(frozen=True)
class Method:
    needs: Needs
```

Why flat: Pydantic / MCP schemas read naturally; event payloads are append-only; one-field wrappers are ceremony. Why hoist at 3: the field-list noise crosses the threshold where reading state takes a second pass.

**Migration when hoisting:**

1. Define the holder VO in `aggregates/<aggregate>/state.py`.
2. Add an additive `<group>` field, default-constructed; keep flat fields.
3. Evolver populates both flat and grouped from the same payload.
4. Migrate readers to the grouped form.
5. In a cleanup commit, remove the flat fields.

Event payloads stay flat; the holder is a state-side ergonomic.
