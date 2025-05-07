from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
import uvicorn

# Initialize FastMCP server
mcp = FastMCP("weather")


@mcp.tool()
async def ping() -> str:
    """Ping the Holster server"""
    return "Pong!"


if __name__ == "__main__":
    mcp.run()
