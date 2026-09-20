# Copyright (c) 2026, Wahni IT Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk_client.utils.support import create_ticket, generate_ticket_details


def make_settings(ticket_details=None):
	settings = MagicMock()
	settings.support_url = "https://support.test"
	settings.get_password.return_value = "secret-token"
	settings.ticket_details = ticket_details or []
	return settings


def detail_row(key, value, type="String", cast_to=None):
	return frappe._dict(key=key, value=value, type=type, cast_to=cast_to)


class TestGenerateTicketDetails(FrappeTestCase):
	def test_string_and_integer_rows(self):
		settings = make_settings([
			detail_row("site_name", "example.com"),
			detail_row("priority", "2", type="Integer"),
		])
		out = generate_ticket_details(settings)
		self.assertEqual(out, {"site_name": "example.com", "priority": 2})

	def test_context_row_is_safely_evaluated(self):
		settings = make_settings([
			detail_row("computed", "1 + 1", type="Context"),
		])
		out = generate_ticket_details(settings)
		self.assertEqual(out["computed"], 2)

	def test_cast_to_overrides(self):
		settings = make_settings([
			detail_row("as_int", "7", cast_to="Int"),
			detail_row("as_str", "7", type="Integer", cast_to="String"),
			detail_row("as_float", "1.5", cast_to="Float"),
		])
		out = generate_ticket_details(settings)
		self.assertEqual(out["as_int"], 7)
		self.assertEqual(out["as_str"], "7")
		self.assertEqual(out["as_float"], 1.5)

	def test_empty_details(self):
		self.assertEqual(generate_ticket_details(make_settings()), {})


class TestCreateTicket(FrappeTestCase):
	"""create_ticket must be purely local — the client holds no credentials
	and makes no outbound request. The Hub pulls Pending tickets over MCP."""

	def enabled_settings(self):
		settings = make_settings()
		settings.enable_ticket_raising = 1
		return settings

	@patch("helpdesk_client.utils.support.frappe.get_cached_doc")
	def test_create_ticket_makes_no_outbound_request(self, mock_settings):
		mock_settings.return_value = self.enabled_settings()

		import helpdesk_client.utils.support as support_module

		self.assertFalse(
			hasattr(support_module, "make_request"),
			"support.py must not import make_request — the client makes no outbound calls",
		)

		name = create_ticket("Printer offline", "<p>Warehouse printer is offline.</p>")

		doc = frappe.get_doc("Support Ticket", name)
		self.assertTrue(name.startswith("SUP-"))
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(doc.subject, "Printer offline")
		self.assertEqual(doc.raised_by, frappe.session.user)
		self.assertFalse(doc.ticket_id)

	@patch("helpdesk_client.utils.support.frappe.get_cached_doc")
	def test_create_ticket_stores_recording_url(self, mock_settings):
		mock_settings.return_value = self.enabled_settings()

		name = create_ticket("With recording", "<p>see video</p>", "/private/files/rec.mp4")

		self.assertEqual(
			frappe.db.get_value("Support Ticket", name, "screen_recording"),
			"/private/files/rec.mp4",
		)

	@patch("helpdesk_client.utils.support.frappe.get_cached_doc")
	def test_create_ticket_blocked_when_disabled(self, mock_settings):
		settings = make_settings()
		settings.enable_ticket_raising = 0
		mock_settings.return_value = settings

		with self.assertRaises(frappe.ValidationError):
			create_ticket("Nope", "<p>disabled</p>")

	@patch("helpdesk_client.utils.support.frappe.get_cached_doc")
	def test_recording_file_is_attached_to_the_ticket(self, mock_settings):
		"""An unattached private File 403s for the Hub's support user, so
		create_ticket must attach the recording to the new ticket."""
		mock_settings.return_value = self.enabled_settings()

		file_doc = frappe.get_doc({
			"doctype": "File",
			"file_name": "attach-test.webm",
			"content": "fake-webm-bytes",
			"is_private": 1,
		}).insert(ignore_permissions=True)

		name = create_ticket("With recording", "<p>video</p>", file_doc.file_url)

		file_doc.reload()
		self.assertEqual(file_doc.attached_to_doctype, "Support Ticket")
		self.assertEqual(file_doc.attached_to_name, name)

	@patch("helpdesk_client.utils.support.frappe.get_cached_doc")
	def test_multiple_screenshots_are_attached(self, mock_settings):
		import json as _json

		mock_settings.return_value = self.enabled_settings()

		urls = []
		for i in range(2):
			f = frappe.get_doc({
				"doctype": "File",
				"file_name": f"shot-{i}.png",
				"content": f"png-bytes-{i}",
				"is_private": 1,
			}).insert(ignore_permissions=True)
			urls.append(f.file_url)

		name = create_ticket("With screenshots", "<p>imgs</p>", screenshots=_json.dumps(urls))

		attached = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Support Ticket", "attached_to_name": name},
			pluck="file_url",
		)
		self.assertEqual(sorted(attached), sorted(urls))

