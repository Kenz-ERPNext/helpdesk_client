# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""API endpoints for Helpdesk Client."""

import frappe
from frappe.utils import now_datetime

SUPPORT_USER = "support@quarkcs.com"


@frappe.whitelist(allow_guest=True)
def health_check():
	"""Health check endpoint - used by Hub's daily ping."""
	settings = frappe.get_single("HDS Support Settings")
	return {
		"status": "ok" if settings.enabled else "disabled",
		"site": frappe.local.site,
		"client_id": settings.client_id or "",
	}


def _require_support_user():
	"""Block all non-Token-auth access: only the Hub (acting as support@quarkcs.com) can call."""
	if frappe.session.user != SUPPORT_USER:
		frappe.throw(
			f"This endpoint must be called by {SUPPORT_USER} via API Token auth.",
			frappe.PermissionError,
		)


@frappe.whitelist()
def register_connection(hub_url=None, client_id=None):
	"""Hub-initiated connection handshake.

	Authenticated via standard Token auth (api_key:api_secret for support@quarkcs.com).
	The Hub admin pre-provisions those credentials by:
	  1. generating them on the customer site via User -> API Access, and
	  2. pasting them into QCS Support Connection on the Hub.

	This endpoint only records the hub_url and client_id so the customer site
	knows who it is paired with. No secrets are exchanged here.
	"""
	_require_support_user()

	if not hub_url or not client_id:
		frappe.throw("hub_url and client_id are required")

	settings = frappe.get_single("HDS Support Settings")

	if not settings.enabled:
		frappe.throw("Helpdesk Support is not enabled on this site", frappe.PermissionError)

	if not settings.qcs_hub_url:
		frappe.throw("Hub URL is not configured on this site", frappe.PermissionError)

	from helpdesk_client.utils import normalize_site_url

	if normalize_site_url(hub_url) != normalize_site_url(settings.qcs_hub_url):
		frappe.throw("Hub URL does not match the configured Hub URL", frappe.PermissionError)

	settings.client_id = client_id
	settings.contract_active = 1
	settings.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "registered",
		"site": frappe.local.site,
		"client_id": client_id,
	}


@frappe.whitelist()
def deregister():
	"""Hub-initiated deregistration.

	Authenticated via Token auth. Clears client_id and contract_active so the
	customer site stops reporting itself as paired with a Hub. Does NOT revoke
	the API keys - the customer admin can do that via User -> API Access if
	they want to fully cut off Hub access.
	"""
	_require_support_user()

	settings = frappe.get_single("HDS Support Settings")
	settings.client_id = ""
	settings.contract_active = 0
	settings.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "deregistered", "site": frappe.local.site}


@frappe.whitelist()
def rotate_credentials(new_api_key=None, new_api_secret=None):
	"""Hub-initiated credential rotation.

	Authenticated via standard Token auth with the CURRENT api_key:api_secret.
	The Hub generates the new credentials, calls this endpoint, and on success
	starts using the new credentials for all subsequent calls.
	"""
	_require_support_user()

	if not new_api_key or not new_api_secret:
		frappe.throw("new_api_key and new_api_secret are required")

	user = frappe.get_doc("User", SUPPORT_USER)
	user.api_key = new_api_key
	user.api_secret = new_api_secret
	user.save(ignore_permissions=True)

	settings = frappe.get_single("HDS Support Settings")
	settings.last_token_rotation = now_datetime()
	settings.rotation_status = "Success"
	settings.rotation_error = ""
	settings.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "rotated", "rotated_at": str(now_datetime())}


@frappe.whitelist()
def get_support_status():
	"""Get current support status for the site admin dashboard."""
	settings = frappe.get_single("HDS Support Settings")
	return {
		"enabled": settings.enabled,
		"contract_active": settings.contract_active,
		"hub_url": settings.qcs_hub_url or "",
		"client_id": settings.client_id or "",
		"allow_write_operations": settings.allow_write_operations,
		"last_token_rotation": str(settings.last_token_rotation) if settings.last_token_rotation else "",
		"rotation_status": settings.rotation_status or "",
	}


@frappe.whitelist()
def generate_login_url():
	"""Generate a one-time login URL for the support user.

	Called by the Hub (authenticated as support@quarkcs.com via Token auth)
	to let agents login to the customer site without sharing credentials.
	"""
	_require_support_user()

	from frappe.utils import get_url

	from helpdesk_client.utils import get_cache

	key = frappe.generate_hash(length=32)
	get_cache().set_value("one_time_login:%s" % key, SUPPORT_USER, expires_in_sec=300)

	login_url = get_url("/api/method/helpdesk_client.api.one_time_login?key=%s" % key)
	return {"login_url": login_url, "expires_in": 300}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def one_time_login(key=None):
	"""One-time login endpoint. Redirects to Desk after authentication.

	The key is validated against the cache and can only be used once.
	"""
	from werkzeug.wrappers import Response

	from helpdesk_client.utils import get_cache

	if not key:
		frappe.throw("Missing login key")

	cache = get_cache()
	cache_key = "one_time_login:%s" % key
	user = cache.get_value(cache_key)

	if not user:
		frappe.throw("Invalid or expired login key")

	# Delete the key so it can't be reused
	cache.delete_value(cache_key)

	# Log the user in
	frappe.local.login_manager.login_as(user)

	# Redirect to Desk
	from frappe.utils import get_url

	return Response("", status=302, headers={"Location": get_url("/app")})


@frappe.whitelist()
def enroll_with_hub(enrollment_key=None):
	"""Client-initiated automatic pairing with the Hub.

	Run by a System Manager on the customer site. Generates fresh API
	credentials for the support user, pushes them to the Hub's enroll_client
	endpoint (authenticated by the shared enrollment key), and stores the
	returned client_id — the whole manual handshake in one call.
	"""
	import requests

	frappe.only_for("System Manager")

	settings = frappe.get_single("HDS Support Settings")
	if not settings.enabled:
		frappe.throw("Helpdesk Support is not enabled on this site")
	if not settings.qcs_hub_url:
		frappe.throw("Hub URL is not configured")
	if not enrollment_key:
		frappe.throw("Enrollment key is required — get it from the Hub's HDS Hub Settings")

	if not frappe.db.exists("User", SUPPORT_USER):
		frappe.throw(f"{SUPPORT_USER} does not exist on this site")

	# Fresh credentials on every enrollment: the Hub is the only holder.
	user = frappe.get_doc("User", SUPPORT_USER)
	api_key = frappe.generate_hash(length=15)
	api_secret = frappe.generate_hash(length=15)
	user.api_key = api_key
	user.api_secret = api_secret
	user.save(ignore_permissions=True)
	frappe.db.commit()

	hub_url = settings.qcs_hub_url.rstrip("/")
	try:
		response = requests.post(
			f"{hub_url}/api/method/helpdesk.hub_api.enroll_client",
			json={
				"enrollment_key": enrollment_key,
				"site_url": frappe.utils.get_url(),
				"customer_name": frappe.local.site,
				"api_key": api_key,
				"api_secret": api_secret,
			},
			timeout=30,
		)
	except requests.RequestException as e:
		frappe.throw(f"Could not reach the Hub: {e}")

	if response.status_code != 200:
		frappe.throw(f"Hub refused enrollment: {response.text[:400]}")

	result = response.json().get("message", {})
	client_id = result.get("client_id")
	if not client_id:
		frappe.throw(f"Hub did not return a client_id: {response.text[:400]}")

	settings.client_id = client_id
	settings.contract_active = 1
	settings.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "enrolled", "client_id": client_id, "hub_url": hub_url}
