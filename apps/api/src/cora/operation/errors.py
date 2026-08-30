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

from uuid import UUID


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


class UnknownTriggerDialectError(ValueError):
    """`ActionContext.trigger_dialect` names a dialect `acquisitions` does not know.

    Application-layer, not domain-layer: which detector-driver vocabulary
    a deployment's camera speaks is a wiring/configuration fact
    (`Settings.detector_trigger_dialect`), not an aggregate invariant.
    Raised instead of letting a typo'd or unconfigured dialect surface as
    a bare `KeyError`, which would name neither the bad value nor what
    was expected. A wrong dialect must fail loudly: silently falling
    back to a default would write a string the real camera's enum does
    not accept, or worse, one it accepts with the inverted meaning.
    """

    def __init__(self, dialect: str, known_dialects: list[str]) -> None:
        super().__init__(
            f"unknown detector_trigger_dialect {dialect!r}; known dialects: {known_dialects}"
        )


class ActionRefusedError(Exception):
    """An action body declined the step BEFORE touching the substrate.

    The Conductor catches this alongside `_CONTROL_ERRORS` at the
    action-dispatch site and gives it the same treatment: a recorded
    `result="failed"` step entry plus a `ConductorFailure`, so the
    Procedure reaches a terminal state. Without a shared base the
    Conductor would need to import each body's private refusal, coupling
    the orchestrator to the acquisition bodies; a body signals "I will
    not do this" by subclassing, and the Conductor never learns why.

    Raising one carries a promise that NOTHING was written yet. That is
    what makes it safe to treat as an ordinary recorded failure: a
    refusal thrown midway would leave the substrate half-configured
    while the record said only that the step failed, which is the
    situation the refusals exist to prevent. Subclasses must be raised
    before the body's first write, and their tests must assert that no
    write occurred.

    Distinct from a `Control*Error`, which means the substrate refused
    or could not be reached: this means CORA refused, on its own reading
    of the request, without asking the substrate anything.
    """


class UnboundedAcquisitionError(ActionRefusedError):
    """A detector acquisition body was asked for `repetitions=None` while it waits for completion.

    Application-layer, not domain-layer: whether a given action body's
    done-poll can tolerate a free-running acquisition is a body-shape
    fact, not an aggregate invariant. `collect` and `continuous` both
    wait on `Acquire_RBV` reaching Done with no internal timeout
    (`cora.operation.acquisitions._await_acquire_done`), and an
    unbounded acquisition (areaDetector `ImageMode=Continuous`) never
    asserts Done on its own, so combining the two would hang the
    caller forever and leave the camera acquiring. Raised before any
    PV write so a caller who wants free-running acquisition never
    leaves the camera partially configured through this action body.
    """

    def __init__(self, detector: str) -> None:
        super().__init__(
            f"unbounded acquisition on {detector!r} cannot be combined with waiting for "
            "completion; a bounded repetitions value is required"
        )
        self.detector = detector


class UnwiredExternalTriggerError(ActionRefusedError):
    """A detector acquisition body was asked for an External trigger_mode CORA cannot arm.

    Application-layer, not domain-layer: whether the trigger EMITTER
    (the device named by `source`) is wired into this deployment is a
    configuration fact, not an aggregate invariant. `collect` and
    `continuous` write only the detector-side PVs (see the module
    docstring's "v1 detector-side / emitter-side split" in
    `cora.operation.acquisitions`); CORA does not configure the
    emitter, so setting the detector's TriggerMode to External and
    then waiting for pulses nothing arranged would hang the caller
    forever, the same hang shape `UnboundedAcquisitionError` guards
    against. Raised before any PV write so a caller who asks for
    external triggering never leaves the detector partially armed
    through this action body.
    """

    def __init__(self, detector: str, trigger_mode: str) -> None:
        super().__init__(
            f"external trigger_mode {trigger_mode!r} on {detector!r} is not wired end to "
            "end: CORA does not configure the trigger emitter, and waiting for pulses "
            "nobody arranged would hang"
        )
        self.detector = detector
        self.trigger_mode = trigger_mode


