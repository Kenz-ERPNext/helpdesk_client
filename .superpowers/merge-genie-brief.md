# Brief: Merge genie's user-facing features INTO helpdesk_client

Land genie's customer-facing features into the EXISTING `helpdesk_client` app (do NOT create a new app; do NOT touch the Hub). The tested source is the `qcs_support` app at `/Users/sammishthundiyil/frappe-bench-15-qcs/apps/qcs_support/qcs_support/` (call it SRC). Destination is `/Users/sammishthundiyil/frappe-bench-15-qcs/apps/helpdesk_client/helpdesk_client/` (call it DST). Bench root: `/Users/sammishthundiyil/frappe-bench-15-qcs`. Run from bench root.

SRC already contains genie's features repathed to the `qcs_support` app id and with doctype `Genie Ticket` renamed to `Support Ticket`, `Genie Settings` merged into `HDS Support Settings`. You are moving the genie-derived parts into DST and changing the app-id token `qcs_support` → `helpdesk_client`, and the doctype `"module"` to `"Helpdesk Client"`.

CRITICAL sed safety: replace ONLY the bare app-id token, never double-suffix. Use this exact form everywhere: `sed -i '' 's/qcs_support\([^_]\)/helpdesk_client\1/g; s/qcs_support$/helpdesk_client/g'` — this matches `qcs_support` NOT already followed by `_` (so it never turns `helpdesk_client` into `helpdesk_client_client`). After each file group, grep to confirm zero `helpdesk_client_client` and zero bare `qcs_support` (not followed by `_client`).

## Step 0 — branch
`git -C apps/helpdesk_client checkout -b feat/merge-genie`

## Step 1 — utils: convert module → package, add genie modules (preserve client code)
- `mkdir apps/helpdesk_client/helpdesk_client/utils`
- Move client's utils.py to the package init KEEPING its exact content: `git -C apps/helpdesk_client mv helpdesk_client/utils.py helpdesk_client/utils/__init__.py`
- Copy the four genie util modules from SRC and repath them:
  `cp apps/qcs_support/qcs_support/utils/{support,ticket_sync,impersonation,requests}.py apps/helpdesk_client/helpdesk_client/utils/`
  Then repath those four files: `sed -i '' 's/qcs_support\([^_]\)/helpdesk_client\1/g; s/qcs_support$/helpdesk_client/g' apps/helpdesk_client/helpdesk_client/utils/{support,ticket_sync,impersonation,requests}.py`
- Verify: `python3 -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('apps/helpdesk_client/helpdesk_client/utils/*.py')]; print('UTILS-OK')"`

## Step 2 — boot.py
- `cp apps/qcs_support/qcs_support/boot.py apps/helpdesk_client/helpdesk_client/boot.py`
- Repath it with the safe sed. (It reads `frappe.get_cached_doc("HDS Support Settings")` — that string has no `qcs_support` token, stays.)

## Step 3 — setup: add create_genie_folder to the EXISTING setup.py (no package)
- Read `apps/qcs_support/qcs_support/setup/file.py` — it defines `create_genie_folder()`.
- Append that `create_genie_folder` function verbatim to the END of `apps/helpdesk_client/helpdesk_client/setup.py` (add `import frappe` at top if not already imported there).
- In DST setup.py's `after_install`, add a call `create_genie_folder()` at the end (so install creates the Home/Genie File folder). Do NOT duplicate if already present.

## Step 4 — public/js
- `cp apps/qcs_support/qcs_support/public/js/*.js apps/helpdesk_client/helpdesk_client/public/js/` (create the dir if missing)
- Delete the SRC-named bundle if copied, and create the DST bundle: ensure a file `apps/helpdesk_client/helpdesk_client/public/js/helpdesk_client.bundle.js` with:
  `import "./file_uploader.js"` / `import "./support_ticket.js"` / `import "./portal.js"` (three import lines). Remove any `qcs_support.bundle.js` file.
- Repath the JS RPC method strings: `sed -i '' 's/qcs_support\([^_]\)/helpdesk_client\1/g; s/qcs_support$/helpdesk_client/g' apps/helpdesk_client/helpdesk_client/public/js/*.js` (turns `qcs_support.utils.support.create_ticket` → `helpdesk_client.utils.support...`, and `/app/support-ticket/` stays). Confirm the success link is `/app/support-ticket/` still.

## Step 5 — doctypes (Support Ticket + address fetcher trio)
- Copy each folder from SRC to DST:
  `cp -R apps/qcs_support/qcs_support/qcs_support/doctype/{support_ticket,address_fetcher,address_fetcher_party,support_ticket_details} apps/helpdesk_client/helpdesk_client/helpdesk_client/doctype/`
