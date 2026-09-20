# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""OAuth 2.0 endpoints for Claude Web App MCP connector.

Provides the minimum OAuth endpoints required by Claude Web App to connect
to the MCP server. Works on Frappe v15 (which lacks built-in OAuth metadata)
and v16 (where it supplements Frappe's OAuth if needed).

Flow:
1. Claude discovers OAuth via /.well-known/oauth-authorization-server
2. Claude registers as a client via /api/method/helpdesk_client.mcp.oauth.register
3. Claude redirects user to /api/method/helpdesk_client.mcp.oauth.authorize
4. User auto-approves (support user only), gets redirected back with auth code
5. Claude exchanges code for access token via /api/method/helpdesk_client.mcp.oauth.token
6. Claude uses Bearer token (api_key:api_secret) in MCP requests
"""

import hmac
import json
from urllib.parse import quote

import frappe
from werkzeug.wrappers import Response

from helpdesk_client.utils import get_cache

SUPPORT_USER = "support@quarkcs.com"


def _is_authorized_oauth_user(user):
	"""Only a real, privileged, logged-in user may complete the OAuth flow.

	The support user itself is API-only (no interactive password), so the human
	completing the connection logs in with their own System Manager account on
	this site. Guests are never authorized.
	"""
	if not user or user == "Guest":
		return False
	if user == SUPPORT_USER:
		return True
	return "System Manager" in frappe.get_roles(user)


def before_request_handler():
	"""Intercept .well-known OAuth discovery requests on Frappe v15.

	On v16, Frappe handles this natively via handle_wellknown in app.py.
	On v15, we intercept the request here and return our OAuth metadata.
	"""
	if not frappe.request:
		return

	path = frappe.request.path
	if path != "/.well-known/oauth-authorization-server":
		return

	# Check if Frappe v16 handles this natively (has handle_wellknown)
	try:
		import importlib

		oauth2_mod = importlib.import_module("frappe.integrations.oauth2")
		if hasattr(oauth2_mod, "handle_wellknown"):
			# v16 - let Frappe handle it
			return
	except ImportError:
		pass

	# v15 - handle it ourselves
	site_url = frappe.utils.get_url()
	metadata = {
		"issuer": site_url,
		"authorization_endpoint": site_url + "/api/method/helpdesk_client.mcp.oauth.authorize",
		"token_endpoint": site_url + "/api/method/helpdesk_client.mcp.oauth.token",
		"registration_endpoint": site_url + "/api/method/helpdesk_client.mcp.oauth.register",
		"response_types_supported": ["code"],
		"grant_types_supported": ["authorization_code"],
		"code_challenge_methods_supported": ["S256"],
		"token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
	}

	# Raise HTTPException with our response to short-circuit request processing
	from werkzeug.exceptions import HTTPException

	resp = Response(
		json.dumps(metadata),
		status=200,
		headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
	)
	exc = HTTPException(response=resp)
	raise exc


@frappe.whitelist(allow_guest=True, methods=["GET"])
def discovery():
	"""OAuth 2.0 Authorization Server Metadata.

	This is called via website_route_rules mapping from
	/.well-known/oauth-authorization-server
	"""
	site_url = frappe.utils.get_url()
	metadata = {
		"issuer": site_url,
		"authorization_endpoint": site_url + "/api/method/helpdesk_client.mcp.oauth.authorize",
		"token_endpoint": site_url + "/api/method/helpdesk_client.mcp.oauth.token",
		"registration_endpoint": site_url + "/api/method/helpdesk_client.mcp.oauth.register",
		"response_types_supported": ["code"],
		"grant_types_supported": ["authorization_code"],
		"code_challenge_methods_supported": ["S256"],
		"token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
	}
	return Response(
		json.dumps(metadata),
		status=200,
		headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
	)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def register():
	"""OAuth 2.0 Dynamic Client Registration (RFC 7591)."""
	body = frappe.request.get_data()
	try:
		data = json.loads(body)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return Response(
			json.dumps({"error": "invalid_request"}),
			status=400,
			headers={"Content-Type": "application/json"},
		)

	client_id = frappe.generate_hash(length=20)
	client_secret = frappe.generate_hash(length=20)

	# Store client in cache (expires in 24h)
	get_cache().set_value(
		"mcp_oauth_client:%s" % client_id,
		{
			"client_secret": client_secret,
			"client_name": data.get("client_name", "unknown"),
			"redirect_uris": data.get("redirect_uris", []),
		},
		expires_in_sec=86400,
	)

	result = {
		"client_id": client_id,
		"client_secret": client_secret,
		"client_name": data.get("client_name", "unknown"),
		"redirect_uris": data.get("redirect_uris", []),
		"grant_types": ["authorization_code"],
		"response_types": ["code"],
		"token_endpoint_auth_method": "client_secret_post",
	}

	return Response(
		json.dumps(result),
		status=201,
		headers={"Content-Type": "application/json"},
	)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def authorize():
	"""OAuth 2.0 Authorization Endpoint.

	Requires an authenticated, privileged session before issuing a code.
	Unauthenticated callers are redirected to /login and returned here after
	logging in. The code is bound to the authenticated user and (if supplied)
	the PKCE challenge, and only maps to support credentials at /token.
	"""
	redirect_uri = frappe.request.args.get("redirect_uri", "")
	state = frappe.request.args.get("state", "")
	client_id = frappe.request.args.get("client_id", "")
	code_challenge = frappe.request.args.get("code_challenge", "")
	code_challenge_method = frappe.request.args.get("code_challenge_method", "")

	if not redirect_uri:
		return Response(
			json.dumps({"error": "invalid_request", "error_description": "missing redirect_uri"}),
			status=400,
			headers={"Content-Type": "application/json"},
		)

	# Require an authenticated session - bounce guests to login and return here.
	if frappe.session.user == "Guest":
		return_to = frappe.request.full_path.rstrip("?")
		login_url = "/login?redirect-to=" + quote(return_to, safe="")
		return Response("", status=302, headers={"Location": login_url})

	# Only a privileged, allow-listed user may approve the connection.
	if not _is_authorized_oauth_user(frappe.session.user):
		return Response(
			json.dumps(
				{
					"error": "access_denied",
					"error_description": "You are not permitted to authorize Helpdesk Support access.",
				}
			),
			status=403,
			headers={"Content-Type": "application/json"},
		)

	# Validate redirect_uri against the client registered via /register.
	client = get_cache().get_value("mcp_oauth_client:%s" % client_id) if client_id else None
	if not client or redirect_uri not in (client.get("redirect_uris") or []):
		return Response(
			json.dumps(
				{
					"error": "invalid_request",
					"error_description": "redirect_uri is not registered for this client",
				}
			),
			status=400,
			headers={"Content-Type": "application/json"},
		)

	# Generate auth code, bound to the authenticated user (+ PKCE challenge).
	code = frappe.generate_hash(length=20)
	get_cache().set_value(
		"mcp_oauth_code:%s" % code,
		{
			"client_id": client_id,
			"redirect_uri": redirect_uri,
			"user": frappe.session.user,
			"code_challenge": code_challenge,
			"code_challenge_method": code_challenge_method,
		},
		expires_in_sec=300,
	)

	# Approve and redirect back with the code.
	separator = "&" if "?" in redirect_uri else "?"
	location = redirect_uri + separator + "code=" + code
	if state:
		location += "&state=" + state

	return Response("", status=302, headers={"Location": location})


@frappe.whitelist(allow_guest=True, methods=["POST"])
def token():
	"""OAuth 2.0 Token Endpoint.

	Exchanges authorization code for an access token.
	The access token is the support user's api_key:api_secret.
	"""
	grant_type = frappe.form_dict.get("grant_type", "")
	code = frappe.form_dict.get("code", "")
	redirect_uri = frappe.form_dict.get("redirect_uri", "")
	code_verifier = frappe.form_dict.get("code_verifier", "")

	if grant_type != "authorization_code":
		return Response(
			json.dumps({"error": "unsupported_grant_type"}),
			status=400,
			headers={"Content-Type": "application/json"},
		)

	# Validate auth code
	cache_key = "mcp_oauth_code:%s" % code
	code_data = get_cache().get_value(cache_key)
	if not code_data:
		return Response(
			json.dumps({"error": "invalid_grant"}),
			status=400,
			headers={"Content-Type": "application/json"},
		)

	# Delete code (single use) - do this before any further validation so a
	# failed exchange can't be retried against the same code.
	get_cache().delete_value(cache_key)

	def _invalid_grant(desc):
		return Response(
			json.dumps({"error": "invalid_grant", "error_description": desc}),
			status=400,
			headers={"Content-Type": "application/json"},
		)

	# redirect_uri must match the value the code was issued for.
	if code_data.get("redirect_uri") and redirect_uri != code_data["redirect_uri"]:
		return _invalid_grant("redirect_uri mismatch")

	# PKCE: if a challenge was issued at /authorize, require a matching verifier.
	challenge = code_data.get("code_challenge")
	if challenge:
		if not code_verifier:
			return _invalid_grant("missing code_verifier")
		method = (code_data.get("code_challenge_method") or "plain").upper()
		if method == "S256":
			import base64
			import hashlib

			digest = hashlib.sha256(code_verifier.encode()).digest()
			computed = base64.urlsafe_b64encode(digest).decode().rstrip("=")
		else:
			computed = code_verifier
		if not hmac.compare_digest(computed, challenge):
			return _invalid_grant("PKCE verification failed")

	# Get support user credentials
	from frappe.utils.password import get_decrypted_password

	if not frappe.db.exists("User", SUPPORT_USER):
		return Response(
			json.dumps({"error": "server_error", "error_description": "Support user not configured"}),
			status=500,
			headers={"Content-Type": "application/json"},
		)

	user = frappe.get_doc("User", SUPPORT_USER)
	api_secret = get_decrypted_password("User", SUPPORT_USER, "api_secret", raise_exception=False)

	if not user.api_key or not api_secret:
		return Response(
			json.dumps(
				{
					"error": "server_error",
					"error_description": "API credentials not generated. Run registration first.",
				}
			),
			status=500,
			headers={"Content-Type": "application/json"},
		)

	# The access token IS api_key:api_secret - our MCP auth handler accepts Bearer with this format
	access_token = user.api_key + ":" + api_secret

	result = {
		"access_token": access_token,
		"token_type": "Bearer",
		"expires_in": 604800,
	}

	return Response(
		json.dumps(result),
		status=200,
		headers={"Content-Type": "application/json"},
	)
