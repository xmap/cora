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

Equipment owns six aggregates (Family, Model, Asset, Frame, Mount, Role).
Three error families share the same response shape and get collapsed
via Trust's `_handle_invalid_name`-style loop pattern:

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
from cora.equipment.aggregates._partition_rule import InvalidPartitionRuleError
from cora.equipment.aggregates._placement import InvalidPlacementError
from cora.equipment.aggregates.assembly import (
    AssemblyAlreadyExistsError,
    AssemblyCannotDeprecateError,
    AssemblyCannotInstantiateError,
    AssemblyCannotVersionError,
    AssemblyNotFoundError,
    AssemblyRolePresentsAsAlreadyError,
    AssemblyRolePresentsAsNotPresentError,
    FamilyNotFoundForAssemblyError,
    FixtureAssetFamilyMismatchError,
    FixtureAssetNotAttachableError,
    FixtureAssetNotFoundError,
    FixtureAssetNotInstalledError,
    FixtureMappingIncompleteError,
    FixtureParameterOverridesInvalidError,
    InvalidAssemblyNameError,
    InvalidParameterOverridesSchemaError,
    InvalidSlotCardinalityError,
    InvalidSlotNameError,
    InvalidTemplateSlotError,
    InvalidWireSpecError,
    WireReferencesUnknownSlotError,
)
from cora.equipment.aggregates.asset import (
    AssetAlreadyAttachedToFixtureError,
    AssetAlreadyExistsError,
    AssetAlternateIdentifierAlreadyPresentError,
    AssetAlternateIdentifierNotPresentError,
    AssetAttachedToDifferentFixtureError,
    AssetCannotActivateError,
    AssetCannotAddAlternateIdentifierError,
    AssetCannotAddFamilyError,
    AssetCannotAddOwnerError,
    AssetCannotAddPortError,
    AssetCannotAttachToFixtureError,
    AssetCannotDecommissionError,
    AssetCannotEnterMaintenanceError,
    AssetCannotExitMaintenanceError,
    AssetCannotRelocateError,
    AssetCannotRemoveFamilyError,
    AssetCannotRemovePortError,
    AssetCannotUpdatePartitionRuleError,
    AssetFacilityCodeAlreadyAssignedError,
    AssetFacilityNotFoundError,
    AssetHasFixtureBindingError,
    AssetIsInstalledError,
    AssetModelMismatchError,
    AssetNotAttachedToFixtureError,
    AssetNotBoundInFixtureError,
    AssetNotFoundError,
    AssetOwnerAlreadyPresentError,
    AssetOwnerNotPresentError,
    AssetPersistentIdAlreadyAssignedError,
    AssetPersistentIdAssignmentForbiddenError,
    InvalidAssetNameError,
    InvalidAssetOwnerContactError,
    InvalidAssetOwnerIdentifierError,
    InvalidAssetOwnerIdentifierPairingError,
    InvalidAssetOwnerIdentifierTypeError,
    InvalidAssetOwnerNameError,
    InvalidAssetParentError,
    InvalidAssetPortNameError,
    InvalidAssetPortSignalTypeError,
    InvalidAssetSettingsError,
)
from cora.equipment.aggregates.family import (
    FamilyAlreadyExistsError,
    FamilyCannotDeprecateError,
    FamilyCannotPresentAsError,
    FamilyCannotVersionError,
    FamilyNotFoundError,
    FamilyRolePresentsAsAlreadyError,
    FamilyRolePresentsAsNotPresentError,
    InvalidAffordanceError,
    InvalidFamilyNameError,
    InvalidFamilySettingsSchemaError,
    InvalidFamilyVersionTagError,
)
from cora.equipment.aggregates.fixture import (
    FixtureAlreadyExistsError,
    FixtureNotFoundError,
    FixturePersistentIdAlreadyAssignedError,
    MalformedFixturePersistentIdentifierError,
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
    MountHasFixtureBoundAssetError,
    MountIsEmptyError,
    MountNotFoundError,
)
from cora.equipment.aggregates.role import (
    InvalidRoleDocstringError,
    InvalidRoleNameError,
    InvalidSignalTypeError,
    RoleAffordanceOverlapError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
)
from cora.equipment.errors import (
    AssetNameMissingError,
    FixtureLandingPageMissingError,
    FixtureManufacturerStateNotAvailableError,
    FixtureNameMissingError,
    FixtureOwnerStateNotAvailableError,
    FixturePidinstSerializationError,
    LandingPageMissingError,
    ManufacturerStateNotAvailableError,
    OwnerStateNotAvailableError,
    UnauthorizedError,
    VirtualAxisNotPidinstableError,
)
from cora.equipment.features import (
    activate_asset,
    add_assembly_presents_as,
    add_asset_alternate_identifier,
    add_asset_family,
    add_asset_owner,
    add_asset_port,
    add_family_presents_as,
    add_model_family,
    assign_asset_persistent_id,
    assign_fixture_persistent_id,
    attach_asset_to_fixture,
    bind_asset_to_facility,
    decommission_asset,
    decommission_frame,
    decommission_mount,
    define_assembly,
    define_family,
    define_model,
    define_role,
    degrade_asset,
    deprecate_assembly,
    deprecate_family,
    deprecate_model,
    detach_asset_from_fixture,
    enter_asset_maintenance,
    exit_asset_maintenance,
    fault_asset,
    get_asset,
    get_asset_integration_view,
    get_asset_pidinst,
    get_family,
    get_fixture,
    get_fixture_pidinst,
    get_model,
    install_asset,
    list_assets,
    list_families,
    list_fixtures,
    register_asset,
    register_fixture,
    register_frame,
    register_mount,
    relocate_asset,
    remove_assembly_presents_as,
    remove_asset_alternate_identifier,
    remove_asset_family,
    remove_asset_owner,
    remove_asset_port,
    remove_family_presents_as,
    remove_model_family,
    restore_asset,
    uninstall_asset,
    update_asset_partition_rule,
    update_asset_settings,
    update_family_settings_schema,
    update_frame_placement,
    update_mount_placement,
    version_assembly,
    version_family,
    version_model,
)
from cora.shared.identifier import (
    InvalidAlternateIdentifierValueError,
    InvalidPersistentIdentifierValueError,
    MalformedPersistentIdentifierError,
)
from cora.shared.ports.doi_minter import PersistentIdentifierMintError


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


