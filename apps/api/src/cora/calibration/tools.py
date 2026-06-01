"""MCP tool registration for the Calibration BC.

`register_calibration_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `CalibrationHandlers` bundle wired during the
FastAPI lifespan; it's invoked per tool call so the latest wiring is
always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.calibration.features.append_calibration_revision import (
    tool as append_calibration_revision_tool,
)
from cora.calibration.features.define_calibration import tool as define_calibration_tool
from cora.calibration.features.get_calibration import tool as get_calibration_tool
from cora.calibration.features.list_calibrations import tool as list_calibrations_tool
from cora.calibration.features.publish_revision import tool as publish_revision_tool
from cora.calibration.wire import CalibrationHandlers


def register_calibration_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], CalibrationHandlers],
) -> None:
    """Register every Calibration slice's MCP tool on the FastMCP server."""
    define_calibration_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_calibration,
    )
    append_calibration_revision_tool.register(
        mcp,
        get_handler=lambda: get_handlers().append_calibration_revision,
    )
    publish_revision_tool.register(
        mcp,
        get_handler=lambda: get_handlers().publish_revision,
    )
    get_calibration_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_calibration,
    )
    list_calibrations_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_calibrations,
    )
