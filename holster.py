from typing import Any, Dict, Tuple
from pathlib import Path


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
