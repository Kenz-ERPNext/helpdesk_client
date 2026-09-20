# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from helpdesk_client.utils import normalize_site_url


class HDSSupportSettings(Document):
	def before_save(self):
		if self.qcs_hub_url:
			self.qcs_hub_url = normalize_site_url(self.qcs_hub_url)

	# No validate() hook. The previous validate_sp_access() called the
	# Helpdesk on every save to confirm it was reachable, using a stored
	# API token — the exact exposure this redesign removes. The client now
	# holds no credentials and makes no outbound calls, so there is nothing
	# to validate remotely.
