# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""Shared helpers for the Helpdesk Client app."""


def get_cache():
	"""Return Frappe's cache instance, compatible with v14 and v15+.

	v14 exposes ``frappe.cache`` as a callable returning the cache instance,
	while v15+ exposes it as the instance directly.
	"""
	import frappe

	return frappe.cache() if callable(frappe.cache) else frappe.cache


def get_settings_limit(fieldname: str, default: int, ceiling: int) -> int:
	"""Read an integer row limit from HDS Support Settings.

	Rules:
	- empty / unset  -> return ``default``
	- positive value -> return min(value, ceiling)
	- 0              -> return ``ceiling`` (admin explicitly opted out of the
	                    customer-side cap, so the only remaining guard is the
	                    hardcoded safety ceiling)
	- lookup error   -> return ``default``
	"""
	import frappe

	try:
		value = frappe.db.get_single_value("HDS Support Settings", fieldname)
		if value is None or value == "":
			return default
		v = int(value)
		if v == 0:
			return ceiling
		if v > 0:
			return min(v, ceiling)
	except Exception:
		pass
	return default


def normalize_site_url(raw: str | None) -> str | None:
	"""Normalize a URL entered by an admin.

	Accepts forms like "example.com", "https://example.com/", etc. and returns
	a base URL with scheme and no trailing slash. If scheme is omitted, it is
	inferred as http for *.localhost hosts and https otherwise.
	"""
	if not raw:
		return raw
	value = raw.strip().rstrip("/")
	if not value:
		return value
	if "://" in value:
		return value
	host = value.split("/")[0]
	scheme = "http" if "localhost" in host.lower() else "https"
	return f"{scheme}://{value}"
