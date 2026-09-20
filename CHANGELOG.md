# Changelog

All notable changes to the Helpdesk Client app are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project aims to follow Frappe's `16.0.x` versioning.

## [16.0.2] - 2026-07-13

Security hardening of the MCP server. Closes two independent, live issues found
in review: the OAuth connector minted permanent support credentials to
unauthenticated callers, and the write tools executed with permissions disabled.
Both are now closed without changing the Claude Web App connect flow or the
Hub-provisioned Token-auth path.

### Security
- **OAuth authorize endpoint now requires an authenticated, privileged session.**
  `mcp/oauth.py::authorize()` previously auto-approved any caller and issued an
  authorization code, which `token()` exchanged for `support@quarkcs.com`'s
  permanent `api_key:api_secret` - three unauthenticated HTTP calls to a known
  URL were enough to walk away with the support identity. `authorize()` now
  redirects guests to `/login?redirect-to=<authorize URL>` and, after login,
  requires the session user to be **System Manager** or the support user
  (`_is_authorized_oauth_user`) before a code is issued. The support user is
  API-only (no interactive password), so the human completing the connection
  logs in with their own System Manager account - no privilege escalation, since
  a System Manager already has full access to their own site.
- **Write tools no longer bypass Frappe permissions.** `mcp/tools/write_tools.py`
  `set_values`, `create_doc`, and `delete_doc` dropped `ignore_permissions=True`;
  they now execute as the calling user and raise the normal `PermissionError`
  when that user lacks doctype/field rights. `check_doctype_access()` remains as
  a narrowing allow/block layer **on top of** real permissions, not a
  replacement for them. (`set_value` was already permission-safe - it routes
  through `frappe.client.set_value` → `doc.save()`.)
- **`run_doc_method` gained a method allowlist.** It previously invoked any
  attribute that passed `hasattr`. It now permits only the lifecycle methods
  `submit` / `cancel` or methods explicitly decorated with `@frappe.whitelist()`,
  and runs `doc.check_permission("read")` first. Arbitrary controller methods
  are rejected with `PermissionError`.

### Changed
- **OAuth code exchange is bound and PKCE-verified.** The authorization code is
  now bound to the authenticated user and the `redirect_uri` is validated
  against the client registered via `/register` (previously ignored).
  `token()` enforces the `redirect_uri` match, verifies **PKCE (S256)** when a
  challenge was supplied, and burns the code before validation so a failed
  exchange cannot be replayed.
- **`set_value` tool description** no longer demonstrates writing `status` on a
  submittable document (a GL-corrupting anti-pattern); it points at
  `run_doc_method` with `submit` / `cancel` instead.

### Notes
- The access token returned by `token()` is still the support user's
  `api_key:api_secret`, so the advertised `expires_in` remains cosmetic. Making
  it a short-lived, self-expiring token (minting a Frappe OAuth Bearer Token) is
  a planned follow-up; the critical exposure - unauthenticated access - is closed
  by this release.
- The MCP audit trail lives in the Hub (`QCS Remote Audit Log`), written by the
  Hub's MCP client on every call; this app intentionally keeps no local audit
  DocType (see 16.0.1).

## [16.0.1] - 2026-04-26

Initial consolidated release. Helpdesk Client is the customer-site half of the
QCS AI support pipeline: it exposes a read/write **MCP (Model Context Protocol)
server** over the site's data, gated by per-site access control, and pairs with
the QCS Support Hub via Hub-initiated, pre-provisioned Token authentication.

### Added - MCP server
- **Streamable-HTTP MCP endpoint** (`mcp/handler.py`) implementing JSON-RPC 2.0
  `initialize`, `notifications/initialized`, `tools/list`, and `tools/call`, with
  UUID4 sessions held in Redis for 1 hour (`mcp/session.py`) and a small
  protocol/error-code layer (`mcp/protocol.py`).
- **Request authentication** (`mcp/auth.py`) accepting `Token api_key:api_secret`,
  `Bearer api_key:api_secret`, and `Bearer <oauth_token>` (Frappe OAuth Bearer
  Token) forms.
- **Read tools** (`mcp/tools/data_tools.py`): `get_doc`, `get_list`, `get_meta`,
  `get_count`, `get_error_log` - permission-aware via `frappe.get_list` /
  `doc.check_permission`.
- **Report tool** (`mcp/tools/report_tools.py`): `execute_report`, inheriting
  report-level permissions from `frappe.desk.query_report`.
- **Site tools** (`mcp/tools/site_tools.py`): `get_installed_apps`, `get_site_info`.
- **Write tools** (`mcp/tools/write_tools.py`): `set_value`, `set_values`,
  `create_doc`, `delete_doc`, `run_doc_method`, `clear_cache`.
- **Configurable row-limit ceilings** with per-site caps under a hard ceiling
  (`utils.get_settings_limit`): list (5000), error log (500), report rows (10000).

### Added - Access control
- **`HDS Support Settings` (Single)** with `enabled`, `allow_write_operations`
  (default off), a blocked/allowed DocType allow-and-block model
  (`HDS Blocked DocType` / `HDS Allowed DocType` child tables), the Hub pairing
  fields (`qcs_hub_url`, `client_id`, `contract_active`), token-rotation status,
  and the row-limit fields.
- **`access_control.check_doctype_access`** enforcing enabled/write/block/allow
  before any doctype-scoped tool runs.
- **Default blocked doctypes** seeded on install (User, Email Account, Email
  Domain, OAuth Client, Social Login Key).

### Added - Hub integration (Token auth)
- **`api.py` Hub-facing endpoints**, all gated on `_require_support_user()`:
  `register_connection`, `deregister`, `rotate_credentials`,
  `get_support_status`, and `generate_login_url` - plus a guest `health_check`.
- **One-time login** (`api.one_time_login`): the Hub mints a short-lived key so an
  agent can open a Desk session as the support user without sharing credentials.
- **Support user provisioning** (`setup.py`): `after_install` creates an API-only
  `support@quarkcs.com` System User (System Manager, no password, no welcome
  email - credentials are provisioned out-of-band by the Hub, never logged) and
  seeds default settings; `after_uninstall` disables the user.

### Added - OAuth connector (Claude Web App)
- **OAuth 2.0 endpoints** (`mcp/oauth.py`): `discovery`, dynamic client
  `register`, `authorize`, `token`, plus a `before_request` interceptor that
  serves `/.well-known/oauth-authorization-server` on Frappe v15 (v16 serves it
  natively). Lets the Claude Web App connect to the MCP endpoint.

### Removed
- **Client-side audit logging** (`QCS Support Action Log` + `mcp/audit.py`).
  The MCP audit trail is owned centrally by the Hub (`QCS Remote Audit Log`);
  the `remove_action_log` patch drops the legacy local DocType.

### Notes
- API credentials are Hub-provisioned per site and never seeded or logged.
- Compatible with Frappe v14-v16 (`get_cache` shims the v14/v15+ cache API);
  developed and run on v16.
