"""Unit tests for the ITFlow API client (no network)."""

from __future__ import annotations

import httpx
import pytest

from itflow_mcp_server.config import Config, ConfigError
from itflow_mcp_server.itflow import ITFlowClient, ITFlowError


def make_config(**overrides) -> Config:
    base = dict(
        itflow_base_url="https://itflow.example.com",
        itflow_api_key="test-key",
        itflow_api_key_password="test-pwd",
        mcp_api_key="",
        verify_ssl=True,
        timeout_seconds=5.0,
        max_retries=1,
    )
    base.update(overrides)
    return Config(**base)


def client_with(handler) -> ITFlowClient:
    config = make_config()
    client = ITFlowClient(config)
    client._client = httpx.AsyncClient(
        base_url=config.api_base,
        transport=httpx.MockTransport(handler),
    )
    return client


async def test_read_sends_api_key_and_params():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={"success": "True", "count": 1, "data": [{"client_id": "1", "client_name": "ACME"}]},
        )

    client = client_with(handler)
    try:
        payload = await client.read("clients", {"limit": 5, "client_name": "ACME"})
    finally:
        await client.aclose()
    assert payload["success"] == "True"
    assert payload["count"] == 1
    assert "api_key=test-key" in seen["url"]
    assert "limit=5" in seen["url"]
    assert "client_name=ACME" in seen["url"]
    assert seen["url"].startswith("https://itflow.example.com/api/v1/clients/read.php")


async def test_read_strips_empty_params():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"success": "True", "count": 0, "data": []})

    client = client_with(handler)
    try:
        await client.read("vendors", {"vendor_id": None, "limit": "", "offset": 0})
    finally:
        await client.aclose()
    assert "vendor_id" not in seen["url"]
    assert "limit" not in seen["url"]


async def test_post_sends_json_body_with_api_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["body"] = json.loads(request.content)
        seen["content_type"] = request.headers.get("content-type", "")
        return httpx.Response(
            200, json={"success": "True", "count": "1", "data": [{"insert_id": 42}]}
        )

    client = client_with(handler)
    try:
        payload = await client.post(
            "tickets", "create", {"client_id": 7, "ticket_subject": "Printer offline"}
        )
    finally:
        await client.aclose()
    assert payload["data"][0]["insert_id"] == 42
    assert seen["body"]["api_key"] == "test-key"
    assert seen["body"]["client_id"] == 7
    assert seen["body"]["ticket_subject"] == "Printer offline"
    assert seen["content_type"].startswith("application/json")
    assert "api_key_decrypt_password" not in seen["body"]


async def test_credentials_post_includes_decrypt_password():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"success": "True", "count": "1", "data": []})

    client = client_with(handler)
    try:
        await client.post(
            "credentials",
            "create",
            {"credential_name": "Router", "credential_password": "s3cret"},
            include_api_key_password=True,
        )
    finally:
        await client.aclose()
    assert seen["body"]["api_key_decrypt_password"] == "test-pwd"


async def test_success_false_raises_with_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": "False",
                "message": "No resource (for this client and company) with the specified parameter(s).",
            },
        )

    client = client_with(handler)
    try:
        with pytest.raises(ITFlowError, match="No resource"):
            await client.read("clients", {"client_name": "Missing"})
    finally:
        await client.aclose()


async def test_http_401_raises_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"success": "False", "message": "Authentication failed. API key is invalid or has expired."},
        )

    client = client_with(handler)
    try:
        with pytest.raises(ITFlowError, match="rejected the API key"):
            await client.read("clients")
    finally:
        await client.aclose()


async def test_transient_500_is_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="service unavailable")
        return httpx.Response(200, json={"success": "True", "count": 0, "data": []})

    client = client_with(handler)
    try:
        payload = await client.read("clients")
    finally:
        await client.aclose()
    assert payload["success"] == "True"
    assert calls["n"] == 2


async def test_missing_config_raises():
    config = make_config(itflow_base_url="", itflow_api_key="")
    with pytest.raises(ConfigError, match="ITFLOW_BASE_URL"):
        ITFlowClient(config)


async def test_non_json_response_is_reported():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>error page</html>")

    client = client_with(handler)
    try:
        with pytest.raises(ITFlowError, match="Non-JSON response"):
            await client.read("clients")
    finally:
        await client.aclose()
