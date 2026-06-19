"""HTTP setup for the Federation BC.

`register_federation_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

Attached routers cover the five Permit lifecycle slices
(`define_permit` + `activate_permit` + `suspend_permit` +
`resume_permit` + `revoke_permit`), the five Credential lifecycle
slices (`register_credential` + `start_credential_rotation` +
`complete_credential_rotation` + `abort_credential_rotation` +
`revoke_credential`), the five Seal lifecycle slices
(`initialize_seal` + `sign_seal_pointer` +
`rotate_seal_online_key` + `start_seal_republishing` +
`complete_seal_republishing`), and the six read-side slices
(`list_permits` + `get_permit` + `list_credentials` +
`get_credential` + `list_seals` + `get_seal`); queries surface
404 on miss through the existing `*NotFoundError` handlers. The
Seal domain-error handlers are wired alongside the Credential
handlers so the arch-fitness
`test_every_domain_error_registered_as_http_handler` stays green.
"""

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.federation.aggregates.credential.state import (
    CredentialAlreadyExistsError,
    CredentialCannotRevokeError,
    CredentialCannotRotateError,
    CredentialExpiredError,
    CredentialNotFoundError,
    InvalidCredentialSecretRefError,
)
from cora.federation.aggregates.facility import (
    FacilityAlreadyExistsError,
    FacilityAreaCannotHaveTrustAnchorsError,
    FacilityAreaMustHaveParentError,
    FacilityAreaParentMustBeSiteError,
    FacilityCannotAddTrustAnchorCredentialError,
    FacilityCannotDecommissionError,
    FacilityNotFoundError,
    FacilityParentNotFoundError,
    FacilitySiteCannotHaveParentError,
    FacilityTrustAnchorCredentialAlreadyPresentError,
    FacilityTrustAnchorCredentialNotPresentError,
    InvalidFacilityNameError,
)
from cora.federation.aggregates.permit.state import (
    InvalidPermitScopeError,
    PermitAlreadyExistsError,
    PermitCannotActivateError,
    PermitCannotResumeError,
    PermitCannotRevokeError,
    PermitCannotSuspendError,
    PermitNotFoundError,
    PermitScopeCollapseError,
    UnsupportedCanonicalizationVersionError,
)
from cora.federation.aggregates.seal.state import (
    InvalidSealFacilityIdError,
    InvalidSealHeadHashError,
    SealAlreadyExistsError,
    SealCannotCompleteRepublishingError,
    SealCannotInitializeWithInactiveCredentialError,
    SealCannotRotateError,
    SealCannotRotateWithInactiveCredentialError,
    SealCannotSignError,
    SealCannotStartRepublishingError,
    SealCredentialNotTrustAnchorError,
    SealKeyCollisionError,
    SealKeyPurposeMismatchError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
)
from cora.federation.errors import FederationError, UnauthorizedError
from cora.federation.features import (
    abort_credential_rotation,
    activate_permit,
    add_facility_trust_anchor_credential,
    complete_credential_rotation,
    complete_seal_republishing,
    decommission_facility,
    define_permit,
    get_credential,
    get_permit,
    get_seal,
    initialize_seal,
    list_credentials,
    list_permits,
    list_seals,
    register_credential,
    register_facility,
    remove_facility_trust_anchor_credential,
    resume_permit,
    revoke_credential,
    revoke_permit,
    rotate_seal_online_key,
    sign_seal_pointer,
    start_credential_rotation,
    start_seal_republishing,
    suspend_permit,
)

federation_router = APIRouter(prefix="/federation", tags=["federation"])


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_unprocessable_error(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_conflict(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


async def _handle_federation_error(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


def register_federation_routes(app: FastAPI) -> None:
    """Attach Federation slice routers and exception handlers to the FastAPI app."""
    app.include_router(federation_router)
    app.include_router(define_permit.router)
    app.include_router(activate_permit.router)
    app.include_router(suspend_permit.router)
    app.include_router(resume_permit.router)
    app.include_router(revoke_permit.router)
    app.include_router(register_credential.router)
    app.include_router(start_credential_rotation.router)
    app.include_router(complete_credential_rotation.router)
    app.include_router(abort_credential_rotation.router)
    app.include_router(revoke_credential.router)
    app.include_router(initialize_seal.router)
    app.include_router(sign_seal_pointer.router)
    app.include_router(rotate_seal_online_key.router)
    app.include_router(start_seal_republishing.router)
    app.include_router(complete_seal_republishing.router)
    app.include_router(register_facility.router)
    app.include_router(decommission_facility.router)
    app.include_router(add_facility_trust_anchor_credential.router)
    app.include_router(remove_facility_trust_anchor_credential.router)
    app.include_router(list_permits.router)
    app.include_router(get_permit.router)
    app.include_router(list_credentials.router)
    app.include_router(get_credential.router)
    app.include_router(list_seals.router)
    app.include_router(get_seal.router)
    for validation_cls in (
        InvalidPermitScopeError,
        InvalidCredentialSecretRefError,
        InvalidFacilityNameError,
        InvalidSealFacilityIdError,
        InvalidSealHeadHashError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for unprocessable_cls in (
        PermitScopeCollapseError,
        UnsupportedCanonicalizationVersionError,
        CredentialExpiredError,
        FacilitySiteCannotHaveParentError,
        FacilityAreaMustHaveParentError,
        FacilityAreaCannotHaveTrustAnchorsError,
        FacilityAreaParentMustBeSiteError,
        SealKeyCollisionError,
        SealKeyPurposeMismatchError,
        SealSequenceNumberRegressionError,
    ):
        app.add_exception_handler(unprocessable_cls, _handle_unprocessable_error)
    for not_found_cls in (
        PermitNotFoundError,
        CredentialNotFoundError,
        FacilityNotFoundError,
        FacilityParentNotFoundError,
        SealNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        PermitAlreadyExistsError,
        CredentialAlreadyExistsError,
        FacilityAlreadyExistsError,
        SealAlreadyExistsError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for conflict_cls in (
        PermitCannotActivateError,
        PermitCannotSuspendError,
        PermitCannotResumeError,
        PermitCannotRevokeError,
        CredentialCannotRotateError,
        CredentialCannotRevokeError,
        FacilityCannotAddTrustAnchorCredentialError,
        FacilityCannotDecommissionError,
        FacilityTrustAnchorCredentialAlreadyPresentError,
        FacilityTrustAnchorCredentialNotPresentError,
        SealCannotSignError,
        SealCannotRotateError,
        SealCannotInitializeWithInactiveCredentialError,
        SealCannotRotateWithInactiveCredentialError,
        SealCannotStartRepublishingError,
        SealCannotCompleteRepublishingError,
        SealCredentialNotTrustAnchorError,
    ):
        app.add_exception_handler(conflict_cls, _handle_conflict)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
    app.add_exception_handler(FederationError, _handle_federation_error)


__all__ = ["federation_router", "register_federation_routes"]
