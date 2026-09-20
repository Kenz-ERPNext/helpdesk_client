"""Frappe `before_tests` hook for genie.

Wired in hooks.py:
    before_tests = "helpdesk_client.tests.bootstrap.before_tests"

Genie installs onto sites that also run ERPNext with local
customizations. When `bench run-tests --app genie` builds test-record
dependencies, Frappe auto-creates the standard `_Test Company`, and a
site Property Setter that promotes a standard Company DocField to
mandatory makes that insert fail before any genie test runs.

This hook relaxes those promoted-mandatory standard fields FOR THE TEST
SESSION ONLY. It is:
  - guarded by `frappe.flags.in_test` (never touches dev/prod data),
  - idempotent (skips a Property Setter already at 0),
  - a silent no-op on sites without the customization (fresh genie-only
    installs have none of these Property Setters, so nothing happens).

Frappe only runs the tested app's `before_tests`, so this cannot rely
on any other installed app's bootstrap.

Add `(doctype, fieldname)` pairs to `PS_BLOCKERS` as new blockers
surface — re-run `bench --site <site> run-tests --app genie`; the error
text names the missing master/field.
"""

import frappe

# Standard DocFields promoted to mandatory via a site Property Setter
# that block Frappe's automatic `_Test Company` (etc.) creation.
PS_BLOCKERS = (
	("Company", "default_warehouse_for_sales_return"),
)

# Mandatory Custom Fields installed by other apps (ksa_compliance's ZATCA
# fields) that block the same bootstrap. These are Custom Field records,
# not Property Setters, so they need their own relaxation pass.
CF_BLOCKERS = (
	("Mode of Payment", "custom_zatca_payment_means_code"),
)


def before_tests():
	"""Entry point called by Frappe before any test module loads.

	Idempotent; silent if not in a test session.
	"""
	if not frappe.flags.in_test:
		return

	relax_test_blocker_mandatory_fields()
	relax_test_blocker_custom_fields()


def relax_test_blocker_mandatory_fields():
	"""Flip `reqd` Property Setters on the blocking standard fields to
	'0' so the test bootstrap can insert the auto-created masters.

	Uses a DB write (not in-process meta mutation): Frappe clears the
	meta cache between `before_tests` and the bootstrap's inserts, so an
	in-memory `df.reqd = 0` would be lost. The Property Setter value is
	stored as a string.
	"""
	changed_doctypes = set()

	for doctype, fieldname in PS_BLOCKERS:
		ps_name = frappe.db.get_value(
			"Property Setter",
			{"doc_type": doctype, "field_name": fieldname, "property": "reqd"},
			"name",
		)
		if not ps_name:
			continue

		if str(frappe.db.get_value("Property Setter", ps_name, "value")) != "0":
			frappe.db.set_value(
				"Property Setter", ps_name, "value", "0", update_modified=False
			)
			changed_doctypes.add(doctype)

	for doctype in changed_doctypes:
		frappe.clear_cache(doctype=doctype)


def relax_test_blocker_custom_fields():
	"""Clear `reqd` on mandatory Custom Fields that block the bootstrap.

	Same rationale as the Property Setter pass, but for Custom Field rows
	installed by other apps on the site (e.g. ksa_compliance's ZATCA
	fields on Mode of Payment). Test-session only, idempotent, and a
	silent no-op where the field is absent.
	"""
	changed_doctypes = set()

	for doctype, fieldname in CF_BLOCKERS:
		cf_name = frappe.db.get_value(
			"Custom Field", {"dt": doctype, "fieldname": fieldname}, "name"
		)
		if not cf_name:
			continue

		if frappe.db.get_value("Custom Field", cf_name, "reqd"):
			frappe.db.set_value("Custom Field", cf_name, "reqd", 0, update_modified=False)
			changed_doctypes.add(doctype)

	for doctype in changed_doctypes:
		frappe.clear_cache(doctype=doctype)
