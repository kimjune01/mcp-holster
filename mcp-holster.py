from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")


@mcp.tool()
async def ping() -> str:
    """Ping the server"""
    return "Pong!"
