"""Vertical slice for the `AnnounceLanguageModelRetirement` command."""

from cora.agent.features.announce_language_model_retirement import tool
from cora.agent.features.announce_language_model_retirement.command import (
    AnnounceLanguageModelRetirement,
)
from cora.agent.features.announce_language_model_retirement.decider import decide
from cora.agent.features.announce_language_model_retirement.handler import Handler, bind
from cora.agent.features.announce_language_model_retirement.route import router

__all__ = [
    "AnnounceLanguageModelRetirement",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
