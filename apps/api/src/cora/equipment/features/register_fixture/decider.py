"""Pure decider for the `RegisterFixture` command.

Pure function: given the empty Fixture state (genesis), the loaded
Assembly + Asset context, and the command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

## Invariants

  - State must be None (genesis-only) -> FixtureAlreadyExistsError
    via stream collision (essentially impossible with UUIDv7 ids;
    defensive guard).
  - `context.assembly_state` must not be None
    -> AssemblyNotFoundError carrying the target assembly_id.
  - `context.assembly_state.status` must not be Deprecated
    -> AssemblyCannotInstantiateError carrying the current status.
  - Every referenced asset_id in the bindings must resolve
    -> FixtureAssetNotFoundError carrying the sorted-first missing
    id for deterministic error responses.
  - Every referenced Asset must NOT be Decommissioned
    -> FixtureAssetNotAttachableError carrying the sorted-first
    offending asset_id (mirrors AssetCannotAttachToFixtureError
    at attach-time).
  - Every referenced Asset must currently be installed in some Mount
    (when the handler loaded asset_location info)
    -> FixtureAssetNotInstalledError carrying the sorted-first
    orphan id. A Fixture should materialize only equipment that is
    already on the floor; install_asset is a hard precondition.
  - Each TemplateSlot's cardinality is satisfied by the count of
    bindings carrying its slot_name
    -> FixtureMappingIncompleteError carrying the offending
    slot_name and a human-readable reason.
  - For every binding, the mapped Asset's family_ids intersect the
    referenced slot's required_family_ids
    -> FixtureAssetFamilyMismatchError carrying the slot_name and
    asset_id.
  - `command.parameter_overrides` validates against the Assembly's
    parameter_overrides_schema (STRICT posture: dict against schema
    only, schema=None + non-empty overrides rejects)
    -> FixtureParameterOverridesInvalidError.

The bindings set is also rejected if any binding references a
slot_name NOT declared in `required_slots`; this is folded into the
cardinality check (an unknown slot has zero required cardinality,
so any binding to it triggers FixtureMappingIncompleteError
carrying the unknown slot_name).
"""

from collections import Counter
from datetime import datetime
from typing import assert_never
from uuid import UUID

from cora.equipment.aggregates.assembly import (
    AssemblyCannotInstantiateError,
    AssemblyNotFoundError,
    AssemblyStatus,
    FixtureAssetFamilyMismatchError,
    FixtureAssetNotAttachableError,
    FixtureAssetNotFoundError,
    FixtureAssetNotInstalledError,
    FixtureMappingIncompleteError,
    FixtureParameterOverridesInvalidError,
    SlotCardinality,
    TemplateSlot,
)
from cora.equipment.aggregates.asset import AssetLifecycle
from cora.equipment.aggregates.fixture import (
    Fixture,
    FixtureAlreadyExistsError,
    FixtureRegistered,
)
from cora.equipment.features.register_fixture.command import RegisterFixture
from cora.equipment.features.register_fixture.context import RegisterFixtureContext
from cora.shared.identity import ActorId
from cora.shared.json_schema_validation import validate_values_against_schema

_NO_SCHEMA_REJECTION = (
    "Assembly does not declare a parameter_overrides_schema; cannot accept "
    "parameter_overrides for keys: {keys}"
)


def _check_cardinality(slot: TemplateSlot, count: int) -> None:
    """Reject the binding count for a single slot under its cardinality."""
    cardinality = slot.cardinality
    slot_name = slot.slot_name.value
    match cardinality:
        case SlotCardinality.EXACTLY_1:
            if count != 1:
                raise FixtureMappingIncompleteError(
                    slot_name,
                    f"cardinality Exactly1 requires exactly 1 binding (got {count})",
                )
        case SlotCardinality.ZERO_OR_ONE:
            if count > 1:
                raise FixtureMappingIncompleteError(
                    slot_name,
                    f"cardinality ZeroOrOne allows at most 1 binding (got {count})",
                )
        case SlotCardinality.ONE_OR_MORE:
            if count < 1:
                raise FixtureMappingIncompleteError(
                    slot_name,
                    f"cardinality OneOrMore requires at least 1 binding (got {count})",
                )
        case SlotCardinality.ZERO_OR_MORE:
            pass
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(cardinality)