class SteeringWireMismatchError(Exception):
    """A steered conduct request's space/objective does not line up with the recipe.

    Raised when `conduct_until_advised`'s pre-FSM wire guard rejects the request:
    a `SteeringSpace` axis the brain could propose is not consumed by any
    `SteeringRef` (or `CaptureRef`) setpoint in the pinned recipe block, or the
    objective captures-slot collides with a seeded axis. The request is
    well-formed (Pydantic accepted it) but cannot be processed against the
    pinned recipe, so the route maps it to HTTP 422 (operator-correctable: align
    the space to the recipe's steering setpoints). Fires BEFORE any FSM event,
    so nothing was started. The handler translates the Conductor's pre-FSM
    ValueError into this typed error so the wire surfaces a 422, not a 500.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ClosingCaptureBeforeBoundaryError(Exception):
    """A closing step's `CaptureRef` names a capture only the pre-boundary
    main steps declare.

    `conduct_from` starts the per-conduct `captures` dict EMPTY: only the
    main steps from `boundary` onward re-run and can deposit into it (the
    same "fails loud rather than resolving against stale data" contract
    `execute_from` already holds for a main-step `CaptureRef`). Closing
    steps always run in full regardless of `boundary`, so a closing
    `CaptureRef` whose only declaring `CaptureStep` / capturing
    `ComputeStep` sits before `boundary` would resolve against nothing
    during THIS resume and fail as `UnresolvedCaptureRef` -- but inside
    `_run_closing`'s per-step isolation, that failure is recorded and the
    walk continues, silently converting a should-be-loud gap into a
    recorded-and-continue one. Checked up front instead, so the operator
    sees a 422 naming the missing capture and can pick a boundary at or
    before the declaring step, rather than a closing_failures entry after
    the fact.
    """

    def __init__(self, capture_name: str, boundary: int) -> None:
        super().__init__(
            f"closing step references capture {capture_name!r}, which only a "
            f"pre-boundary main step (boundary={boundary}) declares; resume "
            "starts captures empty, so this closing step would never see it"
        )
        self.capture_name = capture_name
        self.boundary = boundary


class UnsupportedClosingStepsError(Exception):
    """A loop-driving conduct slice refuses a closing-bearing Recipe (v1 scope).

    `conduct_until_converged` / `conduct_until_advised` / `conduct_until_advised_from`
    each re-walk ONE pass block repeatedly (loop-top abort, per-iteration
    re-expansion); `_run_closing` runs once, on a real conduct terminal, and
    has no defined place in a loop that may never terminate the way `conduct`
    /`conduct_or_hold` do. Rather than silently drop the Recipe's closing
    steps or guess when to run them, these three slices refuse the request
    up front: well-formed, but this Recipe cannot be driven by a loop slice
    until closing-in-a-loop is designed. Mapped to HTTP 422 (operator-
    correctable: use `conduct` / `conduct_or_hold` for this Recipe, or
    author a closing-less variant for loop-driven conduct).
    """

    def __init__(self, procedure_id: UUID) -> None:
        super().__init__(
            f"procedure {procedure_id} is bound to a Recipe with closing_steps, "
            "which loop-driving conduct slices do not support"
        )
        self.procedure_id = procedure_id


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


class PseudoAxisCommandOutsideRangeError(Exception):
    """A LookupTable command fell outside the calibrated range with extrapolation_kind=Error.

    The operator requested an independent value (for example a beam
    energy) below the lowest or above the highest tabulated point of the
    pinned calibration curve, and the rule's `extrapolation_kind` is
    `Error` (refuse rather than clamp to the endpoint). Operator-
    correctable: request a value inside the calibrated range, or extend
    the calibration with a revision that covers it. Mapped to 422,
    alongside the other evaluator-input failures the operator can fix,
    NOT 500 (the command was well-formed; the request is the problem).
    """

    def __init__(self, asset_id: object, commanded: float, low: float, high: float) -> None:
        super().__init__(
            f"PseudoAxis command {commanded!r} for asset {asset_id!r} is outside the "
            f"calibrated range [{low!r}, {high!r}] and extrapolation_kind=Error "
            "forbids extrapolation"
        )
        self.asset_id = asset_id
        self.commanded = commanded
        self.low = low
        self.high = high


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
