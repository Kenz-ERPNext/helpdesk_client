# Zero-Client-Key Ticket Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every outbound credential from the customer site by inverting the ticket flow — the Hub pulls tickets from the client over the existing MCP connection and pushes status back.

**Architecture:** The client becomes credential-free and offline-only: raising a ticket is a plain local `insert`. The Hub, which already holds a per-customer client key and an `MCPClient`, runs a 5-minute job that pulls `Pending` local tickets, creates the HD Ticket, triages it, and writes status back via MCP `set_values`. See the spec at `docs/zero-client-key-design.md`.

**Tech Stack:** Frappe v15 (client) / v16 (Hub), MCP over Streamable HTTP + JSON-RPC 2.0, Anthropic Claude (Hub-side only), `FrappeTestCase`.

## Global Constraints

- Client app `helpdesk_client` on branch **`version-15`**; Hub app `qcs_support_hub` on branch **`version-16`**. Never cross-commit.
- Frappe **v15** on the client: use `FrappeTestCase` only — `IntegrationTestCase` / `UnitTestCase` do not exist.
- The client must end with **zero stored credentials**. No `support_api_token`, no `portal_user_password`, no Anthropic key. Any new outbound HTTP call on the client is a plan violation.
- `frappe.only_for()` is a **no-op** under `frappe.flags.in_test` — assert permissions by patching it, not by calling it.
- `frappe.get_list(pluck="name")` returns plain strings — compare against strings, not ints.
- Deploy to Frappe Cloud via **Update/Migrate, never uninstall/reinstall** (reinstall drops HDS Support Settings and local tickets).
- Run client tests per-module **with `--skip-before-tests`**: `bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_support`.
  Without the flag, `erpnext.setup.utils.before_tests` runs first (hooks fire in app-install order) and dies on ksa_compliance's mandatory ZATCA field `Mode of Payment.custom_zatca_payment_means_code` before our own `before_tests` shim can relax it. None of these tests need `_Test Company`.
- `redis_cache` (13002) and `redis_queue` (11002) must be running or `bench migrate` refuses to start: `redis-server config/redis_cache.conf --daemonize yes && redis-server config/redis_queue.conf --daemonize yes`.
- Every task ends with a commit. Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Environments

**Production (do not test against):**

| Role | Site | App | Frappe |
|---|---|---|---|
| Client | `avientekv21.frappe.cloud` | `helpdesk_client` (`version-15`) | v15 |
| Hub | `support.quarkcs.com` | `qcs_support_hub` (`version-16`) + Helpdesk | v16 |

**Local bench `frappe-bench-15-qcs` (Frappe 15.113.1):**

| Site | Role |
|---|---|
| `avintek.local` | Client dev/test site — `helpdesk_client` installed. Tasks 1-5 run here. |
| `team.quarkcs.local` | Unused (bare frappe + qcs_team_sync) |

`qcs_support_hub` is present in `apps/` but **installed on no local site**, Helpdesk is not cloned, and this bench is v15 while the Hub targets v16. Hub code therefore cannot be executed locally.

**Frappe Cloud staging (being provisioned by Sammish):** two new sites mirroring the production pair —

- *Staging client:* Frappe **v15** + `helpdesk_client` on branch `version-15`.
- *Staging hub:* Frappe **v16** + **Helpdesk** + `qcs_support_hub` on branch `version-16`.
- Pair them: on the staging hub create a QCS Support Connection pointing at the staging client's site URL, using an API key generated for a support user **on the staging client**. Nothing is stored on the client side.

Tasks 6-9 are written now and **executed on the staging hub once it exists** — substitute the staging hub site name for `<staging-hub>` in their test commands. Task 10 runs against the staging pair first, and only then against production.

## File Structure

**Client (`apps/helpdesk_client/helpdesk_client/`)**

| File | Responsibility after this plan |
|---|---|
| `helpdesk_client/doctype/support_ticket/support_ticket.json` | Local ticket record — now the primary record, holds `description`, `Pending` status, Hub-written `category`/`priority` |
| `helpdesk_client/doctype/support_ticket/support_ticket.py` | Controller — permission query + `on_update` notification. `refresh_status` removed. |
| `utils/support.py` | `create_ticket` only — a local insert. No HTTP. |
| `utils/ticket_sync.py` | **Deleted** — replaced by Hub push |
| `utils/notifications.py` | **New** — `notify_status_change`, called from the doctype `on_update` |
| `helpdesk_client/doctype/hds_support_settings/hds_support_settings.json` | Settings minus all credential fields |
| `patches/v1_0/clear_client_credentials.py` | **New** — wipes stored credentials on existing installs |
| `public/js/support_ticket.js` | Dialog — no AI button, async success message |
| `public/js/portal.js` | **Deleted** |

**Hub (`apps/qcs_support_hub/qcs_support_hub/`)**

| File | Responsibility after this plan |
|---|---|
| `ticket_puller.py` | **New** — pull `Pending` tickets, create HD Tickets, attach recordings, push status back |
| `tasks.py` | Registers `pull_client_tickets` + `push_ticket_statuses` |
| `hooks.py` | 5-minute cron |

---

### Task 1: Support Ticket doctype — make it work without an HD Ticket ID

The current doctype is `autoname: field:ticket_id` with `ticket_id` **required and unique**. Under the new flow the record is created *before* any HD Ticket exists, so autoname must change. It also has **no `description` field** — today the description goes straight to Helpdesk and is never stored locally. The Hub can't pull what isn't stored.

