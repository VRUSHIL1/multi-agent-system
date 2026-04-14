from __future__ import annotations

import logging

from langchain_core.tools import BaseTool

from app.mcp.client import mcp_client

logger = logging.getLogger(__name__)


async def get_mcp_langchain_tools() -> list[BaseTool]:
    """Load MCP tools and convert them to LangChain tools."""
    tools = await mcp_client.get_all_tools()
    logger.info("✅ Total MCP tools loaded: %d", len(tools))
    return tools
