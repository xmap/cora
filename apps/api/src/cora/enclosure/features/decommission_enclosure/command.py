"""The `DecommissionEnclosure` command: intent dataclass for this slice.

`enclosure_id` is the target Enclosure aggregate (the internal-opaque
UUID PK; spine reference within this deployment). `reason` is
operator-supplied free text captured at the API boundary for
audit-log breadcrumb purposes ("end-of-life", "decommissioned hutch",
"infrastructure retirement"). `reason` is validated by the
`EnclosureReason` VO at the decider (trimmed; 1-500 chars) and
flows through to the `EnclosureDecommissioned` event payload so
operator context survives on the immutable event log.

The principal-id of the invoker is supplied separately by the
application handler and stamped onto the `EnclosureDecommissioned`
event as `triggered_by` (operator attribution; this slice has no
Monitor-trigger counterpart by design).

Terminal transition: `lifecycle=Active -> Decommissioned`. The
orthogonal `permit_status` axis is preserved verbatim as audit trail
(the terminal transition mutates `lifecycle` only). Strict-not-
idempotent at the decider: re-decommissioning an already-Decommissioned
enclosure raises `EnclosureCannotDecommissionError` (HTTP 409) per
the same convention as `decommission_facility` / `deregister_supply`.

Address reuse: the projection UNIQUE INDEX on enclosure address is
PARTIAL on `lifecycle = 'Active'`, so decommissioning frees the
address for re-registration.
"""

from dataclasses import dataclass

from cora.enclosure.aggregates._value_types import EnclosureId


@dataclass(frozen=True, slots=True)
class DecommissionEnclosure:
    """Operator decommissions an Enclosure (terminal: Active -> Decommissioned).

    Strict-not-idempotent: decommissioning an already-Decommissioned
    enclosure raises `EnclosureCannotDecommissionError`. `reason` is
    validated to `EnclosureReason` at the decider.
    """

    enclosure_id: EnclosureId
    reason: str
