"""Compose the Equipment BC's handlers from `Kernel`.

`wire_equipment(deps)` is invoked once from the FastAPI lifespan
and the returned `EquipmentHandlers` bundle is stored on
`app.state.equipment`. Routes and MCP tools pull their handler out
of that bundle. New slices (commands or queries) add a new field
on `EquipmentHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject (composition order matters, innermost first):

1. `bind(deps)` bare handler.
2. `with_idempotency` (create-style commands only) Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing` OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

Update-style transitions are not idempotency-wrapped: they're
domain-idempotent via `AssetCannot<X>Error` on retry (same precedent
as Subject's transitions). Queries skip idempotency.

The per-aggregate `make_asset_update_handler` factory (see
`cora.equipment._asset_update_handler`) absorbs the byte-identical
Asset transitions; `relocate_asset` stays longhand because its
event payload carries an extra `to_parent_id` field. A future
`make_capability_update_handler` would be a sibling for Family
lifecycle slices.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.features import (
    activate_asset,
    add_asset_alternate_identifier,
    add_asset_family,
    add_asset_port,
    add_model_family,
    decommission_asset,
    decommission_frame,
    decommission_mount,
    define_assembly,
    define_family,
    define_model,
    degrade_asset,
    deprecate_family,
    deprecate_model,
    enter_asset_maintenance,
    exit_asset_maintenance,
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
    remove_asset_alternate_identifier,
    remove_asset_family,
    remove_asset_port,
    remove_model_family,
    restore_asset,
    uninstall_asset,
    update_asset_settings,
    update_family_settings_schema,
    update_frame_placement,
    update_mount_placement,
    version_assembly,
    version_family,
    version_model,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "equipment"


@dataclass(frozen=True)
class EquipmentHandlers:
    """The Equipment BC's handler bundle, each closed over Kernel.

    Five aggregates:

    - `Family`: technique-class catalog (lifecycle Defined,
      Versioned, Deprecated) declaring Affordances + settings schema.
    - `Model`: manufacturer-specific catalog entry under one or more
      Families (lifecycle Defined, Versioned, Deprecated).
    - `Asset`: physical or logical instance with hierarchy, lifecycle,
      family-set, condition, settings, and typed ports.
    - `Frame`: spatial reference frame anchored to a root surface with
      a 6-DoF Placement.
    - `Mount`: a slot on a Frame that can receive at most one Asset
      via install / uninstall.

    Genesis commands (`define_family`, `define_model`, `register_asset`,
    `register_frame`, `register_mount`) are idempotency-wrapped;
    everything else is update-style with bare Handler protocols.
    """

    # Family aggregate
    define_family: define_family.IdempotentHandler
    version_family: version_family.Handler
    deprecate_family: deprecate_family.Handler
    update_family_settings_schema: update_family_settings_schema.Handler
    get_family: get_family.Handler
    list_families: list_families.Handler

    # Model aggregate
    define_model: define_model.IdempotentHandler
    version_model: version_model.Handler
    deprecate_model: deprecate_model.Handler
    add_model_family: add_model_family.Handler
    remove_model_family: remove_model_family.Handler
    get_model: get_model.Handler

    # Asset aggregate
    register_asset: register_asset.IdempotentHandler
    activate_asset: activate_asset.Handler
    decommission_asset: decommission_asset.Handler
    relocate_asset: relocate_asset.Handler
    enter_asset_maintenance: enter_asset_maintenance.Handler
    exit_asset_maintenance: exit_asset_maintenance.Handler
    add_asset_family: add_asset_family.Handler
    remove_asset_family: remove_asset_family.Handler
    degrade_asset: degrade_asset.Handler
    fault_asset: fault_asset.Handler
    restore_asset: restore_asset.Handler
    update_asset_settings: update_asset_settings.Handler
    add_asset_port: add_asset_port.Handler
    remove_asset_port: remove_asset_port.Handler
    add_asset_alternate_identifier: add_asset_alternate_identifier.Handler
    remove_asset_alternate_identifier: remove_asset_alternate_identifier.Handler
    get_asset: get_asset.Handler
    get_asset_integration_view: get_asset_integration_view.Handler
    list_assets: list_assets.Handler

    # Frame aggregate
    register_frame: register_frame.IdempotentHandler
    update_frame_placement: update_frame_placement.Handler
    decommission_frame: decommission_frame.Handler

    # Mount aggregate
    register_mount: register_mount.IdempotentHandler
    update_mount_placement: update_mount_placement.Handler
    decommission_mount: decommission_mount.Handler
    install_asset: install_asset.Handler
    uninstall_asset: uninstall_asset.Handler
    define_assembly: define_assembly.IdempotentHandler
    version_assembly: version_assembly.Handler


def wire_equipment(deps: Kernel) -> EquipmentHandlers:
    """Build the Equipment BC handlers from shared dependencies."""
    return EquipmentHandlers(
        # Family aggregate
        define_family=with_tracing(
            with_idempotency(
                define_family.bind(deps),
                deps.idempotency_store,
                command_name="DefineFamily",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineFamily",
            bc=_BC,
        ),
        version_family=with_tracing(
            version_family.bind(deps),
            command_name="VersionFamily",
            bc=_BC,
        ),
        deprecate_family=with_tracing(
            deprecate_family.bind(deps),
            command_name="DeprecateFamily",
            bc=_BC,
        ),
        update_family_settings_schema=with_tracing(
            update_family_settings_schema.bind(deps),
            command_name="UpdateFamilySettingsSchema",
            bc=_BC,
        ),
        get_family=with_tracing(
            get_family.bind(deps),
            command_name="GetFamily",
            bc=_BC,
            kind="query",
        ),
        list_families=with_tracing(
            list_families.bind(deps),
            command_name="ListFamilies",
            bc=_BC,
            kind="query",
        ),
        # Model aggregate
        define_model=with_tracing(
            with_idempotency(
                define_model.bind(deps),
                deps.idempotency_store,
                command_name="DefineModel",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineModel",
            bc=_BC,
        ),
        version_model=with_tracing(
            version_model.bind(deps),
            command_name="VersionModel",
            bc=_BC,
        ),
        deprecate_model=with_tracing(
            deprecate_model.bind(deps),
            command_name="DeprecateModel",
            bc=_BC,
        ),
        add_model_family=with_tracing(
            add_model_family.bind(deps),
            command_name="AddModelFamily",
            bc=_BC,
        ),
        remove_model_family=with_tracing(
            remove_model_family.bind(deps),
            command_name="RemoveModelFamily",
            bc=_BC,
        ),
        get_model=with_tracing(
            get_model.bind(deps),
            command_name="GetModel",
            bc=_BC,
            kind="query",
        ),
        # Asset aggregate
        register_asset=with_tracing(
            with_idempotency(
                register_asset.bind(deps),
                deps.idempotency_store,
                command_name="RegisterAsset",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterAsset",
            bc=_BC,
        ),
        activate_asset=with_tracing(
            activate_asset.bind(deps),
            command_name="ActivateAsset",
            bc=_BC,
        ),
        decommission_asset=with_tracing(
            decommission_asset.bind(deps),
            command_name="DecommissionAsset",
            bc=_BC,
        ),
        relocate_asset=with_tracing(
            relocate_asset.bind(deps),
            command_name="RelocateAsset",
            bc=_BC,
        ),
        enter_asset_maintenance=with_tracing(
            enter_asset_maintenance.bind(deps),
            command_name="EnterAssetMaintenance",
            bc=_BC,
        ),
        exit_asset_maintenance=with_tracing(
            exit_asset_maintenance.bind(deps),
            command_name="ExitAssetMaintenance",
            bc=_BC,
        ),
        add_asset_family=with_tracing(
            add_asset_family.bind(deps),
            command_name="AddAssetFamily",
            bc=_BC,
        ),
        remove_asset_family=with_tracing(
            remove_asset_family.bind(deps),
            command_name="RemoveAssetFamily",
            bc=_BC,
        ),
        degrade_asset=with_tracing(
            degrade_asset.bind(deps),
            command_name="DegradeAsset",
            bc=_BC,
        ),
        fault_asset=with_tracing(
            fault_asset.bind(deps),
            command_name="FaultAsset",
            bc=_BC,
        ),
        restore_asset=with_tracing(
            restore_asset.bind(deps),
            command_name="RestoreAsset",
            bc=_BC,
        ),
        update_asset_settings=with_tracing(
            update_asset_settings.bind(deps),
            command_name="UpdateAssetSettings",
            bc=_BC,
        ),
        add_asset_port=with_tracing(
            add_asset_port.bind(deps),
            command_name="AddAssetPort",
            bc=_BC,
        ),
        remove_asset_port=with_tracing(
            remove_asset_port.bind(deps),
            command_name="RemoveAssetPort",
            bc=_BC,
        ),
        add_asset_alternate_identifier=with_tracing(
            add_asset_alternate_identifier.bind(deps),
            command_name="AddAssetAlternateIdentifier",
            bc=_BC,
        ),
        remove_asset_alternate_identifier=with_tracing(
            remove_asset_alternate_identifier.bind(deps),
            command_name="RemoveAssetAlternateIdentifier",
            bc=_BC,
        ),
        get_asset=with_tracing(
            get_asset.bind(deps),
            command_name="GetAsset",
            bc=_BC,
            kind="query",
        ),
        get_asset_integration_view=with_tracing(
            get_asset_integration_view.bind(deps),
            command_name="GetAssetIntegrationView",
            bc=_BC,
            kind="query",
        ),
        list_assets=with_tracing(
            list_assets.bind(deps),
            command_name="ListAssets",
            bc=_BC,
            kind="query",
        ),
        # Frame aggregate
        register_frame=with_tracing(
            with_idempotency(
                register_frame.bind(deps),
                deps.idempotency_store,
                command_name="RegisterFrame",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterFrame",
            bc=_BC,
        ),
        update_frame_placement=with_tracing(
            update_frame_placement.bind(deps),
            command_name="UpdateFramePlacement",
            bc=_BC,
        ),
        decommission_frame=with_tracing(
            decommission_frame.bind(deps),
            command_name="DecommissionFrame",
            bc=_BC,
        ),
        # Mount aggregate
        register_mount=with_tracing(
            with_idempotency(
                register_mount.bind(deps),
                deps.idempotency_store,
                command_name="RegisterMount",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterMount",
            bc=_BC,
        ),
        update_mount_placement=with_tracing(
            update_mount_placement.bind(deps),
            command_name="UpdateMountPlacement",
            bc=_BC,
        ),
        decommission_mount=with_tracing(
            decommission_mount.bind(deps),
            command_name="DecommissionMount",
            bc=_BC,
        ),
        install_asset=with_tracing(
            install_asset.bind(deps),
            command_name="InstallAsset",
            bc=_BC,
        ),
        uninstall_asset=with_tracing(
            uninstall_asset.bind(deps),
            command_name="UninstallAsset",
            bc=_BC,
        ),
        define_assembly=with_tracing(
            with_idempotency(
                define_assembly.bind(deps),
                deps.idempotency_store,
                command_name="DefineAssembly",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineAssembly",
            bc=_BC,
        ),
        version_assembly=with_tracing(
            version_assembly.bind(deps),
            command_name="VersionAssembly",
            bc=_BC,
        ),
    )
