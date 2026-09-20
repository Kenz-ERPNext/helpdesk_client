# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""Remove QCS Support Action Log DocType (moved to Hub)."""

import frappe


def execute():
	if frappe.db.exists("DocType", "QCS Support Action Log"):
		# Drop the table and DocType
		frappe.db.delete("Custom Field", {"dt": "QCS Support Action Log"})
		frappe.delete_doc("DocType", "QCS Support Action Log", force=1, ignore_missing=True)
		frappe.db.commit()
