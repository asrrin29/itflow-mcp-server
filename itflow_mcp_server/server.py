"""MCP server exposing ITFlow v1 API modules as tools.

Tools are generated from the declarative specs in :mod:`itflow_mcp_server.specs`
(one tool per ``{module}_{function}``), so every documented ITFlow endpoint
becomes an agent-callable tool.

Transports
----------
- ``stdio``: for local MCP clients (Claude Desktop, IDE plugins, ...).
  No API key is required for the MCP layer itself.
- ``streamable-http``: for remote/network access. Requires ``MCP_API_KEY``;
  clients must send ``Authorization: Bearer <MCP_API_KEY>``.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .config import SERVER_NAME, SERVER_VERSION, Config, ConfigError
from .itflow import ITFlowClient, ITFlowError
from .specs import MODULES, FunctionSpec, ModuleSpec, all_functions

logger = logging.getLogger("itflow_mcp_server")

TYPE_MAP: dict[str, str] = {"int": "int", "str": "str", "float": "float", "bool": "bool"}


class ServerState:
    """Holds the lazily-created ITFlow client for the process."""

    def __init__(self, config: Config):
        self.config = config
        self._client: ITFlowClient | None = None
        self._lock = asyncio.Lock()

    async def get_client(self) -> ITFlowClient:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = ITFlowClient(self.config)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def _tool_name(module: str, function: str) -> str:
    return f"{module}_{function}"


def _tool_description(module: ModuleSpec, fn: FunctionSpec) -> str:
    parts = [f"ITFlow API - {module.name}/{fn.name}. {fn.description}"]
    parts.append(f"Module: {module.purpose}")
    if fn.notes:
        parts.append(fn.notes)
    return " ".join(parts)


def _build_handler_source(fields, impl_name: str) -> str:
    """Generate an async function with an explicit signature.

    Python requires defaulted parameters last, so required fields are
    emitted first (the JSON schema's required list is order-independent).
    """
    ordered = [fl for fl in fields if fl.required] + [fl for fl in fields if not fl.required]
    params: list[str] = []
    for field in ordered:
        py_type = TYPE_MAP[field.kind]
        if field.required:
            params.append(f"{field.name}: {py_type}")
        else:
            params.append(f"{field.name}: {py_type} | None = None")
    args = ", ".join(f"{p.name}={p.name}" for p in ordered)
    param_src = ", ".join(params)
    return (
        f"async def handler({param_src}):\n"
        f"    return await {impl_name}({args})\n"
    )


def _decrypt_password(config: Config) -> dict[str, Any] | None:
    """ITFlow requires api_key_decrypt_password for ALL credential operations
    (reads included), so it must ride in the query string on GET requests."""
    if config.itflow_api_key_password:
        return {"api_key_decrypt_password": config.itflow_api_key_password}
    return None


def _make_impl(state: ServerState, module: ModuleSpec, fn: FunctionSpec) -> Callable:
    async def impl(**kwargs: Any) -> dict[str, Any]:
        args = {k: v for k, v in kwargs.items() if v is not None}
        client = await state.get_client()
        try:
            if fn.name == "read":
                payload = await client.read(
                    module.name,
                    args,
                    extra_query=_decrypt_password(state.config) if module.name == "credentials" else None,
                )
            else:
                payload = await client.post(
                    module.name,
                    fn.name,
                    args,
                    include_api_key_password=(module.name == "credentials"),
                )
        except (ITFlowError, ConfigError) as exc:
            raise ToolError(str(exc)) from exc
        return payload

    return impl


def _tool_annotations(module: ModuleSpec, fn: FunctionSpec) -> ToolAnnotations:
    """Best-effort ToolAnnotations from the function semantics."""
    if fn.name == "read":
        return ToolAnnotations(read_only_hint=True, idempotent_hint=True, destructive_hint=False, open_world_hint=True)
    if fn.name == "delete":
        return ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True)
    if fn.name in ("archive", "unarchive", "resolve"):
        return ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True)
    return ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)


def build_server(config: Config) -> tuple[MCPServer, ServerState]:
    """Create the MCPServer with all ITFlow tools registered."""
    state = ServerState(config)

    @asynccontextmanager
    async def lifespan(server: MCPServer):
        yield state
        await state.aclose()

    mcp = MCPServer(
        name=SERVER_NAME,
        title="ITFlow MCP Server",
        description=(
            "MCP server for ITFlow, the open source PSA for small businesses. "
            "Exposes the ITFlow v1 REST API (clients, contacts, tickets, assets, "
            "credentials, invoices, and more) as tools for AI agents."
        ),
        instructions=(
            "Tools are named {module}_{function} and mirror ITFlow v1 API endpoints "
            "(https://docs.itflow.org/api). Reads return up to 50 records by default; "
            "use limit/offset to paginate. When the API key has all-client scope, "
            "pass client_id on create/update/delete calls. Use itflow_status to "
            "verify connectivity and itflow_list_modules to discover what is available."
        ),
        version=SERVER_VERSION,
        lifespan=lifespan,
    )

    for module, fn in all_functions():
        impl_name = f"_impl_{module.name}_{fn.name}"
        impl = _make_impl(state, module, fn)
        source = _build_handler_source(fn.fields, impl_name)
        namespace: dict[str, Any] = {impl_name: impl}
        exec(compile(source, f"<tool:{_tool_name(module.name, fn.name)}>", "exec"), namespace)
        handler: Callable = namespace["handler"]
        name = _tool_name(module.name, fn.name)
        handler.__name__ = name
        mcp.add_tool(
            handler,
            name=name,
            description=_tool_description(module, fn),
            annotations=_tool_annotations(module, fn),
        )

    @mcp.tool(
        name="itflow_status",
        description=(
            "Check ITFlow MCP server configuration and, optionally, connectivity. "
            "Use ping=true to run a live test call (clients/read with limit=1) "
            "against the configured ITFlow instance."
        ),
    )
    async def itflow_status(ping: bool = False) -> dict[str, Any]:
        cfg = state.config
        info: dict[str, Any] = {
            "itflow_base_url": cfg.itflow_base_url or None,
            "itflow_api_key_configured": bool(cfg.itflow_api_key),
            "itflow_api_key_password_configured": bool(cfg.itflow_api_key_password),
            "verify_ssl": cfg.verify_ssl,
            "timeout_seconds": cfg.timeout_seconds,
            "ready": bool(cfg.itflow_base_url and cfg.itflow_api_key),
        }
        if ping:
            try:
                client = await state.get_client()
                payload = await client.read("clients", {"limit": 1})
                info["ping"] = {
                    "ok": True,
                    "message": payload.get("message"),
                    "count": payload.get("count"),
                }
            except (ITFlowError, ConfigError) as exc:
                info["ping"] = {"ok": False, "error": str(exc)}
        elif not info["ready"]:
            info["hint"] = (
                "Set ITFLOW_BASE_URL (e.g. https://itflow.example.com) and "
                "ITFLOW_API_KEY to enable ITFlow calls."
            )
        return info

    @mcp.tool(
        name="itflow_list_modules",
        description=(
            "List all ITFlow API modules and the functions (tools) available for each, "
            "with a short description. Use this to discover what the agent can do."
        ),
    )
    async def itflow_list_modules() -> dict[str, Any]:
        return {
            "modules": [
                {
                    "name": m.name,
                    "purpose": m.purpose,
                    "tools": [
                        {
                            "tool": _tool_name(m.name, f.name),
                            "function": f.name,
                            "description": f.description,
                            **({"notes": f.notes} if f.notes else {}),
                        }
                        for f in m.functions
                    ],
                }
                for m in MODULES
            ]
        }

    return mcp, state
