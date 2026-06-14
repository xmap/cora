"""The `DefinePolicy` command — intent dataclass for this slice.

Carries what the caller controls: the policy's display name, the
governed conduit's id, and the two permission sets.

`permitted_principal_ids` and `permitted_commands` are `frozenset` so
the command is hashable + deduplicated by construction. The route
layer accepts JSON arrays and converts before constructing this
command. Empty sets are allowed (deny-all policies); see the
Policy aggregate's `state.py` docstring for the rationale.

`conduit_id` is stored as a bare UUID without verifying the
referenced Conduit exists, same eventual-consistency stance as
`Conduit.source_zone_id` / `target_zone_id`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DefinePolicy:
    """Define a new authorization Policy for a Conduit + Surface pair.

    `surface_id` is required: every new Policy must bind a concrete
    arrival Surface (the route resolves it from the request via
    `get_surface_id`). The decider rejects the nil sentinel
    (`InvalidPolicySurfaceError`); the sentinel survives only on the
    retired V1 bootstrap seed stream.
    """

    name: str
    conduit_id: UUID
    permitted_principal_ids: frozenset[UUID]
    permitted_commands: frozenset[str]
    surface_id: UUID
