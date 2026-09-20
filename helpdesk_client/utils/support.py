# Copyright (c) 2023, Wahni IT Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.utils.safe_exec import get_safe_globals, safe_eval


@frappe.whitelist()
def create_ticket(title, description, screen_recording=None, screenshots=None):
	"""Record a support request locally.

	The Hub picks it up over MCP and creates the Helpdesk ticket, so the
	client stores no credentials and makes no outbound call. Returns the
	local Support Ticket name — there is no Helpdesk ID yet.
	"""
	settings = frappe.get_cached_doc("HDS Support Settings")
	if not settings.enable_ticket_raising:
		frappe.throw(_("Ticket raising is not enabled for this site."))

	doc = frappe.get_doc({
		"doctype": "Support Ticket",
		"subject": title,
		"description": description,
		"status": "Pending",
		"raised_by": frappe.session.user,
		"screen_recording": screen_recording,
	}).insert(ignore_permissions=True)

	if screen_recording:
		attach_recording_file(doc.name, screen_recording)

	for file_url in parse_screenshots(screenshots):
		attach_recording_file(doc.name, file_url)

	return doc.name


def parse_screenshots(screenshots):
	"""screenshots arrives as a JSON list of file URLs from the dialog."""
	if not screenshots:
		return []
	if isinstance(screenshots, str):
		try:
			screenshots = json.loads(screenshots)
		except ValueError:
			return []
	return [url for url in screenshots if isinstance(url, str) and url]


def attach_recording_file(ticket_name, file_url):
	"""Link the uploaded recording File to its Support Ticket.

	An unattached private File is served to nobody but its owner, so the
	Hub's support user gets a 403 fetching it. Attached to the ticket, read
	access flows from the ticket's permissions instead.
	"""
	file_name = frappe.db.get_value(
		"File",
		{"file_url": file_url, "attached_to_name": ("is", "not set")},
		"name",
	)
	if file_name:
		frappe.db.set_value(
			"File",
			file_name,
			{"attached_to_doctype": "Support Ticket", "attached_to_name": ticket_name},
			update_modified=False,
		)


def generate_ticket_details(settings):
	req_params = {}
	for row in settings.ticket_details:
		if row.type == "String":
			req_params[row.key] = row.value
		elif row.type == "Integer":
			req_params[row.key] = cint(row.value)
		elif row.type == "Context":
			req_params[row.key] = safe_eval(row.value, get_safe_globals(), {})
		else:
			req_params[row.key] = row.value

		if row.cast_to:
			if row.cast_to == "Int":
				req_params[row.key] = cint(req_params[row.key])
			elif row.cast_to == "String":
				req_params[row.key] = str(req_params[row.key])
			elif row.cast_to == "Float":
				req_params[row.key] = flt(req_params[row.key])

	return req_params
