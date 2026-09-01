"""The `DefinePolicy` command — intent dataclass for this slice.

Carries what the caller controls: the policy's display name, the
governed conduit's id, the bound surface, and the grants.

`grants` is a `frozenset` of `(principal_id, command_name)` pairs, so
the command is hashable + deduplicated by construction. The route layer
accepts either JSON shape and converts before constructing this command.
An empty set is allowed (deny-all policy); see the Policy aggregate's
`state.py` docstring for the rationale.

## Why pairs, and why `from_cross_product` is a separate constructor

A policy used to hold two independent lists that `evaluate` multiplied,
which granted every listed principal every listed command. Pairs make
the grant exact. Some callers genuinely do want the cross-product (two
operator seats who really do share one command list), so
`from_cross_product` builds it — but it has to be named at the call
site. A caller granting everyone everything now says so out loud
instead of getting it as the silent default.

`conduit_id` is stored as a bare UUID without verifying the
referenced Conduit exists, same eventual-consistency stance as
`Conduit.source_zone_id` / `target_zone_id`.
"""

from collections.abc import Iterable
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
    grants: frozenset[tuple[UUID, str]]
    surface_id: UUID

    @classmethod
    def from_cross_product(
        cls,
        *,
        name: str,
        conduit_id: UUID,
        permitted_principal_ids: Iterable[UUID],
        permitted_commands: Iterable[str],
        surface_id: UUID,
    ) -> "DefinePolicy":
        """Grant every listed principal every listed command.

        The honest name for what the two-list shape always meant. Use it
        when the principals really do share one command list; reach for
        the `grants` field directly when they do not.
        """
        principal_ids = tuple(permitted_principal_ids)
        command_names = tuple(permitted_commands)
        return cls(
            name=name,
            conduit_id=conduit_id,
            grants=frozenset(
                (principal_id, command_name)
                for principal_id in principal_ids
                for command_name in command_names
            ),
            surface_id=surface_id,
        )
