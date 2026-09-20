# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

import frappe

CREDENTIAL_FIELDS = (
	"support_api_token",
	"support_url",
	"portal_user",
	"portal_user_password",
)


def execute():
	"""Remove credentials left over from the pre-zero-key ticket flow.

	Dropping a field from the DocType JSON does not delete its stored
	value — it lingers in `tabSingles` and, for Password fields, in the
	encrypted `__Auth` table. The client makes no outbound calls now, so
	these are dead weight and unnecessary exposure on a customer's server.
	"""
	frappe.db.delete(
		"Singles",
		{"doctype": "HDS Support Settings", "field": ("in", CREDENTIAL_FIELDS)},
	)

	for fieldname in CREDENTIAL_FIELDS:
		frappe.db.delete(
			"__Auth",
			{
				"doctype": "HDS Support Settings",
				"name": "HDS Support Settings",
				"fieldname": fieldname,
			},
		)

	frappe.clear_cache(doctype="HDS Support Settings")
