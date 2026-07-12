"""Vertical slice for the `DeprecateLanguageModel` command."""

from cora.agent.features.deprecate_language_model import tool
from cora.agent.features.deprecate_language_model.command import DeprecateLanguageModel
from cora.agent.features.deprecate_language_model.decider import decide
from cora.agent.features.deprecate_language_model.handler import Handler, bind
from cora.agent.features.deprecate_language_model.route import router

__all__ = [
    "DeprecateLanguageModel",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
