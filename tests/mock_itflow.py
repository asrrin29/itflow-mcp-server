"""A minimal mock ITFlow v1 API server for end-to-end tests.

Implements just enough of the documented response contract
(https://docs.itflow.org/api) to exercise the MCP server:
- GET  /api/v1/{module}/read.php?api_key=...
- POST /api/v1/{module}/{function}.php  (JSON body with api_key)
- standard {"success", "message", "count", "data"} envelope
"""

from __future__ import annotations

from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

VALID_KEY = "mock-itflow-key"
VALID_PWD = "mock-decrypt-pwd"

_CLIENTS = [
    {"client_id": "1", "client_name": "ACME Corp"},
    {"client_id": "2", "client_name": "Globex"},
]


def _auth_ok(request: Request) -> bool:
    if request.method == "GET":
        return request.query_params.get("api_key") == VALID_KEY
    return False  # POST checked after body parse


async def _read(request: Request) -> JSONResponse:
    if request.query_params.get("api_key") != VALID_KEY:
        return JSONResponse(
            {"success": "False", "message": "Authentication failed. API key is invalid or has expired."},
            status_code=401,
        )
    module = request.url.path.split("/")[3]
    if module == "credentials" and request.query_params.get("api_key_decrypt_password") != VALID_PWD:
        return JSONResponse({"success": "False", "message": "Decrypt password invalid."})
    if module == "clients":
        data = _CLIENTS
        name = request.query_params.get("client_name")
        if name:
            data = [c for c in data if c["client_name"] == name]
        limit = request.query_params.get("limit")
        if limit:
            data = data[: int(limit)]
        return JSONResponse({"success": "True", "message": "Success", "count": len(data), "data": data})
    return JSONResponse({"success": "True", "message": "Success", "count": 0, "data": []})


async def _create(request: Request) -> JSONResponse:
    body = await request.json()
    if body.get("api_key") != VALID_KEY:
        return JSONResponse(
            {"success": "False", "message": "Authentication failed. API key is invalid or has expired."},
            status_code=401,
        )
    module = request.url.path.split("/")[3]
    fn = request.url.path.split("/")[4].replace(".php", "")
    if module == "credentials" and body.get("api_key_decrypt_password") != VALID_PWD:
        return JSONResponse({"success": "False", "message": "Decrypt password invalid."})
    return JSONResponse(
        {"success": "True", "message": f"{module}/{fn} ok", "count": "1", "data": [{"insert_id": 99}]}
    )


async def _post(request: Request) -> JSONResponse:
    # any POST function that is not create (update/delete/resolve/archive)
    return await _create(request)


async def _health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


routes = [
    Route("/health", _health),
    Route("/api/v1/{module}/read.php", _read, methods=["GET"]),
    Route("/api/v1/{module}/create.php", _create, methods=["POST"]),
    Route("/api/v1/{module}/{fn}.php", _post, methods=["POST"]),
]

app = Starlette(routes=routes)
