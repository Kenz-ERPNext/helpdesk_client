# Helpdesk Client

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Frappe](https://img.shields.io/badge/Frappe-v16-blue.svg)](https://frappeframework.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)

Helpdesk Client is the **customer-site** half of the QCS AI support pipeline.
Installed on a customer's Frappe/ERPNext site, it exposes a permission-gated
**MCP (Model Context Protocol) server** over that site's data so the QCS Support
Hub can triage and investigate helpdesk tickets against the live system - reading
documents, running reports, and (when explicitly enabled) making changes - all
under per-site access control.

It pairs with the **QCS Support Hub** via Hub-initiated, pre-provisioned Token
authentication, and additionally supports an OAuth connector so the Claude Web
App can connect to the same MCP endpoint.

## Features

- **MCP server over Streamable HTTP** - a single JSON-RPC 2.0 endpoint
  (`initialize` / `tools/list` / `tools/call`) with Redis-backed UUID sessions
  (1-hour TTL) and a Frappe-native auth layer.
- **Read, report, and site tools** - `get_doc`, `get_list`, `get_meta`,
  `get_count`, `get_error_log`, `execute_report`, `get_installed_apps`,
  `get_site_info`, all permission-aware.
- **Guarded write tools** - `set_value`, `set_values`, `create_doc`,
  `delete_doc`, `run_doc_method`, `clear_cache`. Writes run with the calling
  user's permissions and are off by default (`allow_write_operations`).
- **Per-site access control** - an enable switch, a write switch, and a
  blocked/allowed DocType allow-and-block model, all configured from a single
  settings page. Configurable row-limit caps sit under hard safety ceilings.
- **Hub-initiated pairing** - Token-authenticated endpoints for registration,
  deregistration, credential rotation, status, and one-time Desk login, gated to
  the support identity.
- **OAuth 2.0 connector** - discovery, dynamic client registration, an
  authenticated authorize step (login + PKCE), and token exchange for the Claude
  Web App connector.

## How it fits together

```
QCS Support Hub  ──►  MCP endpoint (this app)  ──►  customer site data
  (MCP client)         /api/method/helpdesk_client.mcp.handler.handle
  Token auth           - authenticate → session → tools/call
  QCS Remote Audit     - access_control gates every doctype-scoped tool
  Log (central)        - writes run as the support user, permission-checked
```

The Hub authenticates as the pre-provisioned support user, opens an MCP session,
and calls tools. Every call is logged centrally on the Hub (`QCS Remote Audit
Log`); this app deliberately keeps no local audit DocType.

## DocTypes

| DocType | Purpose |
|---|---|
| `HDS Support Settings` | Single: enable/write switches, Hub pairing, access-control tables, row limits |
| `HDS Blocked DocType` | Child table: DocTypes the MCP server may never touch |
| `HDS Allowed DocType` | Child table: optional allow-list (whitelist mode) |

## Architecture

```
helpdesk_client/
├── api.py                 # Hub-facing endpoints (Token auth) + one-time login + health check
├── setup.py               # after_install / after_uninstall (support user, default settings)
├── token_manager.py       # Deprecated no-op stub (rotation is now Hub-initiated)
├── utils.py               # get_cache, get_settings_limit, normalize_site_url
├── hooks.py               # after_install, before_request (OAuth discovery on v15)
├── patches.txt            # remove_action_log, drop_unused_fields
├── mcp/
│   ├── handler.py         # MCP Streamable-HTTP endpoint (JSON-RPC 2.0)
│   ├── auth.py            # Token / Bearer(key:secret) / Bearer(OAuth) authentication
│   ├── session.py        # Redis-backed UUID sessions (1h TTL)
│   ├── protocol.py       # JSON-RPC 2.0 constants + envelope helpers
│   ├── access_control.py # enabled / write / block / allow enforcement
│   ├── oauth.py          # OAuth 2.0 endpoints for the Claude Web App connector
│   └── tools/
│       ├── __init__.py       # tool registry + execute_tool (access-control chokepoint)
│       ├── data_tools.py     # get_doc, get_list, get_meta, get_count, get_error_log
│       ├── report_tools.py   # execute_report
│       ├── site_tools.py     # get_installed_apps, get_site_info
│       └── write_tools.py    # set_value(s), create_doc, delete_doc, run_doc_method, clear_cache
└── helpdesk_client/doctype/   # HDS Support Settings + child tables
```

### Authentication

`mcp/auth.py` accepts three `Authorization` forms and sets the Frappe user for
the request:

1. `Token <api_key>:<api_secret>` - Frappe API keys (the Hub path).
2. `Bearer <api_key>:<api_secret>` - same credentials via `mcp-remote`.
3. `Bearer <oauth_token>` - a Frappe OAuth Bearer Token (the Claude Web App path).

### Access control

`mcp/tools/__init__.py::execute_tool` calls `access_control.check_doctype_access`
for every doctype-scoped tool. It enforces, in order: the site `enabled` switch,
`allow_write_operations` for write tools, the blocked-DocType list, and - when a
non-empty allow-list is configured - whitelist mode. Tools then run as the
authenticated user, so Frappe's own permission engine applies on top.

### OAuth connector (Claude Web App)

`mcp/oauth.py` serves OAuth Authorization Server Metadata and implements dynamic
client registration, an **authenticated** authorization step, and token
exchange. `authorize()` requires a logged-in System Manager (or the support
user) before issuing a code; codes are bound to the user, `redirect_uri` is
validated against the registered client, and token exchange verifies PKCE (S256).

## Whitelisted API methods

```python
# Hub-facing (Token auth as support@quarkcs.com; gated by _require_support_user)
helpdesk_client.api.register_connection(hub_url, client_id)
helpdesk_client.api.deregister()
helpdesk_client.api.rotate_credentials(new_api_key, new_api_secret)
helpdesk_client.api.get_support_status()
helpdesk_client.api.generate_login_url()

# Guest
helpdesk_client.api.health_check()
helpdesk_client.api.one_time_login(key)

# MCP endpoint
helpdesk_client.mcp.handler.handle()          # JSON-RPC 2.0 MCP server

# OAuth 2.0 (Claude Web App connector)
helpdesk_client.mcp.oauth.discovery()
helpdesk_client.mcp.oauth.register()
helpdesk_client.mcp.oauth.authorize()
helpdesk_client.mcp.oauth.token()
```

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench --site [site-name] install-app helpdesk_client
```

`after_install` creates the API-only `support@quarkcs.com` user and seeds default
`HDS Support Settings` (including the default blocked doctypes). API credentials
are **not** generated here - they are provisioned during Hub onboarding and are
never written to logs.

## Configuration

1. **Enable and scope access** - open **HDS Support Settings** and set `Enabled`.
   Leave `Allow Write Operations` off unless the site should accept MCP writes.
   Add DocTypes to **Blocked DocTypes**, or use **Allowed DocTypes** for strict
   whitelist mode. Tune the row limits (0 = only the hard ceiling applies).
2. **Pair with the Hub** - the Hub admin generates this site's API key/secret
   (User → API Access), pastes them into the QCS Support Connection on the Hub,
   and calls `register_connection`, which records `hub_url` / `client_id`.
3. **MCP endpoint** - the server is reachable at
   `/api/method/helpdesk_client.mcp.handler.handle`.

## Development

Run from the bench root:

```bash
bench --site [site-name] install-app helpdesk_client
bench --site [site-name] migrate
bench --site [site-name] run-tests --app helpdesk_client
bench --site [site-name] clear-cache
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install
pre-commit](https://pre-commit.com/#installation) and enable it for this
repository:

```bash
cd apps/helpdesk_client
pre-commit install
```

Pre-commit is configured to use ruff, eslint, prettier and pyupgrade.

### CI

- **CI** - installs the app and runs unit tests on every push to `develop`.
- **Linters** - [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules)
  and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

### License

This project is licensed under the [GNU Affero General Public License v3.0](license.txt).

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).

---

<p align="center">
  <strong>Quark Cyber Systems FZC</strong><br>
  <a href="mailto:support@quarkcs.com">support@quarkcs.com</a><br>
  <sub>&copy; 2026 Quark Cyber Systems FZC. All rights reserved.</sub>
</p>
