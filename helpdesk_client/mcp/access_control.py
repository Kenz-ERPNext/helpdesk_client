# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""Access control for MCP tool calls based on HDS Support Settings."""

import frappe


def check_doctype_access(doctype, is_write=False):
	"""Check if the given doctype is accessible via MCP.

	Raises frappe.PermissionError if access is denied.
	"""
	settings = frappe.get_single("HDS Support Settings")

	if not settings.enabled:
		frappe.throw("Helpdesk Client is disabled", frappe.PermissionError)

	# Check write permission
	if is_write and not settings.allow_write_operations:
		frappe.throw("Write operations are disabled", frappe.PermissionError)

	# Check blocked doctypes
	blocked = {row.doctype_name for row in settings.blocked_doctypes}
	if doctype in blocked:
		frappe.throw("Access to %s is blocked" % doctype, frappe.PermissionError)

	# Check allowed doctypes (whitelist mode)
	allowed = {row.doctype_name for row in settings.allowed_doctypes}
	if allowed and doctype not in allowed:
		frappe.throw("%s is not in the allowed doctypes list" % doctype, frappe.PermissionError)
