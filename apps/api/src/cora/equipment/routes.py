"""HTTP setup for the Equipment BC.

`register_equipment_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Equipment
does not re-register them.

## Loop-collapse pattern

Equipment owns multiple aggregates (Family + Asset, with more
slices to come). Three error families share the same response
shape and get collapsed via Trust's `_handle_invalid_name`-style
loop pattern:

  - 400 (validation): InvalidFamilyName, InvalidAssetName,
    InvalidAssetParent
  - 404 (load miss): FamilyNotFound, AssetNotFound
  - 409 (defensive guard for AlreadyExists): FamilyAlreadyExists,
    AssetAlreadyExists

Adding a new aggregate (or a new transition error) becomes one tuple
entry per family. When the SubjectCannot<X>Error family lands for
Asset lifecycle (5c+), it gets its own loop following Subject's
precedent.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.equipment.aggregates._drawing import InvalidDrawingError
from cora.equipment.aggregates._placement import InvalidPlacementError
from cora.equipment.aggregates.asset import (
    AssetAlreadyExistsError,
    AssetCannotActivateError,
    AssetCannotAddFamilyError,
    AssetCannotAddPortError,
    AssetCannotDecommissionError,
    AssetCannotEnterMaintenanceError,
    AssetCannotExitMaintenanceError,
    AssetCannotRelocateError,
    AssetCannotRemoveFamilyError,
    AssetCannotRemovePortError,
    AssetNotFoundError,
    InvalidAssetNameError,
    InvalidAssetParentError,
    InvalidAssetPortNameError,
    InvalidAssetPortSignalTypeError,
    InvalidAssetSettingsError,
)
from cora.equipment.aggregates.family import (
    FamilyAlreadyExistsError,
    FamilyCannotDeprecateError,
    FamilyCannotVersionError,
    FamilyNotFoundError,
    InvalidAffordanceError,
    InvalidFamilyNameError,
    InvalidFamilySettingsSchemaError,
    InvalidFamilyVersionTagError,
)
from cora.equipment.aggregates.frame import (
    FrameAlreadyExistsError,
    FrameCannotDecommissionError,
    FrameCannotSupersedeError,
    FrameCannotUpdateError,
    FrameInUseError,
    FrameNotFoundError,
    InvalidFrameNameError,
    InvalidFrameRevisionError,
    InvalidFrameRootError,
)
from cora.equipment.aggregates.model import (
    InvalidDeclaredFamiliesError,
    InvalidManufacturerIdentifierError,
    InvalidManufacturerIdentifierPairingError,
    InvalidManufacturerNameError,
    InvalidModelDeprecationReasonError,
    InvalidModelNameError,
    InvalidModelVersionTagError,
    InvalidPartNumberError,
    ModelAlreadyExistsError,
    ModelCannotAddFamilyError,
    ModelCannotDeprecateError,
    ModelCannotRemoveFamilyError,
    ModelCannotVersionError,
    ModelFamilyAlreadyPresentError,
    ModelFamilyNotPresentError,
    ModelNotFoundError,
)
from cora.equipment.aggregates.mount import (
    AssetAlreadyInstalledElsewhereError,
    AssetNotFoundForMountError,
    AssetNotInstallableError,
    InvalidSlotCodeError,
    MountAlreadyExistsError,
    MountAlreadyOccupiedError,
    MountCannotDecommissionError,
    MountCannotUpdateError,
    MountHasActiveChildrenError,
    MountHasAssetInstalledError,
    MountIsEmptyError,
    MountNotFoundError,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features import (
    activate_asset,
    add_asset_family,
    add_asset_port,
    add_model_family,
    decommission_asset,
    decommission_frame,
    decommission_mount,
    define_family,
    define_model,
    degrade_asset,
    deprecate_family,
    deprecate_model,
    enter_maintenance,
    exit_maintenance,
    fault_asset,
    get_asset,
    get_asset_integration_view,
    get_family,
    get_model,
    install_asset,
    list_assets,
    list_families,
    register_asset,
    register_frame,
    register_mount,
    relocate_asset,
    remove_asset_family,
    remove_asset_port,
    remove_model_family,
    restore_asset,
    uninstall_asset,
    update_asset_settings,
    update_family_settings_schema,
    update_frame_placement,
    update_mount_placement,
    version_family,
    version_model,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error.

    Covers Invalid<X>NameError VOs and InvalidAssetParentError. All
    map to the same HTTP 400 + `{"detail": str(exc)}` body. Adding
    a new validation-style error is one extra entry in the tuple in
    `register_equipment_routes`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 404 handler for every aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for every aggregate's AlreadyExistsError.

    The decider raises these if the target stream already has
    events. In production with UUIDv7 ids this is essentially
    impossible, but the unmapped raise would surface as 500 instead
    of a clean 409 — this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers the `<X>Cannot<Verb>Error` family (Asset's Activate /
    Decommission; future Maintenance / Restore). Same pattern as
    Subject's `_handle_cannot_transition`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_equipment_routes(app: FastAPI) -> None:
    """Attach Equipment slice routers and exception handlers to the FastAPI app."""
    app.include_router(define_family.router)
    app.include_router(define_model.router)
    app.include_router(version_model.router)
    app.include_router(deprecate_model.router)
    app.include_router(add_model_family.router)
    app.include_router(remove_model_family.router)
    app.include_router(get_model.router)
    app.include_router(get_family.router)
    app.include_router(version_family.router)
    app.include_router(deprecate_family.router)
    app.include_router(update_family_settings_schema.router)
    app.include_router(list_families.router)
    app.include_router(register_asset.router)
    app.include_router(activate_asset.router)
    app.include_router(decommission_asset.router)
    app.include_router(relocate_asset.router)
    app.include_router(enter_maintenance.router)
    app.include_router(exit_maintenance.router)
    app.include_router(add_asset_family.router)
    app.include_router(remove_asset_family.router)
    app.include_router(degrade_asset.router)
    app.include_router(fault_asset.router)
    app.include_router(restore_asset.router)
    app.include_router(update_asset_settings.router)
    app.include_router(add_asset_port.router)
    app.include_router(remove_asset_port.router)
    app.include_router(get_asset.router)
    app.include_router(get_asset_integration_view.router)
    app.include_router(list_assets.router)
    app.include_router(register_frame.router)
    app.include_router(update_frame_placement.router)
    app.include_router(decommission_frame.router)
    app.include_router(register_mount.router)
    app.include_router(update_mount_placement.router)
    app.include_router(decommission_mount.router)
    app.include_router(install_asset.router)
    app.include_router(uninstall_asset.router)
    for validation_cls in (
        InvalidAffordanceError,
        InvalidFamilyNameError,
        InvalidFamilySettingsSchemaError,
        InvalidFamilyVersionTagError,
        InvalidAssetNameError,
        InvalidAssetParentError,
        InvalidAssetPortNameError,
        InvalidAssetPortSignalTypeError,
        InvalidAssetSettingsError,
        InvalidFrameNameError,
        InvalidFrameRevisionError,
        InvalidFrameRootError,
        InvalidPlacementError,
        InvalidDrawingError,
        InvalidSlotCodeError,
        InvalidModelNameError,
        InvalidPartNumberError,
        InvalidManufacturerNameError,
        InvalidManufacturerIdentifierError,
        InvalidManufacturerIdentifierPairingError,
        InvalidModelVersionTagError,
        InvalidModelDeprecationReasonError,
        InvalidDeclaredFamiliesError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        FamilyNotFoundError,
        AssetNotFoundError,
        FrameNotFoundError,
        MountNotFoundError,
        AssetNotFoundForMountError,
        ModelNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        FamilyAlreadyExistsError,
        AssetAlreadyExistsError,
        FrameAlreadyExistsError,
        MountAlreadyExistsError,
        ModelAlreadyExistsError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        AssetCannotActivateError,
        AssetCannotDecommissionError,
        AssetCannotRelocateError,
        AssetCannotEnterMaintenanceError,
        AssetCannotExitMaintenanceError,
        AssetCannotAddFamilyError,
        AssetCannotRemoveFamilyError,
        AssetCannotAddPortError,
        AssetCannotRemovePortError,
        FamilyCannotVersionError,
        FamilyCannotDeprecateError,
        FrameCannotUpdateError,
        FrameCannotDecommissionError,
        FrameCannotSupersedeError,
        FrameInUseError,
        MountCannotUpdateError,
        MountCannotDecommissionError,
        MountHasAssetInstalledError,
        MountHasActiveChildrenError,
        MountAlreadyOccupiedError,
        MountIsEmptyError,
        AssetNotInstallableError,
        AssetAlreadyInstalledElsewhereError,
        ModelCannotVersionError,
        ModelCannotDeprecateError,
        ModelCannotAddFamilyError,
        ModelCannotRemoveFamilyError,
        ModelFamilyAlreadyPresentError,
        ModelFamilyNotPresentError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
