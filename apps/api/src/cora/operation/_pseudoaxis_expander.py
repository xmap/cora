"""Pre-Conductor PseudoAxis step expansion.

Wires the PseudoAxis runtime evaluator into the path between recipe
expansion (`RecipeExpansionPort.expand`) and the Conductor
(`Conductor.conduct`). A `SetpointStep` whose `address` is of the form
`"pseudoaxis://<asset_id>/<port>"` is REWRITTEN into N sequential
constituent `SetpointStep`s targeting the constituent Assets, each
addressed via the placeholder scheme `"epics_ca://<constituent_asset_id>/setpoint"`.
`ActionStep` and `CheckStep` pass through unchanged.

The real adapter-resolution path (the substrate-specific PV name +
ControlPort registry longest-prefix match) is downstream of the
expander: the expander only rewrites the routing target so the
Conductor's existing dispatch loop walks N constituent setpoints in
declared order rather than a single virtual-port setpoint. The
placeholder scheme `"epics_ca://<id>/setpoint"` keeps the routing
substrate explicit; deployments that wire a non-CA substrate ship a
different prefix and the ControlPort registry resolves it.

## Caller-supplied `constituent_resolver`

The list of constituent Asset ids belonging to a PseudoAxis Asset is
NOT carried on the partition rule today (the rule shapes are pure
math); the wiring lives on `Plan.wiring`, which the conduct_procedure
handler does not load. The expander accepts a `constituent_resolver`
callable so the resolution can be deferred without changing the
expander's signature when the wiring lands. The default resolver
raises `PartitionRuleNotFoundError` with a message naming
`Plan.wiring` as the wiring follow-up; tests and the foundation-only
deployment can pass a stub resolver that returns a frozen tuple per
PseudoAxis Asset id.

## Setpoint addressing

A virtual-axis address parses as `"pseudoaxis://<asset_id>"` or
`"pseudoaxis://<asset_id>/<anything>"` (the suffix is ignored at this
tier; future routing extensions may consume it). `<asset_id>` must
be a UUID; a malformed UUID raises `AssetNotPseudoAxisError` with the
raw address so the operator sees the parse failure rather than a
substrate-shaped error.

Constituent setpoints are emitted with `verify=False` because
verification on the virtual axis is meaningful only after every
constituent has landed; a per-constituent verify would emit N
observational reads that the operator did not ask for. The original
`verify` flag on the PseudoAxis SetpointStep is therefore dropped at
the expander; operators who need post-dispatch verification of the
virtual-axis pose add an explicit CheckStep after the PseudoAxis
SetpointStep in the recipe.

See [[project-pseudoaxis-design]] v3 for the design lock + the
"pre-Conductor expansion" wiring rationale.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

from cora.operation._pseudoaxis_evaluator import resolve_pseudoaxis_command
from cora.operation.conductor import (
    SetpointStep,
    Step,
)
from cora.operation.errors import (
    AssetNotPseudoAxisError,
    PartitionRuleNotFoundError,
    PseudoAxisEvaluationFailedError,
)

if TYPE_CHECKING:
    from cora.infrastructure.ports import EventStore


_PSEUDOAXIS_SCHEME = "pseudoaxis://"
_CONSTITUENT_SCHEME = "epics_ca://"
_CONSTITUENT_PORT_SUFFIX = "/setpoint"


ConstituentResolver = Callable[[UUID], tuple[UUID, ...]]
"""Maps a PseudoAxis Asset id to its declared constituent Asset ids.

The expander invokes the resolver once per PseudoAxis SetpointStep
encountered. The default raises `PartitionRuleNotFoundError` naming
`Plan.wiring` as the follow-up. Deployment wiring will swap in a
real resolver that reads the active Plan's `Plan.wiring` and yields
the constituent Asset ids declared for the given virtual-axis source.
"""


def _default_constituent_resolver(asset_id: UUID) -> tuple[UUID, ...]:
    """Default resolver: refuses with a wiring-deferred error.

    Raises `PartitionRuleNotFoundError` so the operator sees a
    well-typed 409 rather than a generic NotImplementedError. The
    error message names `Plan.wiring` as the follow-up so log readers
    can trace the deferral to the right design memo without re-reading
    the source.
    """
    raise PartitionRuleNotFoundError(asset_id)


def _parse_pseudoaxis_asset_id(address: str) -> UUID:
    """Extract the Asset id from a `pseudoaxis://<asset_id>[/...]` address.

    Returns the parsed UUID. Raises `AssetNotPseudoAxisError` with the
    raw address attached as `asset_id` on any parse failure: a missing
    asset_id segment, a malformed UUID, or an empty address after the
    scheme. The error class matches the family-routing failure mode
    (the address claims to be a PseudoAxis target but is not in fact
    a resolvable PseudoAxis Asset id).
    """
    remainder = address[len(_PSEUDOAXIS_SCHEME) :]
    head = remainder.split("/", 1)[0]
    if not head:
        raise AssetNotPseudoAxisError(address)
    try:
        return UUID(head)
    except ValueError as exc:
        raise AssetNotPseudoAxisError(address) from exc


def _coerce_commanded_value(
    asset_id: UUID,
    value: int | float | bool | str | tuple[object, ...],
) -> float:
    """Coerce a SetpointStep value to a float for the evaluator.

    PseudoAxis partition rules operate on scalar floats. A bool is
    rejected (booleans are not meaningful virtual-axis commands even
    though `isinstance(True, int)` is True); strings and tuples are
    rejected with `PseudoAxisEvaluationFailedError` so the operator
    sees a typed application-layer error rather than a TypeError from
    deeper in the math kernel.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=None,
            reason=(
                f"PseudoAxis SetpointStep value must be int or float (got {type(value).__name__})"
            ),
        )
    return float(value)


