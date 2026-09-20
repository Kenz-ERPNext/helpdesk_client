# Merge genie into helpdesk_client — Report

Branch: `feat/merge-genie`
Commit: `1c3169a3f602d16a92e76c7bdffd1d9da669f805`
Commit message: "feat: merge genie user-facing features (Support Ticket, tracking/sync, impersonation, address fetcher) into helpdesk_client"

## Step 0 — branch
`git -C apps/helpdesk_client checkout -b feat/merge-genie` — done, switched to new branch.

## Step 1 — utils: package conversion + genie modules
- `git -C apps/helpdesk_client mv helpdesk_client/utils.py helpdesk_client/utils/__init__.py` — done (client content preserved exactly, verified via git rename detection at 100%).
- Copied `support.py`, `ticket_sync.py`, `impersonation.py`, `requests.py` from SRC utils/ into DST utils/.
- Repathed with the safe sed form.
- Verify: `python3 -c "import ast; ..."` → printed `UTILS-OK`.

## Step 2 — boot.py
- Copied `apps/qcs_support/qcs_support/boot.py` → `apps/helpdesk_client/helpdesk_client/boot.py`.
- Ran safe sed — no changes applied (the file only references `frappe.get_cached_doc("HDS Support Settings")`, which contains no `qcs_support` token, as anticipated by the brief).

## Step 3 — setup.py: create_genie_folder
- Read SRC `setup/file.py`, appended `create_genie_folder()` verbatim to the end of DST `setup.py` (import frappe already present at top — not duplicated).
- Added a `create_genie_folder()` call at the end of `after_install()` in DST `setup.py`, alongside the existing `_create_support_user()` and `_create_default_settings()` calls. No duplicate call added.

## Step 4 — public/js
- Created `apps/helpdesk_client/helpdesk_client/public/js/` (did not exist; only `.gitkeep` was present in `public/`).
- Copied all 5 files from SRC public/js (`file_uploader.js`, `impersonation.js`, `portal.js`, `qcs_support.bundle.js`, `support_ticket.js`).
- Deleted the copied `qcs_support.bundle.js` and wrote a new `helpdesk_client.bundle.js` with the three import lines (`file_uploader.js`, `support_ticket.js`, `portal.js`).
- Ran safe sed over `*.js` — repathed 3 RPC method strings:
  - `impersonation.js`: `qcs_support.utils.impersonation.generate_impersonation_url` → `helpdesk_client.utils.impersonation.generate_impersonation_url`
  - `support_ticket.js`: `qcs_support.utils.support.create_ticket` → `helpdesk_client.utils.support.create_ticket`
  - `portal.js`: `qcs_support.utils.support.get_portal_url` → `helpdesk_client.utils.support.get_portal_url`
- Confirmed the success link `/app/support-ticket/${encodeURIComponent(r.message)}` is unchanged in `support_ticket.js` (no `qcs_support` token there).

## Step 5 — doctypes (Support Ticket + address fetcher trio)
- Copied `support_ticket`, `address_fetcher`, `address_fetcher_party`, `support_ticket_details` folders from SRC into DST `helpdesk_client/helpdesk_client/doctype/`.
- Removed `__pycache__` dirs that came along with the `cp -R` (not tracked by git anyway — `__pycache__/` is gitignored — but cleaned for hygiene).
- Repathed all `.py` and `.js` files in those 4 folders with the safe sed.
- Fixed the `"module"` field in all 4 JSON files from `"QCS Support"` → `"Helpdesk Client"`.
- Verify: all 4 JSON parse via `json.load` and each reports `module == "Helpdesk Client"` — confirmed OK for `support_ticket.json`, `address_fetcher.json`, `address_fetcher_party.json`, `support_ticket_details.json`.
- Verify: no bare `qcs_support` token remained in those 4 folders after sed (grep empty).