async def _handle_pidinst_state_not_available(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for PIDINST mandatory-state-missing errors.

    Maps `OwnerStateNotAvailableError` and
    `ManufacturerStateNotAvailableError`: the asset exists but its
    state cannot satisfy the PIDINST emission contract (1-n Owner per
    PIDINST Property 5; Manufacturer required per Property 6). 409 not
    422 because the deficiency is in aggregate state, not in the
    request payload.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_persistent_identifier_mint_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Shared 502 handler for upstream mint-authority failures.

    Maps `PersistentIdentifierMintError`: the external DataCite or
    Handle.net authority failed to assign a persistent identifier
    (HTTP 4xx / 5xx after retry, network failure, credential
    misconfiguration). 502 not 409 because this is upstream-port
    failure, not a domain-state conflict.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(exc)},
    )


async def _handle_malformed_stored_event(request: Request, exc: Exception) -> JSONResponse:
    """500 handler for malformed-stored-event deserialization escapes.

    Maps `MalformedPersistentIdentifierError` (Asset tier) and
    `MalformedFixturePersistentIdentifierError` (Fixture tier): a
    stored `AssetPersistentIdAssigned` or `FixturePersistentIdAssigned`
    payload could not be reconstructed because the
    `persistent_id_value` is empty or non-string. The `from_stored`
    wrap convention normally re-raises as `ValueError` via
    `deserialize_or_raise`, so this handler is defense-in-depth for
    the unwrapped path. 500 because this signals a data-integrity bug
    in the event store, not a client error.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


async def _handle_pidinst_serialization_error(request: Request, exc: Exception) -> JSONResponse:
    """500 backstop for unmapped Fixture-tier PIDINST serializer errors.

    The four concrete `FixturePidinstSerializationError` subclasses get
    pinned to 409 / 422 via their own tuple registrations above; this
    handler catches the base class itself plus any future subclass that
    has not yet received an explicit mapping. The choice of 500 mirrors
    the slice E.1 backstop reasoning: an unmapped serializer failure
    signals a server-side gap, not a client error.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


async def _handle_pidinst_view_preparation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 422 handler for PIDINST view-preparation deficiencies.

    Maps `LandingPageMissingError` and `AssetNameMissingError`. The
    view itself failed serializer preconditions despite passing
    aggregate construction, so the source is the view assembler's
    input handling.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


