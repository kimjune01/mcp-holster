# Holster

A Python-based tool for managing MCP servers in Claude's configuration file directly from Claude desktop, eliminating the need for manual text editor modifications.

## Features

- 🔄 Seamless server management within Claude desktop
- 📝 JSON configuration handling with proper parsing and encoding
- 📋 Separate tracking of active and inactive servers
- 🛠️ Simple command-line interface
- ✅ Comprehensive test coverage

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/holster.git
cd holster
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies using `uv`:

```bash
uv pip install -r requirements.txt
```

## Configuration

The default configuration file location is:

```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Add this to your growing list of MCP servers:

```
    "holster": {
        "command": "uv",
        "args": [
            "--directory",
            "<THIS_DIRECTORY>",
            "run",
            "holster.py"
        ]
    }
```

Restart Claude to reload the config.

## Usage

### Understanding Holster

First, you can get a comprehensive explanation of how Holster works:

```python
# Get detailed explanation of Holster's functionality
explanation = await explain_holster()
print(explanation["overview"])
print(explanation["tools"])
```

### Creating a New Server

```python
# Create a new server configuration
server_config = await create_server(
    name="my_server",
    command="uv",
    directory="/path/to/server",
    script="server.py"
)
```

### Reading Server Status

```python
# Get lists of active and inactive servers
servers = await list_servers()
print("Active servers:", list(servers["active"].keys()))
print("Inactive servers:", list(servers["inactive"].keys()))
```

### Updating Server Status

```python
# Deactivate servers
result = await update_server_status(
    server_names=["server1", "server2"],
    active=False
)
print(f"Deactivated {len(result['updated'])} servers")

# Activate servers
result = await update_server_status(
    server_names=["server1", "server2"],
    active=True
)
print(f"Activated {len(result['updated'])} servers")
```

### Deleting Servers

```python
# Delete servers from both active and inactive lists
result = await delete_servers(["server1", "server2"])
print(f"Deleted {len(result['deleted'])} servers")
print(f"Remaining active: {result['remaining_active']}")
print(f"Remaining inactive: {result['remaining_inactive']}")
```

### Health Check

```python
# Check if Holster server is running
response = await ping()
print(response)  # Should print "Pong!"
```

## Development

### Running Tests

```bash
python -m pytest test_holster.py -v
```

## Motivation

Managing MCP servers through text editors is a task well-suited for LLMs, but Claude currently only provides a pointer to the config file. Holster aims to improve this experience by providing a seamless interface for server management directly within Claude desktop.

## Scope

### In Scope

- Server configuration management within Claude's config file
- Tracking of active and inactive servers
- Basic CRUD operations for server configurations

### Out of Scope

- Automatic server discovery and downloading
- Web-based server search
- Workspace management
- Server versioning

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

June Kim & LLM tools
