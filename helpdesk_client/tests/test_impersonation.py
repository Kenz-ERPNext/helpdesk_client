# Copyright (c) 2026, Wahni IT Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk_client.utils.impersonation import generate_impersonation_url


class TestImpersonation(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_requires_system_manager(self):
		# frappe.only_for() is a no-op under frappe.flags.in_test, so the
		# System Manager gate can't be exercised by switching users here.
		# Instead assert the function calls only_for("System Manager") as its
		# first gate and propagates the PermissionError it raises.
		with patch(
			"helpdesk_client.utils.impersonation.frappe.only_for",
			side_effect=frappe.PermissionError,
		) as mock_only_for:
			with self.assertRaises(frappe.PermissionError):
				generate_impersonation_url("some-user@example.com")
		mock_only_for.assert_called_once_with("System Manager")

	def test_blocked_when_disabled(self):
		frappe.db.set_single_value("HDS Support Settings", "enable_user_impersonation", 0)
		with self.assertRaises(frappe.ValidationError):
			generate_impersonation_url("Administrator")

	def test_cannot_impersonate_administrator(self):
		frappe.db.set_single_value("HDS Support Settings", "enable_user_impersonation", 1)
		with self.assertRaises(frappe.ValidationError):
			generate_impersonation_url("Administrator")

	def test_generates_link_for_regular_user(self):
		frappe.db.set_single_value("HDS Support Settings", "enable_user_impersonation", 1)
		url = generate_impersonation_url("Guest")
		self.assertIn("login_via_key?key=", url)
