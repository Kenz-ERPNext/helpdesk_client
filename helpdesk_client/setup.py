# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""Post-install and post-uninstall hooks for Helpdesk Client."""

import frappe

SUPPORT_USER = "support@quarkcs.com"
DEFAULT_BLOCKED_DOCTYPES = [
	"User",
	"Email Account",
	"Email Domain",
	"OAuth Client",
	"Social Login Key",
]


def after_install():
	"""Create support user with API keys and default settings."""
	_create_support_user()
	_create_default_settings()
	create_genie_folder()


def after_uninstall():
	"""Disable the support user."""
	if frappe.db.exists("User", SUPPORT_USER):
		frappe.db.set_value("User", SUPPORT_USER, "enabled", 0)
		frappe.db.commit()
		print(f"Disabled user {SUPPORT_USER}")


def _create_support_user():
	"""Create or enable the support@quarkcs.com user with System Manager role.

	API keys are NOT generated here - they are created during the Hub
	onboarding/registration process to avoid exposing credentials in logs.
	"""
	if frappe.db.exists("User", SUPPORT_USER):
		user = frappe.get_doc("User", SUPPORT_USER)
		if not user.enabled:
			user.enabled = 1
			user.save(ignore_permissions=True)
			print("Re-enabled existing user %s" % SUPPORT_USER)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": SUPPORT_USER,
				"first_name": "Helpdesk Support",
				"user_type": "System User",
				"send_welcome_email": 0,
				"roles": [{"role": "System Manager"}],
			}
		)
		user.insert(ignore_permissions=True)
		print("Created user %s" % SUPPORT_USER)

	frappe.db.commit()


def _create_default_settings():
	"""Create default HDS Support Settings with blocked doctypes."""
	settings = frappe.get_single("HDS Support Settings")

	if not settings.enabled:
		settings.enabled = 1

	if not settings.blocked_doctypes:
		for dt in DEFAULT_BLOCKED_DOCTYPES:
			settings.append("blocked_doctypes", {"doctype_name": dt})

	if not settings.max_list_limit:
		settings.max_list_limit = 100

	if not settings.max_report_rows:
		settings.max_report_rows = 500

	settings.save(ignore_permissions=True)
	frappe.db.commit()
	print("Default HDS Support Settings created")


def create_genie_folder():
	f = frappe.new_doc("File")
	f.file_name = "Genie"
	f.is_folder = 1
	f.folder = "Home"
	f.insert(ignore_if_duplicate=True)
