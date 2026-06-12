"""Application handler for the `get_fixture_pidinst` query slice.

Thin: gates on the Authorize port (matching the `get_asset_pidinst`
precedent), then delegates to `assemble_fixture_pidinst_view`. Returns
the assembled `FixturePidinstView` or `None`; the route maps a None to
404 and runs the view through `to_fixture_pidinst_record` to produce
the wire-shape `PidinstRecord`. Each error propagates as-is to the
route layer, which maps via the BC's exception-handler registration:

  - returned `None`                              -> 404 (route maps)
  - `FixtureOwnerStateNotAvailableError`         -> 409 (serializer-time)
  - `FixtureManufacturerStateNotAvailableError`  -> 409
  - `FixtureLandingPageMissingError`             -> 422
  - `FixtureNameMissingError`                    -> 422
  - `PidinstRecordInvariantError`                -> 500 (kernel backstop)

Per L6 + L22: handler is async, pure aside from loader reads. No
decider, no event emission, no clock injection, no UUID generator.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._pidinst import FixturePidinstView
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.get_fixture_pidinst._view_assembler import (
    assemble_fixture_pidinst_view,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetFixturePidinst"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_fixture_pidinst handler implements."""

    async def __call__(
        self,
        fixture_id: UUID,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> FixturePidinstView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_fixture_pidinst handler closed over the shared deps."""

    async def handler(
        fixture_id: UUID,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> FixturePidinstView | None:
        _log.info(
            "get_fixture_pidinst.start",
            query_name=_QUERY_NAME,
            fixture_id=str(fixture_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )
        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_fixture_pidinst.denied",
                query_name=_QUERY_NAME,
                fixture_id=str(fixture_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)
        view = await assemble_fixture_pidinst_view(fixture_id, deps)
        if view is None:
            _log.info(
                "get_fixture_pidinst.not_found",
                query_name=_QUERY_NAME,
                fixture_id=str(fixture_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return None
        _log.info(
            "get_fixture_pidinst.success",
            query_name=_QUERY_NAME,
            fixture_id=str(fixture_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )
        return view

    return handler


__all__ = ["Handler", "bind"]
