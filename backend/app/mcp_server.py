"""MCP server exposing the agent's typed tools to any MCP client, over stdio.

    KUZOT_MCP_WORKSPACE_ID=<uuid> python -m app.mcp_server

There is no user login here. Whoever can start this process already holds the
database credentials, so access is decided by who runs it. The workspace comes
from the environment and tool arguments can't change it.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agent.data import ToolContext, load_context
from app.agent.tools import (
    TOOLS,
    ComparePricingInput,
    ComparePricingOutput,
    PageHistoryInput,
    PageHistoryOutput,
    SearchChangesInput,
    SearchChangesOutput,
    ToolError,
    compare_pricing,
    get_page_history,
    search_changes,
)
from app.core.config import settings
from app.core.tracing import setup_tracing
from app.db.mongo import close_mongo_connection, connect_to_mongo, get_mongo_db
from app.models import Workspace

# Not the app's engine: in dev that one echoes SQL to stdout, which is this
# server's protocol channel.
_engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
_sessions = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def _workspace_id() -> UUID:
    value = os.environ.get("KUZOT_MCP_WORKSPACE_ID")
    if not value:
        raise RuntimeError("Set KUZOT_MCP_WORKSPACE_ID to the workspace to serve")
    return UUID(value)


async def _context() -> ToolContext:
    # per call, so a competitor added while the server runs is visible at once
    async with _sessions() as db:
        workspace = await db.get(Workspace, _workspace_id())
        if workspace is None:
            raise RuntimeError("KUZOT_MCP_WORKSPACE_ID is not an existing workspace")
        return await load_context(db, get_mongo_db(), workspace)


@asynccontextmanager
async def _client_errors() -> AsyncIterator[None]:
    # MCP hides unexpected errors from clients; these say how to fix the request
    try:
        yield
    except ToolError as exc:
        raise MCPToolError(str(exc)) from exc


@asynccontextmanager
async def _lifespan(_: MCPServer) -> AsyncIterator[None]:
    setup_tracing("kuzot-mcp")
    await connect_to_mongo()
    try:
        yield
    finally:
        await close_mongo_connection()
        await _engine.dispose()


mcp = MCPServer("kuzot", lifespan=_lifespan)


@mcp.tool(name="search_changes", description=TOOLS["search_changes"].description)
async def search_changes_tool(params: SearchChangesInput) -> SearchChangesOutput:
    async with _client_errors():
        return await search_changes(await _context(), params)


@mcp.tool(name="get_page_history", description=TOOLS["get_page_history"].description)
async def get_page_history_tool(params: PageHistoryInput) -> PageHistoryOutput:
    async with _client_errors():
        return await get_page_history(await _context(), params)


@mcp.tool(name="compare_pricing", description=TOOLS["compare_pricing"].description)
async def compare_pricing_tool(params: ComparePricingInput) -> ComparePricingOutput:
    async with _client_errors():
        return await compare_pricing(await _context(), params)


if __name__ == "__main__":
    _workspace_id()  # fail before the client connects, not on its first call
    mcp.run("stdio")
