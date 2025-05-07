import json
import os
import pytest
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch, mock_open

from holster import Holster


@pytest.fixture
def test_config_path(tmp_path: Path) -> Path:
    """Create a temporary config file for testing."""
    return tmp_path / "test_config.json"


@pytest.fixture
def sample_config() -> Dict:
    """Sample config data for testing."""
    return {
        "mcpServers": {
            "server1": {
                "command": "uv",
                "args": ["--directory", "/path/to/server1", "run", "server1.py"],
            },
            "server2": {
                "command": "uv",
                "args": ["--directory", "/path/to/server2", "run", "server2.py"],
            },
        },
        "unusedMcpServers": {
            "server3": {
                "command": "uv",
                "args": ["--directory", "/path/to/server3", "run", "server3.py"],
            }
        },
    }


@pytest.fixture
def holster(test_config_path: Path, sample_config: Dict) -> Holster:
    """Create a Holster instance with test config."""
    # Write sample config to test file
    with open(test_config_path, "w") as f:
        json.dump(sample_config, f, indent=2)

    return Holster(config_path=test_config_path)


@pytest.fixture
def mock_server_directories(tmp_path: Path) -> Dict[str, Path]:
    """Create a mock directory structure with MCP servers."""
    # Create root directories
    mcp_servers = tmp_path / "mcp-servers"
    my_projects = tmp_path / "my-projects"
    mcp_servers.mkdir()
    my_projects.mkdir()

    # Create server1 (Level 1)
    server1 = mcp_servers / "server1"
    server1.mkdir()
    (server1 / "server1.py").write_text(
        "from mcp.server.fastmcp import FastMCP\n@mcp.tool()\ndef tool(): pass"
    )
    (server1 / "requirements.txt").write_text("mcp[cli]>=1.7.1")

    # Create server2 (Level 1)
    server2 = mcp_servers / "server2"
    server2.mkdir()
    (server2 / "server2.py").write_text(
        "from mcp.server.fastmcp import FastMCP\n@mcp.tool()\ndef tool(): pass"
    )
    (server2 / "requirements.txt").write_text("mcp[cli]>=1.7.1")

    # Create project1/mcp-server (Level 2)
    project1 = my_projects / "project1"
    project1.mkdir()
    mcp_server = project1 / "mcp-server"
    mcp_server.mkdir()
    (mcp_server / "server.py").write_text(
        "from mcp.server.fastmcp import FastMCP\n@mcp.tool()\ndef tool(): pass"
    )
    (mcp_server / "requirements.txt").write_text("mcp[cli]>=1.7.1")

    # Create project2/tools (Level 2)
    project2 = my_projects / "project2"
    project2.mkdir()
    tools = project2 / "tools"
    tools.mkdir()
    (tools / "mcp-tool.py").write_text(
        "from mcp.server.fastmcp import FastMCP\n@mcp.tool()\ndef tool(): pass"
    )
    (tools / "requirements.txt").write_text("mcp[cli]>=1.7.1")

    # Create a non-server directory
    non_server = tmp_path / "non-server"
    non_server.mkdir()
    (non_server / "script.py").write_text("print('not a server')")

    return {
        "root": tmp_path,
        "mcp_servers": mcp_servers,
        "my_projects": my_projects,
        "server1": server1,
        "server2": server2,
        "project1_mcp_server": mcp_server,
        "project2_tools": tools,
        "non_server": non_server,
    }