**Files:**
- Modify: `helpdesk_client/helpdesk_client/doctype/support_ticket/support_ticket.json`
- Create: `helpdesk_client/patches/v1_0/migrate_support_ticket_naming.py`
- Modify: `helpdesk_client/patches.txt`
- Test: `helpdesk_client/tests/test_support_ticket.py`

**Interfaces:**
- Produces: a `Support Ticket` that can be inserted with only `subject`, `description`, `raised_by`; named `SUP-.YYYY.-.#####`; `ticket_id` optional, filled later by the Hub.

- [ ] **Step 1: Write the failing test**

```python
# helpdesk_client/tests/test_support_ticket.py
import frappe
from frappe.tests.utils import FrappeTestCase


class TestSupportTicket(FrappeTestCase):
	def test_ticket_can_be_created_without_hd_ticket_id(self):
		doc = frappe.get_doc({
			"doctype": "Support Ticket",
			"subject": "Printer offline",
			"description": "<p>The warehouse printer is offline.</p>",
			"raised_by": "Administrator",
		}).insert(ignore_permissions=True)

		self.assertTrue(doc.name.startswith("SUP-"))
		self.assertEqual(doc.status, "Pending")
		self.assertIsNone(doc.ticket_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_support_ticket`
Expected: FAIL — `MandatoryError: [Support Ticket]: ticket_id`

- [ ] **Step 3: Edit the doctype JSON**

In `support_ticket.json` change `autoname`, `field_order`, and the `ticket_id` / `status` field definitions, and add the new fields:

```json
 "autoname": "naming_series:",
 "field_order": [
  "naming_series",
  "subject",
  "description",
  "status",
  "raised_by",
  "ticket_id",
  "category",
  "priority",
  "screen_recording",
  "last_synced"
 ],
```

Field definitions — replace the `ticket_id` and `status` entries and add the rest:

```json
  {
   "fieldname": "naming_series",
   "fieldtype": "Select",
   "hidden": 1,
   "label": "Series",
   "options": "SUP-.YYYY.-",
   "set_only_once": 1
  },
  {
   "fieldname": "description",
   "fieldtype": "Text Editor",
   "label": "Description",
   "read_only": 1
  },
  {
   "default": "Pending",
   "fieldname": "status",
   "fieldtype": "Select",
   "in_list_view": 1,
   "in_standard_filter": 1,
   "label": "Status",
   "options": "Pending\nOpen\nReplied\nPaused\nResolved\nClosed",
   "read_only": 1
  },
  {
   "fieldname": "ticket_id",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Helpdesk Ticket ID",
   "read_only": 1
  },
  {
   "fieldname": "category",
   "fieldtype": "Data",
   "label": "Category",
   "read_only": 1
  },
  {
   "fieldname": "priority",
   "fieldtype": "Data",
   "label": "Priority",
   "read_only": 1
  },
```

Note: `unique: 1` and `reqd: 1` are **removed** from `ticket_id`. The `subject` field keeps `read_only: 1`.

- [ ] **Step 4: Write the rename patch for existing records**

Existing tickets are named by their HD Ticket ID (e.g. `00042`). They must keep working. Rather than rename them — which would break links — the patch backfills `ticket_id` from the existing `name` so the Hub's status pushes still match.

```python
# helpdesk_client/patches/v1_0/migrate_support_ticket_naming.py
import frappe


def execute():
	"""Backfill ticket_id from name for tickets created under the old
	autoname (field:ticket_id), so Hub status pushes still resolve them.

	Old records keep their HD-ticket-ID names; new records use SUP-YYYY-#####.
	"""
	if not frappe.db.table_exists("Support Ticket"):
		return

	frappe.db.sql("""
		UPDATE `tabSupport Ticket`
		SET ticket_id = name
		WHERE (ticket_id IS NULL OR ticket_id = '')
	""")
```

- [ ] **Step 5: Register the patch**

Append to `helpdesk_client/patches.txt`:

```
helpdesk_client.patches.v1_0.migrate_support_ticket_naming
```

- [ ] **Step 6: Migrate and run the test**

Run: `bench --site avintek.local migrate && bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_support_ticket`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add helpdesk_client/helpdesk_client/doctype/support_ticket/support_ticket.json \
        helpdesk_client/patches/v1_0/migrate_support_ticket_naming.py \
        helpdesk_client/patches.txt \
        helpdesk_client/tests/test_support_ticket.py
git commit -m "feat(ticket): name locally, store description, add Pending status

Support Ticket no longer requires an HD Ticket ID at creation time —
it is created locally first and the Hub fills ticket_id later.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `create_ticket` becomes a local insert

**Files:**
- Modify: `helpdesk_client/utils/support.py`
- Modify: `helpdesk_client/tests/test_support.py`

**Interfaces:**
- Consumes: the Task 1 doctype (`description`, `Pending`, optional `ticket_id`).
- Produces: `create_ticket(title, description, screen_recording=None) -> str` returning the **local** Support Ticket name (e.g. `SUP-2026-00001`), not an HD Ticket ID.

- [ ] **Step 1: Write the failing test**

Replace the existing `create_ticket` tests in `helpdesk_client/tests/test_support.py` with:

```python
	def test_create_ticket_makes_no_outbound_request(self):
		from unittest.mock import patch
		from helpdesk_client.utils.support import create_ticket

		with patch("helpdesk_client.utils.support.make_request") as mocked:
			name = create_ticket(
				title="Printer offline",
				description="<p>Warehouse printer is offline.</p>",
			)

		mocked.assert_not_called()

		doc = frappe.get_doc("Support Ticket", name)
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(doc.subject, "Printer offline")
		self.assertEqual(doc.raised_by, frappe.session.user)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_support`
