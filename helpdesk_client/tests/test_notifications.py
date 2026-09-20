# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestStatusNotifications(FrappeTestCase):
	"""Status now arrives as a Hub write over MCP rather than a local poll,
	so the notification must hang off the document, not off a sync job."""

	def make_ticket(self):
		return frappe.get_doc({
			"doctype": "Support Ticket",
			"subject": "Printer offline",
			"description": "<p>offline</p>",
			"raised_by": "Administrator",
		}).insert(ignore_permissions=True)

	def notification_count(self, doc):
		return frappe.db.count(
			"Notification Log",
			{"document_type": "Support Ticket", "document_name": doc.name},
		)

	def test_status_change_notifies_the_raiser(self):
		doc = self.make_ticket()
		before = self.notification_count(doc)

		doc.status = "Resolved"
		doc.save(ignore_permissions=True)

		self.assertEqual(self.notification_count(doc), before + 1)

	def test_no_notification_when_status_unchanged(self):
		doc = self.make_ticket()
		doc.save(ignore_permissions=True)
		before = self.notification_count(doc)

		doc.screen_recording = "/private/files/rec.mp4"
		doc.save(ignore_permissions=True)

		self.assertEqual(self.notification_count(doc), before)

	def test_last_synced_stamped_on_status_change(self):
		doc = self.make_ticket()
		self.assertIsNone(doc.last_synced)

		doc.status = "Open"
		doc.save(ignore_permissions=True)
		doc.reload()

		self.assertIsNotNone(doc.last_synced)

	def test_client_has_no_scheduled_jobs(self):
		"""The outbound poller is gone; the client runs no cron at all."""
		events = frappe.get_hooks("scheduler_events", app_name="helpdesk_client")
		self.assertFalse(events, f"client must schedule no jobs, found: {events}")
