import os
import json
import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Dict, Any, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.config: Dict[str, Any] | None = None
        self._initialized = False

    async def connect_all(self) -> None:
        """
        Connect to all MCP servers defined in configuration.
        """
        if self._initialized:
            return

        config_path = os.path.join(os.path.dirname(__file__), "mcp_server.json")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"MCP config not found: {config_path}")

        with open(config_path, "r") as f:
            self.config = json.load(f)

        servers = self.config.get("mcpServers", {})

        for name, server_info in servers.items():

            if not server_info.get("is_active", True):
                logger.info(f"[SKIP] MCP server '{name}' is inactive")
                continue

            try:
                command = server_info.get("command")
                args = server_info.get("args", [])
                env_config = server_info.get("env", {})

                # Resolve environment variables
                env = {**os.environ}
                for key, value in env_config.items():
                    env[key] = os.getenv(value, value)

                logger.info(f"[CONNECT] MCP server '{name}'")

                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env,
                )

                # Start stdio transport
                stdio_transport = await asyncio.wait_for(
                    self.exit_stack.enter_async_context(
                        stdio_client(server_params)
                    ),
                    timeout=60,
                )

                stdio, write = stdio_transport

                session = await self.exit_stack.enter_async_context(
                    ClientSession(stdio, write)
                )

                await asyncio.wait_for(session.initialize(), timeout=60)

                self.sessions[name] = session

                response = await session.list_tools()
                tool_count = len(response.tools)

                logger.info(f"[OK] {name} loaded {tool_count} tools")

            except asyncio.TimeoutError:
                logger.error(f"[TIMEOUT] MCP server '{name}' connection timeout")
            except Exception as e:
                logger.error(f"[ERROR] Failed to connect '{name}': {e}")

        self._initialized = True
        logger.info("✅ MCP initialization complete")

    async def get_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Return all tools from all connected MCP servers.
        """

        if not self._initialized:
            await self.connect_all()

        all_tools = {}

        for server_name, session in self.sessions.items():

            try:
                response = await session.list_tools()

                all_tools[server_name] = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    }
                    for tool in response.tools
                ]

            except Exception as e:
                logger.error(f"[ERROR] Failed getting tools from {server_name}: {e}")

        return all_tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """
        Execute tool on MCP server.
        """

        if not self._initialized:
            await self.connect_all()

        session = self.sessions.get(server_name)

        if not session:
            raise ValueError(
                f"MCP server '{server_name}' not found. "
                f"Available: {list(self.sessions.keys())}"
            )

        try:
            result = await session.call_tool(tool_name, arguments)
            return result.content

        except Exception as e:
            logger.error(
                f"[ERROR] Tool call failed: {server_name}.{tool_name} → {e}"
            )
            raise

    async def format_info(self) -> List[Dict[str, str]]:
        """
        Return simplified tool information for LLM prompts.
        """

        if not self._initialized:
            await self.connect_all()

        formatted_tools = []

        for server_name, session in self.sessions.items():

            try:
                response = await session.list_tools()

                for tool in response.tools:

                    tool_name = getattr(tool, "name", "Unknown")
                    description = getattr(
                        tool,
                        "description",
                        "No description available",
                    )

                    description = (
                        description.replace("\n", " ")
                        .replace("  ", " ")
                        .strip()
                    )

                    formatted_tools.append(
                        {
                            "server": server_name,
                            "name": tool_name,
                            "description": description
                            or "No description available",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"[ERROR] Failed to load tools from {server_name}: {e}"
                )

        return formatted_tools

    async def cleanup(self) -> None:
        """
        Close all MCP sessions.
        """
        try:
            await asyncio.wait_for(self.exit_stack.aclose(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ MCP cleanup timeout - forcing close")
        except Exception as e:
            logger.error(f"❌ MCP cleanup error: {e}")
        finally:
            self.sessions.clear()
            self._initialized = False
            logger.info("🧹 MCP connections closed")


# Global singleton instance
mcp_client = MCPClient()


async def call_mcp_tool(
    server_name: str,
    tool_name: str,
    arguments: Dict[str, Any],
):
    """
    Helper wrapper for calling MCP tools.
    """
    return await mcp_client.call_tool(server_name, tool_name, arguments)


# Standalone test runner
if __name__ == "__main__":

    async def main():
        client = MCPClient()

        await client.connect_all()

        tools = await client.get_all_tools()

        print(json.dumps(tools, indent=2))

        await client.cleanup()

    asyncio.run(main())