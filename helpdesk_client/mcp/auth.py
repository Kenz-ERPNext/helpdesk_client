# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""MCP request authentication.

Supports three auth methods:
1. Token auth: Authorization: Token <api_key>:<api_secret> (Frappe API keys)
2. Bearer with API keys: Authorization: Bearer <api_key>:<api_secret> (from mcp-remote)
3. Bearer OAuth: Authorization: Bearer <oauth_token> (from Claude Web App via Frappe OAuth)
"""

import frappe
from frappe.utils.password import get_decrypted_password


def authenticate_request():
	"""Authenticate the current request using the Authorization header.

	Returns the authenticated username.
	Raises frappe.AuthenticationError on failure.
	"""
	auth_header = frappe.get_request_header("Authorization")
	if not auth_header:
		frappe.throw("Missing Authorization header", frappe.AuthenticationError)

	parts = auth_header.split(" ", 1)
	if len(parts) != 2:
		frappe.throw("Invalid Authorization header format", frappe.AuthenticationError)

	auth_type = parts[0].lower()
	credentials = parts[1]

	if auth_type == "token":
		return _authenticate_token(credentials)
	elif auth_type == "bearer":
		# Try API key format first (key:secret), then OAuth token
		if ":" in credentials:
			return _authenticate_token(credentials)
		else:
			return _authenticate_oauth_bearer(credentials)
	else:
		frappe.throw("Unsupported auth type: %s" % auth_type, frappe.AuthenticationError)


def _authenticate_token(credentials):
	"""Authenticate using api_key:api_secret format."""
	if ":" not in credentials:
		frappe.throw("Credentials must be in format api_key:api_secret", frappe.AuthenticationError)

	api_key, api_secret = credentials.split(":", 1)

	user = frappe.db.get_value("User", {"api_key": api_key, "enabled": True}, "name")
	if not user:
		frappe.throw("Invalid API key", frappe.AuthenticationError)

	stored_secret = get_decrypted_password("User", user, fieldname="api_secret", raise_exception=False)
	if not stored_secret or api_secret != stored_secret:
		frappe.throw("Invalid API secret", frappe.AuthenticationError)

	frappe.set_user(user)
	return user


def _authenticate_oauth_bearer(token):
	"""Authenticate using an OAuth Bearer token from Frappe's OAuth provider.

	Looks up the token in Frappe's OAuth Bearer Token table.
	"""
	try:
		token_doc = frappe.db.get_value(
			"OAuth Bearer Token",
			{"access_token": token, "status": "Active"},
			["user", "expiration_time"],
			as_dict=True,
		)

		if not token_doc:
			frappe.throw("Invalid or expired OAuth token", frappe.AuthenticationError)

		# Check expiry
		from frappe.utils import now_datetime

		if token_doc.expiration_time and now_datetime() > token_doc.expiration_time:
			frappe.throw("OAuth token expired", frappe.AuthenticationError)

		frappe.set_user(token_doc.user)
		return token_doc.user

	except frappe.AuthenticationError:
		raise
	except Exception as e:
		frappe.throw("OAuth authentication failed: %s" % str(e), frappe.AuthenticationError)
