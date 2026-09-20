# Copyright (c) 2026, Wahni IT Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk_client.setup import create_genie_folder


class TestSupportFolder(FrappeTestCase):
	def test_folder_created(self):
		create_genie_folder()
		self.assertTrue(frappe.db.exists("File", {"file_name": "Genie", "is_folder": 1}))

	def test_idempotent(self):
		create_genie_folder()
		create_genie_folder()
		count = frappe.db.count("File", {"file_name": "Genie", "is_folder": 1, "folder": "Home"})
		self.assertEqual(count, 1)
