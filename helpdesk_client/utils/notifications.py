# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def notify_status_change(doc, new_status):
	"""Raise a desk notification for the user who reported the ticket.

	Called from Support Ticket.on_update, so it fires whether the status
	was changed by the Hub over MCP or by a local edit.
	"""
	if not doc.raised_by:
		return

	reference = doc.ticket_id or doc.name
	frappe.get_doc({
		"doctype": "Notification Log",
		"for_user": doc.raised_by,
		"type": "Alert",
		"subject": _("Your support ticket #{0} is now {1}").format(reference, _(new_status)),
		"document_type": "Support Ticket",
		"document_name": doc.name,
	}).insert(ignore_permissions=True)
