"""Application handler for the `get_asset_pidinst` query slice.

Thin: calls `assemble_pidinst_view` then `to_pidinst_record`. Each
error propagates as-is to the route layer, which maps via the BC's
exception-handler registration:

  - `AssetNotFoundError`               -> 404 (existing not-found tuple)
  - `VirtualAxisNotPidinstableError`   -> 404 (Asset carries a
    partition_rule; virtual axes are PIDINST-ineligible by design)
  - `OwnerStateNotAvailableError`      -> 409 (per L8 + L9; new)
  - `ManufacturerStateNotAvailableError` -> 409 (per L8 + L9; new)
  - `LandingPageMissingError`          -> 422 (per L8 + L9; new)
  - `AssetNameMissingError`            -> 422 (per L8 + L9; new)
  - `PidinstRecordInvariantError`      -> 500 (intentional per L11 of
    project_asset_persistent_id_design: server-bug backstop, NOT a
    routable error. The four pre-construction validators above cover
    every client-fixable case; if this fires the assembler produced
    a malformed view, which is a CORA bug. FastAPI default 500 is
    the locked policy; this handler logs the violation at error
    level before re-raising so monitoring still sees it (the
    serializer cannot log directly per L22 purity).

Per L5 + L22: handler is async, pure aside from loader reads. No
decider, no event emission, no clock injection, no UUID generator.
The assembler is fed `facility_publisher` + `landing_page_template`
from settings at bind time; per-request callers do not pass these in.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._pidinst import PidinstRecord, to_pidinst_record
from cora.equipment.errors import PidinstRecordInvariantError, UnauthorizedError
from cora.equipment.features.get_asset_pidinst._view_assembler import assemble_pidinst_view
from cora.equipment.features.get_asset_pidinst.query import GetAssetPidinst
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetAssetPidinst"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_asset_pidinst handler implements."""

    async def __call__(
        self,
        query: GetAssetPidinst,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PidinstRecord: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_asset_pidinst handler closed over the shared deps."""
    facility_publisher = deps.settings.facility_publisher
    landing_page_template = deps.settings.landing_page_template

    async def handler(
        query: GetAssetPidinst,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PidinstRecord:
        _log.info(
            "get_asset_pidinst.start",
            query_name=_QUERY_NAME,
            asset_id=str(query.asset_id),
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
                "get_asset_pidinst.denied",
                query_name=_QUERY_NAME,
                asset_id=str(query.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)
        view = await assemble_pidinst_view(
            deps.event_store,
            query.asset_id,
            facility_publisher=facility_publisher,
            landing_page_template=landing_page_template,
        )
        try:
            record = to_pidinst_record(view)
        except PidinstRecordInvariantError as exc:
            # Should never fire: the four pre-construction validators
            # inside `to_pidinst_record` cover every PIDINST-mandatory-
            # state gap, so a PidinstRecord invariant violation here is
            # a CORA bug (assembler produced a malformed view, or
            # PidinstRecord.__post_init__ added an invariant without a
            # matching pre-construction guard). Lock 11 of
            # project_asset_persistent_id_design forbids wiring this to
            # a custom HTTP handler; FastAPI's default 500 fires after
            # this re-raise. The structured log closes the
            # observability gap that the bare-500 path would otherwise
            # leave, and lives at the application boundary because L22
            # forbids logging inside the serializer.
            _log.exception(
                "get_asset_pidinst.pidinst_record_invariant",
                query_name=_QUERY_NAME,
                asset_id=str(query.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=exc.reason,
            )
            raise
        _log.info(
            "get_asset_pidinst.success",
            query_name=_QUERY_NAME,
            asset_id=str(query.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )
        return record

    return handler


__all__ = ["Handler", "bind"]
