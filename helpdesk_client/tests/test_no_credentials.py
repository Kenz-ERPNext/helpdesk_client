# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

FORBIDDEN_FIELDS = {
	"support_api_token",
	"support_url",
	"portal_user",
	"portal_user_password",
}


class TestNoStoredCredentials(FrappeTestCase):
	"""The customer site must hold no API reference of any kind. The Hub
	reaches in over MCP using a key stored on the Hub, never the reverse."""

	def test_settings_store_no_credentials(self):
		meta = frappe.get_meta("HDS Support Settings")
		present = {df.fieldname for df in meta.fields} & FORBIDDEN_FIELDS
		self.assertEqual(
			present,
			set(),
			f"HDS Support Settings must hold no credentials, found: {sorted(present)}",
		)

	def test_settings_save_makes_no_outbound_call(self):
		import helpdesk_client.helpdesk_client.doctype.hds_support_settings.hds_support_settings as module

		self.assertFalse(
			hasattr(module, "make_request"),
			"the settings controller must not import make_request",
		)
		self.assertFalse(
			hasattr(module.HDSSupportSettings, "validate_sp_access"),
			"validate_sp_access made an outbound call on every save",
		)

	def test_no_credentials_left_in_the_database(self):
		"""`Singles` is a bare table, not a DocType, so query it directly."""
		rows = frappe.db.sql(
			"""
			SELECT field FROM `tabSingles`
			WHERE doctype = 'HDS Support Settings' AND field IN %(fields)s
			""",
			{"fields": tuple(FORBIDDEN_FIELDS)},
			as_dict=True,
		)
		leftovers = [r.field for r in rows]
		self.assertEqual(leftovers, [], f"stale credential values remain: {leftovers}")
