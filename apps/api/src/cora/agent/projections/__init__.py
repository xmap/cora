"""Agent BC's projection modules.

Agent BC ships its projections per the Path C lock: state stays
decider-minimal; lifecycle timestamps live on the projection.
Mirrors the per-BC convention where each
`cora.<bc>.projections.<aggregate>` module owns a single
`*SummaryProjection` class registered via `cora.<bc>._projections`.
"""

from cora.agent.projections.agent import AgentSummaryProjection
from cora.agent.projections.language_model import LanguageModelSummaryProjection

__all__ = ["AgentSummaryProjection", "LanguageModelSummaryProjection"]