Expected: FAIL — `AttributeError` on the patch target, or `mocked.assert_not_called()` fails because `create_ticket` still calls Helpdesk.

- [ ] **Step 3: Rewrite `create_ticket`**

In `helpdesk_client/utils/support.py`, replace `create_ticket` and `create_local_ticket` with a single function, and delete `get_portal_url`, `ai_suggest`, and the now-unused `make_request` import:

```python
@frappe.whitelist()
def create_ticket(title, description, screen_recording=None):
	"""Record a support request locally. The Hub picks it up over MCP and
	creates the Helpdesk ticket — the client holds no credentials and makes
	no outbound call."""
	settings = frappe.get_cached_doc("HDS Support Settings")
	if not settings.enable_ticket_raising:
		frappe.throw(_("Ticket raising is not enabled for this site."))

	doc = frappe.get_doc({
		"doctype": "Support Ticket",
		"subject": title,
		"description": description,
		"status": "Pending",
		"raised_by": frappe.session.user,
		"screen_recording": screen_recording,
	}).insert(ignore_permissions=True)

	return doc.name
```

Keep `generate_ticket_details` — Task 6 has the Hub read the `ticket_details` child table over MCP, so it stays useful. Update the imports at the top of the file to:

```python
import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.utils.safe_exec import get_safe_globals, safe_eval
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_support`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add helpdesk_client/utils/support.py helpdesk_client/tests/test_support.py
git commit -m "feat(ticket): create tickets locally, no outbound call

create_ticket now inserts a Pending Support Ticket and returns its local
name. Drops get_portal_url and ai_suggest — both needed a client key.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Notifications fire on Hub-written status, poller deleted

The desk notification is currently emitted by the outbound poller. With the Hub pushing status via MCP `set_values`, the notification must hang off the document itself.

**Files:**
- Create: `helpdesk_client/utils/notifications.py`
- Delete: `helpdesk_client/utils/ticket_sync.py`
- Modify: `helpdesk_client/helpdesk_client/doctype/support_ticket/support_ticket.py`
- Modify: `helpdesk_client/hooks.py`
- Delete: `helpdesk_client/tests/test_ticket_sync.py`
- Modify: `helpdesk_client/helpdesk_client/doctype/support_ticket/test_support_ticket.py`
- Create: `helpdesk_client/tests/test_notifications.py`

**Note:** a second, doctype-level test file already exists at `helpdesk_client/helpdesk_client/doctype/support_ticket/test_support_ticket.py`. Its `test_refresh_status_updates_single_ticket` (line 83) patches `helpdesk_client.utils.ticket_sync.make_request` and will break when that module is deleted. Delete that one test method; keep the rest of the file. This is a different file from the `helpdesk_client/tests/test_support_ticket.py` created in Task 1 — do not confuse them.

**Interfaces:**
- Consumes: `Support Ticket.status` written by the Hub.
- Produces: `notify_status_change(doc, new_status)` in `helpdesk_client.utils.notifications`.

- [ ] **Step 1: Write the failing test**

```python
# helpdesk_client/tests/test_notifications.py
import frappe
from frappe.tests.utils import FrappeTestCase


class TestStatusNotifications(FrappeTestCase):
	def make_ticket(self):
		return frappe.get_doc({
			"doctype": "Support Ticket",
			"subject": "Printer offline",
			"description": "<p>offline</p>",
			"raised_by": "Administrator",
		}).insert(ignore_permissions=True)

	def test_status_change_notifies_the_raiser(self):
		doc = self.make_ticket()
		before = frappe.db.count("Notification Log", {"document_name": doc.name})

		doc.status = "Resolved"
		doc.save(ignore_permissions=True)

		after = frappe.db.count("Notification Log", {"document_name": doc.name})
		self.assertEqual(after, before + 1)

	def test_no_notification_when_status_unchanged(self):
		doc = self.make_ticket()
		doc.save(ignore_permissions=True)
		before = frappe.db.count("Notification Log", {"document_name": doc.name})

		doc.subject = doc.subject  # touch without changing status
		doc.save(ignore_permissions=True)

		after = frappe.db.count("Notification Log", {"document_name": doc.name})
		self.assertEqual(after, before)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_notifications`
Expected: FAIL on `test_status_change_notifies_the_raiser` — no notification is created.

- [ ] **Step 3: Create the notifications module**

```python
# helpdesk_client/utils/notifications.py
# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def notify_status_change(doc, new_status):
	"""Raise a desk notification for the user who reported the ticket."""
	if not doc.raised_by:
		return

	reference = doc.ticket_id or doc.name
	frappe.get_doc({
		"doctype": "Notification Log",
		"for_user": doc.raised_by,
		"type": "Alert",
		"subject": _("Your support ticket #{0} is now {1}").format(reference, _(new_status)),
		"document_type": "Support Ticket",
		"document_name": doc.name,
	}).insert(ignore_permissions=True)
```

- [ ] **Step 4: Hook it to the document**

Replace `helpdesk_client/helpdesk_client/doctype/support_ticket/support_ticket.py` entirely — `refresh_status` goes with the poller:

```python
# Copyright (c) 2026, Wahni IT Solutions Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from helpdesk_client.utils.notifications import notify_status_change


class SupportTicket(Document):
	def on_update(self):
		"""Notify the reporter when the Hub pushes a new status."""
		previous = self.get_doc_before_save()
		if not previous or previous.status == self.status:
			return

		self.db_set("last_synced", now_datetime(), update_modified=False)
		notify_status_change(self, self.status)


def get_permission_query_conditions(user):
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return ""
	return f"(`tabSupport Ticket`.`owner` = {frappe.db.escape(user)})"
```