- Repath the python + js in those folders (safe sed) — `.py` and `.js`.
- Fix the doctype JSON module: `sed -i '' 's/"module": "QCS Support"/"module": "Helpdesk Client"/' <each of the 4 doctype .json files>` (there are exactly 4 json to fix: support_ticket.json, address_fetcher.json, address_fetcher_party.json, support_ticket_details.json).
- Verify all 4 JSON parse and are on module "Helpdesk Client".

## Step 6 — merge settings (fields + controller), preserve client code
- Settings JSON: DST `.../doctype/hds_support_settings/hds_support_settings.json` currently has ONLY client fields. Add the genie ticketing fields present in SRC's version (`apps/qcs_support/qcs_support/qcs_support/doctype/hds_support_settings/hds_support_settings.json`): the section + fields `support_url, enable_ticket_raising, support_api_token, ticket_details (Table → Support Ticket Details), save_recording, max_recording_size, enable_user_impersonation, enable_portal_access, portal_user, portal_user_password`. Append them to DST's `field_order` and `fields`, keeping ALL existing client fields. Keep DST module `"Helpdesk Client"`.
- Controller: DST `hds_support_settings.py` currently is `class HDSSupportSettings(Document)` with only `before_save`. KEEP before_save. ADD a `validate(self)` that calls `validate_sp_access(self)`, and add `validate_sp_access` (the Helpdesk-installed check). Copy the validate_sp_access body from SRC's controller (`apps/qcs_support/qcs_support/qcs_support/doctype/hds_support_settings/hds_support_settings.py`) and repath its import `qcs_support.utils.requests` → `helpdesk_client.utils.requests`. Add needed imports (`import frappe`, `from frappe import _`, `from helpdesk_client.utils.requests import make_request`). Final class has BOTH before_save AND validate/validate_sp_access.

## Step 7 — tests
- `cp -R apps/qcs_support/qcs_support/tests apps/helpdesk_client/helpdesk_client/tests`
- Repath the tests dir (safe sed) on all `.py` there. This includes `bootstrap.py`.
- The doctype test files came with Step 5's folders — repath already applied.

## Step 8 — hooks.py (ADD genie hooks, keep client's)
Edit DST `hooks.py`. Keep app_name="helpdesk_client" and all existing hooks (after_install, after_uninstall, before_request). CHANGE `app_title` to `"Genie"`. ADD these lines:
```python
app_include_js = ["helpdesk_client.bundle.js"]
doctype_js = {"User": "public/js/impersonation.js"}
extend_bootinfo = "helpdesk_client.boot.set_bootinfo"
after_migrate = "helpdesk_client.setup.create_genie_folder"
permission_query_conditions = {
	"Support Ticket": "helpdesk_client.helpdesk_client.doctype.support_ticket.support_ticket.get_permission_query_conditions",
}
scheduler_events = {
	"hourly": ["helpdesk_client.utils.ticket_sync.sync_ticket_statuses"],
}
before_tests = "helpdesk_client.tests.bootstrap.before_tests"
```
Note DST's existing `scheduler_events = {}` — REPLACE it with the hourly one above (do not leave two scheduler_events).

## Step 9 — static verification
From bench root:
- `grep -rn "helpdesk_client_client" apps/helpdesk_client/helpdesk_client` → MUST be empty (no double-suffix).
- `grep -rn "qcs_support\([^_]\)" apps/helpdesk_client/helpdesk_client --include=*.py --include=*.js` → MUST be empty (no bare app-id left; every ref is helpdesk_client). Note "QCS Support" (spaces) and "Support Ticket" are fine — you're grepping the lowercase token only.
- `grep -rn "Genie Ticket\|genie_ticket\|genie-ticket\|Genie Settings\|from genie\.\|import genie\." apps/helpdesk_client/helpdesk_client` → MUST be empty. (Legit keeps: `create_genie_folder`, "Genie" folder label, "Genie User" role, `genie_*` bootinfo keys, app_title "Genie" — those are fine.)
- `python3 -m py_compile $(find apps/helpdesk_client/helpdesk_client -name '*.py')` → succeeds; echo PY-OK.
- `node --check` each new/updated JS file.

## Step 10 — build + commit (NO migrate/test yet — that needs a site decision)
- `cd /Users/sammishthundiyil/frappe-bench-15-qcs && bench build --app helpdesk_client 2>&1 | grep -iE "done|error"` → DONE, no error. (Start redis first if needed: `redis-cli -p 13002 ping` else `redis-server config/redis_cache.conf --daemonize yes && redis-server config/redis_queue.conf --daemonize yes`.)
- Commit: `git -C apps/helpdesk_client add -A && git -C apps/helpdesk_client commit -m "feat: merge genie user-facing features (Support Ticket, tracking/sync, impersonation, address fetcher) into helpdesk_client"`

Do NOT modify apps/genie or apps/qcs_support. Do NOT run bench migrate or run-tests (a later step decides the test site). Do NOT touch the Hub.
