# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

app_name = "helpdesk_client"
app_title = "Helpdesk Client"
app_publisher = "Quark Cyber Systems FZC"
app_description = "Helpdesk Support Client"
app_email = "support@quarkcs.com"
app_license = "agpl-3.0"
extend_bootinfo = "helpdesk_client.boot.set_bootinfo"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "helpdesk_client",
# 		"logo": "/assets/helpdesk_client/logo.png",
# 		"title": "Helpdesk Client",
# 		"route": "/helpdesk_client",
# 		"has_permission": "helpdesk_client.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/helpdesk_client/css/helpdesk_client.css"
# app_include_js = "/assets/helpdesk_client/js/helpdesk_client.js"
app_include_js = ["helpdesk_client.bundle.js"]

# include js, css files in header of web template
# web_include_css = "/assets/helpdesk_client/css/helpdesk_client.css"
# web_include_js = "/assets/helpdesk_client/js/helpdesk_client.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "helpdesk_client/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {"User": "public/js/impersonation.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "helpdesk_client/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "helpdesk_client.utils.jinja_methods",
# 	"filters": "helpdesk_client.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "helpdesk_client.install.before_install"
after_install = "helpdesk_client.setup.after_install"
after_migrate = "helpdesk_client.setup.create_genie_folder"

# Uninstallation
# ------------

# before_uninstall = "helpdesk_client.uninstall.before_uninstall"
after_uninstall = "helpdesk_client.setup.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "helpdesk_client.utils.before_app_install"
# after_app_install = "helpdesk_client.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "helpdesk_client.utils.before_app_uninstall"
# after_app_uninstall = "helpdesk_client.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "helpdesk_client.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }
doc_events = {
	"Comment": {
		"after_insert": "helpdesk_client.helpdesk_client.doctype.support_ticket.support_ticket.notify_reply",
	},
}

permission_query_conditions = {
	"Support Ticket": "helpdesk_client.helpdesk_client.doctype.support_ticket.support_ticket.get_permission_query_conditions",
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# The client schedules no jobs. Ticket status arrives as a Hub write over
# MCP (see qcs_support_hub.ticket_puller), so there is nothing to poll.

# scheduler_events = {
# 	"all": [
# 		"helpdesk_client.tasks.all"
# 	],
# 	"daily": [
# 		"helpdesk_client.tasks.daily"
# 	],
# 	"hourly": [
# 		"helpdesk_client.tasks.hourly"
# 	],
# 	"weekly": [
# 		"helpdesk_client.tasks.weekly"
# 	],
# 	"monthly": [
# 		"helpdesk_client.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "helpdesk_client.install.before_tests"
before_tests = "helpdesk_client.tests.bootstrap.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "helpdesk_client.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "helpdesk_client.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "helpdesk_client.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# OAuth discovery interceptor for /.well-known/oauth-authorization-server (needed for v15)
before_request = ["helpdesk_client.mcp.oauth.before_request_handler"]
# after_request = ["helpdesk_client.utils.after_request"]

# Job Events
# ----------
# before_job = ["helpdesk_client.utils.before_job"]
# after_job = ["helpdesk_client.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"helpdesk_client.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True


# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
