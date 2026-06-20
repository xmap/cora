"""MCP tool registration for the Recipe BC.

`register_recipe_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `RecipeHandlers` bundle wired during the
FastAPI lifespan; it's invoked per tool call so the latest wiring
is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.recipe.features.add_method_required_role import (
    tool as add_method_required_role_tool,
)
from cora.recipe.features.add_plan_wire import tool as add_plan_wire_tool
from cora.recipe.features.bind_plan_role import tool as bind_plan_role_tool
from cora.recipe.features.define_capability import tool as define_capability_tool
from cora.recipe.features.define_method import tool as define_method_tool
from cora.recipe.features.define_plan import tool as define_plan_tool
from cora.recipe.features.define_practice import tool as define_practice_tool
from cora.recipe.features.define_recipe import tool as define_recipe_tool
from cora.recipe.features.deprecate_capability import tool as deprecate_capability_tool
from cora.recipe.features.deprecate_method import tool as deprecate_method_tool
from cora.recipe.features.deprecate_plan import tool as deprecate_plan_tool
from cora.recipe.features.deprecate_practice import tool as deprecate_practice_tool
from cora.recipe.features.deprecate_recipe import tool as deprecate_recipe_tool
from cora.recipe.features.get_capability import tool as get_capability_tool
from cora.recipe.features.get_method import tool as get_method_tool
from cora.recipe.features.get_plan import tool as get_plan_tool
from cora.recipe.features.get_practice import tool as get_practice_tool
from cora.recipe.features.get_recipe import tool as get_recipe_tool
from cora.recipe.features.inspect_plan_binding import tool as inspect_plan_binding_tool
from cora.recipe.features.list_methods import tool as list_methods_tool
from cora.recipe.features.list_plans import tool as list_plans_tool
from cora.recipe.features.list_practices import tool as list_practices_tool
from cora.recipe.features.remove_method_required_role import (
    tool as remove_method_required_role_tool,
)
from cora.recipe.features.remove_plan_wire import tool as remove_plan_wire_tool
from cora.recipe.features.unbind_plan_role import tool as unbind_plan_role_tool
from cora.recipe.features.update_capability_suggested_roles import (
    tool as update_capability_suggested_roles_tool,
)
from cora.recipe.features.update_method_launch_spec import (
    tool as update_method_launch_spec_tool,
)
from cora.recipe.features.update_method_parameters_schema import (
    tool as update_method_parameters_schema_tool,
)
from cora.recipe.features.update_plan_default_parameters import (
    tool as update_plan_default_parameters_tool,
)
from cora.recipe.features.version_capability import tool as version_capability_tool
from cora.recipe.features.version_method import tool as version_method_tool
from cora.recipe.features.version_plan import tool as version_plan_tool
from cora.recipe.features.version_practice import tool as version_practice_tool
from cora.recipe.features.version_recipe import tool as version_recipe_tool
from cora.recipe.wire import RecipeHandlers


def register_recipe_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], RecipeHandlers],
) -> None:
    """Register every Recipe slice's MCP tool on the FastMCP server."""
    define_method_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_method,
    )
    get_method_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_method,
    )
    version_method_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_method,
    )
    deprecate_method_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_method,
    )
    update_method_parameters_schema_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_method_parameters_schema,
    )
    update_method_launch_spec_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_method_launch_spec,
    )
    add_method_required_role_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_method_required_role,
    )
    remove_method_required_role_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_method_required_role,
    )
    define_practice_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_practice,
    )
    get_practice_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_practice,
    )
    version_practice_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_practice,
    )
    deprecate_practice_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_practice,
    )
    define_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_plan,
    )
    get_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_plan,
    )
    version_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_plan,
    )
    deprecate_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_plan,
    )
    update_plan_default_parameters_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_plan_default_parameters,
    )
    add_plan_wire_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_plan_wire,
    )
    remove_plan_wire_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_plan_wire,
    )
    bind_plan_role_tool.register(
        mcp,
        get_handler=lambda: get_handlers().bind_plan_role,
    )
    unbind_plan_role_tool.register(
        mcp,
        get_handler=lambda: get_handlers().unbind_plan_role,
    )
    list_methods_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_methods,
    )
    list_practices_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_practices,
    )
    list_plans_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_plans,
    )
    define_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_capability,
    )
    version_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_capability,
    )
    deprecate_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_capability,
    )
    update_capability_suggested_roles_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_capability_suggested_roles,
    )
    get_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_capability,
    )
    define_recipe_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_recipe,
    )
    version_recipe_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_recipe,
    )
    deprecate_recipe_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_recipe,
    )
    get_recipe_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_recipe,
    )
    inspect_plan_binding_tool.register(
        mcp,
        get_handler=lambda: get_handlers().inspect_plan_binding,
    )
