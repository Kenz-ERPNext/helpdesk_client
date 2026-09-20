# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Backfill ticket_id from name for tickets created under the old
	autoname (field:ticket_id), so Hub status pushes still resolve them.

	Old records keep their HD-ticket-ID names; new records use SUP-YYYY-#####.
	Renaming the old ones would break existing links, so we leave them be.
	"""
	if not frappe.db.table_exists("Support Ticket"):
		return

	frappe.db.sql("""
		UPDATE `tabSupport Ticket`
		SET ticket_id = name
		WHERE ticket_id IS NULL OR ticket_id = ''
	""")