- [ ] **Step 5: Delete the poller and its hook**

```bash
git rm helpdesk_client/utils/ticket_sync.py helpdesk_client/tests/test_ticket_sync.py
```

In `helpdesk_client/hooks.py`, delete the entire `scheduler_events` block (lines 156-162 — the `*/15` cron). The client has no scheduled jobs after this change.

- [ ] **Step 6: Remove the "Refresh Status" button**

In `helpdesk_client/helpdesk_client/doctype/support_ticket/support_ticket.js`, delete the `refresh_status` custom button and its call — the Hub now pushes status, so there is nothing for the client to pull.

- [ ] **Step 7: Run the tests**

Run: `bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_notifications`
Expected: PASS (both tests)

- [ ] **Step 8: Commit**

```bash
git add -A helpdesk_client/utils helpdesk_client/tests helpdesk_client/hooks.py \
           helpdesk_client/helpdesk_client/doctype/support_ticket
git commit -m "feat(ticket): notify on Hub-pushed status, delete outbound poller

Notifications now fire from Support Ticket.on_update, so they work when the
Hub writes status over MCP. Removes the */15 cron and refresh_status.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Strip every credential from HDS Support Settings

**Files:**
- Modify: `helpdesk_client/helpdesk_client/doctype/hds_support_settings/hds_support_settings.json`
- Modify: `helpdesk_client/helpdesk_client/doctype/hds_support_settings/hds_support_settings.py`
- Create: `helpdesk_client/patches/v1_0/clear_client_credentials.py`
- Modify: `helpdesk_client/patches.txt`
- Create: `helpdesk_client/tests/test_no_credentials.py`

**Blocker to handle first:** the settings controller makes an outbound call on every save. `hds_support_settings.py:20` defines `validate_sp_access()`, which hits `{support_url}/api/method/frappe.utils.change_log.get_versions` with the API token to check Helpdesk is installed. This is what produced the 401s during the July rollout. Once the fields are gone this method raises `AttributeError` and **Settings becomes unsaveable**, so it must go in the same task.

**Interfaces:**
- Produces: a `HDS Support Settings` doctype with no `support_api_token`, `support_url`, `portal_user`, or `portal_user_password` fields.

- [ ] **Step 1: Write the failing test**

```python
# helpdesk_client/tests/test_no_credentials.py
import frappe
from frappe.tests.utils import FrappeTestCase

FORBIDDEN_FIELDS = {
	"support_api_token",
	"support_url",
	"portal_user",
	"portal_user_password",
}


class TestNoStoredCredentials(FrappeTestCase):
	def test_settings_store_no_credentials(self):
		meta = frappe.get_meta("HDS Support Settings")
		present = {df.fieldname for df in meta.fields} & FORBIDDEN_FIELDS
		self.assertEqual(
			present,
			set(),
			f"HDS Support Settings must hold no credentials, found: {sorted(present)}",
		)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_no_credentials`
Expected: FAIL — reports all four fields present.

- [ ] **Step 3: Remove the fields from the settings JSON**

In `hds_support_settings.json`, delete these four entries from `field_order`:

```
"support_url", "support_api_token", "portal_user", "portal_user_password"
```

and delete their four matching objects from `fields`. Also delete `enable_portal_access` and the now-empty `column_break_atib`, since portal access is gone (Option A in the spec).

Do **not** touch `enable_ticket_raising`, `save_recording`, `max_recording_size`, `ticket_details`, or `enable_user_impersonation` — those stay.

Do **not** re-add `depends_on` to `support_portal_section`. It was removed deliberately: a section that depends on the checkbox it contains is a catch-22 and hides itself forever.

- [ ] **Step 4: Delete the outbound validation from the settings controller**

Replace `helpdesk_client/helpdesk_client/doctype/hds_support_settings/hds_support_settings.py` entirely. There is nothing left to validate remotely — the client cannot reach the Hub, and does not need to.

```python
# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from helpdesk_client.utils import normalize_site_url


class HDSSupportSettings(Document):
	def before_save(self):
		if self.qcs_hub_url:
			self.qcs_hub_url = normalize_site_url(self.qcs_hub_url)
```

Note `make_request` and `frappe`/`_` imports go with it. After this task `helpdesk_client/utils/requests.py` has no non-test callers left; leave the module in place for now (the follow-up list covers removing it) but confirm with:

Run: `grep -rn "make_request" helpdesk_client --include="*.py" | grep -v __pycache__ | grep -v tests/`
Expected: only the definition in `utils/requests.py`.

- [ ] **Step 5: Write the credential-wipe patch**

Removing a field from the JSON does not delete the stored value — it lingers in `tabSingles` and in the encrypted `__Auth` table. Wipe both.

```python
# helpdesk_client/patches/v1_0/clear_client_credentials.py
import frappe

CREDENTIAL_FIELDS = (
	"support_api_token",
	"support_url",
	"portal_user",
	"portal_user_password",
)


def execute():
	"""Remove credentials left over from the pre-zero-key ticket flow.

	The client no longer makes outbound calls, so these values are dead
	weight and unnecessary exposure on a customer's server.
	"""
	frappe.db.delete(
		"Singles",
		{"doctype": "HDS Support Settings", "field": ("in", CREDENTIAL_FIELDS)},
	)

	for fieldname in CREDENTIAL_FIELDS:
		frappe.db.delete(
			"__Auth",
			{
				"doctype": "HDS Support Settings",
				"name": "HDS Support Settings",
				"fieldname": fieldname,
			},
		)

	frappe.clear_cache(doctype="HDS Support Settings")
