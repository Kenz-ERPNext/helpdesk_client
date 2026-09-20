# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""MCP tools for reading Frappe documents and data."""

import frappe

from helpdesk_client.mcp.tools import register_tool
from helpdesk_client.utils import get_settings_limit

# Hard safety ceilings - admins can configure the effective limit in
# HDS Support Settings up to these values. Used to prevent a misconfigured
# Settings value from producing an unbounded query.
LIST_LIMIT_CEILING = 5000
ERROR_LOG_LIMIT_CEILING = 500


def get_doc(doctype: str, name: str, fields=None, **_kwargs) -> str:
	"""Fetch a single document."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	data = doc.as_dict()
	if fields:
		data = {k: v for k, v in data.items() if k in fields}
	return frappe.as_json(data, indent=2)


def get_list(
	doctype: str,
	filters=None,
	fields=None,
	order_by=None,
	limit: int = 20,
	**_kwargs,
) -> str:
	"""List documents with optional filters."""
	max_limit = get_settings_limit("max_list_limit", 100, LIST_LIMIT_CEILING)
	limit = min(int(limit), max_limit)
	result = frappe.get_list(
		doctype,
		filters=filters,
		fields=fields or ["name"],
		order_by=order_by or "modified desc",
		limit_page_length=limit,
	)
	return frappe.as_json(result, indent=2)


def get_meta(doctype: str, **_kwargs) -> str:
	"""Get DocType metadata: fields, permissions, naming, workflow."""
	meta = frappe.get_meta(doctype)
	data = meta.as_dict()
	# Keep only useful fields to reduce payload
	keep_keys = [
		"name",
		"module",
		"issingle",
		"istable",
		"is_submittable",
		"autoname",
		"title_field",
		"search_fields",
		"sort_field",
		"sort_order",
		"fields",
		"permissions",
	]
	filtered = {k: data[k] for k in keep_keys if k in data}
	# Slim down field definitions
	if "fields" in filtered:
		field_keys = [
			"fieldname",
			"fieldtype",
			"label",
			"options",
			"reqd",
			"read_only",
			"hidden",
			"in_list_view",
			"in_standard_filter",
			"default",
			"description",
		]
		filtered["fields"] = [{k: f.get(k) for k in field_keys if f.get(k)} for f in filtered["fields"]]
	return frappe.as_json(filtered, indent=2)


def get_count(doctype: str, filters=None, **_kwargs) -> str:
	"""Count documents matching filters."""
	count = frappe.db.count(doctype, filters=filters)
	return frappe.as_json({"doctype": doctype, "count": count})


def get_error_log(method=None, limit: int = 20, **_kwargs) -> str:
	"""Fetch recent error logs, optionally filtered by method."""
	max_limit = get_settings_limit("max_error_log_limit", 50, ERROR_LOG_LIMIT_CEILING)
	limit = min(int(limit), max_limit)
	filters = {}
	if method:
		filters["method"] = ["like", f"%{method}%"]

	result = frappe.get_list(
		"Error Log",
		filters=filters,
		fields=["name", "method", "error", "creation"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	return frappe.as_json(result, indent=2)


# --- Register tools ---

register_tool(
	"get_doc",
	description="Fetch a single Frappe document by doctype and name. Returns all fields by default, or specify a list of field names.",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": "The DocType name (e.g. 'Sales Invoice', 'Customer')",
			},
			"name": {"type": "string", "description": "The document name/ID"},
			"fields": {
				"type": "array",
				"items": {"type": "string"},
				"description": "Optional list of field names to return. Omit for all fields.",
			},
		},
		"required": ["doctype", "name"],
	},
	handler=get_doc,
)

register_tool(
	"get_list",
	description="List Frappe documents with optional filters, field selection, ordering, and limit. Returns up to 100 results.",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "description": "The DocType name"},
			"filters": {
				"type": "object",
				"description": "Filter conditions as {field: value} or {field: [operator, value]}. Operators: =, !=, <, >, <=, >=, like, not like, in, not in, between",
			},
			"fields": {
				"type": "array",
				"items": {"type": "string"},
				"description": "Fields to return. Default: ['name']",
			},
			"order_by": {
				"type": "string",
				"description": "Sort order, e.g. 'creation desc'. Default: 'modified desc'",
			},
			"limit": {
				"type": "integer",
				"description": "Max results to return. Capped by HDS Support Settings -> Max List Limit. Default: 20",
			},
		},
		"required": ["doctype"],
	},
	handler=get_list,
)

register_tool(
	"get_meta",
	description="Get DocType metadata: field definitions (name, type, label, options, required), permissions, naming rule, and key settings. Useful for understanding a DocType's schema before querying it.",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "description": "The DocType name"},
		},
		"required": ["doctype"],
	},
	handler=get_meta,
)

register_tool(
	"get_count",
	description="Count documents in a DocType, optionally filtered.",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "description": "The DocType name"},
			"filters": {
				"type": "object",
				"description": "Optional filter conditions as {field: value}",
			},
		},
		"required": ["doctype"],
	},
	handler=get_count,
)

register_tool(
	"get_error_log",
	description="Fetch recent Error Log entries, optionally filtered by method name. Useful for diagnosing background job failures or API errors.",
	input_schema={
		"type": "object",
		"properties": {
			"method": {"type": "string", "description": "Filter by method name (partial match)"},
			"limit": {
				"type": "integer",
				"description": "Max results. Capped by HDS Support Settings -> Max Error Log Limit. Default: 20",
			},
		},
	},
	handler=get_error_log,
)