## Step 6 — merge settings (fields + controller)
JSON (`hds_support_settings.json`):
- Appended the 14 genie fieldnames to `field_order` after `max_report_rows`: `support_portal_section, support_url, column_break_nuxg, enable_ticket_raising, support_api_token, ticket_details, column_break_atib, save_recording, section_break_tazx, max_recording_size, enable_user_impersonation, enable_portal_access, portal_user, portal_user_password`.
- Appended the corresponding 14 field definitions to `fields` (verbatim from SRC, including `ticket_details` Table → options `Support Ticket Details`).
- Kept all existing client fields (`enabled`, `allow_write_operations`, hub/token/ACL/limits sections) untouched.
- Kept `"module": "Helpdesk Client"` (was already correct in DST, untouched).
- Verify: `json.load` succeeds; `module == "Helpdesk Client"`; `field_order` and `fields` fieldnames sets match exactly (34 fields, 34 field_order entries, no duplicates/omissions).

Controller (`hds_support_settings.py`):
- Kept existing `before_save` (normalize_site_url) unchanged.
- Added imports: `import frappe`, `from frappe import _`, `from helpdesk_client.utils.requests import make_request` (alongside existing `from helpdesk_client.utils import normalize_site_url`).
- Added `validate(self)` calling `self.validate_sp_access()`.
- Added `validate_sp_access(self)` (Helpdesk-install check), copied verbatim from SRC with the import repathed to `helpdesk_client.utils.requests`.
- Final class has both `before_save` and `validate`/`validate_sp_access`. Confirmed tabs-indentation consistent with rest of file; `py_compile` passes.

## Step 7 — tests
- Copied SRC `tests/` directory (`__init__.py`, `bootstrap.py`, `test_boot.py`, `test_impersonation.py`, `test_requests.py`, `test_setup.py`, `test_support.py`, `test_ticket_sync.py`) into DST `helpdesk_client/tests/`.
- Removed the copied `__pycache__` (gitignored, cleaned for hygiene).
- Repathed all `.py` files (including `bootstrap.py`) with the safe sed.
- **Adaptation required**: `test_setup.py` imported `from helpdesk_client.setup.file import create_genie_folder` after sed — this is wrong for DST because, per Step 3, DST's `setup.py` is a flat module (no `setup/` package, no `file.py` submodule) — `create_genie_folder` was appended directly into `helpdesk_client/setup.py`. Fixed the import to `from helpdesk_client.setup import create_genie_folder`. All other test files' imports already matched DST's actual module layout (`helpdesk_client.utils.requests`, `helpdesk_client.utils.impersonation`, `helpdesk_client.boot`, `helpdesk_client.utils.ticket_sync`, `helpdesk_client.utils.support`) with no further changes needed.
- Verify: no remaining bare `qcs_support` token in `tests/` (grep empty); `python3 -m py_compile` on all test files succeeded.

## Step 8 — hooks.py
Edited DST `hooks.py`, keeping `app_name = "helpdesk_client"` and all existing hooks (`after_install`, `after_uninstall`, `before_request`). Changes:
- `app_title` changed from `"Helpdesk Client"` → `"Genie"`.
- Added `app_include_js = ["helpdesk_client.bundle.js"]`.
- Added `doctype_js = {"User": "public/js/impersonation.js"}`.
- Added `extend_bootinfo = "helpdesk_client.boot.set_bootinfo"`.
- Added `after_migrate = "helpdesk_client.setup.create_genie_folder"` (alongside existing `after_install`/`after_uninstall`, no duplication).
- Added `permission_query_conditions = {"Support Ticket": "helpdesk_client.helpdesk_client.doctype.support_ticket.support_ticket.get_permission_query_conditions"}` — verified `get_permission_query_conditions` is defined in the copied `support_ticket.py`.
- Replaced the empty `scheduler_events = {}` with `scheduler_events = {"hourly": ["helpdesk_client.utils.ticket_sync.sync_ticket_statuses"]}` — verified `sync_ticket_statuses` is defined in the copied `utils/ticket_sync.py`. Confirmed only one active (non-commented) `scheduler_events` assignment remains in the file (the large commented-out template block below is untouched, as it was already commented).
- Added `before_tests = "helpdesk_client.tests.bootstrap.before_tests"` (existing commented-out `# before_tests = ...` line left as-is above it).
- `py_compile` on `hooks.py` succeeded.

