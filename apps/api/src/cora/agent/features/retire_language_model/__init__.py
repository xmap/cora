"""Vertical slice for the `RetireLanguageModel` command."""

from cora.agent.features.retire_language_model import tool
from cora.agent.features.retire_language_model.command import RetireLanguageModel
from cora.agent.features.retire_language_model.decider import decide
from cora.agent.features.retire_language_model.handler import Handler, bind
from cora.agent.features.retire_language_model.route import router

__all__ = [
    "Handler",
    "RetireLanguageModel",
    "bind",
    "decide",
    "router",
    "tool",
]
