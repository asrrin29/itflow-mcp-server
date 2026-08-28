# ITFlow MCP Server

An [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server that lets AI
agents communicate with an [ITFlow](https://www.itflow.org/) instance, an IT documentation,
ticketing and accounting system for small MSPs, through its v1 REST API.

Every documented ITFlow API module becomes a set of tools an agent can call:
list clients, create tickets, manage assets and contacts, look up credentials,
read invoices, and more.

Built on the [MCP Python SDK](https://py.sdk.modelcontextprotocol.io) (v2, `MCPServer`).

Tested and confirmed working with ITFlow version 26.08.2.

## Disclaimer

This is an **unofficial, fan-made contribution**. It is **not** associated with, endorsed
by, or affiliated with the [ITFlow](https://www.itflow.org/) organization in any way.

The author is not a programmer by trade. They built this because they run their own
ITFlow instance and wanted to connect it to AI to improve their day-to-day workflows.

This project was written **with the assistance of a large language model (LLM)**. Please
review the code before relying on it, especially for anything security-sensitive.

## ITFlow API coverage

Tools are generated from the module reference in
[https://docs.itflow.org/api](https://docs.itflow.org/api), with one tool per
`{module}/{function}.php` endpoint:

| Module | Tools |
|---|---|
| `assets` | `assets_read`, `assets_create`, `assets_update`, `assets_delete` |
| `certificates` | `certificates_read`, `certificates_create` |
| `clients` | `clients_read`, `clients_create`, `clients_update`, `clients_archive`, `clients_unarchive` |
| `contacts` | `contacts_read`, `contacts_create`, `contacts_update`, `contacts_delete`, `contacts_archive`, `contacts_unarchive` |
| `credentials` | `credentials_read`, `credentials_create`, `credentials_update` |
| `documents` | `documents_read`, `documents_create`, `documents_update` |
| `domains` | `domains_read` |
| `expenses` | `expenses_read` |
| `invoices` | `invoices_read` |
| `invoice_items` | `invoice_items_read` |
| `locations` | `locations_read`, `locations_create` |
| `networks` | `networks_read` |
| `payments` | `payments_read` |
| `products` | `products_read` |
| `quotes` | `quotes_read` |
| `software` | `software_read` |
| `tickets` | `tickets_read`, `tickets_create`, `tickets_resolve` |
| `vendors` | `vendors_read` |

Plus two helper tools (always available, regardless of permissions):

- `itflow_status`: show the server's configuration and (with `ping: true`) run a
  live test call against ITFlow.
- `itflow_list_modules`: discover all modules and their tools (only lists the
  tools currently enabled).

Which of these tools the AI actually gets is controlled by
`MCP_TOOL_PERMISSIONS` — see [Tool permissions](#tool-permissions).

Notes from the ITFlow docs that the server enforces or documents:

- Reads return 50 records by default; pass `limit`/`offset` to paginate.
- `client_id` is required on create/update/delete when the API key has
  all-client scope.
- `api_key` is always supplied by the server from `ITFLOW_API_KEY`; it is never
  a tool parameter.
- `credentials_*` tools automatically send `api_key_decrypt_password` from
  `ITFLOW_API_KEY_PASSWORD` (ITFlow requires it for all credential operations).
- ITFlow's standard response envelope (`success`, `message`, `count`, `data`) is
  returned verbatim; `success: "False"` is surfaced as a tool error so the agent
  can react to it.

## Tool permissions

The AI only gets tools it is allowed to use. `MCP_TOOL_PERMISSIONS` gates tools
by what the underlying ITFlow call does to an object:

| Level | What it allows | Example tools |
|---|---|---|
| `read` | List/fetch records only. Changes nothing. | `clients_read`, `assets_read`, `invoices_read` |
| `write` | Create or modify records. Reversible in practice (records can be edited or unarchived), but the AI **will change your data** when it calls them. | `tickets_create`, `contacts_update`, `clients_archive`, `tickets_resolve` |
| `delete` | **Permanently remove records.** Deletions cannot be undone. | `assets_delete`, `contacts_delete` |

```bash
MCP_TOOL_PERMISSIONS=read              # AI can only look at data (default)
MCP_TOOL_PERMISSIONS=read,write        # AI can look at and change data
MCP_TOOL_PERMISSIONS=read,write,delete # full control — dangerous
```

How it works:

- Levels are combined with commas; a higher level does **not** imply lower
  ones — list everything you want.
- Unset/empty defaults to `read` only, so a fresh install is read-only.
- Disallowed tools are **not registered**: they never appear in the tool list
  the AI sees, so the model cannot call what it cannot see. (The ITFlow API
  key's own scope is an independent second layer of control.)
- Typos (e.g. `MCP_TOOL_PERMISSIONS=read,rite`) make the server refuse to
  start rather than silently fall back.
- `itflow_status` and `itflow_list_modules` always report the active
  permission set, so you (or the agent) can verify what is enabled.

> **Warning:** enabling `delete` lets the AI permanently delete records in
> your ITFlow instance (assets and contacts, including related data such as
> asset network interfaces). Only enable it deliberately, and consider
> scoping `ITFLOW_API_KEY` to a single client as a safety net. `itflow-mcp-server check`
> also prints a warning to the console when delete permission is active.

## Quick start

### 1. Create an ITFlow API key

1. Log in to ITFlow as admin.
2. Go to **Admin Settings → API Keys → Create**.
3. Choose the scope (all clients, or one specific client).
4. Copy the **API key** and the **credential password** (shown once).

### 2. Install

```bash
cd itflow-mcp-server
pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
# edit .env:
#   ITFLOW_BASE_URL=https://itflow.example.com
#   ITFLOW_API_KEY=...
#   ITFLOW_API_KEY_PASSWORD=...   (only needed for credentials tools)
#   MCP_API_KEY=...               (only needed for serve-http)
```

Generate the MCP server's own API key:

```bash
itflow-mcp-server gen-key
```

Verify connectivity:

```bash
itflow-mcp-server check
```

### 4. Run

**stdio** (the default, for local MCP clients):

```bash
itflow-mcp-server
# or: itflow-mcp-server serve
```

**streamable HTTP** (for remote access, protected by `MCP_API_KEY`):

```bash
itflow-mcp-server serve-http
# → http://127.0.0.1:8700/mcp   (clients send: Authorization: Bearer <MCP_API_KEY>)
#   http://127.0.0.1:8700/health (unauthenticated liveness probe)
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ITFLOW_BASE_URL` | yes | Base URL of the ITFlow instance, e.g. `https://itflow.example.com` (no trailing slash). |
| `ITFLOW_API_KEY` | yes | API key created in ITFlow (Admin → API Keys). Sent automatically on every call. |
| `ITFLOW_API_KEY_PASSWORD` | for credentials tools | The decryption password shown with the API key. Sent as `api_key_decrypt_password` on `credentials_*` calls. |
| `MCP_API_KEY` | for `serve-http` | API key(s) clients must present to use *this* MCP server. Comma-separated list supported. Clients send `Authorization: Bearer <key>`. |
| `MCP_HTTP_HOST` | no | Bind host for `serve-http` (default `127.0.0.1`). |
| `MCP_HTTP_PORT` | no | Bind port for `serve-http` (default `8700`). |
| `MCP_ALLOWED_HOSTS` | no | Comma-separated `Host` allowlist for the HTTP transport (see note below). |
| `MCP_ALLOWED_ORIGINS` | no | Comma-separated browser `Origin` allowlist for the HTTP transport. |
| `MCP_TOOL_PERMISSIONS` | no | Which tools the AI may use, by what they do to an object: `read` (fetch only), `write` (create/modify), `delete` (remove — dangerous). Comma-separated, e.g. `read,write`. Default (unset): `read`. See [Tool permissions](#tool-permissions). |
| `ITFLOW_VERIFY_SSL` | no | `true` (default) or `false`. Set `false` only for self-signed local test instances. |
| `ITFLOW_TIMEOUT` | no | HTTP timeout in seconds (default `30`). |
| `ITFLOW_MAX_RETRIES` | no | Extra retries on transient failures, 429/5xx (default `2`). |
| `MCP_LOG_LEVEL` | no | `DEBUG`, `INFO`, `WARNING`, `ERROR` (default `INFO`). Logs go to stderr. |

A `.env` file in the working directory (or the project root) is loaded
automatically if `python-dotenv` is installed; real environment variables always
win.

**DNS rebinding protection:** when `serve-http` binds to a loopback host the SDK
enables DNS-rebinding protection and only allows `127.0.0.1`/`localhost` Host
headers. Serving from a real hostname? Bind to that interface (e.g.
`MCP_HTTP_HOST=0.0.0.0`) and set `MCP_ALLOWED_HOSTS`/`MCP_ALLOWED_ORIGINS`.

## MCP client configuration

### Claude Desktop / any stdio client

```json
{
  "mcpServers": {
    "itflow": {
      "command": "itflow-mcp-server",
      "env": {
        "ITFLOW_BASE_URL": "https://itflow.example.com",
        "ITFLOW_API_KEY": "your-itflow-api-key",
        "ITFLOW_API_KEY_PASSWORD": "your-decrypt-password"
      }
    }
  }
}
```

(Or point `command` at `python` with `args: ["-m", "itflow_mcp_server"]` and put
the config in a `.env` file.)

### Streamable HTTP client

- URL: `http://<host>:8700/mcp`
- Header: `Authorization: Bearer <MCP_API_KEY>`

```bash
# example with the official mcp CLI / any streamable-HTTP client
export MCP_API_KEY=itflow-mcp-xxxx
```

## Docker

A production `Dockerfile` (multi-stage, non-root, slim) and `docker-compose.yml`
are included. The container serves streamable HTTP on port `8700` by default.

```bash
# 1. configure (same variables as above)
cp .env.example .env   # fill in ITFLOW_BASE_URL, ITFLOW_API_KEY, MCP_API_KEY, ...

# 2. build and run
docker compose up -d --build

# 3. verify
curl http://localhost:8700/health
# → {"status": "ok", "server": "itflow-mcp-server", "version": "1.0.0"}
```

MCP clients connect to `http://<host>:8700/mcp` with
`Authorization: Bearer <MCP_API_KEY>`.

`docker-compose.yml` passes every environment variable through from `.env`
(required ones fail fast with a clear message if unset) and applies container
hardening: non-root user, `cap_drop: ALL`, `no-new-privileges`, read-only root
filesystem, bounded log files, and a `/health`-based healthcheck.

Running without compose:

```bash
docker build -t itflow-mcp-server .
docker run --rm -d --name itflow-mcp -p 8700:8700 --env-file .env \
  -e MCP_HTTP_HOST=0.0.0.0 itflow-mcp-server
```

**Serving behind a real hostname:** DNS-rebinding protection auto-enables for
loopback binds. For a public hostname, set `MCP_ALLOWED_HOSTS` (and
`MCP_ALLOWED_ORIGINS` for browser clients) in `.env`; see the variable table
above. Terminate TLS at a reverse proxy (Caddy/Traefik/nginx) in front of the
container; the server itself speaks plain HTTP.

**stdio in a container** (for MCP clients that spawn processes):

```bash
docker run --rm -i --env-file .env itflow-mcp-server serve
```

## Development

```bash
pip install -e ".[dev]"
pytest            # unit tests (mocked ITFlow) + end-to-end tests
```

The end-to-end suite spawns the real server (stdio and HTTP) against a bundled
mock ITFlow instance (`tests/mock_itflow.py`) that implements the documented
response contract, so no live ITFlow is needed.

## Project layout

```
itflow_mcp_server/
├── __init__.py      # package metadata
├── __main__.py      # CLI: serve, serve-http, gen-key, check
├── config.py        # environment variable handling
├── itflow.py        # async ITFlow v1 API client (httpx)
├── server.py        # MCPServer + tool generation + HTTP auth
└── specs.py         # declarative spec of every ITFlow module/function
tests/
├── mock_itflow.py   # mock ITFlow v1 API for tests
├── test_itflow.py   # client unit tests
└── test_e2e.py      # full server tests (stdio + HTTP)
```

## Security notes

- The ITFlow API key and the MCP API key are only ever read from the
  environment. They are never logged and never a tool parameter.
- `MCP_API_KEY` comparison is constant-time (`hmac.compare_digest`).
- Use HTTPS for ITFlow and for anything beyond localhost; rotate both keys
  regularly (ITFlow docs recommend monthly for ITFlow keys).
- Scope ITFlow keys to a single client where possible; the MCP server respects
  whatever scope the key has.
- `MCP_TOOL_PERMISSIONS` is the first line of defense: the AI only ever sees
  the tools you allow (read-only by default). It complements, not replaces,
  ITFlow's own API-key scoping — use both.

## License

Distributed under the [MIT License](LICENSE). See the `LICENSE` file for full
terms.
