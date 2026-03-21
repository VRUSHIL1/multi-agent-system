from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.mcp.client import mcp_client

logger = logging.getLogger(__name__)


class MCPToolWrapper(BaseTool):
    """Wrapper to expose MCP tools as LangChain tools."""

    name: str
    description: str

    server_name: str = Field(description="MCP server name")
    tool_name: str = Field(description="MCP tool name")

    args_schema: type[BaseModel] | None = None

    def _run(self, **kwargs: Any) -> str:
        """Synchronous execution (not supported)."""
        raise NotImplementedError("MCP tools must run asynchronously")

    async def _arun(self, **kwargs: Any) -> str:
        """Execute MCP tool asynchronously."""
        try:
            # Unwrap kwargs if they're nested
            if 'kwargs' in kwargs and len(kwargs) == 1:
                kwargs = kwargs['kwargs']
            
            # Log the arguments being passed
            logger.info(f"Calling MCP tool {self.server_name}.{self.tool_name} with args: {kwargs}")
            
            result = await mcp_client.call_tool(
                server_name=self.server_name,
                tool_name=self.tool_name,
                arguments=kwargs,
            )

            # Extract text from MCP TextContent objects
            if isinstance(result, list):
                text_parts = []
                for item in result:
                    if hasattr(item, 'text'):
                        text_parts.append(item.text)
                    elif isinstance(item, dict) and 'text' in item:
                        text_parts.append(item['text'])
                    else:
                        text_parts.append(str(item))
                return '\n'.join(text_parts)
            
            # Handle single TextContent object
            if hasattr(result, 'text'):
                return result.text
            
            # Fallback to string conversion
            return str(result)

        except Exception as e:
            error_msg = f"MCP tool {self.server_name}.{self.tool_name} failed: {str(e)}"
            logger.exception(error_msg)
            return error_msg


async def get_mcp_langchain_tools() -> list[BaseTool]:
    """Load MCP tools and convert them to LangChain tools."""

    tools_by_server = await mcp_client.get_all_tools()
    langchain_tools: list[BaseTool] = []

    for server_name, server_tools in tools_by_server.items():
        for tool in server_tools:
            tool_name = tool["name"]
            description = tool.get("description", "")

            unique_name = f"{server_name}_{tool_name}"

            langchain_tools.append(
                MCPToolWrapper(
                    name=unique_name,
                    description=description,
                    server_name=server_name,
                    tool_name=tool_name,
                )
            )

    logger.info("✅ Total MCP tools loaded: %d", len(langchain_tools))

    return langchain_tools