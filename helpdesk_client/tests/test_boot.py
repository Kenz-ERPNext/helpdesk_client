# Copyright (c) 2026, Wahni IT Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from helpdesk_client.boot import set_bootinfo


def make_settings(enable_ticket_raising=1, max_recording_size=50, save_recording="Public"):
	settings = MagicMock()
	settings.enable_ticket_raising = enable_ticket_raising
	settings.max_recording_size = max_recording_size
	settings.save_recording = save_recording
	return settings


class TestSetBootinfo(FrappeTestCase):
	@patch("helpdesk_client.boot.frappe.get_cached_doc")
	def test_bootinfo_keys(self, mock_settings):
		mock_settings.return_value = make_settings()
		bootinfo = {}
		set_bootinfo(bootinfo)
		self.assertEqual(bootinfo["genie_support_enabled"], 1)
		self.assertEqual(bootinfo["genie_max_file_size"], 50)
		self.assertEqual(bootinfo["genie_file_type"], 0)

	@patch("helpdesk_client.boot.frappe.get_cached_doc")
	def test_private_recording_flag(self, mock_settings):
		mock_settings.return_value = make_settings(save_recording="Private")
		bootinfo = {}
		set_bootinfo(bootinfo)
		self.assertEqual(bootinfo["genie_file_type"], 1)
