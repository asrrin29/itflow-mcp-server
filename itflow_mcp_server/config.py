"""Configuration for the ITFlow MCP server.

All settings come from environment variables (optionally loaded from a
``.env`` file in the working directory or the project root).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional, only needed for .env file support
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

SERVER_NAME = "itflow-mcp-server"
SERVER_VERSION = "1.0.0"

# Environment variable names
ENV_BASE_URL = "ITFLOW_BASE_URL"
ENV_API_KEY = "ITFLOW_API_KEY"
ENV_API_KEY_PASSWORD = "ITFLOW_API_KEY_PASSWORD"
ENV_MCP_API_KEY = "MCP_API_KEY"
ENV_VERIFY_SSL = "ITFLOW_VERIFY_SSL"
ENV_TIMEOUT = "ITFLOW_TIMEOUT"
ENV_MAX_RETRIES = "ITFLOW_MAX_RETRIES"
ENV_HTTP_HOST = "MCP_HTTP_HOST"
ENV_HTTP_PORT = "MCP_HTTP_PORT"
ENV_ALLOWED_HOSTS = "MCP_ALLOWED_HOSTS"
ENV_ALLOWED_ORIGINS = "MCP_ALLOWED_ORIGINS"
ENV_TOOL_PERMISSIONS = "MCP_TOOL_PERMISSIONS"

# Tool permission levels, in escalating order. Each level gates a set of
# tools based on what the underlying ITFlow call does to an object:
#   read   - list/fetch records only (never changes anything)
#   write  - creates or modifies records (create/update/archive/unarchive/resolve)
#   delete - permanently removes records (delete)
TOOL_PERMISSION_LEVELS: tuple[str, ...] = ("read", "write", "delete")
# Secure default: the AI may only read.
DEFAULT_TOOL_PERMISSIONS: tuple[str, ...] = ("read",)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _load_dotenv() -> None:
    if load_dotenv is None:
        return
    # Prefer a .env in the current directory, then the project root.
    candidates = [Path.cwd() / ".env"]
    project_root = Path(__file__).resolve().parent.parent
    candidates.append(project_root / ".env")
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            return


def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_bool(name: str, default: bool) -> bool:
    value = _env_str(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    value = _env_str(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {value!r}") from exc


def _env_int(name: str, default: int) -> int:
    value = _env_str(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {value!r}") from exc


@dataclass(frozen=True)
class Config:
    """Runtime configuration for the server."""

    itflow_base_url: str
    itflow_api_key: str
    itflow_api_key_password: str = ""
    mcp_api_key: str = ""
    verify_ssl: bool = True
    timeout_seconds: float = 30.0
    max_retries: int = 2
    http_host: str = "127.0.0.1"
    http_port: int = 8700
    allowed_hosts: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ()
    tool_permissions: tuple[str, ...] = DEFAULT_TOOL_PERMISSIONS

    def allows_action(self, action: str) -> bool:
        """Whether a tool whose action tier is ``action`` (read/write/delete) is permitted."""
        return action in self.tool_permissions

    @property
    def mcp_api_keys(self) -> tuple[str, ...]:
        """All configured MCP API keys (MCP_API_KEY may hold a comma-separated list)."""
        return tuple(k.strip() for k in self.mcp_api_key.split(",") if k.strip())

    @property
    def api_base(self) -> str:
        """Full base URL for ITFlow v1 API endpoints."""
        return f"{self.itflow_base_url.rstrip('/')}/api/v1"

    def require_itflow(self) -> None:
        """Validate the settings needed to talk to ITFlow."""
        if not self.itflow_base_url:
            raise ConfigError(
                f"Missing required environment variable {ENV_BASE_URL} "
                "(e.g. https://itflow.example.com)."
            )
        if not self.itflow_api_key:
            raise ConfigError(
                f"Missing required environment variable {ENV_API_KEY} "
                "(create one in ITFlow under Admin > API Keys)."
            )

    def require_mcp_key(self) -> None:
        """Validate the MCP server's own API key (required for HTTP transport)."""
        if not self.mcp_api_key:
            raise ConfigError(
                f"Missing required environment variable {ENV_MCP_API_KEY}. "
                "Generate one with: itflow-mcp-server gen-key"
            )


def _env_list(name: str) -> tuple[str, ...]:
    value = _env_str(name)
    if value is None:
        return ()
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _env_permissions(name: str) -> tuple[str, ...]:
    """Parse the tool-permission level list (e.g. ``read,write``).

    Unset means the secure default (read-only). Unknown values are a hard
    error so a typo can never silently widen (or narrow) access.
    """
    value = _env_str(name)
    if value is None:
        return DEFAULT_TOOL_PERMISSIONS
    levels = tuple(v.strip().lower() for v in value.split(",") if v.strip())
    if not levels:
        raise ConfigError(
            f"{name} must be a comma-separated list of: {', '.join(TOOL_PERMISSION_LEVELS)}"
        )
    unknown = [v for v in levels if v not in TOOL_PERMISSION_LEVELS]
    if unknown:
        raise ConfigError(
            f"{name} contains unknown permission level(s) {', '.join(unknown)}. "
            f"Valid levels: {', '.join(TOOL_PERMISSION_LEVELS)} "
            "(combine with commas, e.g. read,write)."
        )
    # De-duplicate and return in canonical escalating order.
    return tuple(level for level in TOOL_PERMISSION_LEVELS if level in levels)


def load_config() -> Config:
    """Build a Config from the environment."""
    _load_dotenv()
    base_url = _env_str(ENV_BASE_URL, "")
    base_url = base_url.rstrip("/")
    if base_url and not base_url.startswith(("http://", "https://")):
        raise ConfigError(
            f"{ENV_BASE_URL} must start with http:// or https:// (got {base_url!r})."
        )
    return Config(
        itflow_base_url=base_url,
        itflow_api_key=_env_str(ENV_API_KEY, "") or "",
        itflow_api_key_password=_env_str(ENV_API_KEY_PASSWORD, "") or "",
        mcp_api_key=_env_str(ENV_MCP_API_KEY, "") or "",
        verify_ssl=_env_bool(ENV_VERIFY_SSL, True),
        timeout_seconds=_env_float(ENV_TIMEOUT, 30.0),
        max_retries=_env_int(ENV_MAX_RETRIES, 2),
        http_host=_env_str(ENV_HTTP_HOST, "127.0.0.1") or "127.0.0.1",
        http_port=_env_int(ENV_HTTP_PORT, 8700),
        allowed_hosts=_env_list(ENV_ALLOWED_HOSTS),
        allowed_origins=_env_list(ENV_ALLOWED_ORIGINS),
        tool_permissions=_env_permissions(ENV_TOOL_PERMISSIONS),
    )