def register_equipment_routes(app: FastAPI) -> None:
    """Attach Equipment slice routers and exception handlers to the FastAPI app."""
    # Family aggregate
    app.include_router(define_family.router)
    app.include_router(version_family.router)
    app.include_router(deprecate_family.router)
    app.include_router(update_family_settings_schema.router)
    app.include_router(get_family.router)
    app.include_router(list_families.router)
    app.include_router(add_family_presents_as.router)
    app.include_router(remove_family_presents_as.router)
    # Role aggregate
    app.include_router(define_role.router)
    # Model aggregate
    app.include_router(define_model.router)
    app.include_router(version_model.router)
    app.include_router(deprecate_model.router)
    app.include_router(add_model_family.router)
    app.include_router(remove_model_family.router)
    app.include_router(get_model.router)
    # Asset aggregate
    app.include_router(register_asset.router)
    app.include_router(activate_asset.router)
    app.include_router(decommission_asset.router)
    app.include_router(relocate_asset.router)
    app.include_router(enter_asset_maintenance.router)
    app.include_router(exit_asset_maintenance.router)
    app.include_router(add_asset_family.router)
    app.include_router(remove_asset_family.router)
    app.include_router(degrade_asset.router)
    app.include_router(fault_asset.router)
    app.include_router(restore_asset.router)
    app.include_router(update_asset_settings.router)
    app.include_router(update_asset_partition_rule.router)
    app.include_router(add_asset_port.router)
    app.include_router(remove_asset_port.router)
    app.include_router(add_asset_alternate_identifier.router)
    app.include_router(remove_asset_alternate_identifier.router)
    app.include_router(add_asset_owner.router)
    app.include_router(remove_asset_owner.router)
    app.include_router(assign_asset_persistent_id.router)
    app.include_router(get_asset.router)
    app.include_router(get_asset_integration_view.router)
    app.include_router(get_asset_pidinst.router)
    app.include_router(list_assets.router)
    # Frame aggregate
    app.include_router(register_frame.router)
    app.include_router(update_frame_placement.router)
    app.include_router(decommission_frame.router)
    # Mount aggregate
    app.include_router(register_mount.router)
    app.include_router(update_mount_placement.router)
    app.include_router(decommission_mount.router)
    app.include_router(install_asset.router)
    app.include_router(uninstall_asset.router)
    app.include_router(define_assembly.router)
    app.include_router(version_assembly.router)
    app.include_router(deprecate_assembly.router)
    app.include_router(add_assembly_presents_as.router)
    app.include_router(remove_assembly_presents_as.router)
    app.include_router(register_fixture.router)
    app.include_router(attach_asset_to_fixture.router)
    app.include_router(bind_asset_to_facility.router)
    app.include_router(detach_asset_from_fixture.router)
    app.include_router(assign_fixture_persistent_id.router)
    app.include_router(get_fixture.router)
    app.include_router(get_fixture_pidinst.router)
    app.include_router(list_fixtures.router)
    for validation_cls in (
        InvalidAffordanceError,
        InvalidFamilyNameError,
        InvalidFamilySettingsSchemaError,
        InvalidFamilyVersionTagError,
        InvalidRoleNameError,
        InvalidRoleDocstringError,
        InvalidSignalTypeError,
        RoleAffordanceOverlapError,
        InvalidAssetNameError,
        InvalidAssetParentError,
        InvalidAssetPortNameError,
        InvalidAssetPortSignalTypeError,
        InvalidAssetSettingsError,
        InvalidAlternateIdentifierValueError,
        InvalidAssetOwnerNameError,
        InvalidAssetOwnerContactError,
        InvalidAssetOwnerIdentifierError,
        InvalidAssetOwnerIdentifierTypeError,
        InvalidAssetOwnerIdentifierPairingError,
        InvalidPersistentIdentifierValueError,
        InvalidFrameNameError,
        InvalidFrameRevisionError,
        InvalidFrameRootError,
        InvalidPlacementError,
        InvalidDrawingError,
        InvalidPartitionRuleError,
        InvalidSlotCodeError,
        InvalidModelNameError,
        InvalidPartNumberError,
        InvalidManufacturerNameError,
        InvalidManufacturerIdentifierError,
        InvalidManufacturerIdentifierPairingError,
        InvalidModelVersionTagError,
        InvalidModelDeprecationReasonError,
        InvalidDeclaredFamiliesError,
        InvalidAssemblyNameError,
        InvalidSlotNameError,
        InvalidSlotCardinalityError,
        InvalidTemplateSlotError,
        InvalidWireSpecError,
        WireReferencesUnknownSlotError,
        InvalidParameterOverridesSchemaError,
        FixtureMappingIncompleteError,
        FixtureAssetFamilyMismatchError,
        FixtureParameterOverridesInvalidError,
        AssetNotBoundInFixtureError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        FamilyNotFoundError,
        RoleNotFoundError,
        AssetNotFoundError,
        AssetOwnerNotPresentError,
        AssetFacilityNotFoundError,
        FrameNotFoundError,
        MountNotFoundError,
        AssetNotFoundForMountError,
        ModelNotFoundError,
        AssemblyNotFoundError,
        FamilyNotFoundForAssemblyError,
        FixtureAssetNotFoundError,
        FixtureNotFoundError,
        VirtualAxisNotPidinstableError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        FamilyAlreadyExistsError,
        RoleAlreadyExistsError,
        AssetAlreadyExistsError,
        FrameAlreadyExistsError,
        MountAlreadyExistsError,
        ModelAlreadyExistsError,
        AssemblyAlreadyExistsError,
        FixtureAlreadyExistsError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        AssetCannotActivateError,
        AssetCannotDecommissionError,
        AssetHasFixtureBindingError,
        AssetIsInstalledError,
        AssetCannotRelocateError,
        AssetCannotEnterMaintenanceError,
        AssetCannotExitMaintenanceError,
        AssetCannotAddFamilyError,
        AssetCannotRemoveFamilyError,
        AssetCannotAddPortError,
        AssetCannotRemovePortError,
        AssetAlternateIdentifierAlreadyPresentError,
        AssetAlternateIdentifierNotPresentError,
        AssetCannotAddAlternateIdentifierError,
        AssetOwnerAlreadyPresentError,
        AssetCannotAddOwnerError,
        AssetFacilityCodeAlreadyAssignedError,
        AssetPersistentIdAlreadyAssignedError,
        AssetPersistentIdAssignmentForbiddenError,
        FixturePersistentIdAlreadyAssignedError,
        AssetModelMismatchError,
        FamilyCannotVersionError,
        FamilyCannotDeprecateError,
        FamilyCannotPresentAsError,
        FamilyRolePresentsAsAlreadyError,
        FamilyRolePresentsAsNotPresentError,
        FrameCannotUpdateError,
        FrameCannotDecommissionError,
        FrameCannotSupersedeError,
        FrameInUseError,
        MountCannotUpdateError,
        MountCannotDecommissionError,
        MountHasAssetInstalledError,
        MountHasActiveChildrenError,
        MountHasFixtureBoundAssetError,
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
        AssemblyCannotVersionError,
        AssemblyCannotDeprecateError,
        AssemblyRolePresentsAsAlreadyError,
        AssemblyRolePresentsAsNotPresentError,
        AssemblyCannotInstantiateError,
        AssetAlreadyAttachedToFixtureError,
        AssetCannotAttachToFixtureError,
        AssetNotAttachedToFixtureError,
        AssetAttachedToDifferentFixtureError,
        AssetCannotUpdatePartitionRuleError,
        FixtureAssetNotAttachableError,
        FixtureAssetNotInstalledError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    for pidinst_state_cls in (
        OwnerStateNotAvailableError,
        ManufacturerStateNotAvailableError,
        FixtureOwnerStateNotAvailableError,
        FixtureManufacturerStateNotAvailableError,
    ):
        app.add_exception_handler(pidinst_state_cls, _handle_pidinst_state_not_available)
    for pidinst_view_cls in (
        LandingPageMissingError,
        AssetNameMissingError,
        FixtureLandingPageMissingError,
        FixtureNameMissingError,
    ):
        app.add_exception_handler(pidinst_view_cls, _handle_pidinst_view_preparation_error)
    app.add_exception_handler(FixturePidinstSerializationError, _handle_pidinst_serialization_error)
    app.add_exception_handler(
        PersistentIdentifierMintError, _handle_persistent_identifier_mint_error
    )
    app.add_exception_handler(MalformedPersistentIdentifierError, _handle_malformed_stored_event)
    app.add_exception_handler(
        MalformedFixturePersistentIdentifierError, _handle_malformed_stored_event
    )
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
