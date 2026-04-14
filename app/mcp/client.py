import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self):
        self.config: Dict[str, Any] | None = None
        self._client: MultiServerMCPClient | None = None
        self._tools: List[BaseTool] = []
        self._exit_stack = AsyncExitStack()
        self._initialized = False

    def _load_server_config(self) -> Dict[str, Any]:
        """
        Load and convert mcp_server.json into MultiServerMCPClient format.
        """
        config_path = os.path.join(os.path.dirname(__file__), "mcp_server.json")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"MCP config not found: {config_path}")

        with open(config_path, "r") as f:
            raw = json.load(f)

        servers = {}

        for name, server_info in raw.get("mcpServers", {}).items():
            if not server_info.get("is_active", True):
                logger.info(f"[SKIP] MCP server '{name}' is inactive")
                continue

            env_config = server_info.get("env", {})
            resolved_env = {
                key: os.getenv(value, value) for key, value in env_config.items()
            }

            transport = server_info.get("transport", "stdio")

            if transport == "stdio":
                servers[name] = {
                    "transport": "stdio",
                    "command": server_info.get("command"),
                    "args": server_info.get("args", []),
                    "env": {**os.environ, **resolved_env},
                }
            elif transport in ("http", "streamable_http"):
                entry: Dict[str, Any] = {
                    "transport": "http",
                    "url": server_info.get("url"),
                }
                if server_info.get("headers"):
                    entry["headers"] = server_info["headers"]
                if server_info.get("auth"):
                    entry["auth"] = server_info["auth"]
                servers[name] = entry
            else:
                logger.warning(f"[SKIP] Unknown transport '{transport}' for '{name}'")

        return servers

    async def connect_all(self) -> None:
        """
        Connect to all MCP servers and eagerly load all tools.
        Sessions are owned by AsyncExitStack so cleanup is always safe.
        """
        if self._initialized:
            return

        servers = self._load_server_config()

        if not servers:
            logger.warning("No active MCP servers found in config")
            self._initialized = True
            return

        logger.info(
            f"[CONNECT] Initializing {len(servers)} MCP server(s): {list(servers.keys())}"
        )

        self._client = MultiServerMCPClient(servers)
        self.config = servers

        # Enter the exit stack so it owns the cleanup scope
        await self._exit_stack.__aenter__()

        all_tools: List[BaseTool] = []

        for server_name in servers:
            try:
                logger.info(f"[CONNECT] Opening session for '{server_name}'...")

                # Register the session inside our exit stack —
                # the stack now owns the anyio cancel scope, preventing
                # "cancel scope that isn't the current task's scope" errors
                session = await asyncio.wait_for(
                    self._exit_stack.enter_async_context(
                        self._client.session(server_name)
                    ),
                    timeout=60,
                )

                tools = await asyncio.wait_for(
                    load_mcp_tools(session),
                    timeout=60,
                )

                logger.info(f"[OK] '{server_name}' loaded {len(tools)} tool(s)")
                all_tools.extend(tools)

            except asyncio.TimeoutError:
                logger.error(f"[TIMEOUT] '{server_name}' timed out during connect")
            except Exception as e:
                logger.error(f"[ERROR] Failed to connect '{server_name}': {e}")

        self._tools = all_tools
        self._initialized = True
        logger.info(
            f"✅ MCP initialization complete | {len(self._tools)} total tool(s)"
        )

    async def get_all_tools(self) -> List[BaseTool]:
        """
        Return cached tools — no subprocess or session spawned here.
        """
        if not self._initialized:
            await self.connect_all()

        return self._tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """
        Execute a tool via LangChain's invoke on the cached tool object.
        Falls back to a fresh stateless session if the tool isn't cached.
        """
        if not self._initialized:
            await self.connect_all()

        # Try to invoke via the cached LangChain tool first
        for tool in self._tools:
            if tool.name == tool_name:
                try:
                    result = await tool.ainvoke(arguments)
                    return result
                except Exception as e:
                    logger.error(f"[ERROR] Tool invoke failed: {tool_name} → {e}")
                    raise

        # Fallback: open a short-lived session for the specific server
        if not self._client:
            raise RuntimeError("MCP client is not initialized")

        if server_name not in (self.config or {}):
            raise ValueError(
                f"MCP server '{server_name}' not found. "
                f"Available: {list((self.config or {}).keys())}"
            )

        try:
            async with self._client.session(server_name) as session:
                result = await session.call_tool(tool_name, arguments)
                return result.content
        except Exception as e:
            logger.error(f"[ERROR] Tool call failed: {server_name}.{tool_name} → {e}")
            raise

    async def format_info(self) -> List[Dict[str, str]]:
        """
        Return simplified tool information for LLM prompts.
        """
        if not self._initialized:
            await self.connect_all()

        return [
            {
                "name": tool.name,
                "description": (
                    (tool.description or "No description available")
                    .replace("\n", " ")
                    .replace("  ", " ")
                    .strip()
                ),
            }
            for tool in self._tools
        ]

    async def cleanup(self) -> None:
        """
        Close all MCP sessions safely via the exit stack.
        The exit stack owns the anyio cancel scopes so teardown is clean.
        """
        try:
            await self._exit_stack.__aexit__(None, None, None)
            logger.info("🧹 MCP sessions closed via exit stack")
        except Exception as e:
            logger.error(f"❌ MCP cleanup error: {e}")
        finally:
            self._tools.clear()
            self._client = None
            self.config = None
            self._initialized = False
            # Fresh stack for potential re-initialization
            self._exit_stack = AsyncExitStack()
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

        print(
            json.dumps(
                [{"name": t.name, "description": t.description} for t in tools],
                indent=2,
            )
        )

        await client.cleanup()

    asyncio.run(main())
