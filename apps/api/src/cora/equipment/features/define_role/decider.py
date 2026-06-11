"""Pure decider for the `DefineRole` command.

Pure function: given the current Role state (None for a fresh stream)
and a `DefineRole` command, returns the events to append. No I/O, no
awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.role import (
    ROLE_DOCSTRING_MAX_LENGTH,
    InvalidRoleDocstringError,
    Role,
    RoleAffordanceOverlapError,
    RoleAlreadyExistsError,
    RoleDefined,
    RoleName,
    SignalType,
    normalize_signal_type,
)
from cora.equipment.features.define_role.command import DefineRole


def decide(
    state: Role | None,
    command: DefineRole,
    *,
    now: datetime,
    new_id: UUID,
) -> list[RoleDefined]:
    """Decide the events produced by defining a new Role.

    Invariants:
      - State must be None (genesis-only) -> RoleAlreadyExistsError
      - Name must be valid (non-empty, 1-200 chars after trim) ->
        InvalidRoleNameError (via RoleName VO)
      - Docstring must be non-empty + 1-2000 chars after trim ->
        InvalidRoleDocstringError
      - `required_affordances` and `optional_affordances` must be
        disjoint -> RoleAffordanceOverlapError
      - Every SignalType in `produces` / `consumes` must trim to
        1-50 chars -> InvalidSignalTypeError (via
        normalize_signal_type)
    """
    if state is not None:
        raise RoleAlreadyExistsError(state.id)
    name = RoleName(command.name)  # validates + trims; raises InvalidRoleNameError

    trimmed_doc = command.docstring.strip()
    if not trimmed_doc or len(trimmed_doc) > ROLE_DOCSTRING_MAX_LENGTH:
        raise InvalidRoleDocstringError(command.docstring)

    overlap = command.required_affordances & command.optional_affordances
    if overlap:
        raise RoleAffordanceOverlapError(role_id=new_id, overlap=overlap)

    produces: frozenset[SignalType] = frozenset(normalize_signal_type(s) for s in command.produces)
    consumes: frozenset[SignalType] = frozenset(normalize_signal_type(s) for s in command.consumes)

    return [
        RoleDefined(
            role_id=new_id,
            name=name.value,
            docstring=trimmed_doc,
            occurred_at=now,
            required_affordances=command.required_affordances,
            optional_affordances=command.optional_affordances,
            produces=produces,
            consumes=consumes,
        )
    ]
