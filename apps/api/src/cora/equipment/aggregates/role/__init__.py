"""Role aggregate: state, errors, events, evolver, read repo, seed registry.

Vertical slices that operate on this aggregate live under
`cora.equipment.features.<verb>_role/` and import from here for state
and event types. The 3A sub-slice ships `define_role` only; future
slices (deferred per [[project-role-aggregate-design]] Q1) add the
update slices when Lock 14 versioning triggers fire.
"""

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.role._role_registry import (
    CONTROLLER,
    DETECTOR,
    POSITIONER,
    REGULATOR,
    SEED_ROLE_CONTROLLER_ID,
    SEED_ROLE_DETECTOR_ID,
    SEED_ROLE_POSITIONER_ID,
    SEED_ROLE_REGULATOR_ID,
    SEED_ROLE_SENSOR_ID,
    SEED_ROLES,
    SENSOR,
    role_stream_id,
)
from cora.equipment.aggregates.role._signal_type import (
    SIGNAL_TYPE_MAX_LENGTH,
    InvalidSignalTypeError,
    SignalType,
    normalize_signal_type,
)
from cora.equipment.aggregates.role.events import (
    RoleDefined,
    RoleEvent,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.role.evolver import evolve, fold
from cora.equipment.aggregates.role.read import load_role
from cora.equipment.aggregates.role.state import (
    ROLE_DOCSTRING_MAX_LENGTH,
    ROLE_NAME_MAX_LENGTH,
    InvalidRoleDocstringError,
    InvalidRoleNameError,
    Role,
    RoleAffordanceOverlapError,
    RoleAlreadyExistsError,
    RoleName,
    RoleNotFoundError,
)

__all__ = [
    "CONTROLLER",
    "DETECTOR",
    "POSITIONER",
    "REGULATOR",
    "ROLE_DOCSTRING_MAX_LENGTH",
    "ROLE_NAME_MAX_LENGTH",
    "SEED_ROLES",
    "SEED_ROLE_CONTROLLER_ID",
    "SEED_ROLE_DETECTOR_ID",
    "SEED_ROLE_POSITIONER_ID",
    "SEED_ROLE_REGULATOR_ID",
    "SEED_ROLE_SENSOR_ID",
    "SENSOR",
    "SIGNAL_TYPE_MAX_LENGTH",
    "InvalidRoleDocstringError",
    "InvalidRoleNameError",
    "InvalidSignalTypeError",
    "Role",
    "RoleAffordanceOverlapError",
    "RoleAlreadyExistsError",
    "RoleDefined",
    "RoleEvent",
    "RoleId",
    "RoleName",
    "RoleNotFoundError",
    "SignalType",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_role",
    "normalize_signal_type",
    "role_stream_id",
    "to_payload",
]
