# Zero-Client-Key Ticket Flow — Design Spec

**Status:** Proposed — awaiting sign-off (Bibin)
**Date:** 2026-07-21
**Apps:** `helpdesk_client` (version-15), `qcs_support_hub` (version-16)

---

## 1. The principle

> "The whole idea of the support client is so that we do not need to keep any API
> reference in the client system. It's unnecessary exposure we can avoid." — Bibin

Today the customer site stores credentials it should not have. This spec removes
all of them.

## 2. What the client stores today (the problem)

| Stored on customer site | Used for | Exposure |
|---|---|---|
| `support_api_token` (Helpdesk `api_key:api_secret`) | Raise ticket, upload recording, poll status, AI-assist | A Helpdesk key sitting on a customer's server. Any customer System Manager can read it via the Settings form or a script. |
| `portal_user` / `portal_user_password` | "Open Support Portal" SSO | A live password for our Helpdesk, stored on their box. |

Both are **outbound** credentials: the client reaches *into* our Helpdesk.

## 3. The change in one line

**Invert the direction.** The client never calls out. The Hub — which already
holds a per-customer client key and already speaks MCP — pulls tickets and pushes
status back.

```
BEFORE   customer site --[Helpdesk API key]--> support.quarkcs.com
AFTER    customer site <--[client key, Hub-side]-- support.quarkcs.com
```

The Hub→client key is not new exposure: it already exists on the Hub
(QCS Support Connection), it is scoped to the customer's own site, and it lives on
infrastructure we control. That is the correct and only place for a credential.

## 4. Target flow

1. **Raise** — User fills the Support Ticket dialog. Client does a plain local
   `insert` of a `Support Ticket` with `status = "Pending"`. No HTTP, no key.
   The screen recording is saved as a normal local File and linked on the ticket.
2. **Pull** — A Hub scheduled job (every 5 min) iterates active
   `QCS Support Connection` records and calls the client's existing MCP
   `get_list` tool for `Support Ticket` where `status = "Pending"`.
3. **Create** — For each, the Hub creates the `HD Ticket` in Helpdesk, and fetches
   the linked recording using the same client credential it already holds, then
   attaches it to the HD Ticket.
4. **Triage** — The Hub runs its existing Anthropic triage (`ai_engine.py`). The
   Anthropic key stays on the Hub, where it always belonged.
5. **Push back** — The Hub calls the client's MCP `set_values` to write
   `ticket_id`, `status`, and the triaged `category` / `priority` onto the local
   Support Ticket. The client's existing notification hook fires and the user gets
   a desk notification.
6. **Ongoing status** — Same push path on each Hub cycle. The client's outbound
   poller (`utils/ticket_sync.py`) is deleted.

## 5. Feature-by-feature impact

| Feature | Impact |
|---|---|
| "Raise a Ticket" launcher + dialog | **Unchanged** |
| Screen recording | **Unchanged** for the user; upload becomes local-only |
| Local Support Ticket list + own/managers permissions | **Unchanged** — becomes the primary record rather than a mirror |
| Status updates + desk notifications | **Unchanged** for the user; delivery flips from pull to push |
| Impersonation | **Unchanged** (already Hub→client over MCP) |
| Address Fetcher (GSTIN) | **Unchanged** (purely local) |
| MCP server / QCS Support Connection | **Unchanged** |
| AI-assist "✨ Improve with AI" button | **Removed.** It requires a client-side key. AI value is delivered by Hub triage in step 4 instead. |
| "Open Support Portal" button | **Removed** (see §6) |

**No user-facing capability is lost** except the portal shortcut.

## 6. Decision: "Open Portal" — Option A (agreed)

Portal SSO is the only feature needing a *synchronous outbound* call, which a
zero-key client cannot make. **Decision: drop the button.** Users track tickets in
the local Support Ticket list, which now carries full status, Hub-assigned
priority/category, and notifications.

Rejected alternative: Hub pushes a rotating short-lived login link on each cycle.
Keeps SSO with no stored password, but the link can be up to one cycle stale and
it adds a credential-shaped object back onto the client. Not worth it.

## 7. Accepted trade-off — ticket creation becomes asynchronous

Today the user gets a Helpdesk ticket number instantly. After this change they see
`Pending` until the Hub's next poll (≤5 min), then the number appears.

This is the real cost of the inversion and should be accepted knowingly. Mitigation:
the dialog confirms "Your ticket has been submitted and will be picked up by
support shortly" rather than quoting an ID, and the local ticket is immediately
visible in the user's list.

## 8. Work required

**Client (`helpdesk_client`, version-15)**
- `utils/support.py` — `create_ticket` becomes a local insert; delete `get_portal_url`; delete `ai_suggest`.
- `utils/ticket_sync.py` — delete the poller and `fetch_remote_statuses`; keep `notify_status_change`, moved to a `Support Ticket` `on_update` hook so it fires when the Hub writes status.
- `hooks.py` — remove the `*/15` cron; add the `doc_events` notification hook.
- `public/js/support_ticket.js` — remove the AI-assist button; adjust the success message.
- `public/js/portal.js` + launcher — remove the portal entry point.
- `hds_support_settings.json` — remove `support_api_token`, `portal_user`, `portal_user_password`; add `Pending` to the Support Ticket status options.
- Migration patch: clear the three credential fields on existing installs.

**Hub (`qcs_support_hub`, version-16)**
- `tasks.py` — new `pull_client_tickets()` using the existing `MCPClient`; register on a 5-minute cron.
- `api.py` — remove `suggest_ticket` (or leave dormant; it is Hub-side and harmless, but unused).
- Recording fetch + HD Ticket attach helper.

**No new MCP tools are needed** — `get_list`, `get_doc`, `set_value`, `set_values`
and `create_doc` already exist in `helpdesk_client/mcp/tools/`.

## 9. Migration & rollback

- Existing local Support Tickets already carry `ticket_id`; they continue to be
  status-pushed by the Hub. No data migration beyond clearing credential fields.
- Rollback is a Frappe Cloud revert to the prior commit on each branch, plus
  re-entering the two credentials in HDS Support Settings.
- Deploy via **Update/Migrate, never uninstall/reinstall** (reinstall drops
  HDS Support Settings and local tickets).

## 10. Sign-off

- [ ] Bibin — direction approved
- [ ] Sammish — Option A on Open Portal confirmed *(confirmed 2026-07-21)*

Once approved, this spec is converted into a task-by-task implementation plan.
