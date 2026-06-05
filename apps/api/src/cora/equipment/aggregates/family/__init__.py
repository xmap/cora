"""Family aggregate: state, status enum, affordance enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.equipment.features.<verb>_family/` and import from here for
state and event types.
"""

from cora.equipment.aggregates.family.affordance import (
    Affordance,
    InvalidAffordanceError,
)
from cora.equipment.aggregates.family.events import (
    FamilyDefined,
    FamilyDeprecated,
    FamilyEvent,
    FamilySettingsSchemaUpdated,
    FamilyVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.family.evolver import evolve, fold
from cora.equipment.aggregates.family.read import (
    FamilyLifecycleTimestamps,
    find_missing_families_per_id,
    list_all_family_ids,
    list_asset_ids_in_families,
    list_family_ids,
    load_family,
    load_family_timestamps,
)
from cora.equipment.aggregates.family.settings_validation import (
    InvalidFamilySettingsSchemaError,
    validate_settings_schema,
)
from cora.equipment.aggregates.family.state import (
    FAMILY_NAME_MAX_LENGTH,
    FAMILY_VERSION_TAG_MAX_LENGTH,
    Family,
    FamilyAlreadyExistsError,
    FamilyCannotDeprecateError,
    FamilyCannotVersionError,
    FamilyName,
    FamilyNotFoundError,
    FamilyStatus,
    InvalidFamilyNameError,
    InvalidFamilyVersionTagError,
)

__all__ = [
    "FAMILY_NAME_MAX_LENGTH",
    "FAMILY_VERSION_TAG_MAX_LENGTH",
    "Affordance",
    "Family",
    "FamilyAlreadyExistsError",
    "FamilyCannotDeprecateError",
    "FamilyCannotVersionError",
    "FamilyDefined",
    "FamilyDeprecated",
    "FamilyEvent",
    "FamilyLifecycleTimestamps",
    "FamilyName",
    "FamilyNotFoundError",
    "FamilySettingsSchemaUpdated",
    "FamilyStatus",
    "FamilyVersioned",
    "InvalidAffordanceError",
    "InvalidFamilyNameError",
    "InvalidFamilySettingsSchemaError",
    "InvalidFamilyVersionTagError",
    "event_type_name",
    "evolve",
    "find_missing_families_per_id",
    "fold",
    "from_stored",
    "list_all_family_ids",
    "list_asset_ids_in_families",
    "list_family_ids",
    "load_family",
    "load_family_timestamps",
    "to_payload",
    "validate_settings_schema",
]
