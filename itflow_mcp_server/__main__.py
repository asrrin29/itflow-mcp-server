"""Command line entry point for the ITFlow MCP server.

Usage:
    itflow-mcp-server                 # run on stdio (default)
    itflow-mcp-server serve           # run on stdio
    itflow-mcp-server serve-http      # run on streamable HTTP with API key auth
    itflow-mcp-server gen-key         # print a new random MCP API key
    itflow-mcp-server check           # validate configuration and ping ITFlow
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import logging
import os
import secrets
import sys
from contextlib import asynccontextmanager

from . import __version__
from .config import (
    ENV_MCP_API_KEY,
    SERVER_NAME,
    Config,
    ConfigError,
    load_config,
)
from .server import build_server


def _setup_logging() -> None:
    level = os.environ.get("MCP_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )


def _print_version() -> None:
    print(f"{SERVER_NAME} {__version__}")


def _cmd_gen_key() -> int:
    key = f"itflow-mcp-{secrets.token_urlsafe(32)}"
    print(key)
    print(
        f"\nSet it in your environment (or .env file):\n  {ENV_MCP_API_KEY}={key}",
        file=sys.stderr,
    )
    return 0


async def _cmd_check(config: Config) -> int:
    from .itflow import ITFlowClient, ITFlowError

    try:
        config.require_itflow()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    print(f"ITFlow base URL: {config.itflow_base_url}")
    print(f"API key:         {'set' if config.itflow_api_key else 'MISSING'}")
    print(
        f"Decrypt pwd:     {'set' if config.itflow_api_key_password else 'not set (only needed for credentials tools)'}"
    )
    perms = ",".join(config.tool_permissions) or "<none>"
    print(f"Tool perms:      {perms} (MCP_TOOL_PERMISSIONS)")
    if "delete" in config.tool_permissions:
        print(
            "WARNING: delete permission is enabled - the AI can PERMANENTLY REMOVE ITFlow records.\n"
            "         Remove 'delete' from MCP_TOOL_PERMISSIONS if you did not mean to allow this.",
            file=sys.stderr,
        )
    print(f"Verify SSL:      {config.verify_ssl}")
    print("Pinging ITFlow (clients/read, limit=1)...")
    async with ITFlowClient(config) as client:
        try:
            payload = await client.read("clients", {"limit": 1})
        except ITFlowError as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            return 1
    print(f"  OK: success={payload.get('success')!r} count={payload.get('count')!r}")
    return 0


def _run_stdio(config: Config) -> int:
    mcp, _state = build_server(config)
    mcp.run(transport="stdio")
    return 0


def _run_http(config: Config) -> int:
    """Serve streamable HTTP with Bearer-token (MCP_API_KEY) authentication."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    config.require_mcp_key()
    valid_keys = {k.encode() for k in config.mcp_api_keys}

    mcp, _state = build_server(config)

    transport_security = None
    if config.allowed_hosts or config.allowed_origins:
        from mcp.server.transport_security import TransportSecuritySettings

        transport_security = TransportSecuritySettings(
            allowed_hosts=list(config.allowed_hosts),
            allowed_origins=list(config.allowed_origins),
        )

    mcp_app = mcp.streamable_http_app(
        stateless_http=True,
        transport_security=transport_security,
    )

    class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if not request.url.path.startswith("/mcp"):
                return await call_next(request)
            header = request.headers.get("authorization", "")
            scheme, _, token = header.partition(" ")
            if scheme.lower() != "bearer" or not token or not any(
                hmac.compare_digest(token.encode(), k) for k in valid_keys
            ):
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Provide 'Authorization: Bearer <MCP_API_KEY>'"},
                    status_code=401,
                )
            return await call_next(request)

    async def health(request):
        return JSONResponse({"status": "ok", "server": SERVER_NAME, "version": __version__})

    @asynccontextmanager
    async def lifespan(app):
        # The mounted streamable-HTTP sub-app's lifespan never runs; the host
        # app must start the session manager (MCP v2 SDK requirement).
        async with mcp.session_manager.run():
            yield

    app = Starlette(
        routes=[Route("/health", health), Mount("/", mcp_app)],
        lifespan=lifespan,
        middleware=[Middleware(ApiKeyAuthMiddleware)],
    )

    print(
        f"{SERVER_NAME} {__version__} listening on http://{config.http_host}:{config.http_port}/mcp "
        f"({len(valid_keys)} API key(s) configured)",
        file=sys.stderr,
    )
    uvicorn.run(app, host=config.http_host, port=config.http_port, log_level="info")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="itflow-mcp-server",
        description="MCP server that lets AI agents communicate with an ITFlow instance.",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Run the MCP server on stdio (default)")
    sub.add_parser("serve-http", help="Run the MCP server on streamable HTTP with API key auth")
    sub.add_parser("gen-key", help="Generate a new MCP API key")
    sub.add_parser("check", help="Validate configuration and ping ITFlow")
    args = parser.parse_args(argv)

    if args.version:
        _print_version()
        return 0

    command = args.command or "serve"
    if command == "gen-key":
        return _cmd_gen_key()

    _setup_logging()
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    if command == "check":
        return asyncio.run(_cmd_check(config))
    if command == "serve-http":
        return _run_http(config)
    # default: serve on stdio
    return _run_stdio(config)


if __name__ == "__main__":
    raise SystemExit(main())
