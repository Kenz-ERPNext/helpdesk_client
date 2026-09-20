# Copyright (c) 2026, Wahni IT Solutions Pvt Ltd and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

USER_A = "support-ticket-a@example.com"
USER_B = "support-ticket-b@example.com"


def ensure_user(email):
	if not frappe.db.exists("Role", "Genie User"):
		frappe.get_doc(
			{"doctype": "Role", "role_name": "Genie User", "desk_access": 1}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": "Genie User"}],
			}
		).insert(ignore_permissions=True)


def make_ticket(ticket_id, owner):
	"""Create a locally-named Support Ticket owned by `owner`.

	`ticket_id` is now the Helpdesk ID the Hub fills in later, not the
	record name, so callers must key off the returned doc.name.
	"""
	frappe.set_user(owner)
	doc = frappe.get_doc(
		{
			"doctype": "Support Ticket",
			"ticket_id": ticket_id,
			"subject": f"Issue {ticket_id}",
			"description": f"<p>Issue {ticket_id}</p>",
			"raised_by": owner,
		}
	).insert(ignore_permissions=True)
	frappe.set_user("Administrator")
	return doc


class TestSupportTicket(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_user(USER_A)
		ensure_user(USER_B)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_insert_and_autoname(self):
		doc = make_ticket("HD-TEST-1", USER_A)
		self.assertTrue(doc.name.startswith("SUP-"))
		self.assertEqual(doc.ticket_id, "HD-TEST-1")
		self.assertEqual(doc.status, "Pending")

	def test_owner_cannot_see_others_tickets(self):
		mine = make_ticket("HD-TEST-2", USER_A)
		theirs = make_ticket("HD-TEST-3", USER_B)

		frappe.set_user(USER_B)
		visible = set(frappe.get_list("Support Ticket", pluck="name"))
		self.assertIn(theirs.name, visible)
		self.assertNotIn(mine.name, visible)  # forbidden row absent

	def test_system_manager_sees_all(self):
		doc = make_ticket("HD-TEST-4", USER_A)
		frappe.set_user("Administrator")
		visible = set(frappe.get_list("Support Ticket", pluck="name"))
		self.assertIn(doc.name, visible)
