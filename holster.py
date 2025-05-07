from typing import Any, Dict, List, Tuple, Set
from pathlib import Path
from mcp.server.fastmcp import FastMCP
import json
import os
import signal
from contextlib import contextmanager
import time
import re


class ScanTimeoutError(Exception):
    """Raised when scanning takes too long."""

    pass


@contextmanager
def timeout(seconds):
    def handler(signum, frame):
        raise ScanTimeoutError(f"Scanning timed out after {seconds} seconds")

    # Set the signal handler and a timer
    original_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Restore the original handler and cancel the timer
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)


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

    def list_potential_servers(self) -> Dict[str, Any]:
        """List potential MCP server directories without scanning their contents.

        This method quickly lists directories that might contain MCP servers by looking
        for common project structures and Python files, without reading their contents.
        It checks common project locations where users typically keep their servers.

        Returns:
            Dict containing:
                - locations: Dict mapping location name to its results
                    Each result contains:
                    - directories: List of potential server directories
                    - count: Number of directories found
                    - path: Full path that was scanned
                    - exists: Whether the directory exists
                - directories: Dict mapping directory name to its full path
                    This is a flat list of all potential server directories found
                - summary: Overall statistics
                    - total_directories_found: Total number of potential directories
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
            if item.is_dir() and not item.name.startswith(
                "."
            ):  # Skip hidden directories
                locations[f"home-{item.name}"] = item

        results: Dict[str, Any] = {"locations": {}, "directories": {}}
        total_dirs = 0
        locations_exist = 0

        # Helper function to check if a directory looks like a potential server
        def is_potential_server(dir_path: Path) -> bool:
            # Check for common server indicators
            has_py_files = any(dir_path.glob("*.py"))
            has_requirements = (dir_path / "requirements.txt").exists()
            has_pyproject = (dir_path / "pyproject.toml").exists()
            has_src = (dir_path / "src").exists()

            return has_py_files or has_requirements or has_pyproject or has_src

        # Scan each location
        for name, path in locations.items():
            if path.exists():
                locations_exist += 1
                potential_dirs: Set[Path] = set()

                try:
                    # Scan Level 1 (immediate subdirectories)
                    for item in path.iterdir():
                        if not item.is_dir():
                            continue

                        if is_potential_server(item):
                            potential_dirs.add(item)
                            # Add to flat directory list with a unique key
                            dir_key = f"{name}-{item.name}"
                            results["directories"][dir_key] = str(item)
                            continue

                        # Scan Level 2 (subdirectories)
                        try:
                            for subitem in item.iterdir():
                                if not subitem.is_dir():
                                    continue

                                if is_potential_server(subitem):
                                    potential_dirs.add(subitem)
                                    # Add to flat directory list with a unique key
                                    dir_key = f"{name}-{item.name}-{subitem.name}"
                                    results["directories"][dir_key] = str(subitem)
                                    continue

                                # Scan subdirectories of Level 2
                                try:
                                    for subsubitem in subitem.iterdir():
                                        if subsubitem.is_dir() and is_potential_server(
                                            subsubitem
                                        ):
                                            potential_dirs.add(subsubitem)
                                            # Add to flat directory list with a unique key
                                            dir_key = f"{name}-{item.name}-{subitem.name}-{subsubitem.name}"
                                            results["directories"][dir_key] = str(
                                                subsubitem
                                            )
                                except PermissionError:
                                    pass
                        except PermissionError:
                            pass

                    dir_count = len(potential_dirs)
                    total_dirs += dir_count
                    results["locations"][name] = {
                        "directories": [str(d) for d in potential_dirs],
                        "count": dir_count,
                        "path": str(path),
                        "exists": True,
                    }
                except Exception as e:
                    results["locations"][name] = {
                        "directories": [],
                        "count": 0,
                        "path": str(path),
                        "exists": True,
                        "error": str(e),
                    }
            else:
                results["locations"][name] = {
                    "directories": [],
                    "count": 0,
                    "path": str(path),
                    "exists": False,
                }

        # Add summary statistics
        results["summary"] = {
            "total_directories_found": total_dirs,
            "locations_checked": len(locations),
            "locations_exist": locations_exist,
        }

        return results

    def scan_specific_directories(self, directories: List[Path]) -> Dict[str, Any]:
        """Scan specific directories for MCP servers.

        This method scans only the provided directories for MCP servers, checking their
        contents for MCP indicators and README files for configuration instructions.

        Args:
            directories: List of directories to scan

        Returns:
            Dict containing:
                - servers: Dict mapping server name to its configuration
                    Each server config contains:
                    - path: Full path to the server directory
                    - name: Suggested server name
                    - command: Command to run (e.g. 'uvx')
                    - args: List of command arguments
                    - instructions: Instructions from README if found
                - count: Number of servers found
        """
        server_configs: Dict[str, Dict[str, Any]] = {}

        # Helper function to check if a directory is a valid MCP server
        def is_mcp_server(dir_path: Path) -> bool:
            # Check for Python files with MCP indicators
            for py_file in dir_path.glob("**/*.py"):
                try:
                    content = py_file.read_text()
                    if "FastMCP" in content or "@mcp.tool()" in content:
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

        # Helper function to extract server config from README
        def extract_server_config(dir_path: Path) -> Dict[str, Any]:
            config = {
                "path": str(dir_path),
                "name": dir_path.name,
                "command": "uv",  # Default command
                "args": [],  # Default args
                "instructions": None,
            }

            # Check for README files
            readme_files = list(dir_path.glob("README*"))
            if not readme_files:
                print(f"No README files found in {dir_path}")
                return config

            # Read the first README file found
            try:
                content = readme_files[0].read_text()
                print(f"Found README: {readme_files[0]}")
                print(f"Content length: {len(content)}")

                # Look for JSON configuration
                import json

                # Find JSON blocks in the README
                json_blocks = re.finditer(
                    r"```(?:json)?\s*(?:{)?\s*\"mcpServers\":\s*({[\s\S]*?})\s*(?:})?```",
                    content,
                )
                blocks_found = 0
                for match in json_blocks:
                    blocks_found += 1
                    try:
                        json_str = '{"mcpServers": ' + match.group(1) + "}"
                        print(f"Found JSON block {blocks_found}:")
                        print(json_str)
                        json_config = json.loads(json_str)

                        # Check if this is an MCP server configuration
                        if "mcpServers" in json_config:
                            server_config = json_config["mcpServers"]
                            if isinstance(server_config, dict):
                                # Use the first server config found
                                for name, server in server_config.items():
                                    if isinstance(server, dict):
                                        print(f"Found server config for {name}:")
                                        print(server)
                                        config.update(
                                            {
                                                "name": name,
                                                "command": server.get("command", "uv"),
                                                "args": server.get("args", []),
                                                "instructions": content,
                                            }
                                        )
                                        return config
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}")
                        continue
                    except Exception as e:
                        print(f"Other error: {e}")
                        continue

                print(f"No valid JSON blocks found in {blocks_found} blocks")
            except Exception as e:
                print(f"Error reading README: {e}")

            return config

        for directory in directories:
            if directory.exists() and is_mcp_server(directory):
                root_dir = get_project_root(directory)
                server_config = extract_server_config(root_dir)
                server_configs[server_config["name"]] = server_config

        return {"servers": server_configs, "count": len(server_configs)}


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
        them based on their code structure, dependencies, and README configuration.
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
        6. list_potential_servers: Quick directory listing without scanning contents
        7. scan_specific_directories: Detailed scan of selected directories
        8. explain_holster: This tool, explaining how Holster works

        Server Discovery:
        - list_potential_servers: Quickly lists directories that might contain servers by checking:
          * ~/Documents/
          * ~/Projects/
          * ~/dev/
          * ~/workspace/
          * Current directory and its parent
          * Any immediate subdirectories in home (excluding hidden directories)

        - scan_specific_directories: Detailed scan of selected directories, checking for:
          * Python files containing FastMCP imports and @mcp.tool decorators
          * Associated requirements.txt or pyproject.toml files
          * README files with server configuration in JSON format
        """,
        "best_practices": """
        Recommended usage patterns:
        1. Always check server existence before operations
        2. Use list_servers to verify current state
        3. Keep server names unique and descriptive
        4. Use update_server_status to activate/deactivate servers instead of deleting/recreating
        5. Use list_potential_servers for quick directory listing
        6. Use scan_specific_directories for detailed scanning of selected directories
        7. Add server configuration to README files in JSON format:
           ```json
           "mcpServers": {
             "server-name": {
               "command": "uvx",
               "args": ["server-package"]
             }
           }
           ```
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
async def list_potential_servers() -> Dict[str, Any]:
    """List potential MCP server directories without scanning their contents.

    This tool quickly lists directories that might contain MCP servers by looking
    for common project structures and Python files, without reading their contents.
    It automatically checks common project locations where users typically keep
    their servers:
    - ~/Documents/
    - ~/Projects/
    - ~/dev/
    - ~/workspace/
    - Current directory and its parent
    - Any immediate subdirectories in home that might contain projects

    Returns:
        Dict containing:
            - locations: Dict mapping location name to its results
                Each result contains:
                - directories: List of potential server directory paths
                - count: Number of directories found
                - path: Full path that was scanned
                - exists: Whether the directory exists
            - directories: Dict mapping directory name to its full path
                This is a flat list of all potential server directories found
            - summary: Overall statistics
                - total_directories_found: Total number of potential directories
                - locations_checked: Number of locations checked
                - locations_exist: Number of locations that exist
    """
    return holster.list_potential_servers()


@mcp.tool()
async def scan_specific_directories(directories: List[str]) -> Dict[str, Any]:
    """Scan specific directories for MCP servers.

    This tool scans only the provided directories for MCP servers, checking their
    contents for MCP indicators and README files for configuration instructions.
    Use this after list_potential_servers to scan only the directories you're
    interested in.

    Args:
        directories: List of directory paths to scan

    Returns:
        Dict containing:
            - servers: Dict mapping server name to its configuration
                Each server config contains:
                - path: Full path to the server directory
                - name: Suggested server name
                - command: Command to run (e.g. 'uvx')
                - args: List of command arguments
                - instructions: Instructions from README if found
            - count: Number of servers found
    """
    dir_paths = [Path(d) for d in directories]
    return holster.scan_specific_directories(dir_paths)


if __name__ == "__main__":
    mcp.run()
