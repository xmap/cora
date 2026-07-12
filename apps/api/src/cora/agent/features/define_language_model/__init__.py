"""Vertical slice for the `DefineLanguageModel` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.agent.features import define_language_model

    cmd = define_language_model.DefineLanguageModel(
        name="Claude Sonnet 4.6", provider="anthropic",
        model="claude-sonnet-4-6", served_via="Argo",
        cost_basis={"kind": "TokenPricing", ...},
        data_tier="Internal", archivability="Alias",
    )
    handler = define_language_model.bind(deps)
    language_model_id = await handler(
        cmd, principal_id=..., correlation_id=...
    )
"""

from cora.agent.features.define_language_model import tool
from cora.agent.features.define_language_model.command import DefineLanguageModel
from cora.agent.features.define_language_model.decider import decide
from cora.agent.features.define_language_model.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.agent.features.define_language_model.route import router

__all__ = [
    "DefineLanguageModel",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
