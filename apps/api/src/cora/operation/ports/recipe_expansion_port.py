"""RecipeExpansionPort: pure function from Recipe step tuple + bindings to Step tuple.

Per [[project-recipe-aggregate-design]] the expansion is a PURE function:
no clock, no port I/O, no randomness, no module-global state. The port
carries a `version` attribute so `RecipeExpansionRecorded` provenance
events capture which expander emitted a given expansion, enabling
replay even if a deployment later swaps the default for a custom
expander.

The default adapter (`InMemoryRecipeExpansionPort`) delegates to the
pure `expand` function in `cora.operation._recipe_expansion`. Future
custom expanders (a deployment-specific DSL or a memoizing cache)
implement the same Protocol and ship their own `version` string.

Errors propagate unchanged: `UnboundRecipeBindingError` (from Recipe BC)
when a `BindingRef.name` is missing from `bindings`; `ValueError` for
unknown criterion kinds in a check step.

## 2-arg pure-substitution contract

Schema validation does NOT belong on this port. BindingRef-vs-schema
integrity lives in `cora.recipe.aggregates.recipe.steps_validation`
(called by the slice handler before expansion); operator-binding-value
shape validation lives in the slice decider via
`validate_values_against_schema` (raises `InvalidRecipeBindingsError`).
The port is pure substitution + ordering of typed Step VOs.

## PseudoAxis-aware widening

Past `v1` the port is widened with a second method,
`expand_pseudoaxis`, which rewrites virtual-axis SetpointSteps into N
sequential constituent SetpointSteps BEFORE the Conductor walks them
([[project-pseudoaxis-design]] v3). The two methods are kept
separate so the recipe-replay determinism gate (which re-runs
`expand` and compares hashes) is not perturbed by the PseudoAxis path:
`expand_pseudoaxis` is impure (loads Assets through the event_store),
so it lives outside the deterministic substitution kernel and runs
at conduct time on a per-invocation basis.

Adapters that bump the PseudoAxis path's semantics bump `version` to
the next stable tag (e.g., `"v2-pseudoaxis-aware"`). Provenance events
capture the version so re-expansion at replay time can detect drift.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from cora.infrastructure.ports import EventStore
    from cora.operation.conductor import Step
    from cora.recipe.aggregates.recipe import RecipeStep


@runtime_checkable
class RecipeExpansionPort(Protocol):
    """Pure expansion of a Recipe's step tuple to a Conductor `Step` tuple.

    `version` is a stable string identifying the expander (default impl
    pins to `"v2-pseudoaxis-aware"` since the PseudoAxis pre-Conductor
    expansion shipped). Provenance events capture `version` so the
    same `(steps, bindings)` inputs reproduce the same outputs even
    after a deployment swaps expanders.
    """

    @property
    def version(self) -> str: ...

    def expand(
        self, steps: tuple[RecipeStep, ...], bindings: Mapping[str, Any]
    ) -> tuple[Step, ...]: ...

    async def expand_pseudoaxis(
        self,
        steps: tuple[Step, ...],
        *,
        event_store: EventStore,
        correlation_id: UUID,
    ) -> tuple[Step, ...]:
        """Rewrite PseudoAxis SetpointSteps into N constituent SetpointSteps.

        Walks `steps` in order; PseudoAxis virtual-axis setpoints
        (address prefix `"pseudoaxis://"`) are replaced in place with
        the resolved tuple of constituent setpoints. ActionStep and
        CheckStep pass through unchanged. Non-PseudoAxis SetpointSteps
        pass through unchanged.

        Impure by design: the underlying evaluator loads Assets via
        `event_store`. This is the seam that keeps the deterministic
        `expand` kernel pure while threading the PseudoAxis path
        through the same port for symmetry with the `expansion_port`
        wiring site on the conduct_procedure handler.
        """
        ...


__all__ = ["RecipeExpansionPort"]
