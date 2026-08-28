"""End-to-end tests: real `itflow-mcp-server` process against a mock ITFlow.

- stdio transport: spawns the installed module with the MCP SDK's high-level
  Client and calls tools that hit the mock ITFlow instance.
- HTTP transport: spawns `serve-http`, checks Bearer auth (MCP_API_KEY) and a
  tool call over streamable HTTP.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys

import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tests.mock_itflow import app as mock_itflow_app

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MockITFlow:
    def __init__(self):
        self.port = _free_port()
        self.config = uvicorn.Config(mock_itflow_app, host="127.0.0.1", port=self.port, log_level="error")
        self.server = uvicorn.Server(self.config)
        self._task: asyncio.Task | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def start(self):
        self._task = asyncio.create_task(self.server.serve())
        for _ in range(100):
            if self.server.started:
                return
            await asyncio.sleep(0.05)
        raise RuntimeError("mock ITFlow did not start")

    async def stop(self):
        self.server.should_exit = True
        if self._task:
            await self._task


def _env(mock: MockITFlow, **extra) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        ITFLOW_BASE_URL=mock.base_url,
        ITFLOW_API_KEY="mock-itflow-key",
        ITFLOW_API_KEY_PASSWORD="mock-decrypt-pwd",
        MCP_LOG_LEVEL="WARNING",
    )
    env.update({k: v for k, v in extra.items() if v is not None})
    return env


def _server_params(env: dict[str, str], *args: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "itflow_mcp_server", *args],
        env=env,
        cwd=PROJECT_ROOT,
    )


@pytest.fixture()
async def mock():
    m = MockITFlow()
    await m.start()
    yield m
    await m.stop()


def _tool_text(result) -> dict:
    assert not result.is_error, f"tool returned error: {result.content[0].text}"
    return json.loads(result.content[0].text)


async def test_stdio_tool_list_and_calls(mock):
    env = _env(mock, MCP_TOOL_PERMISSIONS="read,write,delete")
    async with Client(_server_params(env)) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools.tools}
        expected = {
            "itflow_status",
            "itflow_list_modules",
            "clients_read",
            "assets_create",
            "tickets_create",
            "credentials_read",
            "credentials_create",
            "domains_read",
            "invoices_read",
        }
        assert expected <= names, f"missing tools: {expected - names}"
        assert len(names) == 40

        # status + ping (live call against mock ITFlow)
        data = _tool_text(await client.call_tool("itflow_status", {"ping": True}))
        assert data["ready"] is True
        assert data["ping"]["ok"] is True

        # read clients
        data = _tool_text(await client.call_tool("clients_read", {"limit": 10}))
        assert data["success"] == "True"
        assert data["count"] == 2
        assert data["data"][0]["client_name"] == "ACME Corp"

        # read one client by name
        data = _tool_text(await client.call_tool("clients_read", {"client_name": "Globex"}))
        assert data["count"] == 1
        assert data["data"][0]["client_id"] == "2"

        # create ticket
        data = _tool_text(
            await client.call_tool(
                "tickets_create",
                {"client_id": 1, "ticket_subject": "Printer offline", "ticket_priority": "High"},
            )
        )
        assert data["success"] == "True"
        assert data["data"][0]["insert_id"] == 99

        # credentials read (requires decrypt password from env)
        _tool_text(await client.call_tool("credentials_read", {}))

        # module discovery
        data = _tool_text(await client.call_tool("itflow_list_modules", {}))
        assert {m["name"] for m in data["modules"]} >= {"clients", "tickets", "assets"}


async def test_stdio_missing_required_arg_rejected(mock):
    env = _env(mock, MCP_TOOL_PERMISSIONS="read,write")
    async with Client(_server_params(env)) as client:
        # tickets_create requires ticket_subject
        result = await client.call_tool("tickets_create", {"client_id": 1})
        assert result.is_error


async def test_stdio_bad_itflow_key_returns_tool_error(mock):
    env = _env(mock, ITFLOW_API_KEY="wrong-key")
    async with Client(_server_params(env)) as client:
        result = await client.call_tool("clients_read", {})
        assert result.is_error
        assert "rejected the API key" in result.content[0].text


# ---------------------------------------------------------------------------
# MCP_TOOL_PERMISSIONS: tools are gated by what they do to an ITFlow object
# (read = fetch only, write = create/modify, delete = remove). Disallowed
# tools are not registered, so they never appear in tools/list.
# ---------------------------------------------------------------------------

READ_ONLY_TOOLS = {
    "itflow_status",
    "itflow_list_modules",
    "assets_read",
    "clients_read",
    "contacts_read",
    "credentials_read",
    "documents_read",
    "domains_read",
    "expenses_read",
    "invoices_read",
    "invoice_items_read",
    "locations_read",
    "networks_read",
    "payments_read",
    "products_read",
    "quotes_read",
    "software_read",
    "tickets_read",
    "vendors_read",
    "certificates_read",
}


async def _tool_names(mock, **extra) -> set[str]:
    env = _env(mock, **extra)
    async with Client(_server_params(env)) as client:
        tools = await client.list_tools()
        return {t.name for t in tools.tools}


async def test_stdio_read_only_by_default(mock):
    # No MCP_TOOL_PERMISSIONS set -> read-only: 18 read + 2 helper tools,
    # no create/update/archive/resolve/delete tools at all.
    names = await _tool_names(mock)
    assert names == READ_ONLY_TOOLS
    assert "tickets_create" not in names
    assert "assets_delete" not in names


async def test_stdio_read_write_permissions(mock):
    names = await _tool_names(mock, MCP_TOOL_PERMISSIONS="read,write")
    # write-tier tools are exposed ...
    assert {"tickets_create", "clients_update", "contacts_archive", "tickets_resolve"} <= names
    # ...but delete-tier tools are still hidden
    assert "assets_delete" not in names
    assert "contacts_delete" not in names
    assert len(names) == len(READ_ONLY_TOOLS) + 18  # 18 write-tier tools


async def test_stdio_delete_permission_exposes_delete_tools(mock):
    names = await _tool_names(mock, MCP_TOOL_PERMISSIONS="read,write,delete")
    assert "assets_delete" in names
    assert "contacts_delete" in names
    assert len(names) == 40  # all tools


async def test_stdio_status_reports_permissions(mock):
    env = _env(mock, MCP_TOOL_PERMISSIONS="read,write")
    async with Client(_server_params(env)) as client:
        data = _tool_text(await client.call_tool("itflow_status", {}))
        assert data["tool_permissions"] == ["read", "write"]
        # list_modules only reports tools that are actually enabled
        data = _tool_text(await client.call_tool("itflow_list_modules", {}))
        assert data["tool_permissions"] == ["read", "write"]
        listed = {t["tool"] for m in data["modules"] for t in m["tools"]}
        assert "assets_delete" not in listed
        assert "tickets_create" in listed


async def test_stdio_invalid_permission_level_refuses_to_start(mock):
    env = _env(mock, MCP_TOOL_PERMISSIONS="read,bogus")
    proc = subprocess.run(
        [sys.executable, "-m", "itflow_mcp_server", "serve"],
        env=env,
        cwd=PROJECT_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode != 0
    assert "MCP_TOOL_PERMISSIONS" in proc.stderr
    assert "bogus" in proc.stderr


async def test_http_requires_bearer_key(mock):
    port = _free_port()
    env = _env(
        mock,
        MCP_API_KEY="mcp-secret-key-123",
        MCP_HTTP_PORT=str(port),
        MCP_HTTP_HOST="127.0.0.1",
        MCP_TOOL_PERMISSIONS="read",
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "itflow_mcp_server", "serve-http"],
        env=env,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(200):
            if proc.poll() is not None:
                raise RuntimeError(f"server exited early: {proc.stderr.read().decode()[:1000]}")
            try:
                async with httpx2.AsyncClient() as hc:
                    r = await hc.get(f"http://127.0.0.1:{port}/health", timeout=2)
                if r.status_code == 200:
                    break
            except (httpx2.HTTPError, OSError):
                await asyncio.sleep(0.1)
        else:
            raise RuntimeError("HTTP server did not come up")

        async with httpx2.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10) as hc:
            # no key -> 401
            r = await hc.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            assert r.status_code == 401

            # wrong key -> 401
            r = await hc.post(
                "/mcp",
                headers={"Authorization": "Bearer wrong"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            assert r.status_code == 401

        # full MCP session with the right key
        http_client = httpx2.AsyncClient(
            headers={"Authorization": "Bearer mcp-secret-key-123"},
            timeout=httpx2.Timeout(10, read=30),
            follow_redirects=True,
        )
        async with http_client:
            async with streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=http_client) as (
                read,
                write,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("clients_read", {"limit": 5})
                    assert not result.is_error
                    data = json.loads(result.content[0].text)
                    assert data["count"] == 2
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
