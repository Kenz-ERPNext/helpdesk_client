# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""MCP tools for writing/modifying Frappe documents."""

import frappe

from helpdesk_client.mcp.tools import register_tool


def set_value(doctype, name, fieldname, value, **_kwargs):
	"""Set a single field value on a document."""
	frappe.set_value(doctype, name, fieldname, value)
	frappe.db.commit()
	return frappe.as_json(
		{
			"status": "success",
			"doctype": doctype,
			"name": name,
			"fieldname": fieldname,
			"value": value,
		}
	)


def set_values(doctype, name, values, **_kwargs):
	"""Set multiple field values on a document."""
	if isinstance(values, str):
		import json

		values = json.loads(values)
	doc = frappe.get_doc(doctype, name)
	doc.update(values)
	doc.save()
	frappe.db.commit()
	return frappe.as_json(
		{
			"status": "success",
			"doctype": doctype,
			"name": name,
			"updated_fields": list(values.keys()),
		}
	)


def create_doc(doctype, values, **_kwargs):
	"""Create a new document."""
	if isinstance(values, str):
		import json

		values = json.loads(values)
	values["doctype"] = doctype
	doc = frappe.get_doc(values)
	doc.insert()
	frappe.db.commit()
	return frappe.as_json(
		{
			"status": "created",
			"doctype": doctype,
			"name": doc.name,
		}
	)


def delete_doc(doctype, name, **_kwargs):
	"""Delete a document."""
	frappe.delete_doc(doctype, name)
	frappe.db.commit()
	return frappe.as_json(
		{
			"status": "deleted",
			"doctype": doctype,
			"name": name,
		}
	)


# Controller methods callable via run_doc_method without an explicit
# @frappe.whitelist() decorator. Limited to permission-checked lifecycle
# transitions. Direct field/status writes are intentionally excluded - use
# set_value/set_values, which run validation and permission checks.
ALLOWED_DOC_METHODS = {"submit", "cancel"}


def run_doc_method(doctype, name, method, args=None, **_kwargs):
	"""Run a permitted method on a document.

	Only lifecycle methods (submit/cancel) or methods explicitly decorated
	with @frappe.whitelist() may be invoked. The method executes with the
	calling user's permissions - no permission bypass.
	"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	fn = getattr(doc, method, None)
	if not callable(fn):
		frappe.throw("Method %s not found on %s" % (method, doctype))

	is_whitelisted = getattr(fn, "__func__", fn) in frappe.whitelisted
	if method not in ALLOWED_DOC_METHODS and not is_whitelisted:
		frappe.throw("Method '%s' is not permitted via MCP" % method, frappe.PermissionError)

	if args:
		if isinstance(args, str):
			import json

			args = json.loads(args)
		result = fn(**args)
	else:
		result = fn()
	frappe.db.commit()
	return frappe.as_json(
		{
			"status": "success",
			"doctype": doctype,
			"name": name,
			"method": method,
			"result": str(result)[:500] if result else None,
		}
	)


def clear_cache(**_kwargs):
	"""Clear the site cache."""
	frappe.clear_cache()
	return frappe.as_json({"status": "cache_cleared"})


# --- Register tools ---

register_tool(
	"set_value",
	description="Set a single field value on a document. Runs validation and permission checks. Example: set_value('Task', 'TASK-0001', 'priority', 'High'). Do not write 'status' on submittable documents directly - use run_doc_method with 'submit'/'cancel'.",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "description": "The DocType name"},
			"name": {"type": "string", "description": "The document name/ID"},
			"fieldname": {"type": "string", "description": "The field to update"},
			"value": {"description": "The new value to set"},
		},
		"required": ["doctype", "name", "fieldname", "value"],
	},
	handler=set_value,
)

register_tool(
	"set_values",
	description="Set multiple field values on a document at once.",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "description": "The DocType name"},
			"name": {"type": "string", "description": "The document name/ID"},
			"values": {"type": "object", "description": "Key-value pairs of fields to update"},
		},
		"required": ["doctype", "name", "values"],
	},
	handler=set_values,
)

register_tool(
	"create_doc",
	description="Create a new document in the specified DocType.",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "description": "The DocType name"},
			"values": {"type": "object", "description": "Field values for the new document"},
		},
		"required": ["doctype", "values"],
	},
	handler=create_doc,
)

register_tool(
	"delete_doc",
	description="Delete a document. Use with caution.",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "description": "The DocType name"},
			"name": {"type": "string", "description": "The document name/ID to delete"},
		},
		"required": ["doctype", "name"],
	},
	handler=delete_doc,
)

register_tool(
	"run_doc_method",
	description="Run a method on a document (e.g. submit, cancel, or custom methods).",
	input_schema={
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "description": "The DocType name"},
			"name": {"type": "string", "description": "The document name/ID"},
			"method": {"type": "string", "description": "Method name to call (e.g. 'submit', 'cancel')"},
			"args": {"type": "object", "description": "Optional arguments to pass to the method"},
		},
		"required": ["doctype", "name", "method"],
	},
	handler=run_doc_method,
)

register_tool(
	"clear_cache",
	description="Clear the site cache. Useful after making configuration changes.",
	input_schema={
		"type": "object",
		"properties": {},
	},
	handler=clear_cache,
)
