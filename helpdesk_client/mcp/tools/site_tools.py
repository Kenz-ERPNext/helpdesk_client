# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""MCP tools for site-level information."""

import frappe

from helpdesk_client.mcp.tools import register_tool


def get_installed_apps(**_kwargs) -> str:
	"""Return list of installed apps with versions."""
	apps = []
	for app in frappe.get_installed_apps():
		app_info = {"app": app}
		try:
			app_info["version"] = frappe.get_attr(f"{app}.__version__")
		except Exception:
			app_info["version"] = "unknown"
		apps.append(app_info)
	return frappe.as_json(apps, indent=2)


def get_site_info(**_kwargs) -> str:
	"""Return basic site configuration and status info."""
	info = {
		"site_name": frappe.local.site,
		"frappe_version": frappe.__version__,
		"installed_apps": frappe.get_installed_apps(),
		"default_language": frappe.db.get_default("lang") or "en",
		"time_zone": frappe.db.get_default("time_zone") or "UTC",
		"scheduler_enabled": bool(frappe.utils.scheduler.is_scheduler_inactive()),
	}
	return frappe.as_json(info, indent=2)


# Register tools
register_tool(
	"get_installed_apps",
	description="List all installed Frappe apps with their versions",
	input_schema={
		"type": "object",
		"properties": {},
	},
	handler=get_installed_apps,
)

register_tool(
	"get_site_info",
	description="Get basic site configuration: site name, Frappe version, language, timezone, installed apps",
	input_schema={
		"type": "object",
		"properties": {},
	},
	handler=get_site_info,
)
