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
def test_dir(tmp_path: Path) -> Path:
    """Create a test directory with a README file and minimal MCP server."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    # Create test_readme.md in the test directory
    readme_path = test_dir / "README.md"  # Use README.md instead of test_readme.md
    with open("test_readme.md", "r") as src:
        content = src.read()
        readme_path.write_text(content)
        print(f"Wrote {len(content)} bytes to {readme_path}")

    # Create a minimal MCP server
    server_py = test_dir / "server.py"
    server_py.write_text(
        "from mcp.server.fastmcp import FastMCP\n@mcp.tool()\ndef tool(): pass"
    )

    # Create requirements.txt
    requirements = test_dir / "requirements.txt"
    requirements.write_text("mcp[cli]>=1.7.1")

    # Verify files were created
    assert readme_path.exists(), f"README.md not found at {readme_path}"
    assert server_py.exists(), f"server.py not found at {server_py}"
    assert requirements.exists(), f"requirements.txt not found at {requirements}"

    return test_dir


def test_create_server(holster: Holster, test_config_path: Path):
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


def test_read_servers(holster: Holster):
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


def test_update_server_status(holster: Holster, test_config_path: Path):
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


def test_delete_servers(holster: Holster, test_config_path: Path):
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


def test_invalid_server_name(holster: Holster):
    """Test handling of invalid server names."""
    with pytest.raises(ValueError):
        holster.update_server_status(["nonexistent_server"], active=False)

    with pytest.raises(ValueError):
        holster.delete_servers(["nonexistent_server"])


def test_duplicate_server_name(holster: Holster):
    """Test handling of duplicate server names."""
    new_server = {
        "name": "server1",  # Already exists
        "command": "uv",
        "args": ["--directory", "/path/to/duplicate", "run", "duplicate.py"],
    }

    with pytest.raises(ValueError):
        holster.create_server(new_server)


def test_round_trip(holster: Holster, test_config_path: Path):
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


def test_extract_server_config(holster: Holster, test_dir: Path):
    """Test extracting server configuration from README."""
    # Test scanning the test directory
    result = holster.scan_specific_directories([test_dir])

    # Verify the results
    assert result["count"] == 1
    assert "calculator" in result["servers"]

    server_config = result["servers"]["calculator"]
    assert server_config["command"] == "uvx"
    assert server_config["args"] == ["mcp-server-calculator"]
    assert server_config["instructions"] is not None

    # Verify that the second configuration (PIP) was not used
    assert "calculator-pip" not in result["servers"]
