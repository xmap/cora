"""Default `RecipeExpander` adapter: pure delegation to `expand`.

Wraps the module-level `cora.operation._recipe_expansion.expand` function
in a Protocol-conforming object and pins a stable `version` string. The
version is recorded in `RecipeExpansionRecorded` provenance events so
replay can verify which expander produced a given step sequence.

A new expander version is a code change here: bump `version` to the
next stable tag when expansion semantics change in a way that affects
already-recorded provenance events.

## v2-pseudoaxis-aware

`version` bumped from `"v1"` to `"v2-pseudoaxis-aware"` when the
pre-Conductor PseudoAxis expansion shipped: the deterministic
`expand` kernel is unchanged, but the port now carries a second
method `expand_pseudoaxis` that the conduct_procedure handler invokes
after recipe expansion and before the Conductor walks the resulting
steps. The version bump invalidates any cached expansions whose
provenance events pinned `"v1"`, even though the recipe-substitution
semantics are unchanged: future PseudoAxis-path semantic changes will
share the same `version` knob.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cora.operation._pseudoaxis_expander import (
    ConstituentResolver,
    expand_pseudoaxis_steps,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from uuid import UUID

    from cora.infrastructure.ports import EventStore
    from cora.operation.conductor import Step
    from cora.recipe.aggregates.recipe import RecipeStep

_DEFAULT_VERSION = "v2-pseudoaxis-aware"


@dataclass(frozen=True)
class InMemoryRecipeExpander:
    """Pure-function `RecipeExpander` backed by the default `expand`.

    `version` defaults to `"v2-pseudoaxis-aware"` and is rarely
    overridden in production; tests pass a different version when they
    need to assert provenance carries the expander identity.

    `constituent_resolver` defaults to the wiring-deferred resolver in
    `_pseudoaxis_expander`; the Plan.wiring-backed resolver lands in a
    follow-up slice. The runtime evaluator self-gates on
    `Asset.partition_rule is not None`, so no Family-id wiring is
    required on this adapter.
    """

    version: str = _DEFAULT_VERSION
    constituent_resolver: ConstituentResolver | None = None

    def expand(
        self, steps: tuple[RecipeStep, ...], bindings: Mapping[str, Any]
    ) -> tuple[Step, ...]:
        from cora.operation._recipe_expansion import expand as _expand

        return _expand(steps, bindings)

    async def expand_pseudoaxis(
        self,
        steps: tuple[Step, ...],
        *,
        event_store: EventStore,
        correlation_id: UUID,
    ) -> tuple[Step, ...]:
        """Delegate to `expand_pseudoaxis_steps` with the configured resolver.

        When no resolver is configured the expander's wiring-deferred
        default is used, which raises `PartitionRuleNotFoundError` so
        every PseudoAxis SetpointStep encountered is rejected with the
        right typed error until the Plan.wiring-backed resolver lands.
        """
        if self.constituent_resolver is None:
            return await expand_pseudoaxis_steps(
                steps,
                event_store=event_store,
                correlation_id=correlation_id,
            )
        resolver: Callable[[UUID], tuple[UUID, ...]] = self.constituent_resolver
        return await expand_pseudoaxis_steps(
            steps,
            event_store=event_store,
            correlation_id=correlation_id,
            constituent_resolver=resolver,
        )


__all__ = ["InMemoryRecipeExpander"]