def decide(
    state: Fixture | None,
    command: RegisterFixture,
    *,
    context: RegisterFixtureContext,
    now: datetime,
    new_id: UUID,
    registered_by: ActorId,
) -> list[FixtureRegistered]:
    """Decide the events produced by registering a Fixture against an Assembly.

    Invariants:
      - State must be None (genesis-only) -> FixtureAlreadyExistsError
        carrying the pre-existing fixture_id (essentially impossible
        with UUIDv7 ids; defensive guard above expected_version=0).
      - context.assembly_state must not be None -> AssemblyNotFoundError
        carrying the target assembly_id.
      - context.assembly_state.status must not be Deprecated
        -> AssemblyCannotInstantiateError carrying the current status.
      - Every referenced asset_id must resolve to a registered Asset
        -> FixtureAssetNotFoundError carrying the sorted-first missing
        id for deterministic error responses.
      - Every referenced Asset must NOT be Decommissioned
        -> FixtureAssetNotAttachableError carrying the sorted-first
        offending asset_id (mirrors AssetCannotAttachToFixtureError
        at attach-time).
      - Every referenced Asset must currently be installed in some Mount
        (when the handler loaded asset_location info)
        -> FixtureAssetNotInstalledError carrying the sorted-first
        orphan id. A Fixture should materialize only equipment that is
        already on the floor; install_asset is a hard precondition.
      - Each TemplateSlot's cardinality must be satisfied by the count
        of bindings carrying its slot_name
        -> FixtureMappingIncompleteError carrying the offending
        slot_name. Also fires when a binding references a slot_name not
        declared in the Assembly's required_slots.
      - For every binding, the mapped Asset's family_ids must intersect
        the referenced slot's required_family_ids
        -> FixtureAssetFamilyMismatchError carrying the slot_name and
        asset_id.
      - command.parameter_overrides must validate against the Assembly's
        parameter_overrides_schema (STRICT posture: non-empty overrides
        on a schema-less Assembly rejects)
        -> FixtureParameterOverridesInvalidError.
    """
    if state is not None:
        raise FixtureAlreadyExistsError(state.id)

    assembly = context.assembly_state
    if assembly is None:
        raise AssemblyNotFoundError(command.assembly_id)

    if assembly.status is AssemblyStatus.DEPRECATED:
        raise AssemblyCannotInstantiateError(
            assembly.id,
            f"current status is {assembly.status.value}; expected one of "
            f"{AssemblyStatus.DEFINED.value}, {AssemblyStatus.VERSIONED.value}",
        )

    missing_asset_ids = sorted(
        (
            asset_id
            for asset_id, family_ids in context.family_ids_by_asset_id.items()
            if family_ids is None
        ),
        key=str,
    )
    if missing_asset_ids:
        raise FixtureAssetNotFoundError(missing_asset_ids[0])

    # Cross-aggregate guard: every referenced Asset must NOT be
    # Decommissioned (mirrors AssetCannotAttachToFixtureError at
    # attach-time; rejecting here prevents registering a Fixture that
    # would inevitably fail at the per-Asset attach step since the
    # Fixture is single-event-genesis and cannot be amended).
    # Empty dict means no lifecycle info loaded -> guard skipped.
    decommissioned_asset_ids = sorted(
        (
            asset_id
            for asset_id, lifecycle in context.lifecycle_by_asset_id.items()
            if lifecycle is AssetLifecycle.DECOMMISSIONED
        ),
        key=str,
    )
    if decommissioned_asset_ids:
        raise FixtureAssetNotAttachableError(
            decommissioned_asset_ids[0],
            AssetLifecycle.DECOMMISSIONED.value,
        )

    # Cross-aggregate guard: every referenced Asset must currently be
    # installed in some Mount. A Fixture should snapshot only equipment
    # already racked on the floor, so the install-then-register-fixture
    # choreography is the contract.
    # `mount_id_by_asset_id is None` means the handler ran without a
    # pool (test path) and the guard is disabled entirely.
    if context.mount_id_by_asset_id is not None:
        orphan_asset_ids = sorted(
            (
                asset_id
                for asset_id, mount_id in context.mount_id_by_asset_id.items()
                if mount_id is None
            ),
            key=str,
        )
        if orphan_asset_ids:
            raise FixtureAssetNotInstalledError(orphan_asset_ids[0])

    slots_by_name = {slot.slot_name.value: slot for slot in assembly.required_slots}
    binding_counts: Counter[str] = Counter(
        binding.slot_name for binding in command.slot_asset_bindings
    )

    unknown_slot_names = sorted(set(binding_counts) - set(slots_by_name))
    if unknown_slot_names:
        first = unknown_slot_names[0]
        raise FixtureMappingIncompleteError(
            first,
            f"slot {first!r} is not declared on the Assembly",
        )

    for slot_name in sorted(slots_by_name):
        slot = slots_by_name[slot_name]
        _check_cardinality(slot, binding_counts.get(slot_name, 0))

    for binding in sorted(
        command.slot_asset_bindings, key=lambda b: (b.slot_name, str(b.asset_id))
    ):
        slot = slots_by_name[binding.slot_name]
        asset_family_ids = context.family_ids_by_asset_id.get(binding.asset_id)
        if asset_family_ids is None or not (asset_family_ids & slot.required_family_ids):
            raise FixtureAssetFamilyMismatchError(binding.slot_name, binding.asset_id)

    validate_values_against_schema(
        command.parameter_overrides,
        assembly.parameter_overrides_schema,
        error_class=FixtureParameterOverridesInvalidError,
        no_schema_message=_NO_SCHEMA_REJECTION,
    )

    surface_id = command.surface_id if command.surface_id is not None else assembly.id
    content_hash = assembly.content_hash or ""

    return [
        FixtureRegistered(
            fixture_id=new_id,
            assembly_id=assembly.id,
            assembly_content_hash=content_hash,
            surface_id=surface_id,
            slot_asset_bindings=command.slot_asset_bindings,
            parameter_overrides=command.parameter_overrides,
            occurred_at=now,
            registered_by=registered_by,
        )
    ]