```

- [ ] **Step 6: Register the patch**

Append to `helpdesk_client/patches.txt`:

```
helpdesk_client.patches.v1_0.clear_client_credentials
```

- [ ] **Step 7: Migrate and run the test**

Run: `bench --site avintek.local migrate && bench --site avintek.local run-tests --skip-before-tests --module helpdesk_client.tests.test_no_credentials`
Expected: PASS

If the settings form still shows the old fields after migrate, that is the Frappe **meta cache** — hard-refresh (Cmd+Shift+R) or `bench --site avintek.local clear-cache`.

- [ ] **Step 8: Commit**

```bash
git add helpdesk_client/helpdesk_client/doctype/hds_support_settings/hds_support_settings.json \
        helpdesk_client/helpdesk_client/doctype/hds_support_settings/hds_support_settings.py \
        helpdesk_client/patches/v1_0/clear_client_credentials.py \
        helpdesk_client/patches.txt \
        helpdesk_client/tests/test_no_credentials.py
git commit -m "feat(settings): remove all stored credentials from the client

Drops support_url, support_api_token, portal_user and portal_user_password
from HDS Support Settings and wipes existing values from Singles and __Auth.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Client UI — async confirmation, portal removed

**Files:**
- Modify: `helpdesk_client/public/js/support_ticket.js`
- Delete: `helpdesk_client/public/js/portal.js`
- Modify: `helpdesk_client/public/js/helpdesk_client.bundle.js`

**Interfaces:**
- Consumes: `create_ticket` from Task 2, which now returns a local `SUP-YYYY-#####` name.

- [ ] **Step 1: Update the success message**

The dialog currently promises a Helpdesk ticket number. There is no number yet, so it must not claim one. In `support_ticket.js`, replace the `callback` inside `raise_ticket`:

```javascript
			callback: (r) => {
				if (!r.exc && r.message) {
					frappe.show_alert({
						indicator: "green",
						message: __("Ticket submitted"),
					});
					this.dialog.hide();
					frappe.msgprint(
						__("Your ticket has been submitted ({0}) and will be picked up by support shortly. You will be notified as it progresses.",
							[`<a href="/app/support-ticket/${encodeURIComponent(r.message)}">${r.message}</a>`])
					)
				}
			}
```

- [ ] **Step 2: Delete the portal entry point**

```bash
git rm helpdesk_client/public/js/portal.js
```

In `helpdesk_client/public/js/helpdesk_client.bundle.js`, delete the `import "./portal";` line (keep the `file_uploader`, `support_ticket`, and `launcher` imports).

- [ ] **Step 3: Build and verify**

Run: `bench build --app helpdesk_client`
Expected: build succeeds. Then:

Run: `grep -r "ai_assist\|ai_suggest\|get_portal_url\|OpenPortal" helpdesk_client/ --include=*.js --include=*.py | grep -v dist/`
Expected: **no output** — the source tree is free of every credential-dependent entry point. (`public/dist/` is gitignored and regenerated on deploy; ignore hits there.)

- [ ] **Step 4: Commit**

```bash
git add -A helpdesk_client/public/js
git commit -m "feat(ui): async ticket confirmation, remove portal entry point

The dialog no longer quotes a Helpdesk ID it does not have yet. Open Portal
is gone — it required a stored password (Option A in the design spec).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Hub pulls Pending tickets and creates HD Tickets

Switch to the Hub repo: `cd apps/qcs_support_hub && git checkout version-16`.

**Files:**
- Create: `qcs_support_hub/ticket_puller.py`
- Test: `qcs_support_hub/tests/test_ticket_puller.py`

**Interfaces:**
- Consumes: `MCPClient(connection_name).call_tool(tool_name, arguments)` from `qcs_support_hub/mcp_client.py:112`, which returns `{"content": [{"type": "text", "text": "<json>"}], "isError": bool}`.
- Produces: `pull_client_tickets() -> int` (count created) and `_pending_tickets(mcp) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# qcs_support_hub/tests/test_ticket_puller.py
import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


