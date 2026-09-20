# QCS Support — Setup & Operations Guide

Zero-client-key architecture: the customer site stores **no credentials** and
makes **no outbound calls**. The Hub holds one API key per customer (on its
QCS Support Connection) and does all the reaching. Design: `zero-client-key-design.md`.

## Install

- **Client** `helpdesk_client` (branch `version-15`) on the customer site.
- **Hub** `qcs_support_hub` (branch `version-16`) on a site that already runs
  Helpdesk. The old HD Ticket `raised_outside_working_hours` install error is
  auto-repaired by a `before_install` hook — no manual step.
- Deploy upgrades via Frappe Cloud **Update/Migrate. Never uninstall/reinstall** —
  reinstall drops HDS Support Settings and local Support Tickets.

## Pair a customer (one-time, ~10 min)

**On the client site:**
1. HDS Support Settings → tick **Enabled**, set **QCS Hub URL**, tick
   **Allow Write Operations** (the Hub pushes status back with it), tick
   **Enable Ticket Raising**, Save Recording = **Private**.
2. Create user `support@quarkcs.com` (System Manager, no welcome email).
3. That user → API Access → **Generate Keys**. Copy the pair — it is the only
   secret in the system and it lives on the Hub, never here.

**On the Hub:**
4. Create the HD Customer if missing.
5. New **QCS Support Connection**: customer, Site URL, MCP Endpoint
   `https://<client-site>/api/method/helpdesk_client.mcp.handler.handle`,
   plus the api_key/api_secret from step 3.
6. Trigger **Register Client**. The client verifies the Hub URL matches its
   settings and the connection flips to **Connected**. A URL mismatch is
   refused — that guard is intentional.

**Hub once, not per customer:** QCS Hub Settings → AI Provider + key
(see below). The 5-minute cron jobs register themselves.

## How a ticket flows

1. User clicks the floating **Raise a Ticket** button (a guided tour runs
   until they untick "Show this tour next time"; `?` replays it).
2. They describe the issue, optionally record their screen (the dialog
   minimizes; a draggable pill with a timer floats until Stop — from the
   pill or Chrome's own bar) and capture/attach screenshots.
3. Submit = a **local** Support Ticket, status **Pending**. No HTTP.
4. Within 5 minutes the Hub pulls it over MCP, creates the HD Ticket,
   copies every attached file (📹/🖼 comments in the agent feed), AI-triages
   it, and pushes the ticket number + **Open** back.
5. Status changes on the Hub mirror to the client each cycle; the reporter
   gets desk notifications.

**Expectations to set with users:**
- *Pending for up to 5 minutes is normal.* Stuck longer → check the Hub's
  Error Log; the reason will be there.
- Chrome's *"sharing your screen"* bar cannot be hidden by any website —
  it is browser trusted UI (the user may click its own Hide). *Stop sharing*
  on that bar ends the recording cleanly, same as our Stop button.

## AI

- **Provider** (QCS Hub Settings): `Anthropic` (default — triage +
  investigation sessions), `Anthropic Compatible` (Kimi/Moonshot, GLM —
  set Base URL, everything works), `OpenAI Compatible` (Poolside, Qwen —
  set Base URL, **triage only**; investigation sessions refuse clearly).
- Set **Triage Model** to a model the provider actually serves
  (e.g. `poolside/laguna-s-2.1`) — a wrong model id is the usual cause of
  `Triage Status: Failed`.
- Add the model to **QCS Model Pricing** or usage logs show $0.
- Failed triages retry daily; closed tickets are skipped.

## Troubleshooting quick table

| Symptom | Cause / fix |
|---|---|
| Ticket Pending > 10 min | Hub Error Log names the ticket — usually connection or ACL |
| Media missing on HD Ticket | File must be attached to the client ticket (automatic since v16.1); a customer blocking the `File` doctype in MCP ACL also disables media — ticket still imports |
| Triage Failed | Wrong/missing key, or Triage Model not served by the provider |
| Settings form shows stale fields after Update | Meta cache — hard refresh / `bench clear-cache` |
| Install fails on HD Ticket Check default | Only on pre-16.1 builds; fixed by the `before_install` hook |
