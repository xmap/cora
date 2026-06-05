"""BC-application-layer errors for the Operation BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/operation/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/procedure/state.py`.

Distinct class from each other BC's `UnauthorizedError`: each BC
owns its own application-error namespace so an Operation 403 is
distinguishable from other BCs' 403s in logs / aggregator filters
(documented in CONTRIBUTING.md "BC-application-layer errors").
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class UnknownActionError(Exception):
    """The Conductor was asked to run an action whose name is not registered.

    Application-layer, not domain-layer: a missing registry entry is a
    configuration gap (the deployment didn't wire the action body),
    not an aggregate-invariant violation. Surfaces as a recorded
    `result="failed"` step entry on the Procedure's logbook plus a
    `ConductorFailure` on the result; the caller decides whether to
    abort the Procedure or fix the registry and retry.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"No action body registered for {name!r}")
        self.name = name


class CheckFailedError(Exception):
    """A `CheckStep` either read a non-Good quality or its criterion did not match.

    Application-layer: the substrate responded successfully, but the
    operator-supplied acceptance criterion did not approve the
    observation. Distinct from `Control*Error` so log filters can
    split substrate failures (network / IOC / access) from operator-
    spec-mismatch failures (criterion didn't match, quality flagged).

    The `reason` carries a short human-readable explanation (e.g.,
    `"quality=Bad"` or `"value 12.5 not in tolerance 10 +/- 1"`) so
    operators can triage from logs alone without re-running the check.
    """

    def __init__(self, address: str, reason: str) -> None:
        super().__init__(f"Check at {address!r} failed: {reason}")
        self.address = address
        self.reason = reason


class AssetNotPseudoAxisError(Exception):
    """A pre-expansion target asset_id exists but is not of Family PseudoAxis.

    Application-layer: the routing layer dispatched a virtual-port
    setpoint into the PseudoAxis evaluator for an Asset whose
    `family_ids` does NOT contain the PseudoAxis Family. This is a
    routing bug (the dispatcher should only have called the evaluator
    for PseudoAxis Assets), surfaced as a 409 so logs flag the
    mis-routing rather than 404-hiding it.
    """

    def __init__(self, asset_id: object) -> None:
        super().__init__(f"Asset {asset_id!r} is not of Family PseudoAxis")
        self.asset_id = asset_id


class PartitionRuleNotFoundError(Exception):
    """A PseudoAxis Asset has no partition rule set.

    The evaluator was invoked on a PseudoAxis Asset whose
    `partition_rule` is None (either never set or explicitly cleared).
    Mapped to 409 at the route layer: the Asset exists and is correctly
    classified, but the operating math is missing.
    """

    def __init__(self, asset_id: object) -> None:
        super().__init__(f"PseudoAxis Asset {asset_id!r} has no partition rule set")
        self.asset_id = asset_id


class PseudoAxisEvaluationFailedError(Exception):
    """A partition-rule evaluator returned a mathematical failure.

    Examples: NaN result from the math kernel, a LookupTable input
    outside the tabulated range with `extrapolation_kind=Error`, a
    solver divergence below the singularity threshold. Carries the
    rule `kind` and a short `reason` so operators can triage from
    logs alone.
    """

    def __init__(self, asset_id: object, kind: object, reason: str) -> None:
        super().__init__(
            f"PseudoAxis evaluation failed for asset {asset_id!r} (rule kind {kind!r}): {reason}"
        )
        self.asset_id = asset_id
        self.kind = kind
        self.reason = reason


class PseudoAxisConstituentNotFoundError(Exception):
    """A constituent asset_id referenced by the partition rule does not exist.

    The evaluator looked up the partition rule's
    `constituent_asset_ids` and one of them returned None from
    `load_asset` (or is Decommissioned, treated the same way for
    dispatch). Mapped to 409 because the PseudoAxis Asset's own
    rule references a constituent that the Equipment BC cannot
    resolve.
    """

    def __init__(self, asset_id: object, constituent_asset_id: object) -> None:
        super().__init__(
            f"PseudoAxis asset {asset_id!r} references "
            f"constituent asset {constituent_asset_id!r} that was not found"
        )
        self.asset_id = asset_id
        self.constituent_asset_id = constituent_asset_id


class PseudoAxisSingularityExceededError(Exception):
    """A SolverReference rule returned a residual exceeding singularity_threshold.

    The external solver converged on a candidate solution whose
    post-solve residual exceeds the rule's declared
    `singularity_threshold`. Treated as a singular pose; the evaluator
    refuses to dispatch the resulting setpoints to the constituents.
    """

    def __init__(self, asset_id: object, residual: float, threshold: float) -> None:
        super().__init__(
            f"PseudoAxis asset {asset_id!r} solver residual "
            f"{residual!r} exceeds singularity threshold {threshold!r}"
        )
        self.asset_id = asset_id
        self.residual = residual
        self.threshold = threshold


class PseudoAxisConstituentDispatchError(Exception):
    """A ControlPort write to one of the constituents failed mid-dispatch.

    Sequential-with-cancel-on-failure dispatch hit a constituent
    setpoint that the substrate rejected. Carries the failed
    constituent id, the resolved setpoint that was being applied,
    and the underlying ControlPort exception so the post-mortem has
    full evidence. Partial-progress state (constituents already
    dispatched) is recorded separately in the structured-log event,
    not on this exception.
    """

    def __init__(
        self,
        asset_id: object,
        failed_constituent_id: object,
        applied: object,
        underlying: BaseException,
    ) -> None:
        super().__init__(
            f"PseudoAxis asset {asset_id!r} constituent "
            f"{failed_constituent_id!r} dispatch failed (applied={applied!r}): "
            f"{underlying!r}"
        )
        self.asset_id = asset_id
        self.failed_constituent_id = failed_constituent_id
        self.applied = applied
        self.underlying = underlying


class PseudoAxisConstituentUnauthorizedError(Exception):
    """A constituent's Surface authorization failed pre-validation.

    The pre-dispatch authz sweep verified the principal's permission
    for every constituent's Surface BEFORE the evaluator accepted the
    operator's command. One constituent failed; the entire command
    is rejected at command-acceptance time (HTTP 403), NOT mid-dispatch.
    Defined here so the wiring follow-up can raise it without
    re-shaping this module; not raised by the foundation evaluator.
    """

    def __init__(
        self,
        asset_id: object,
        constituent_asset_id: object,
        reason: str,
    ) -> None:
        super().__init__(
            f"PseudoAxis asset {asset_id!r} constituent "
            f"{constituent_asset_id!r} unauthorized: {reason}"
        )
        self.asset_id = asset_id
        self.constituent_asset_id = constituent_asset_id
        self.reason = reason
