# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""MCP session management backed by Redis cache."""

import uuid

from helpdesk_client.utils import get_cache

SESSION_PREFIX = "mcp_session:"
SESSION_TTL = 3600  # 1 hour


def create_session(user: str) -> str:
	"""Create a new MCP session for the authenticated user.

	Returns the session ID (UUID string).
	"""
	session_id = str(uuid.uuid4())
	get_cache().set_value(f"{SESSION_PREFIX}{session_id}", user, expires_in_sec=SESSION_TTL)
	return session_id


def validate_session(session_id: str) -> bool:
	"""Check if a session ID is valid and not expired."""
	if not session_id:
		return False
	user = get_cache().get_value(f"{SESSION_PREFIX}{session_id}")
	return user is not None


def get_session_user(session_id: str):
	"""Return the username associated with a session, or None if invalid."""
	if not session_id:
		return None
	return get_cache().get_value(f"{SESSION_PREFIX}{session_id}")
