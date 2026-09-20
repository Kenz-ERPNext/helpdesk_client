# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSupportTicket(FrappeTestCase):
	def test_ticket_can_be_created_without_hd_ticket_id(self):
		"""Under the zero-client-key flow the ticket is created before any
		Helpdesk ticket exists, so ticket_id cannot be required."""
		doc = frappe.get_doc({
			"doctype": "Support Ticket",
			"subject": "Printer offline",
			"description": "<p>The warehouse printer is offline.</p>",
			"raised_by": "Administrator",
		}).insert(ignore_permissions=True)

		self.assertTrue(doc.name.startswith("SUP-"))
		self.assertEqual(doc.status, "Pending")
		self.assertFalse(doc.ticket_id)
		self.assertEqual(doc.description, "<p>The warehouse printer is offline.</p>")
