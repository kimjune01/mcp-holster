from typing import Any, Dict, List, Tuple
from pathlib import Path
import httpx
from mcp.server.fastmcp import FastMCP
import uvicorn
import json
import os


class Holster:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def create_server(self, server_config: Dict[str, Any]) -> None:
        """Create a new server configuration."""
        pass

    def read_servers(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Read active and inactive servers.

        Returns:
            Tuple containing (active_servers, inactive_servers)
        """
        return {}, {}

    def update_server_status(self, server_names: list[str], active: bool) -> None:
        """Move servers between active and inactive lists."""
        pass

    def delete_servers(self, server_names: list[str]) -> None:
        """Delete servers from both active and inactive lists."""
        pass


# Initialize FastMCP server
mcp = FastMCP("holster")

# Default config path for Claude Desktop
DEFAULT_CONFIG_PATH = Path(
    os.path.expanduser(
        "~/Library/Application Support/Claude/claude_desktop_config.json"
    )
)

# Initialize Holster with default config path
holster = Holster(DEFAULT_CONFIG_PATH)


@mcp.tool()
async def ping() -> str:
    """Ping the Holster server"""
    return "Pong!"


@mcp.tool()
async def create_server(
    name: str, command: str, directory: str, script: str
) -> Dict[str, Any]:
    """Create a new MCP server configuration.

    Args:
        name: Name of the server
        command: Command to run (e.g. 'uv')
        directory: Directory where the server code is located
        script: Script file to run

    Returns:
        Dict containing the created server configuration
    """
    server_config = {
        "name": name,
        "command": command,
        "args": ["--directory", directory, "run", script],
    }
    holster.create_server(server_config)
    return server_config


@mcp.tool()
async def list_servers() -> Dict[str, Dict[str, Any]]:
    """List all active and inactive MCP servers.

    Returns:
        Dict containing 'active' and 'inactive' server lists
    """
    active, inactive = holster.read_servers()
    return {"active": active, "inactive": inactive}


@mcp.tool()
async def update_server_status(server_names: List[str], active: bool) -> Dict[str, Any]:
    """Move servers between active and inactive lists.

    Args:
        server_names: List of server names to update
        active: True to make active, False to make inactive

    Returns:
        Dict containing the updated server status
    """
    holster.update_server_status(server_names, active)
    active_servers, inactive_servers = holster.read_servers()
    return {
        "updated": server_names,
        "active_count": len(active_servers),
        "inactive_count": len(inactive_servers),
    }


@mcp.tool()
async def delete_servers(server_names: List[str]) -> Dict[str, Any]:
    """Delete servers from both active and inactive lists.

    Args:
        server_names: List of server names to delete

    Returns:
        Dict containing the deletion status
    """
    holster.delete_servers(server_names)
    active_servers, inactive_servers = holster.read_servers()
    return {
        "deleted": server_names,
        "remaining_active": len(active_servers),
        "remaining_inactive": len(inactive_servers),
    }


if __name__ == "__main__":
    mcp.run()
