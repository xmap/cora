"""Content-hash helper for the Assembly aggregate.

Wraps the shared `cora.infrastructure.content_hash.compute_content_hash`
pipeline with the Assembly-specific payload_type and the canonical
subset materialized by `canonical_assembly_subset`.

Used at two sites: `define_assembly` and `version_assembly`. Both
fire the same hash for the same structural content; the
payload_type is aggregate-level
(`application/vnd.cora.assembly+json`), NOT event-level, so the
hash is stable across "define" and "version" snapshots of the same
canonical subset.

Per `project_content_addressed_identity_design`: SHA-256 hex of
DSSE PAE-wrapped canonical JSON. Per
`project_canonicalization_research`: stdlib json sort-keys + NFC +
set-to-sorted-list, all delegated to the shared
`canonical_body_bytes`.

Lives at BC root (`equipment/aggregates/_assembly_content_hash.py`)
alongside `_drawing.py` and `_placement.py`, following the
shared-helper convention.
"""

from uuid import UUID

from cora.equipment.aggregates.assembly.state import (
    Assembly,
    AssemblyName,
    TemplateSlot,
    TemplateWire,
    canonical_assembly_subset,
)
from cora.infrastructure.content_hash import compute_content_hash
from cora.infrastructure.signing import event_type_to_payload_type

# Aggregate-level payload_type: stable across define / version events
# so two snapshots of the same canonical subset produce the same hash.
ASSEMBLY_PAYLOAD_TYPE = "application/vnd.cora.assembly+json"

# Per-event payload_types for signing the events themselves (not the
# canonical-subset hash). Kept here to avoid scattering the strings
# across slice deciders that emit these events.
ASSEMBLY_DEFINED_PAYLOAD_TYPE = event_type_to_payload_type("AssemblyDefined")
ASSEMBLY_VERSIONED_PAYLOAD_TYPE = event_type_to_payload_type("AssemblyVersioned")
ASSEMBLY_DEPRECATED_PAYLOAD_TYPE = event_type_to_payload_type("AssemblyDeprecated")


def compute_assembly_content_hash(
    name: AssemblyName | str,
    presents_as_family_id: UUID,
    required_slots: frozenset[TemplateSlot],
    required_wires: frozenset[TemplateWire],
    parameter_overrides_schema: dict[str, object] | None,
) -> str:
    """Compute SHA-256 hex over an Assembly's canonical content subset.

    Accepts either an AssemblyName VO or a raw string for `name` so
    callers building from operator-supplied input do not need to
    construct the VO twice (the AssemblyDefined decider validates
    once via the VO, then passes the VO here for hashing).

    Round-trip equivalence with
    `compute_assembly_content_hash_from_state(Assembly(...))` is
    pinned in tests; both paths funnel through
    `canonical_assembly_subset` so structural drift between them is
    impossible.
    """
    body = canonical_assembly_subset(
        name=name,
        presents_as_family_id=presents_as_family_id,
        required_slots=required_slots,
        required_wires=required_wires,
        parameter_overrides_schema=parameter_overrides_schema,
    )
    return compute_content_hash(ASSEMBLY_PAYLOAD_TYPE, body)


def compute_assembly_content_hash_from_state(state: Assembly) -> str:
    """Compute the content_hash for a fully-constructed Assembly state.

    Convenience wrapper: extracts the canonical subset via
    `state.content_subset()` (which itself delegates to
    `canonical_assembly_subset`) and feeds it to the shared
    `compute_content_hash` pipeline under `ASSEMBLY_PAYLOAD_TYPE`.

    Used in tests to verify that the state-method path and the
    explicit-args path produce identical hashes, and may be useful
    in future re-hash flows (e.g., a one-shot fitness that recomputes
    all live Assembly hashes and asserts they match the stored
    content_hash).
    """
    return compute_content_hash(ASSEMBLY_PAYLOAD_TYPE, state.content_subset())


__all__ = [
    "ASSEMBLY_DEFINED_PAYLOAD_TYPE",
    "ASSEMBLY_DEPRECATED_PAYLOAD_TYPE",
    "ASSEMBLY_PAYLOAD_TYPE",
    "ASSEMBLY_VERSIONED_PAYLOAD_TYPE",
    "compute_assembly_content_hash",
    "compute_assembly_content_hash_from_state",
]
