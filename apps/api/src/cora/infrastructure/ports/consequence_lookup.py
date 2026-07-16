"""ConsequenceLookup port: cross-BC query for Trust BC's ratification-coverage
projection (consequence gate, Gate IV).

Used by Run BC's `stop_run` handler to gate a consequence-classed command on the
presence of a GRANTED Ratification covering this action's scope
`(run_id, command_name)`. A second, independent principal must have granted the
co-signature before the action is admitted; absent that, the gate refuses and the
run is placed in the shared hold pending the co-sign.

## Convention

Mirrors `ClearanceLookup` exactly: one implementor (Trust BC ships
`PostgresConsequenceLookup` reading `proj_trust_ratification_coverage`), one
consumer today (Run's `stop_run`; more in-scope commands later). Lives in
`cora.infrastructure.ports` for neutral cross-BC access. The port is shaped around
the CONSUMER's need ("is this action co-signed?"), not Trust's domain language;
the adapter translates the projection's columns to this shape.

## Coverage semantics

"Covered" means: a Ratification exists with `status = 'Granted'`, `run_id = <the
run>`, and `command_name = <the gated command>`. The consequence-class trigger
(which commands require co-sign) is a static allowlist on the Run side
(`COMMANDS_REQUIRING_RATIFICATION`); this port answers ONLY the coverage question,
keeping the trigger and the lookup orthogonal. A log-folded first-of-kind
refinement of the trigger is a documented follow-up and does not change this
port's contract.
"""

from typing import Protocol
from uuid import UUID


class ConsequenceLookup(Protocol):
    """Cross-BC port: query Trust's ratification-coverage projection from Run BC."""

    async def granted_coverage_exists(
        self,
        *,
        run_id: UUID,
        command_name: str,
    ) -> bool:
        """Return True iff a Granted Ratification covers `(run_id, command_name)`.

        A Requested (pending) or Denied Ratification does NOT count as coverage:
        only a second principal's Grant admits the action. False means the gated
        command must be refused (and the run placed in the shared hold pending a
        co-sign).
        """
        ...


class NeverRatifiedConsequenceLookup:
    """Test-default stub: nothing is ever co-signed (no coverage).

    The conservative default: a consequence-gated command is never pre-covered, so
    a test that does not exercise ratification sees the gate's refuse-and-hold
    path only when it opts a command into the allowlist. Tests that exercise the
    grant path override with the real `PostgresConsequenceLookup` and seed a
    Granted Ratification via `request_ratification` + `grant_ratification`.

    Named in the `AllowAll` / `AlwaysCovered` / `NeverRatified` test-default
    family (the disposition is in the name).
    """

    async def granted_coverage_exists(
        self,
        *,
        run_id: UUID,
        command_name: str,
    ) -> bool:
        _ = (run_id, command_name)  # no coverage recorded
        return False


class AlwaysRatifiedConsequenceLookup:
    """Test-default stub: everything is co-signed (coverage always present).

    The permissive default for the many existing Run tests that call stop_run
    WITHOUT caring about the consequence gate: with stop_run in the allowlist,
    those tests would otherwise all trip the gate. Wiring this as the
    build_postgres_deps / make_*_kernel default keeps them green; gate tests
    override with NeverRatifiedConsequenceLookup (refuse path) or the real adapter
    (end-to-end).
    """

    async def granted_coverage_exists(
        self,
        *,
        run_id: UUID,
        command_name: str,
    ) -> bool:
        _ = (run_id, command_name)  # synthetic coverage for everything
        return True


__all__ = [
    "AlwaysRatifiedConsequenceLookup",
    "ConsequenceLookup",
    "NeverRatifiedConsequenceLookup",
]
