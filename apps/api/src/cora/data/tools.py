"""MCP tool registration for the Data BC.

`register_data_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `DataHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is always
used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.data.features.add_dataset_to_edition import tool as add_dataset_to_edition_tool
from cora.data.features.demote_dataset import tool as demote_dataset_tool
from cora.data.features.discard_dataset import tool as discard_dataset_tool
from cora.data.features.get_dataset import tool as get_dataset_tool
from cora.data.features.list_datasets import tool as list_datasets_tool
from cora.data.features.promote_dataset import tool as promote_dataset_tool
from cora.data.features.publish_edition import tool as publish_edition_tool
from cora.data.features.record_acquisition import tool as record_acquisition_tool
from cora.data.features.record_attestation import tool as record_attestation_tool
from cora.data.features.register_dataset import tool as register_dataset_tool
from cora.data.features.register_distribution import tool as register_distribution_tool
from cora.data.features.register_edition import tool as register_edition_tool
from cora.data.features.remove_dataset_from_edition import (
    tool as remove_dataset_from_edition_tool,
)
from cora.data.features.seal_edition import tool as seal_edition_tool
from cora.data.features.withdraw_edition import tool as withdraw_edition_tool
from cora.data.wire import DataHandlers


def register_data_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], DataHandlers],
) -> None:
    """Register every Data slice's MCP tool on the FastMCP server."""
    register_dataset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_dataset,
    )
    discard_dataset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().discard_dataset,
    )
    promote_dataset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().promote_dataset,
    )
    demote_dataset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().demote_dataset,
    )
    get_dataset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_dataset,
    )
    list_datasets_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_datasets,
    )
    record_acquisition_tool.register(
        mcp,
        get_handler=lambda: get_handlers().record_acquisition,
    )
    register_distribution_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_distribution,
    )
    register_edition_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_edition,
    )
    add_dataset_to_edition_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_dataset_to_edition,
    )
    remove_dataset_from_edition_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_dataset_from_edition,
    )
    seal_edition_tool.register(
        mcp,
        get_handler=lambda: get_handlers().seal_edition,
    )
    publish_edition_tool.register(
        mcp,
        get_handler=lambda: get_handlers().publish_edition,
    )
    withdraw_edition_tool.register(
        mcp,
        get_handler=lambda: get_handlers().withdraw_edition,
    )
    record_attestation_tool.register(
        mcp,
        get_handler=lambda: get_handlers().record_attestation,
    )
