# Copyright (c) 2026, Wahni IT Solutions Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from helpdesk_client.utils.notifications import notify_status_change


class SupportTicket(Document):
	def on_update(self):
		"""Notify the reporter when the status changes.

		Under the zero-client-key flow the Hub writes status here over MCP,
		so this is the only place a status change can be observed — the
		client no longer polls the Helpdesk.
		"""
		previous = self.get_doc_before_save()
		if not previous or previous.status == self.status:
			return

		self.db_set("last_synced", now_datetime(), update_modified=False)
		notify_status_change(self, self.status)


def get_permission_query_conditions(user):
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return ""
	return f"(`tabSupport Ticket`.`owner` = {frappe.db.escape(user)})"


@frappe.whitelist()
def request_close(ticket):
	"""Owner asks to close: flag it; the Hub closes the HD Ticket next cycle."""
	doc = frappe.get_doc("Support Ticket", ticket)
	if doc.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(frappe._("Only the ticket owner can close it."), frappe.PermissionError)
	doc.db_set("close_requested", 1)
	return "ok"


def _attach_to_ticket(ticket_name, file_url):
	"""Make an uploaded file an attachment of the ticket.

	The Hub lists files by attached_to_doctype/name, so a reply attachment only
	reaches the agent once it is attached to the ticket itself.
	"""
	if frappe.db.exists("File", {
		"file_url": file_url,
		"attached_to_doctype": "Support Ticket",
		"attached_to_name": ticket_name,
	}):
		return

	src = frappe.db.get_value(
		"File", {"file_url": file_url}, ["name", "file_name", "is_private"], as_dict=True
	)
	orphan = src and not frappe.db.get_value("File", src.name, "attached_to_name")
	if orphan:
		frappe.db.set_value("File", src.name, {
			"attached_to_doctype": "Support Ticket",
			"attached_to_name": ticket_name,
		})
		return

	frappe.get_doc({
		"doctype": "File",
		"file_url": file_url,
		"file_name": (src or {}).get("file_name") or file_url.rsplit("/", 1)[-1],
		"is_private": (src or {}).get("is_private") or 0,
		"attached_to_doctype": "Support Ticket",
		"attached_to_name": ticket_name,
	}).insert(ignore_permissions=True)


@frappe.whitelist()
def post_reply(ticket, message, file_url=None):
	"""Owner answers an agent reply, optionally with a screenshot or video.

	Stored as a plain Comment owned by the customer — the Hub's conversation
	sync picks up comments that are not authored by the support user and
	mirrors them onto the Helpdesk ticket. Any attachment rides along as a
	ticket attachment, which the Hub copies onto the Helpdesk ticket too.
	"""
	message = (message or "").strip()
	if not message and not file_url:
		frappe.throw(frappe._("Write a message or attach a file before sending."))

	doc = frappe.get_doc("Support Ticket", ticket)
	if doc.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(frappe._("Only the ticket owner can reply."), frappe.PermissionError)

	content = message
	if file_url:
		_attach_to_ticket(doc.name, file_url)
		# Reference the file by name only: the Hub mirrors this text onto its
		# own site, where a client-relative URL would not resolve. The file
		# itself is synced separately as an attachment.
		content = "%s\n\n\N{PAPERCLIP} %s" % (content, file_url.rsplit("/", 1)[-1])

	comment = frappe.get_doc({
		"doctype": "Comment",
		"comment_type": "Comment",
		"reference_doctype": "Support Ticket",
		"reference_name": doc.name,
		"content": content.strip(),
	})
	comment.insert(ignore_permissions=True)
	frappe.db.commit()
	return comment.name


def notify_reply(doc, method):
	"""Comment after_insert: a support-user comment on a Support Ticket is an
	agent reply pushed by the Hub — notify the reporter with the text."""
	if doc.reference_doctype != "Support Ticket" or doc.comment_type != "Comment":
		return
	if doc.owner != "support@quarkcs.com":
		return
	raised_by = frappe.db.get_value("Support Ticket", doc.reference_name, "raised_by")
	if not raised_by or raised_by == doc.owner:
		return
	frappe.get_doc({
		"doctype": "Notification Log",
		"for_user": raised_by,
		"type": "Alert",
		"subject": frappe._("Support replied on {0}").format(doc.reference_name),
		"email_content": doc.content,
		"document_type": "Support Ticket",
		"document_name": doc.reference_name,
	}).insert(ignore_permissions=True)

