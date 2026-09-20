# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""MCP Streamable HTTP endpoint for Frappe.

Single endpoint handling all MCP JSON-RPC 2.0 methods:
- initialize
- notifications/initialized
- tools/list
- tools/call
"""

import json
import time

import frappe
from werkzeug.wrappers import Response

import helpdesk_client.mcp.tools.data_tools
import helpdesk_client.mcp.tools.report_tools
import helpdesk_client.mcp.tools.site_tools
import helpdesk_client.mcp.tools.write_tools
from helpdesk_client.mcp.auth import authenticate_request
from helpdesk_client.mcp.protocol import (
	INTERNAL_ERROR,
	INVALID_PARAMS,
	INVALID_REQUEST,
	MCP_PROTOCOL_VERSION,
	METHOD_NOT_FOUND,
	PARSE_ERROR,
	SERVER_NAME,
	SERVER_VERSION,
	make_error,
	make_response,
	parse_request,
)
from helpdesk_client.mcp.session import create_session, get_session_user, validate_session
from helpdesk_client.mcp.tools import WRITE_TOOLS, execute_tool, get_tool_definitions


def _json_response(data: dict, status: int = 200, session_id=None) -> Response:
	"""Build a werkzeug Response with JSON-RPC body and MCP headers."""
	headers = {"Content-Type": "application/json"}
	if session_id:
		headers["Mcp-Session-Id"] = session_id
	return Response(json.dumps(data), status=status, headers=headers)


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def handle():
	"""Main MCP endpoint. Handles all JSON-RPC 2.0 requests."""
	# GET requests are SSE stream attempts for server-initiated notifications.
	# Return a valid SSE stream that immediately closes - signals no server notifications.
	if frappe.request.method == "GET":
		session_id = frappe.request.headers.get("Mcp-Session-Id", "")
		return Response(
			"event: close\ndata: {}\n\n",
			status=200,
			headers={
				"Content-Type": "text/event-stream",
				"Cache-Control": "no-cache",
				"Connection": "keep-alive",
				"Mcp-Session-Id": session_id,
			},
		)

	body = frappe.request.get_data()

	try:
		request = parse_request(body)
	except ValueError as e:
		return _json_response(make_error(None, PARSE_ERROR, str(e)), status=400)

	method = request.get("method")
	params = request.get("params", {})
	req_id = request.get("id")  # None for notifications

	# --- initialize ---
	if method == "initialize":
		try:
			user = authenticate_request()
		except frappe.AuthenticationError:
			return _json_response(make_error(req_id, -32000, "Authentication failed"), status=401)

		session_id = create_session(user)
		result = {
			"protocolVersion": MCP_PROTOCOL_VERSION,
			"capabilities": {"tools": {"listChanged": False}},
			"serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
		}
		return _json_response(make_response(req_id, result), session_id=session_id)

	# --- notifications/initialized ---
	if method == "notifications/initialized":
		return Response("", status=202)

	# --- All other methods require a valid session ---
	session_id = frappe.request.headers.get("Mcp-Session-Id")
	if not session_id or not validate_session(session_id):
		return _json_response(make_error(req_id, INVALID_REQUEST, "Invalid or missing session"), status=400)

	user = get_session_user(session_id)
	frappe.set_user(user)

	# --- tools/list ---
	if method == "tools/list":
		result = {"tools": get_tool_definitions()}
		return _json_response(make_response(req_id, result), session_id=session_id)

	# --- tools/call ---
	if method == "tools/call":
		tool_name = params.get("name")
		arguments = params.get("arguments", {})

		if not tool_name:
			return _json_response(
				make_error(req_id, INVALID_PARAMS, "Missing tool name"),
				session_id=session_id,
			)

		start = time.monotonic()
		result = execute_tool(tool_name, arguments)
		elapsed_ms = round((time.monotonic() - start) * 1000)

		# Add timing metadata
		result["_meta"] = {"execution_time_ms": elapsed_ms}

		return _json_response(make_response(req_id, result), session_id=session_id)

	# --- Unknown method ---
	return _json_response(
		make_error(req_id, METHOD_NOT_FOUND, f"Unknown method: {method}"),
		session_id=session_id,
	)