## Step 9 — static verification (all commands run from bench root)

1. `grep -rn "helpdesk_client_client" apps/helpdesk_client/helpdesk_client` → **EMPTY** (no double-suffix).
2. `grep -rn "qcs_support\([^_]\)" apps/helpdesk_client/helpdesk_client --include="*.py" --include="*.js"` → **EMPTY** (no bare app-id token left in any .py/.js file). Note: had to quote the `--include` globs under zsh (bare `--include=*.py` triggers zsh glob expansion before reaching grep and errors with "no matches found" — this is a shell quirk, not a grep/data issue; quoted form ran clean).
3. `grep -rn "Genie Ticket\|genie_ticket\|genie-ticket\|Genie Settings\|from genie\.\|import genie\." apps/helpdesk_client/helpdesk_client` → **EMPTY**.
4. `python3 -m py_compile $(find apps/helpdesk_client/helpdesk_client -name '*.py')` → succeeded, echoed **PY-OK**.
5. `node --check` on every new/updated JS file (`public/js/file_uploader.js`, `impersonation.js`, `portal.js`, `helpdesk_client.bundle.js`, `support_ticket.js`, and the doctype JS `support_ticket.js`, `address_fetcher.js`) → all **OK**.

## Step 10 — build + commit

- Redis check: `redis-cli -p 13002 ping` / `-p 11002 ping` → both `PONG` already, no need to start redis-server manually.
- `bench build --app helpdesk_client` → `DONE  Total Build Time: 69.085ms`, bundle compiled to `helpdesk_client/dist/js/helpdesk_client.bundle.FJP6TDYO.js` (7.24 Kb), no errors. `dist/` output is gitignored via the app's existing `.gitignore` (`dist/` pattern), confirmed via `git check-ignore -v`.
- Reviewed `git status` before staging: file set matched exactly what the brief's steps produced (boot.py, public/js/*, 4 doctype folders, settings json+py changes, setup.py changes, hooks.py changes, tests/*, utils/* incl. the utils.py→utils/__init__.py rename). No stray/unexpected files.
- Staged with `git -C apps/helpdesk_client add -A -- helpdesk_client` (scoped to the app package dir, deliberately excluding the untracked `.superpowers/` brief/report directory, which is out of scope for this feature commit).
- Committed: `1c3169a3f602d16a92e76c7bdffd1d9da669f805` — "feat: merge genie user-facing features (Support Ticket, tracking/sync, impersonation, address fetcher) into helpdesk_client" — 39 files changed, 2183 insertions(+), 3 deletions(-).
- Did **not** run `bench migrate` or `run-tests`, per instructions (left for a later step/site decision).
- Did **not** touch `apps/genie` or `apps/qcs_support`, and did not touch the Hub.

## Adaptations from the brief (summary)
1. **test_setup.py import fix**: sed-repathed import `helpdesk_client.setup.file` doesn't exist in DST (DST's `create_genie_folder` lives directly in `setup.py`, not a `setup/file.py` submodule per Step 3's "no package" instruction). Fixed to `from helpdesk_client.setup import create_genie_folder`.
2. **zsh glob quoting**: the Step 9 grep command as literally written (`--include=*.py`) fails under zsh due to glob expansion; used quoted `--include="*.py"` — same semantics, no behavior change.
3. Cleaned up `__pycache__` directories that `cp -R` carried over from SRC (gitignored, so not a commit-affecting change, just hygiene).

No other deviations. All merges preserved existing client code (before_save, after_install support-user/settings creation, existing client settings fields, existing hooks) as required.
