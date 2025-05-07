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
        # Create config file if it doesn't exist
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump({"mcpServers": {}, "unusedMcpServers": {}}, f, indent=2)

    def _read_config(self) -> Dict[str, Any]:
        """Read the config file."""
        with open(self.config_path) as f:
            return json.load(f)

    def _write_config(self, config: Dict[str, Any]) -> None:
        """Write to the config file."""
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def create_server(self, server_config: Dict[str, Any]) -> None:
        """Create a new server configuration."""
        config = self._read_config()
        name = server_config["name"]

        # Check if server name already exists
        if name in config["mcpServers"] or name in config["unusedMcpServers"]:
            raise ValueError(f"Server '{name}' already exists")

        # Add server to active list
        config["mcpServers"][name] = {
            "command": server_config["command"],
            "args": server_config["args"],
        }

        self._write_config(config)

    def read_servers(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Read active and inactive servers.

        Returns:
            Tuple containing (active_servers, inactive_servers)
        """
        config = self._read_config()
        return config["mcpServers"], config["unusedMcpServers"]

    def update_server_status(self, server_names: list[str], active: bool) -> None:
        """Move servers between active and inactive lists."""
        config = self._read_config()
        source_key = "mcpServers" if not active else "unusedMcpServers"
        target_key = "unusedMcpServers" if not active else "mcpServers"

        for name in server_names:
            # Check if server exists in source list
            if name not in config[source_key]:
                raise ValueError(
                    f"Server '{name}' not found in {'active' if not active else 'inactive'} list"
                )

            # Move server to target list
            config[target_key][name] = config[source_key][name]
            del config[source_key][name]

        self._write_config(config)

    def delete_servers(self, server_names: list[str]) -> None:
        """Delete servers from both active and inactive lists."""
        config = self._read_config()

        for name in server_names:
            # Check if server exists in either list
            if (
                name not in config["mcpServers"]
                and name not in config["unusedMcpServers"]
            ):
                raise ValueError(f"Server '{name}' not found")

            # Delete from both lists (in case it exists in both)
            config["mcpServers"].pop(name, None)
            config["unusedMcpServers"].pop(name, None)

        self._write_config(config)


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
async def explain_holster() -> Dict[str, Any]:
    """Explain how the Holster MCP server management tool works.

    This tool provides a comprehensive explanation of Holster's functionality,
    architecture, and usage patterns.

    Returns:
        Dict containing:
            - overview: General description of Holster
            - architecture: How Holster is structured
            - config_management: How Holster manages Claude's config
            - tools: Description of available tools
            - best_practices: Recommended usage patterns
    """
    return {
        "overview": """
        Holster is a Python-based tool that manages MCP servers in Claude's configuration
        file directly from Claude desktop. It eliminates the need for manual text editor
        modifications by providing a programmatic interface for server management.
        """,
        "architecture": """
        Holster consists of two main components:
        1. A Python class (Holster) that handles config file operations
        2. An MCP server interface that exposes these operations as tools
        
        The tool maintains two lists in Claude's config:
        - mcpServers: Currently active servers
        - unusedMcpServers: Servers that are stored but not active
        """,
        "config_management": """
        Holster manages Claude's configuration file at:
        ~/Library/Application Support/Claude/claude_desktop_config.json
        
        It handles:
        - Reading and writing JSON configuration
        - Maintaining server lists
        - Validating server configurations
        - Ensuring data consistency
        """,
        "tools": """
        Available tools:
        1. ping: Health check for the Holster server
        2. create_server: Add new servers to the active list
        3. list_servers: View all active and inactive servers
        4. update_server_status: Move servers between active/inactive lists
        5. delete_servers: Remove servers from the configuration
        6. explain_holster: This tool, explaining how Holster works
        """,
        "best_practices": """
        Recommended usage patterns:
        1. Always check server existence before operations
        2. Use list_servers to verify current state
        3. Keep server names unique and descriptive
        4. Use update_server_status instead of deleting/recreating
        5. Verify changes with list_servers after operations
        """,
    }


@mcp.tool()
async def ping() -> str:
    """Health check for the Holster MCP server management tool.

    Returns:
        str: "Pong!" if the Holster server is running
    """
    return "Pong!"


@mcp.tool()
async def create_server(
    name: str, command: str, directory: str, script: str
) -> Dict[str, Any]:
    """Create a new MCP server configuration in Holster's managed config file.

    This tool adds a new server to Holster's active server list. The server will be
    immediately available to Claude Desktop after creation.

    Args:
        name: Unique identifier for the server in Holster's configuration
        command: Command to run (e.g. 'uv')
        directory: Directory where the server code is located
        script: Script file to run

    Returns:
        Dict containing the created server configuration as stored in Holster

    Raises:
        ValueError: If a server with the given name already exists in Holster
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
    """List all MCP servers managed by Holster.

    Returns a dictionary containing two lists:
    - active: Servers currently enabled in Claude Desktop
    - inactive: Servers stored but not currently enabled

    Returns:
        Dict containing 'active' and 'inactive' server lists from Holster's config
    """
    active, inactive = holster.read_servers()
    return {"active": active, "inactive": inactive}


@mcp.tool()
async def update_server_status(server_names: List[str], active: bool) -> Dict[str, Any]:
    """Update the status of servers in Holster's configuration.

    This tool moves servers between Holster's active and inactive lists, effectively
    enabling or disabling them in Claude Desktop.

    Args:
        server_names: List of server names to update in Holster
        active: True to enable servers in Claude Desktop, False to disable them

    Returns:
        Dict containing:
            - updated: List of server names that were moved
            - active_count: Number of servers now active
            - inactive_count: Number of servers now inactive

    Raises:
        ValueError: If any server is not found in the source list
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
    """Remove servers from Holster's configuration.

    This tool permanently removes servers from both active and inactive lists in
    Holster's configuration. The servers will no longer be available to Claude Desktop.

    Args:
        server_names: List of server names to remove from Holster

    Returns:
        Dict containing:
            - deleted: List of server names that were removed
            - remaining_active: Number of servers still active
            - remaining_inactive: Number of servers still inactive

    Raises:
        ValueError: If any server is not found in either list
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
