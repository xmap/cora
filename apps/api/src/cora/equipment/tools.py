"""MCP tool registration for the Equipment BC.

`register_equipment_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `EquipmentHandlers` bundle wired during the
FastAPI lifespan; it's invoked per tool call so the latest wiring
is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.equipment.features.activate_asset import tool as activate_asset_tool
from cora.equipment.features.add_asset_alternate_identifier import (
    tool as add_asset_alternate_identifier_tool,
)
from cora.equipment.features.add_asset_family import (
    tool as add_asset_family_tool,
)
from cora.equipment.features.add_asset_owner import tool as add_asset_owner_tool
from cora.equipment.features.add_asset_port import tool as add_asset_port_tool
from cora.equipment.features.add_model_family import tool as add_model_family_tool
from cora.equipment.features.assign_asset_persistent_id import (
    tool as assign_asset_persistent_id_tool,
)
from cora.equipment.features.assign_fixture_persistent_id import (
    tool as assign_fixture_persistent_id_tool,
)
from cora.equipment.features.attach_asset_to_fixture import tool as attach_asset_to_fixture_tool
from cora.equipment.features.decommission_asset import tool as decommission_asset_tool
from cora.equipment.features.decommission_frame import tool as decommission_frame_tool
from cora.equipment.features.decommission_mount import tool as decommission_mount_tool
from cora.equipment.features.define_assembly import tool as define_assembly_tool
from cora.equipment.features.define_family import tool as define_family_tool
from cora.equipment.features.define_model import tool as define_model_tool
from cora.equipment.features.degrade_asset import tool as degrade_asset_tool
from cora.equipment.features.deprecate_assembly import tool as deprecate_assembly_tool
from cora.equipment.features.deprecate_family import (
    tool as deprecate_family_tool,
)
from cora.equipment.features.deprecate_model import tool as deprecate_model_tool
from cora.equipment.features.detach_asset_from_fixture import (
    tool as detach_asset_from_fixture_tool,
)
from cora.equipment.features.enter_asset_maintenance import tool as enter_asset_maintenance_tool
from cora.equipment.features.exit_asset_maintenance import (
    tool as exit_asset_maintenance_tool,
)
from cora.equipment.features.fault_asset import tool as fault_asset_tool
from cora.equipment.features.get_asset import tool as get_asset_tool
from cora.equipment.features.get_asset_integration_view import (
    tool as get_asset_integration_view_tool,
)
from cora.equipment.features.get_asset_pidinst import tool as get_asset_pidinst_tool
from cora.equipment.features.get_family import tool as get_family_tool
from cora.equipment.features.get_fixture import tool as get_fixture_tool
from cora.equipment.features.get_fixture_pidinst import tool as get_fixture_pidinst_tool
from cora.equipment.features.get_model import tool as get_model_tool
from cora.equipment.features.install_asset import tool as install_asset_tool
from cora.equipment.features.list_assets import tool as list_assets_tool
from cora.equipment.features.list_families import tool as list_families_tool
from cora.equipment.features.list_fixtures import tool as list_fixtures_tool
from cora.equipment.features.register_asset import tool as register_asset_tool
from cora.equipment.features.register_fixture import tool as register_fixture_tool
from cora.equipment.features.register_frame import tool as register_frame_tool
from cora.equipment.features.register_mount import tool as register_mount_tool
from cora.equipment.features.relocate_asset import tool as relocate_asset_tool
from cora.equipment.features.remove_asset_alternate_identifier import (
    tool as remove_asset_alternate_identifier_tool,
)
from cora.equipment.features.remove_asset_family import (
    tool as remove_asset_family_tool,
)
from cora.equipment.features.remove_asset_owner import tool as remove_asset_owner_tool
from cora.equipment.features.remove_asset_port import tool as remove_asset_port_tool
from cora.equipment.features.remove_model_family import tool as remove_model_family_tool
from cora.equipment.features.restore_asset import tool as restore_asset_tool
from cora.equipment.features.uninstall_asset import tool as uninstall_asset_tool
from cora.equipment.features.update_asset_partition_rule import (
    tool as update_asset_partition_rule_tool,
)
from cora.equipment.features.update_asset_settings import (
    tool as update_asset_settings_tool,
)
from cora.equipment.features.update_family_settings_schema import (
    tool as update_family_settings_schema_tool,
)
from cora.equipment.features.update_frame_placement import tool as update_frame_placement_tool
from cora.equipment.features.update_mount_placement import tool as update_mount_placement_tool
from cora.equipment.features.version_assembly import tool as version_assembly_tool
from cora.equipment.features.version_family import tool as version_family_tool
from cora.equipment.features.version_model import tool as version_model_tool
from cora.equipment.wire import EquipmentHandlers


def register_equipment_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], EquipmentHandlers],
) -> None:
    """Register every Equipment slice's MCP tool on the FastMCP server."""
    # Family aggregate
    define_family_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_family,
    )
    version_family_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_family,
    )
    deprecate_family_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_family,
    )
    update_family_settings_schema_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_family_settings_schema,
    )
    get_family_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_family,
    )
    list_families_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_families,
    )
    # Model aggregate
    define_model_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_model,
    )
    version_model_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_model,
    )
    deprecate_model_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_model,
    )
    add_model_family_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_model_family,
    )
    remove_model_family_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_model_family,
    )
    get_model_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_model,
    )
    # Asset aggregate
    register_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_asset,
    )
    activate_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().activate_asset,
    )
    decommission_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().decommission_asset,
    )
    relocate_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().relocate_asset,
    )
    enter_asset_maintenance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().enter_asset_maintenance,
    )
    exit_asset_maintenance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().exit_asset_maintenance,
    )
    add_asset_family_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_asset_family,
    )
    remove_asset_family_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_asset_family,
    )
    degrade_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().degrade_asset,
    )
    fault_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().fault_asset,
    )
    restore_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().restore_asset,
    )
    update_asset_settings_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_asset_settings,
    )
    update_asset_partition_rule_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_asset_partition_rule,
    )
    add_asset_port_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_asset_port,
    )
    remove_asset_port_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_asset_port,
    )
    add_asset_alternate_identifier_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_asset_alternate_identifier,
    )
    remove_asset_alternate_identifier_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_asset_alternate_identifier,
    )
    add_asset_owner_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_asset_owner,
    )
    remove_asset_owner_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_asset_owner,
    )
    assign_asset_persistent_id_tool.register(
        mcp,
        get_handler=lambda: get_handlers().assign_asset_persistent_id,
    )
    get_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_asset,
    )
    get_asset_integration_view_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_asset_integration_view,
    )
    get_asset_pidinst_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_asset_pidinst,
    )
    list_assets_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_assets,
    )
    # Frame aggregate
    register_frame_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_frame,
    )
    update_frame_placement_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_frame_placement,
    )
    decommission_frame_tool.register(
        mcp,
        get_handler=lambda: get_handlers().decommission_frame,
    )
    # Mount aggregate
    register_mount_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_mount,
    )
    update_mount_placement_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_mount_placement,
    )
    decommission_mount_tool.register(
        mcp,
        get_handler=lambda: get_handlers().decommission_mount,
    )
    install_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().install_asset,
    )
    uninstall_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().uninstall_asset,
    )
    define_assembly_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_assembly,
    )
    version_assembly_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_assembly,
    )
    deprecate_assembly_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_assembly,
    )
    register_fixture_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_fixture,
    )
    attach_asset_to_fixture_tool.register(
        mcp,
        get_handler=lambda: get_handlers().attach_asset_to_fixture,
    )
    detach_asset_from_fixture_tool.register(
        mcp,
        get_handler=lambda: get_handlers().detach_asset_from_fixture,
    )
    assign_fixture_persistent_id_tool.register(
        mcp,
        get_handler=lambda: get_handlers().assign_fixture_persistent_id,
    )
    get_fixture_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_fixture,
    )
    get_fixture_pidinst_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_fixture_pidinst,
    )
    list_fixtures_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_fixtures,
    )