class TestHolster:
    def test_create_server(self, holster: Holster, test_config_path: Path):
        """Test creating a new server configuration."""
        new_server = {
            "name": "new_server",
            "command": "uv",
            "args": ["--directory", "/path/to/new_server", "run", "new_server.py"],
        }

        # Test creating a new server
        holster.create_server(new_server)

        # Verify the server was added to mcpServers
        with open(test_config_path) as f:
            config = json.load(f)
            assert "new_server" in config["mcpServers"]
            assert config["mcpServers"]["new_server"] == {
                "command": new_server["command"],
                "args": new_server["args"],
            }
            assert len(config["mcpServers"]) == 3  # Original 2 + new 1

    def test_read_servers(self, holster: Holster):
        """Test reading active and inactive servers."""
        active, inactive = holster.read_servers()

        # Verify correct number of servers in each list
        assert len(active) == 2
        assert len(inactive) == 1

        # Verify server names and structure
        assert "server1" in active
        assert "server2" in active
        assert "server3" in inactive

        # Verify server configurations
        assert active["server1"]["command"] == "uv"
        assert active["server2"]["command"] == "uv"
        assert inactive["server3"]["command"] == "uv"

    def test_update_server_status(self, holster: Holster, test_config_path: Path):
        """Test moving servers between active and inactive lists."""
        # Test moving server1 to inactive
        holster.update_server_status(["server1"], active=False)

        # Verify the move
        with open(test_config_path) as f:
            config = json.load(f)
            assert "server1" not in config["mcpServers"]
            assert "server1" in config["unusedMcpServers"]
            assert len(config["mcpServers"]) == 1
            assert len(config["unusedMcpServers"]) == 2

        # Test moving server1 back to active
        holster.update_server_status(["server1"], active=True)

        # Verify the move back
        with open(test_config_path) as f:
            config = json.load(f)
            assert "server1" in config["mcpServers"]
            assert "server1" not in config["unusedMcpServers"]
            assert len(config["mcpServers"]) == 2
            assert len(config["unusedMcpServers"]) == 1

    def test_delete_servers(self, holster: Holster, test_config_path: Path):
        """Test deleting servers from both active and inactive lists."""
        # Test deleting server1 from active and server3 from inactive
        holster.delete_servers(["server1", "server3"])

        # Verify the deletions
        with open(test_config_path) as f:
            config = json.load(f)
            assert "server1" not in config["mcpServers"]
            assert "server3" not in config["unusedMcpServers"]
            assert len(config["mcpServers"]) == 1
            assert len(config["unusedMcpServers"]) == 0

    def test_invalid_server_name(self, holster: Holster):
        """Test handling of invalid server names."""
        with pytest.raises(ValueError):
            holster.update_server_status(["nonexistent_server"], active=False)

        with pytest.raises(ValueError):
            holster.delete_servers(["nonexistent_server"])

    def test_duplicate_server_name(self, holster: Holster):
        """Test handling of duplicate server names."""
        new_server = {
            "name": "server1",  # Already exists
            "command": "uv",
            "args": ["--directory", "/path/to/duplicate", "run", "duplicate.py"],
        }

        with pytest.raises(ValueError):
            holster.create_server(new_server)

    def test_round_trip(self, holster: Holster, test_config_path: Path):
        """Test a complete round trip of CRUD operations."""
        # Initial read
        active, inactive = holster.read_servers()
        assert len(active) == 2
        assert len(inactive) == 1
        assert "server1" in active
        assert "server2" in active
        assert "server3" in inactive

        # Create new server
        new_server = {
            "name": "round_trip_server",
            "command": "uv",
            "args": ["--directory", "/path/to/round_trip", "run", "round_trip.py"],
        }
        holster.create_server(new_server)

        # Read after create
        active, inactive = holster.read_servers()
        assert len(active) == 3
        assert len(inactive) == 1
        assert "round_trip_server" in active
        assert active["round_trip_server"]["command"] == "uv"

        # Update status (move to inactive)
        holster.update_server_status(["round_trip_server"], active=False)

        # Read after update
        active, inactive = holster.read_servers()
        assert len(active) == 2
        assert len(inactive) == 2
        assert "round_trip_server" not in active
        assert "round_trip_server" in inactive
        assert inactive["round_trip_server"]["command"] == "uv"

        # Delete server
        holster.delete_servers(["round_trip_server"])

        # Final read
        active, inactive = holster.read_servers()
        assert len(active) == 2
        assert len(inactive) == 1
        assert "round_trip_server" not in active
        assert "round_trip_server" not in inactive

        # Verify config file state
        with open(test_config_path) as f:
            config = json.load(f)
            assert "round_trip_server" not in config["mcpServers"]
            assert "round_trip_server" not in config["unusedMcpServers"]
            assert len(config["mcpServers"]) == 2
            assert len(config["unusedMcpServers"]) == 1

    def test_scan_mcp_servers(
        self, holster: Holster, mock_server_directories: Dict[str, Path]
    ):
        """Test scanning for MCP servers in directories."""
        # Test scanning root directory
        servers = holster.scan_mcp_servers(mock_server_directories["root"])

        # Verify all server directories were found
        assert len(servers) == 4
        server_paths = {str(path) for path in servers}

        # Check Level 1 servers
        assert str(mock_server_directories["server1"]) in server_paths
        assert str(mock_server_directories["server2"]) in server_paths

        # Check Level 2 servers
        assert str(mock_server_directories["project1_mcp_server"]) in server_paths
        assert str(mock_server_directories["project2_tools"]) in server_paths

        # Verify non-server directory was not included
        assert str(mock_server_directories["non_server"]) not in server_paths

    def test_scan_mcp_servers_empty_directory(self, holster: Holster, tmp_path: Path):
        """Test scanning an empty directory."""
        servers = holster.scan_mcp_servers(tmp_path)
        assert len(servers) == 0

    def test_scan_mcp_servers_invalid_directory(self, holster: Holster):
        """Test scanning a non-existent directory."""
        with pytest.raises(ValueError):
            holster.scan_mcp_servers(Path("/non/existent/path"))

    def test_scan_mcp_servers_with_invalid_servers(
        self, holster: Holster, tmp_path: Path
    ):
        """Test scanning directories with invalid server configurations."""
        # Create a directory with invalid server files
        invalid_server = tmp_path / "invalid-server"
        invalid_server.mkdir()
        (invalid_server / "server.py").write_text("print('not a real server')")
        (invalid_server / "requirements.txt").write_text("some-package>=1.0.0")

        servers = holster.scan_mcp_servers(tmp_path)
        assert len(servers) == 0