def _is_pseudoaxis_address(address: str) -> bool:
    return address.startswith(_PSEUDOAXIS_SCHEME)


def _format_constituent_address(constituent_asset_id: UUID) -> str:
    """Build the placeholder constituent-dispatch address.

    Format `"epics_ca://<asset_id>/setpoint"`. The real ControlPort
    registry resolves the scheme prefix to the configured substrate
    adapter via longest-prefix-match. The path segment after the
    asset id is reserved for future routing extensions; today every
    constituent dispatch uses `/setpoint`.
    """
    return f"{_CONSTITUENT_SCHEME}{constituent_asset_id}{_CONSTITUENT_PORT_SUFFIX}"


async def expand_pseudoaxis_steps(
    steps: tuple[Step, ...],
    *,
    event_store: EventStore,
    correlation_id: UUID,
    pseudoaxis_family_ids: frozenset[UUID],
    constituent_resolver: ConstituentResolver = _default_constituent_resolver,
) -> tuple[Step, ...]:
    """Rewrite PseudoAxis SetpointSteps into N sequential constituent setpoints.

    Walks `steps` in order. For each `SetpointStep` whose `address`
    starts with `"pseudoaxis://"`:

      1. Parse the PseudoAxis Asset id from the address (raises
         `AssetNotPseudoAxisError` on a malformed address).
      2. Coerce the commanded value to float (raises
         `PseudoAxisEvaluationFailedError` on non-numeric values).
      3. Call `constituent_resolver(asset_id)` to get the tuple of
         constituent Asset ids declared for this virtual axis
         (default resolver raises `PartitionRuleNotFoundError`).
      4. Call `resolve_pseudoaxis_command` to evaluate the partition
         rule against the commanded value; surfaces every other
         PseudoAxis* error class on rule failure (singularity, missing
         partition rule, evaluation failure).
      5. Emit one `SetpointStep` per constituent in declared order,
         each addressed `"epics_ca://<id>/setpoint"`, value =
         resolved float, `verify=False`.

    `ActionStep` and `CheckStep` pass through unchanged. Non-
    PseudoAxis `SetpointStep`s pass through unchanged. The function is
    a pure rewrite over Step VOs modulo the event-store I/O the
    evaluator performs (Asset load) and the resolver call.

    `pseudoaxis_family_ids` is threaded into `resolve_pseudoaxis_command`
    so the evaluator can verify the resolved Asset's `family_ids`
    intersects the configured PseudoAxis Family id set; the wiring layer
    supplies the canonical PseudoAxis Family id at startup.

    Errors raised by the evaluator propagate unchanged so the
    routes-layer status-code mapping surfaces the right HTTP semantics
    (409 for routing / data-substrate gaps, 422 for evaluator-input
    failures, 500 for evaluator-internal failures, 502 for downstream
    dispatch, 403 for constituent-Surface authorization).
    """
    rewritten: list[Step] = []
    for step in steps:
        if isinstance(step, SetpointStep) and _is_pseudoaxis_address(step.address):
            asset_id = _parse_pseudoaxis_asset_id(step.address)
            commanded = _coerce_commanded_value(asset_id, step.value)
            constituent_asset_ids = constituent_resolver(asset_id)
            resolved = await resolve_pseudoaxis_command(
                event_store=event_store,
                asset_id=asset_id,
                commanded_value=commanded,
                constituent_asset_ids=constituent_asset_ids,
                correlation_id=correlation_id,
                pseudoaxis_family_ids=pseudoaxis_family_ids,
            )
            for constituent_id, value in zip(
                resolved.constituent_asset_ids,
                resolved.constituent_values,
                strict=True,
            ):
                rewritten.append(
                    SetpointStep(
                        address=_format_constituent_address(constituent_id),
                        value=value,
                        verify=False,
                    )
                )
        else:
            # ActionStep / CheckStep / non-PseudoAxis SetpointStep pass
            # through. Step is a closed union (SetpointStep | ActionStep
            # | CheckStep), so a future variant would land here as a
            # type-check error at the Conductor boundary.
            rewritten.append(step)
    return tuple(rewritten)


__all__ = [
    "ConstituentResolver",
    "expand_pseudoaxis_steps",
]
