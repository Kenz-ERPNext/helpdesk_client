# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

import frappe

TOOL_REGISTRY: dict[str, dict] = {}

WRITE_TOOLS = {"set_value", "set_values", "create_doc", "delete_doc", "run_doc_method", "clear_cache"}


def register_tool(name, *, description, input_schema, handler):
	"""Register an MCP tool in the global registry."""
	TOOL_REGISTRY[name] = {
		"name": name,
		"description": description,
		"inputSchema": input_schema,
		"handler": handler,
	}


def get_tool_definitions() -> list[dict]:
	"""Return tool definitions for tools/list response."""
	return [
		{
			"name": t["name"],
			"description": t["description"],
			"inputSchema": t["inputSchema"],
		}
		for t in TOOL_REGISTRY.values()
	]


def execute_tool(name: str, arguments: dict) -> dict:
	"""Execute a tool and return MCP-formatted result."""
	from helpdesk_client.mcp.access_control import check_doctype_access

	if name not in TOOL_REGISTRY:
		return {
			"content": [{"type": "text", "text": f"Unknown tool: {name}"}],
			"isError": True,
		}

	tool = TOOL_REGISTRY[name]
	try:
		# Check access control for doctype-based tools
		is_write = name in WRITE_TOOLS
		if "doctype" in arguments:
			check_doctype_access(arguments["doctype"], is_write=is_write)

		result = tool["handler"](**arguments)
		return {
			"content": [{"type": "text", "text": result}],
			"isError": False,
		}
	except Exception as e:
		frappe.log_error(f"MCP tool error: {name}", str(e))
		return {
			"content": [{"type": "text", "text": f"Error executing {name}: {e}"}],
			"isError": True,
		}
