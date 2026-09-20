# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""JSON-RPC 2.0 and MCP protocol constants and helpers."""

import json

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "qcs-support-client"
SERVER_VERSION = "0.1.0"

# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def make_response(req_id, result: dict) -> dict:
	"""Build a JSON-RPC 2.0 success response."""
	return {
		"jsonrpc": JSONRPC_VERSION,
		"id": req_id,
		"result": result,
	}


def make_error(req_id, code: int, message: str, data=None) -> dict:
	"""Build a JSON-RPC 2.0 error response."""
	error = {"code": code, "message": message}
	if data is not None:
		error["data"] = data
	return {
		"jsonrpc": JSONRPC_VERSION,
		"id": req_id,
		"error": error,
	}


def parse_request(body: bytes) -> dict:
	"""Parse and validate a JSON-RPC 2.0 request envelope.

	Returns the parsed dict.
	Raises ValueError on invalid JSON or missing required fields.
	"""
	try:
		request = json.loads(body)
	except (json.JSONDecodeError, UnicodeDecodeError) as e:
		raise ValueError(f"Invalid JSON: {e}") from e

	if not isinstance(request, dict):
		raise ValueError("Request must be a JSON object")

	if request.get("jsonrpc") != JSONRPC_VERSION:
		raise ValueError("Missing or invalid jsonrpc version")

	if "method" not in request:
		raise ValueError("Missing method field")

	return request
