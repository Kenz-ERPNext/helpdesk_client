# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""Drop now-unused fields from HDS Support Settings (a Single DocType).

- registration_key, disable_auto_rotation, rotation_frequency_days become
  obsolete once registration + rotation move to Hub-initiated Token auth.

Single DocTypes store their values in the `tabSingles` table (doctype/field/value
rows), not their own table - so we delete rows, not columns.
"""

import frappe

DOCTYPE = "HDS Support Settings"
FIELDS_TO_DROP = [
	"registration_key",
	"disable_auto_rotation",
	"rotation_frequency_days",
]


def execute():
	# Remove stored values for the deprecated fields.
	frappe.db.delete(
		"Singles",
		{"doctype": DOCTYPE, "field": ("in", FIELDS_TO_DROP)},
	)

	# Clean up encrypted value for the removed Password field (registration_key).
	frappe.db.delete(
		"__Auth",
		{"doctype": DOCTYPE, "fieldname": "registration_key"},
	)
	frappe.db.commit()
