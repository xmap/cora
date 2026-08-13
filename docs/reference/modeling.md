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

**Primitives in events, VOs at state and decider boundaries, EXCEPT a closed vocabulary.** Events carry primitives (str, int, UUID, datetime, dict), never VOs. Decider unwraps: `ActorRegistered(name=actor_name.value)`. Evolver re-validates: `Actor(name=ActorName(event.name))`. The round-trip test at `tests/unit/<bc>/test_evolver.py` verifies this per aggregate.

The carve-out: a field whose VALUE SET is closed, a `StrEnum`, or a frozen VO every one of whose fields is closed by construction (a fixed charset and length, a closed literal set), may be declared on the event as that type directly, unwrapped-and-rewrapped ceremony skipped. Two independent forces created this exception and both must hold before using it:

1. `tools/gen_record_dispositions.py`, the record exporter's redaction-profile generator, resolves a field's publishability from its DECLARED TYPE. A field wrapped down to bare `str` on the event is unpublishable by construction even when its own constructor already closes its range: this is why `DatasetRegistered.checksum: DatasetChecksum` (not `checksum_algorithm: str` + `checksum_value: str`) and `.intent: Intent` (not `str`) are declared as their real types. A hex digest and a closed trust-level tag disclose nothing a redaction reviewer needs to withhold, and wrapping them to `str` first only cost the record its own checksum for a release cycle (see `project_2bm_first_scan_record.md` F6, the published record of the first real 2-BM scan).
2. The type must be reachable from wherever the event class lives. `cora.data.aggregates` may depend on `cora.infrastructure` and `cora.shared` only (`tach.toml`), narrower than the feature layer above it (`cora.data`) that a decider runs in. `DatasetRegistered.producing_run_end_state` stays a bare `str`, deliberately, because the Run BC's `RunStatus` enum is reachable from `cora.data`'s deciders but not from `cora.data.aggregates`'s events, and a Data-BC-local mirror enum would raise at the decider on any future `RunStatus` member the mirror has not caught up to. A closed type that is not SAFELY reachable stays a primitive; that is the ordinary rule, not an exception to it.

A frozen VO that opts into this carve-out for the record exporter's benefit marks itself with `cora.shared.closed_value.ClosedValueObject`, so the generator can ask a type object "does this VO close its own range?" without a hand-maintained list of class names. See that module's docstring for the exact criterion (every field closed, none free text) before subclassing it.

A second, narrower reason to declare a VO directly on an event even when it is NOT closed: a `dict`/`Mapping`-typed field always resolves to `drop:opaque` whole, so a structured carrier with a MIX of closed and open leaves loses the closed ones too unless the generator can see the mix. `AcquisitionRecorded.evidence: AcquisitionEvidence` is this case: `reader_kind` and `checksum_computer_kind` are open-vocabulary strings that correctly recurse to `drop:text`, but `projection_count`, the angle range, and (via the `StrEnum` carve-out above) `captured_at_source` would otherwise be dropped along with them by the same all-or-nothing rule that made `evidence: dict[str, Any]` unpublishable by construction. `DatasetRegistered.encoding: DatasetEncoding` predates this reasoning and was justified ad hoc as "shape symmetry" with the closed `checksum` field on the same event; treat that docstring and this one as the same pattern, not two.

When a genesis command carries TWO sibling freeform carrier dicts and only one gets this treatment (`AcquisitionRecorded.settings` stayed `dict[str, Any]` / `drop:opaque` while `evidence` was typed), the dividing line is real writer content, not a coin flip: type the one a production writer actually populates with a stable shape today; leave the other opaque until one does, rather than inventing a shape ahead of demand. This is a narrower, cheaper bar than a full `Capability.settings_schema` (`project_capability_settings_schema.md`'s per-Family JSON Schema mechanism, which several aggregates' `settings` fields are already deferred to): it only asks "does anything real write more than `{}` into this field," not "is there an operator-declared schema for it." A carrier that clears the Capability-schema bar (e.g. `Asset.settings`, populated in production and validated against a per-Family schema union) is a STRONGER candidate for this same treatment than `AcquisitionRecorded.settings` ever was; that gap is a known, unscoped follow-up, not evidence the rule is wrong.

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

## Run vs Procedure boundary

Two spine aggregates record planned work, and the same act must have exactly one home. Select on the act's **output of record**, not on whether CORA drives it.

**An act is a `Run` iff its reason-for-existing is to leave a finite, identity-bearing primary `Dataset`** (a measurement or a computed / reconstructed lot). **Otherwise it is a `Procedure`**: it changes or verifies equipment state, and its output of record, if any, is a `Calibration` revision or an incidental diagnostic, never a Dataset-of-record.

The one-question test: *does the act leave a Dataset of record?* Yes (acquired or computed) -> Run. No (a calibration value, or only a state change) -> Procedure. `subject_id` is plain optional metadata on a Run (`UUID | None`); it never enters the selection.

Two structural facts already enforce most of this, so it is mostly derivation, not decree:

- A **measured `Calibration` can only be sourced from a Procedure.** `CalibrationSource = MeasuredSource(procedure_id) | ComputedSource(dataset_id) | AssertedSource(asserted_by)` has no `run_id` arm. Any act whose output of record is a measured calibration (alignment, characterization) is a Procedure by construction.
- A `Run` requires a `plan_id` and is the batch producer with AsShot calibration pinning; a `Procedure` carries `target_asset_ids` plus a Setpoint / Action / Check step log.

**Data that merely transits an act is not a Dataset of record.** An alignment rotates and reads frames to compute a centroid, but it registers the `rotation_center` value, not the frames (the fit lives at the edge). A Procedure that does retain frames registers them on the secondary `Dataset.producing_procedure_id` arm as a diagnostic; its output of record stays the Calibration.

Orthogonal axes, do not conflate with selection:

- **Conducted vs recorded** (who drives the act): CORA's conducting engine drives either spine aggregate across the relevant port (control over `ControlPort`, compute over `ComputePort`, transfer over `TransferPort`); an externally-driven act (a scan loop a facility tool runs) is recorded. Both Runs and Procedures span both modes.
- **Compute** homes by the same test: a reconstruction leaves a Dataset, so it is a Run (conducted over `ComputePort`); its provenance is the Dataset's `derived_from` plus `used_calibration_ids`.
- **Transfer** moves bytes onto a `Distribution` and leaves no new Dataset of record, so it is an edge job, not a spine aggregate, until a publish / custody invariant earns it one.

The one genuinely undecidable shape is an act whose registered Dataset and Calibration are co-equal deliverables. No shipped act crosses that seam today; resolve it then by a declared primary output, not now.

A dark- or flat-field capture leaves a baseline Dataset, so it is a Run by the same test, with any conducting Procedure carried as a phase via `parent_run_id` and the Dataset attributed to the Run. The 2-BM scenarios model them this way; the absence of a `subject_id` changes nothing.

Why: selecting on a single observable fact (the produced Dataset of record) keeps five-year ledger queries unique. Reproduce-this-result walks the Run plus Dataset lineage; how-did-the-instrument-behave walks the Procedure plus Calibration history; and the same act never lands in two places. Corpus precedent (ISA-88 finite-lot, Bluesky `open_run` bracket, PROV / schema.org generated-entity, SciCat raw / derived) converges on the produced-data-lot as the axis and rejects Subject as the axis.
