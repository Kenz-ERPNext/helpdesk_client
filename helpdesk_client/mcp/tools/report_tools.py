# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""MCP tools for executing Frappe reports."""

import frappe
from frappe.desk.query_report import run as run_report

from helpdesk_client.mcp.tools import register_tool
from helpdesk_client.utils import get_settings_limit

# Hard safety ceiling - admins configure the effective limit in
# HDS Support Settings -> Max Report Rows up to this value.
REPORT_ROWS_CEILING = 10000


def execute_report(report_name: str, filters=None, limit: int = 100, **_kwargs) -> str:
	"""Execute a Frappe report and return columns + rows."""
	max_limit = get_settings_limit("max_report_rows", 500, REPORT_ROWS_CEILING)
	limit = min(int(limit), max_limit)

	result = run_report(report_name, filters=frappe.as_json(filters) if filters else None)

	columns = result.get("columns", [])
	rows = result.get("result", [])

	# Truncate rows
	truncated = len(rows) > limit
	rows = rows[:limit]

	output = {
		"report_name": report_name,
		"columns": columns,
		"rows": rows,
		"total_rows": len(result.get("result", [])),
		"returned_rows": len(rows),
		"truncated": truncated,
	}

	if result.get("report_summary"):
		output["report_summary"] = result["report_summary"]

	return frappe.as_json(output, indent=2)


register_tool(
	"execute_report",
	description="Execute a Frappe report (Script Report or Query Report) with optional filters. Returns column definitions and data rows. Use get_list with doctype='Report' to discover available reports.",
	input_schema={
		"type": "object",
		"properties": {
			"report_name": {
				"type": "string",
				"description": "The report name (e.g. 'General Ledger', 'Profit and Loss Statement')",
			},
			"filters": {
				"type": "object",
				"description": "Report filter values as {filter_name: value}",
			},
			"limit": {
				"type": "integer",
				"description": "Max rows to return. Capped by HDS Support Settings -> Max Report Rows. Default: 100",
			},
		},
		"required": ["report_name"],
	},
	handler=execute_report,
)
