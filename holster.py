from typing import Any, Dict, List, Tuple, Set
from pathlib import Path
from mcp.server.fastmcp import FastMCP
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

    def scan_mcp_servers(self, directory: Path) -> Set[Path]:
        """Scan a directory for MCP servers.

        This method scans the given directory and its subdirectories (up to 2 levels deep)
        for potential MCP servers. A directory is considered a server if it contains:
        - A Python file with MCP indicators (FastMCP import or @mcp.tool decorator)
        - A requirements.txt or pyproject.toml file (optional if MCP code is found)

        Args:
            directory: Root directory to scan for MCP servers

        Returns:
            Set of Path objects pointing to valid MCP server directories

        Raises:
            ValueError: If the directory does not exist
        """
        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")

        server_dirs: Set[Path] = set()

        # Helper function to check if a directory is a valid MCP server
        def is_mcp_server(dir_path: Path) -> bool:
            # Check for Python files with MCP indicators (including in src/ and package directories)
            for py_file in dir_path.glob("**/*.py"):
                try:
                    content = py_file.read_text()
                    if "FastMCP" in content or "@mcp.tool()" in content:
                        # If we find MCP code in a nested directory, return the root project directory
                        if "src" in py_file.parts:
                            return True
                        if (
                            len(py_file.parts) > len(dir_path.parts) + 2
                        ):  # More than 2 levels deep
                            return True
                        return True
                except Exception:
                    continue

            # If no MCP code found, check for dependencies
            req_file = dir_path / "requirements.txt"
            pyproject_file = dir_path / "pyproject.toml"

            if req_file.exists():
                try:
                    content = req_file.read_text()
                    if "mcp" in content.lower():
                        return True
                except Exception:
                    pass

            if pyproject_file.exists():
                try:
                    content = pyproject_file.read_text()
                    if "mcp" in content.lower():
                        return True
                except Exception:
                    pass

            return False

        # Helper function to get the project root directory
        def get_project_root(path: Path) -> Path:
            # If we're in a src directory, go up to the project root
            if "src" in path.parts:
                src_index = path.parts.index("src")
                return Path(*path.parts[:src_index])
            return path

        # Scan Level 1 (immediate subdirectories)
        try:
            for item in directory.iterdir():
                if not item.is_dir():
                    continue

                if is_mcp_server(item):
                    server_dirs.add(get_project_root(item))
                    continue  # Skip deeper scanning if we found a server

                # Scan Level 2 (subdirectories)
                try:
                    for subitem in item.iterdir():
                        if not subitem.is_dir():
                            continue

                        if is_mcp_server(subitem):
                            server_dirs.add(get_project_root(subitem))
                            continue  # Skip deeper scanning if we found a server

                        # Scan subdirectories of Level 2
                        try:
                            for subsubitem in subitem.iterdir():
                                if subsubitem.is_dir() and is_mcp_server(subsubitem):
                                    server_dirs.add(get_project_root(subsubitem))
                        except PermissionError:
                            pass
                except PermissionError:
                    pass
        except PermissionError:
            pass

        return server_dirs


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
        modifications by providing a programmatic interface for server management and discovery.
        """,
        "architecture": """
        Holster consists of two main components:
        1. A Python class (Holster) that handles config file operations and server discovery
        2. An MCP server interface that exposes these operations as tools
        
        The tool maintains two lists in Claude's config:
        - mcpServers: Currently active servers
        - unusedMcpServers: Servers that are stored but not active

        It also provides functionality to scan directories for MCP servers, identifying
        them based on their code structure and dependencies.
        """,
        "config_management": """
        Holster manages Claude's configuration file at:
        ~/Library/Application Support/Claude/claude_desktop_config.json
        
        It handles:
        - Reading and writing JSON configuration
        - Maintaining server lists
        - Validating server configurations
        - Ensuring data consistency
        - Discovering and validating MCP servers in directories
        """,
        "tools": """
        Available tools:
        1. ping: Health check for the Holster server
        2. create_server: Add new servers to the active list
        3. list_servers: View all active and inactive servers
        4. update_server_status: Activate or deactivate servers in Claude Desktop
        5. delete_servers: Remove servers from the configuration
        6. scan_servers: Discover MCP servers in a specific directory (up to 2 levels deep)
        7. discover_mcp_servers: Automatically scan common project directories for MCP servers
        8. explain_holster: This tool, explaining how Holster works

        Server Discovery:
        - scan_servers: Scans a specific directory for MCP servers
        - discover_mcp_servers: Automatically scans common project locations:
          * ~/Documents/
          * ~/Projects/
          * ~/dev/
          * ~/workspace/
          * Current directory and its parent
          * Any immediate subdirectories in home (excluding hidden directories)

        Both tools identify MCP servers by looking for:
        - Python files containing FastMCP imports and @mcp.tool decorators
        - Associated requirements.txt or pyproject.toml files
        - Proper directory structure up to 2 levels deep
        """,
        "best_practices": """
        Recommended usage patterns:
        1. Always check server existence before operations
        2. Use list_servers to verify current state
        3. Keep server names unique and descriptive
        4. Use update_server_status to activate/deactivate servers instead of deleting/recreating
        5. Use discover_mcp_servers to find MCP servers in common project locations
        6. Use scan_servers for targeted directory scanning
        7. Verify discovered servers before adding them to configuration
        8. Maintain proper requirements files for all MCP servers
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

    This tool activates or deactivates servers in Claude Desktop by moving them between
    Holster's active and inactive lists.

    Args:
        server_names: List of server names to update in Holster
        active: True to activate servers in Claude Desktop, False to deactivate them

    Returns:
        Dict containing:
            - updated: List of server names that were activated/deactivated
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


