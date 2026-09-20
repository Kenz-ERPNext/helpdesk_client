# Copyright (c) 2026, Wahni IT Solutions Pvt Ltd and Contributors
# See license.txt

import copy
import importlib
import sys
import types
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

GSTIN_INFO_PATH = "india_compliance.gst_india.utils.gstin_info"


def fake_gstin_module(gstin_info_by_gstin):
	"""Build a fake india_compliance module tree exposing get_gstin_info.

	Used only when india_compliance is NOT installed; when it is, we patch
	the real module attribute directly (a sys.modules swap doesn't take
	when the real submodule is already imported).
	"""
	root = types.ModuleType("india_compliance")
	gst_india = types.ModuleType("india_compliance.gst_india")
	utils = types.ModuleType("india_compliance.gst_india.utils")
	gstin_info = types.ModuleType(GSTIN_INFO_PATH)
	# deepcopy: create_address mutates the returned dict (address_data.pop),
	# so never hand back the shared fixture object.
	gstin_info.get_gstin_info = (
		lambda gstin, throw_error=False: copy.deepcopy(gstin_info_by_gstin.get(gstin))
	)
	return {
		"india_compliance": root,
		"india_compliance.gst_india": gst_india,
		"india_compliance.gst_india.utils": utils,
		GSTIN_INFO_PATH: gstin_info,
	}


def patch_gstin_lookup(stack, gstin_info_by_gstin):
	"""Route get_gstin_info to the test data whether or not india_compliance
	is installed. Returns via the supplied ExitStack."""

	def fake_lookup(gstin, throw_error=False):
		# deepcopy: create_address mutates the returned dict (address_data.pop),
		# so never hand back the shared fixture object.
		return copy.deepcopy(gstin_info_by_gstin.get(gstin))

	try:
		mod = importlib.import_module(GSTIN_INFO_PATH)
		stack.enter_context(patch.object(mod, "get_gstin_info", side_effect=fake_lookup))
	except ModuleNotFoundError:
		stack.enter_context(patch.dict(sys.modules, fake_gstin_module(gstin_info_by_gstin)))


def in_memory_db_set(self, fieldname, value=None, *args, **kwargs):
	if isinstance(fieldname, dict):
		for key, val in fieldname.items():
			setattr(self, key, val)
	else:
		setattr(self, fieldname, value)


def make_fetcher(parties):
	return frappe.get_doc(
		{
			"doctype": "Address Fetcher",
			"status": "In Process",
			"parties": parties,
		}
	)


class TestAddressFetcherValidation(FrappeTestCase):
	def test_save_blocked_when_not_pending(self):
		doc = frappe.new_doc("Address Fetcher")
		doc.status = "Completed"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_save_allowed_when_pending(self):
		# `parties` is mandatory and `party` is a Dynamic Link, so a real
		# party master is required. Reuse an existing Customer; skip on an
		# empty site rather than dragging in ERPNext master bootstrap.
		party = frappe.db.get_value("Customer", {}, "name")
		if not party:
			self.skipTest("no Customer master available to link")

		doc = frappe.get_doc(
			{
				"doctype": "Address Fetcher",
				"status": "Pending",
				"parties": [{"party_type": "Customer", "party": party}],
			}
		)
		doc.save()
		self.assertTrue(doc.name)

	def test_fetch_parties_rejects_invalid_party_type(self):
		doc = frappe.new_doc("Address Fetcher")
		doc.status = "Pending"
		self.assertRaises(frappe.ValidationError, doc.fetch_parties, "User")

	def test_fetch_parties_blocked_when_not_pending(self):
		doc = frappe.new_doc("Address Fetcher")
		doc.status = "In Process"
		self.assertRaises(frappe.ValidationError, doc.fetch_parties, "Customer")

	def test_init_blocked_when_not_pending(self):
		doc = frappe.new_doc("Address Fetcher")
		doc.status = "In Process"
		self.assertRaises(frappe.ValidationError, doc.init_address_creation)

	def test_create_address_blocked_when_not_in_process(self):
		doc = frappe.new_doc("Address Fetcher")
		doc.status = "Pending"
		self.assertRaises(frappe.ValidationError, doc.create_address)


class TestCreateAddressLogic(FrappeTestCase):
	"""Pure-logic tests: db writes and GSTIN lookups are stubbed out."""

	GSTIN_DATA = {
		"GSTIN1": {
			"business_name": "Acme Traders",
			"all_addresses": [
				{"address_line1": "1 Main St", "city": "Kochi"},
				{"address_line1": "2 Side St", "city": "Calicut"},
			],
		},
		"GSTIN-EMPTY": {"business_name": "No Address Co", "all_addresses": []},
	}

	def run_create_address(self, doc):
		with ExitStack() as stack:
			patch_gstin_lookup(stack, self.GSTIN_DATA)
			stack.enter_context(
				patch("frappe.model.document.Document.db_set", in_memory_db_set)
			)
			mock_add = stack.enter_context(
				patch.object(type(doc), "add_address", MagicMock())
			)
			mock_enqueue = stack.enter_context(patch("frappe.enqueue_doc"))
			doc.create_address()
		return mock_add, mock_enqueue

	def test_addresses_created_and_status_completed(self):
		doc = make_fetcher([
			{"party_type": "Customer", "party": "CUST-1", "gstin": "GSTIN1"},
		])
		mock_add, mock_enqueue = self.run_create_address(doc)

		self.assertEqual(mock_add.call_count, 2)
		first_address = mock_add.call_args_list[0].args[0]
		self.assertEqual(first_address["is_primary_address"], 1)
		self.assertEqual(first_address["address_title"], "Acme Traders")
		self.assertEqual(doc.parties[0].fetched, 1)
		self.assertEqual(doc.status, "Completed")
		mock_enqueue.assert_not_called()

	def test_party_without_gstin_is_marked_fetched(self):
		doc = make_fetcher([
			{"party_type": "Customer", "party": "CUST-1", "gstin": ""},
		])
		mock_add, _ = self.run_create_address(doc)
		self.assertEqual(mock_add.call_count, 0)
		self.assertEqual(doc.parties[0].fetched, 1)
		self.assertEqual(doc.status, "Completed")

	def test_gstin_without_addresses_still_completes(self):
		# regression: rows with no address data used to leave the
		# document stuck "In Process" forever
		doc = make_fetcher([
			{"party_type": "Customer", "party": "CUST-1", "gstin": "GSTIN-EMPTY"},
			{"party_type": "Customer", "party": "CUST-2", "gstin": "GSTIN1"},
		])
		mock_add, _ = self.run_create_address(doc)
		self.assertEqual(mock_add.call_count, 2)
		self.assertEqual(doc.parties[0].fetched, 1)
		self.assertEqual(doc.status, "Completed")

	def test_batch_of_ten_requeues_instead_of_completing(self):
		doc = make_fetcher([
			{"party_type": "Customer", "party": f"CUST-{i}", "gstin": "GSTIN1"}
			for i in range(12)
		])
		_, mock_enqueue = self.run_create_address(doc)
		mock_enqueue.assert_called_once()
		self.assertEqual(doc.status, "In Process")
		self.assertEqual(sum(1 for row in doc.parties if row.fetched), 10)

	def test_already_fetched_rows_are_skipped(self):
		doc = make_fetcher([
			{"party_type": "Customer", "party": "CUST-1", "gstin": "GSTIN1", "fetched": 1},
		])
		mock_add, _ = self.run_create_address(doc)
		self.assertEqual(mock_add.call_count, 0)
		self.assertEqual(doc.status, "Completed")
