# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""Deprecated: client-side token rotation.

Rotation is now Hub-initiated via helpdesk_client.api.rotate_credentials.
This stub is kept only so the historical scheduled-job reference in hooks.py
does not crash if it was retained by an old deployment.
"""


def rotate_api_tokens():
	"""Deprecated no-op. Rotation is now Hub-initiated.

	Kept so old scheduler registrations don't fail. Remove this file once
	all deployments have migrated past the scheduled job reference.
	"""
	return