def mcp_result(payload):
	return {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": False}


class TestTicketPuller(FrappeTestCase):
	def test_pending_tickets_parses_mcp_payload(self):
		from qcs_support_hub.ticket_puller import _pending_tickets

		mcp = MagicMock()
		mcp.call_tool.return_value = mcp_result([
			{"name": "SUP-2026-00001", "subject": "Printer offline",
			 "description": "<p>offline</p>", "raised_by": "user@avientek.com",
			 "screen_recording": "/private/files/rec.mp4"},
		])

		tickets = _pending_tickets(mcp)

		self.assertEqual(len(tickets), 1)
		self.assertEqual(tickets[0]["name"], "SUP-2026-00001")
		mcp.call_tool.assert_called_once()
		args = mcp.call_tool.call_args[0]
		self.assertEqual(args[0], "get_list")
		self.assertEqual(args[1]["doctype"], "Support Ticket")
		self.assertEqual(args[1]["filters"], {"status": "Pending"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: FAIL — `ModuleNotFoundError: No module named 'qcs_support_hub.ticket_puller'`

- [ ] **Step 3: Write the puller**

```python
# qcs_support_hub/ticket_puller.py
# Copyright (c) 2026, Quark Cyber Systems FZC and contributors
# For license information, please see license.txt

"""Pull Pending Support Tickets from customer sites over MCP and turn them
into HD Tickets. The customer site holds no credentials — every call
originates here, using the per-connection key stored on the Hub."""

import json

import frappe

from qcs_support_hub.mcp_client import MCPClient

PULL_LIMIT = 20


def _unwrap(result: dict):
	"""MCP tool results arrive as {"content": [{"type": "text", "text": "<json>"}]}."""
	if not result or result.get("isError"):
		raise ValueError("MCP call failed: %s" % result)

	for block in result.get("content", []):
		if block.get("type") == "text":
			return json.loads(block["text"])

	return None


def _pending_tickets(mcp: MCPClient) -> list[dict]:
	"""Fetch tickets the customer has raised but we have not processed."""
	result = mcp.call_tool(
		"get_list",
		{
			"doctype": "Support Ticket",
			"filters": {"status": "Pending"},
			"fields": [
				"name", "subject", "description", "raised_by",
				"screen_recording", "creation",
			],
			"limit": PULL_LIMIT,
		},
	)
	return _unwrap(result) or []
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: PASS

- [ ] **Step 5: Write the failing test for HD Ticket creation**

Append to `qcs_support_hub/tests/test_ticket_puller.py`:

```python
	def test_creates_hd_ticket_from_pulled_payload(self):
		from qcs_support_hub.ticket_puller import _create_hd_ticket

		hd_name = _create_hd_ticket(
			connection_name="QCS-CONN-TEST",
			customer="Avientek Electronics Trading LLC",
			ticket={
				"name": "SUP-2026-00001",
				"subject": "Printer offline",
				"description": "<p>offline</p>",
				"raised_by": "user@avientek.com",
			},
		)

		hd = frappe.get_doc("HD Ticket", hd_name)
		self.assertEqual(hd.subject, "Printer offline")
		self.assertEqual(hd.customer, "Avientek Electronics Trading LLC")
```

- [ ] **Step 6: Run it to verify it fails**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: FAIL — `ImportError: cannot import name '_create_hd_ticket'`

- [ ] **Step 7: Implement HD Ticket creation**

Append to `qcs_support_hub/ticket_puller.py`:

```python
def _create_hd_ticket(connection_name: str, customer: str, ticket: dict) -> str:
	"""Create the Helpdesk ticket for a pulled customer request."""
	hd = frappe.get_doc({
		"doctype": "HD Ticket",
		"subject": ticket.get("subject") or "Support request",
		"description": ticket.get("description") or "",
		"customer": customer,
		"raised_by": ticket.get("raised_by"),
		"via_customer_portal": 1,
	}).insert(ignore_permissions=True)

	frappe.db.set_value(
		"HD Ticket", hd.name,
		{
			"custom_qcs_connection": connection_name,
			"custom_client_ticket": ticket.get("name"),
		},
		update_modified=False,
	)

	return hd.name
```

If `custom_qcs_connection` / `custom_client_ticket` do not exist on HD Ticket, create them first as Custom Fields (Data, read-only) via `Customize Form → HD Ticket`, and add them to the app's fixtures so they ship with the app.

- [ ] **Step 8: Run the tests**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: PASS (both tests)

- [ ] **Step 9: Commit**

```bash
git add qcs_support_hub/ticket_puller.py qcs_support_hub/tests/test_ticket_puller.py
git commit -m "feat(hub): pull Pending client tickets over MCP into HD Tickets

Inverts the ticket flow so the customer site needs no credentials.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Attach the screen recording to the HD Ticket

**Files:**
- Modify: `qcs_support_hub/ticket_puller.py`
- Modify: `qcs_support_hub/tests/test_ticket_puller.py`

**Interfaces:**
- Consumes: `ticket["screen_recording"]` — a client-site file URL like `/private/files/rec.mp4`.
- Produces: `_attach_recording(mcp, hd_ticket_name, file_url) -> str | None` returning the Hub File name.

- [ ] **Step 1: Write the failing test**

```python
	def test_attach_recording_skips_when_absent(self):
		from qcs_support_hub.ticket_puller import _attach_recording

		self.assertIsNone(_attach_recording(MagicMock(), "HD-TICKET-0001", None))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: FAIL — `ImportError: cannot import name '_attach_recording'`

- [ ] **Step 3: Implement the fetch-and-attach**

The recording lives on the customer's site as a private File. The Hub already has that site's API key on the connection, so it fetches over plain HTTP with token auth — no new MCP tool needed.

Append to `qcs_support_hub/ticket_puller.py`:

```python
import requests

RECORDING_TIMEOUT = 60
MAX_RECORDING_BYTES = 100 * 1024 * 1024


def _attach_recording(mcp: MCPClient, hd_ticket_name: str, file_url: str | None) -> str | None:
	"""Download the customer's screen recording and attach it to the HD Ticket."""
	if not file_url:
		return None

	response = requests.get(
		f"{mcp.site_url.rstrip('/')}{file_url}",
		headers={"Authorization": f"token {mcp.api_key}:{mcp.api_secret}"},
		timeout=RECORDING_TIMEOUT,
		stream=True,
	)
	response.raise_for_status()

	content = response.raw.read(MAX_RECORDING_BYTES + 1, decode_content=True)
	if len(content) > MAX_RECORDING_BYTES:
		frappe.log_error(
			title=f"Recording too large for {hd_ticket_name}",
			message=f"{file_url} exceeded {MAX_RECORDING_BYTES} bytes; not attached",
		)
		return None

	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": file_url.rsplit("/", 1)[-1],
		"attached_to_doctype": "HD Ticket",
		"attached_to_name": hd_ticket_name,
		"is_private": 1,
		"content": content,
	}).insert(ignore_permissions=True)

	return file_doc.name
```

- [ ] **Step 4: Run the tests**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qcs_support_hub/ticket_puller.py qcs_support_hub/tests/test_ticket_puller.py
git commit -m "feat(hub): fetch and attach client screen recordings

Uses the per-connection key already held on the Hub; the client never uploads.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Push status, ticket ID and triage back to the client

**Files:**
- Modify: `qcs_support_hub/ticket_puller.py`
- Modify: `qcs_support_hub/tests/test_ticket_puller.py`

**Interfaces:**
- Consumes: `_create_hd_ticket` (Task 6), `_attach_recording` (Task 7).
- Produces: `_push_back(mcp, client_ticket, values: dict) -> None` and `pull_client_tickets() -> int`.

- [ ] **Step 1: Write the failing test**

```python
	def test_push_back_writes_status_and_ticket_id(self):
		from qcs_support_hub.ticket_puller import _push_back

		mcp = MagicMock()
		mcp.call_tool.return_value = mcp_result({"name": "SUP-2026-00001"})

		_push_back(mcp, "SUP-2026-00001", {"ticket_id": "42", "status": "Open"})

		args = mcp.call_tool.call_args[0]
		self.assertEqual(args[0], "set_values")
		self.assertEqual(args[1]["doctype"], "Support Ticket")
		self.assertEqual(args[1]["name"], "SUP-2026-00001")
		self.assertEqual(args[1]["values"]["status"], "Open")
		self.assertEqual(args[1]["values"]["ticket_id"], "42")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: FAIL — `ImportError: cannot import name '_push_back'`

- [ ] **Step 3: Implement push-back and the top-level job**

Append to `qcs_support_hub/ticket_puller.py`:

```python
def _push_back(mcp: MCPClient, client_ticket: str, values: dict) -> None:
	"""Write status/ID/triage back onto the customer's local Support Ticket."""
	mcp.call_tool(
		"set_values",
		{
			"doctype": "Support Ticket",
			"name": client_ticket,
			"values": values,
		},
	)


def pull_client_tickets() -> int:
	"""Scheduled every 5 minutes: turn Pending client tickets into HD Tickets."""
	connections = frappe.get_all(
		"QCS Support Connection",
		filters={"connection_status": "Connected"},
		fields=["name", "customer_name"],
	)

	created = 0
	for conn in connections:
		try:
			mcp = MCPClient(conn.name)
			tickets = _pending_tickets(mcp)
		except Exception:
			frappe.log_error(
				title=f"Ticket pull failed for {conn.name}",
				message=frappe.get_traceback(),
			)
			continue

		for ticket in tickets:
			try:
				hd_name = _create_hd_ticket(conn.name, conn.customer_name, ticket)
				_attach_recording(mcp, hd_name, ticket.get("screen_recording"))
				_push_back(mcp, ticket["name"], {
					"ticket_id": hd_name,
					"status": "Open",
				})
				frappe.db.commit()
				created += 1
			except Exception:
				frappe.db.rollback()
				frappe.log_error(
					title=f"Ticket import failed for {ticket.get('name')}",
					message=frappe.get_traceback(),
				)

	return created
```

The `_push_back` happens **after** `frappe.db.commit()` is safe to call — if push-back fails the ticket stays `Pending` on the client and is retried next cycle. Creating a duplicate HD Ticket on retry is the failure mode; Task 9's dedupe guard handles it.

- [ ] **Step 4: Add the status-sync job**

Append:

```python
def push_ticket_statuses() -> int:
	"""Scheduled every 5 minutes: mirror HD Ticket status onto client tickets."""
	rows = frappe.get_all(
		"HD Ticket",
		filters={
			"custom_client_ticket": ["is", "set"],
			"custom_qcs_connection": ["is", "set"],
		},
		fields=["name", "status", "priority", "custom_client_ticket", "custom_qcs_connection"],
		limit=200,
	)

	by_connection = {}
	for row in rows:
		by_connection.setdefault(row.custom_qcs_connection, []).append(row)

	pushed = 0
	for connection_name, tickets in by_connection.items():
		try:
			mcp = MCPClient(connection_name)
		except Exception:
			frappe.log_error(
				title=f"Status push failed for {connection_name}",
				message=frappe.get_traceback(),
			)
			continue

		for row in tickets:
			try:
				_push_back(mcp, row.custom_client_ticket, {
					"status": row.status,
					"priority": row.priority or "",
				})
				pushed += 1
			except Exception:
				frappe.log_error(
					title=f"Status push failed for {row.name}",
					message=frappe.get_traceback(),
				)

	return pushed
```

- [ ] **Step 5: Run the tests**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add qcs_support_hub/ticket_puller.py qcs_support_hub/tests/test_ticket_puller.py
git commit -m "feat(hub): push ticket ID and status back to client over MCP

Completes the inverted flow: the client is written to, never reads out.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Dedupe guard, triage wiring and the 5-minute cron

**Files:**
- Modify: `qcs_support_hub/ticket_puller.py`
- Modify: `qcs_support_hub/tasks.py`
- Modify: `qcs_support_hub/hooks.py`
- Modify: `qcs_support_hub/tests/test_ticket_puller.py`

**Interfaces:**
- Consumes: `pull_client_tickets`, `push_ticket_statuses` (Task 8); `qcs_support_hub.triage` for AI triage.

- [ ] **Step 1: Write the failing dedupe test**

```python
	def test_already_imported_ticket_is_skipped(self):
		from qcs_support_hub.ticket_puller import _already_imported

		frappe.get_doc({
			"doctype": "HD Ticket",
			"subject": "Dupe check",
			"custom_qcs_connection": "QCS-CONN-TEST",
			"custom_client_ticket": "SUP-2026-00099",
		}).insert(ignore_permissions=True)

		self.assertTrue(_already_imported("QCS-CONN-TEST", "SUP-2026-00099"))
		self.assertFalse(_already_imported("QCS-CONN-TEST", "SUP-2026-00100"))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: FAIL — `ImportError: cannot import name '_already_imported'`

- [ ] **Step 3: Implement the guard and wire triage**

Append to `qcs_support_hub/ticket_puller.py`:

```python
def _already_imported(connection_name: str, client_ticket: str) -> bool:
	"""Guard against re-importing when a previous push-back failed."""
	return bool(
		frappe.db.exists(
			"HD Ticket",
			{
				"custom_qcs_connection": connection_name,
				"custom_client_ticket": client_ticket,
			},
		)
	)
```

In `pull_client_tickets`, add the guard as the first line of the per-ticket `try` block:

```python
			try:
				if _already_imported(conn.name, ticket["name"]):
					_push_back(mcp, ticket["name"], {"status": "Open"})
					continue

				hd_name = _create_hd_ticket(conn.name, conn.customer_name, ticket)
```

**Do not add a triage call here.** The Hub already triages automatically — `qcs_support_hub/hooks.py:146` wires `doc_events = {"HD Ticket": {"after_insert": "qcs_support_hub.triage.auto_triage_ticket"}}`. Creating the HD Ticket in Task 6 fires triage on its own; enqueueing again would triage every ticket twice and double the Anthropic spend.

This means spec §4 step 4 (Hub AI triage) needs **no new code** — it comes free with `_create_hd_ticket`.

- [ ] **Step 4: Register the jobs**

In `qcs_support_hub/tasks.py`, add thin wrappers under the existing functions:

```python
def pull_client_tickets():
	"""Every 5 min: import Pending tickets from customer sites."""
	from qcs_support_hub.ticket_puller import pull_client_tickets as _pull

	return _pull()


def push_ticket_statuses():
	"""Every 5 min: mirror HD Ticket status back to customer sites."""
	from qcs_support_hub.ticket_puller import push_ticket_statuses as _push

	return _push()
```

In `qcs_support_hub/hooks.py`, extend `scheduler_events` (currently lines 159-167) with a `cron` key:

```python
scheduler_events = {
	"cron": {
		"*/5 * * * *": [
			"qcs_support_hub.tasks.pull_client_tickets",
			"qcs_support_hub.tasks.push_ticket_statuses",
		],
	},
	"daily": [
		"qcs_support_hub.tasks.health_check_connections",
		"qcs_support_hub.tasks.retry_pending_triages",
	],
	"weekly": [
		"qcs_support_hub.tasks.sync_model_pricing",
	],
}
```

- [ ] **Step 5: Run the tests**

Run: `bench --site <staging-hub> run-tests --module qcs_support_hub.tests.test_ticket_puller`
Expected: PASS (all tests)

- [ ] **Step 6: Verify the scheduler sees the jobs**

Run: `bench --site support.local console` then:

```python
from frappe.utils.scheduler import get_scheduler_events
print([e for e in frappe.get_hooks("scheduler_events")["cron"]["*/5 * * * *"]])
```

Expected: both `qcs_support_hub.tasks.pull_client_tickets` and `qcs_support_hub.tasks.push_ticket_statuses`.

- [ ] **Step 7: Commit**

```bash
git add qcs_support_hub/ticket_puller.py qcs_support_hub/tasks.py \
        qcs_support_hub/hooks.py qcs_support_hub/tests/test_ticket_puller.py
git commit -m "feat(hub): dedupe guard, triage enqueue and 5-minute cron

Completes the zero-client-key flow end to end.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: End-to-end verification on the live pair

Only run this once Tasks 1-9 are merged and deployed via Frappe Cloud **Update**.

- [ ] **Step 1: Confirm the client holds nothing**

On avientekv21, open HDS Support Settings. Expected: no Support URL, no API Token, no Portal User/Password fields anywhere on the form.

- [ ] **Step 2: Raise a ticket end to end**

Click "Raise a Ticket", fill title + description, record ~5 seconds of screen, submit.
Expected: confirmation names a `SUP-2026-#####` link, no Helpdesk ID. The local ticket shows `Pending`.

- [ ] **Step 3: Wait one cycle (≤5 min) and re-check**

Expected on the client: `status = Open`, `ticket_id` populated with the HD Ticket name.
Expected on support.quarkcs.com: a new HD Ticket for Avientek with the recording attached and triage fields set.

- [ ] **Step 4: Close it on the Hub and confirm the push**

Close the HD Ticket in Helpdesk. Within 5 minutes the client ticket shows `Closed` and the reporter has a desk notification.

- [ ] **Step 5: Confirm no outbound traffic from the client**

Outbound calls are logged to Frappe's core **Integration Request** with `service_name="Genie"` (see `create_request_log` in `helpdesk_client/utils/requests.py`).

Run on the client site: `bench --site <site> console`

```python
print(frappe.get_all(
	"Integration Request",
	filters={"integration_request_service": "Genie"},
	fields=["name", "creation", "status"],
	order_by="creation desc",
	limit=5,
))
```

Expected: no entries created after the deploy timestamp. The client makes no outbound calls.

- [ ] **Step 6: Tick the sign-off boxes**

Update `docs/zero-client-key-design.md` §10 and commit.

---

## Post-plan follow-ups (not in scope)

- Rotate the two API keys pasted in chat on 2026-07-14.
- `qcs_support_hub.api.suggest_ticket` is now unused — remove it in a later cleanup.
- MediaRecorder produces WebM but files are named `.mp4` — mislabelled since before this plan.