@mcp.tool()
async def scan_servers(directory: str) -> Dict[str, Any]:
    """Scan a directory for MCP servers and return their locations.

    This tool scans the specified directory and its subdirectories (up to 2 levels deep)
    for potential MCP servers. It identifies directories containing MCP server code
    and returns their locations.

    Args:
        directory: Path to the directory to scan

    Returns:
        Dict containing:
            - servers: List of server directory paths
            - count: Number of servers found
            - scanned_directory: The directory that was scanned

    Raises:
        ValueError: If the directory does not exist
    """
    dir_path = Path(directory)
    server_dirs = holster.scan_mcp_servers(dir_path)

    return {
        "servers": [str(path) for path in server_dirs],
        "count": len(server_dirs),
        "scanned_directory": str(dir_path),
    }


@mcp.tool()
async def discover_mcp_servers() -> Dict[str, Any]:
    """Discover MCP servers in common project locations.

    This tool scans common project directories where MCP servers might be stored:
    1. ~/Documents/
    2. ~/Projects/
    3. ~/dev/
    4. ~/workspace/
    5. Current directory and its parent
    6. Any immediate subdirectories in home that might contain projects

    Returns:
        Dict containing:
            - locations: Dict mapping location name to its scan results
                Each scan result contains:
                - servers: List of server directory paths
                - count: Number of servers found
                - path: Full path that was scanned
                - exists: Whether the directory exists
            - summary: Overall statistics
                - total_servers_found: Total number of potential servers
                - locations_checked: Number of locations checked
                - locations_exist: Number of locations that exist
    """
    # Get home directory
    home = Path.home()

    # Define common project locations to check
    locations = {
        "documents": home / "Documents",
        "projects": home / "Projects",
        "dev": home / "dev",
        "workspace": home / "workspace",
        "current": Path.cwd(),
        "parent": Path.cwd().parent,
    }

    # Add any immediate subdirectories in home that might contain projects
    for item in home.iterdir():
        if item.is_dir() and not item.name.startswith("."):  # Skip hidden directories
            locations[f"home-{item.name}"] = item

    # Scan each location
    results: Dict[str, Any] = {"locations": {}}
    total_servers = 0
    locations_exist = 0

    for name, path in locations.items():
        if path.exists():
            locations_exist += 1
            try:
                server_dirs = holster.scan_mcp_servers(path)
                server_count = len(server_dirs)
                total_servers += server_count
                results["locations"][name] = {
                    "servers": [str(server_dir) for server_dir in server_dirs],
                    "count": server_count,
                    "path": str(path),
                    "exists": True,
                }
            except Exception as e:
                results["locations"][name] = {
                    "servers": [],
                    "count": 0,
                    "path": str(path),
                    "exists": True,
                    "error": str(e),
                }
        else:
            results["locations"][name] = {
                "servers": [],
                "count": 0,
                "path": str(path),
                "exists": False,
            }

    # Add summary statistics
    results["summary"] = {
        "total_servers_found": total_servers,
        "locations_checked": len(locations),
        "locations_exist": locations_exist,
    }

    return results


if __name__ == "__main__":
    mcp.run()
