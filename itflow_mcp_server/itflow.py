"""Thin async client for the ITFlow v1 REST API.

ITFlow API overview (https://docs.itflow.org/api):

- Base URL: ``{base}/api/v1/{module}/{function}.php``
- Auth: ``api_key`` query parameter for GET, JSON body field for POST.
- Standard response: ``{"success": "True"|"False", "message": str,
  "count": int, "data": [...]}``.
- Reads default to 50 rows; paginate with ``limit``/``offset``.
- POSTs require ``client_id`` when the key has all-client scope.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .config import Config

logger = logging.getLogger("itflow_mcp_server")


class ITFlowError(RuntimeError):
    """An ITFlow API request failed (transport or success=False)."""

    def __init__(self, message: str, *, http_status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.http_status = http_status
        self.payload = payload


class ITFlowClient:
    """Async client wrapping one ITFlow instance."""

    def __init__(self, config: Config):
        config.require_itflow()
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_base,
            timeout=httpx.Timeout(config.timeout_seconds),
            verify=config.verify_ssl,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "ITFlowClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Core request handling
    # ------------------------------------------------------------------

    async def read(
        self,
        module: str,
        params: dict[str, Any] | None = None,
        extra_query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GET ``/{module}/read.php`` and return the parsed JSON payload.

        ``extra_query`` carries auth-related parameters the docs require in the
        query string (e.g. ``api_key_decrypt_password`` for credentials).
        """
        query: dict[str, Any] = {"api_key": self._config.itflow_api_key}
        if params:
            query.update({k: v for k, v in params.items() if v is not None and v != ""})
        if extra_query:
            query.update({k: v for k, v in extra_query.items() if v})
        return await self._request("GET", f"/{module}/read.php", query=query)

    async def post(
        self,
        module: str,
        function: str,
        data: dict[str, Any] | None = None,
        *,
        include_api_key_password: bool = False,
    ) -> dict[str, Any]:
        """POST ``/{module}/{function}.php`` with a JSON body."""
        body: dict[str, Any] = {"api_key": self._config.itflow_api_key}
        if include_api_key_password and self._config.itflow_api_key_password:
            body["api_key_decrypt_password"] = self._config.itflow_api_key_password
        if data:
            body.update({k: v for k, v in data.items() if v is not None and v != ""})
        return await self._request("POST", f"/{module}/{function}.php", json_body=body)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        attempts = self._config.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.request(
                    method, path, params=query, json=json_body
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise ITFlowError(f"Request to ITFlow failed: {exc}") from exc

            if response.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
                last_error = ITFlowError(
                    f"ITFlow returned HTTP {response.status_code}",
                    http_status=response.status_code,
                )
                await asyncio.sleep(0.5 * attempt)
                continue

            payload = self._parse(response)
            if response.status_code == 401:
                raise ITFlowError(
                    "ITFlow rejected the API key (HTTP 401). "
                    "Check ITFLOW_API_KEY and that the key has not expired.",
                    http_status=401,
                    payload=payload,
                )
            if response.status_code >= 400:
                raise ITFlowError(
                    f"ITFlow returned HTTP {response.status_code}: "
                    f"{_short(payload)}",
                    http_status=response.status_code,
                    payload=payload,
                )
            if isinstance(payload, dict) and str(payload.get("success", "")).lower() == "false":
                message = payload.get("message") or "Unknown error"
                raise ITFlowError(str(message), http_status=response.status_code, payload=payload)
            return payload if isinstance(payload, dict) else {"success": "True", "data": payload}

        raise ITFlowError(f"Request to ITFlow failed after {attempts} attempts: {last_error}")

    @staticmethod
    def _parse(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            body = response.text or ""
            return {"success": "False", "message": f"Non-JSON response: {body[:300]}"}


def _short(payload: Any) -> str:
    if isinstance(payload, dict):
        message = payload.get("message")
        if message:
            return str(message)[:300]
    return str(payload)[:300]
