"""Vertical slice for the `ReactivateActor` command.

Module-as-namespace surface:

    from cora.access.features import reactivate_actor

    cmd = reactivate_actor.ReactivateActor(actor_id=...)
    handler = reactivate_actor.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.access.features.reactivate_actor import tool
from cora.access.features.reactivate_actor.command import ReactivateActor
from cora.access.features.reactivate_actor.decider import decide
from cora.access.features.reactivate_actor.handler import Handler, bind
from cora.access.features.reactivate_actor.route import router

__all__ = [
    "Handler",
    "ReactivateActor",
    "bind",
    "decide",
    "router",
    "tool",
]
