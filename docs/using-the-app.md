# Using the App

This guide walks you through the middleware from first login to daily use. It's written for someone who has already [deployed the middleware](middleware-setup.md) and wants to start scanning.

---

## First Login

Open the middleware in your browser (default: `http://<host>:9930`). On first run you'll be prompted to create an admin account — pick a username and password, then log in.

The **Dashboard** shows your system at a glance:

- **Stats cards** — total barcodes, linked items, unknowns, retry queue
- **Mealie status** — green means connected; if it's red, check your `MEALIE_URL` and `MEALIE_API_KEY` in the [configuration](middleware-setup.md#configuration)
- **Recent scans** — the last 10 barcodes with status badges

If the Mealie status shows connected but the item count is zero, the middleware will sync on first startup. You can also trigger a manual sync from the [Items page](web-dashboard.md#items-items).

---

## Creating a Scan Token

Before your scanner (ESP32, phone app, or shortcut) can submit barcodes, it needs an API token.

1. Go to **Settings → Tokens**
2. Enter a name (e.g. "Kitchen Scanner") and click **Create**
3. Copy the token immediately — it's shown once and stored as a hash

Use this token as a Bearer token in your scanner's HTTP configuration. See [ESPHome Firmware](esphome-firmware.md) or [Mobile App Scanning](mobile-apps.md) for scanner-specific setup.

---

## Your First Scan

Scan any barcode — a product from your kitchen works well. Here's what can happen:

| What you see                  | What it means                                                                                                                     | What to do                                                                                                   |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Green "Added" toast**       | The barcode was already linked to a Mealie item, or was auto-linked via fuzzy matching. The item was added to your shopping list. | Nothing — it worked! If it was auto-linked, review the match (see below).                                    |
| **Yellow "Not Linked" toast** | The product was found in an external database (OpenFoodFacts, etc.) but couldn't be matched to a Mealie item.                     | Go to the barcode detail page and link it manually.                                                          |
| **Red "Unknown" toast**       | The barcode wasn't found in any product database.                                                                                 | Go to the barcode detail page — you can retry the lookup, search for a Mealie item, or create a manual item. |

Live toast notifications appear in the corner of any page via Server-Sent Events — no page reload needed.

---

## Linking a Barcode to a Mealie Item

When a barcode isn't linked, you'll see a notification in the **bell icon** (top-right). Click it to go to the barcode's detail page.

On the detail page you have several options:

- **Fuzzy match candidates** — the middleware shows the top-scoring Mealie items. If one matches, click it to link.
- **Item search** — search your Mealie catalog by name. Type "milk" and pick the right item.
- **Create & link** — if the item doesn't exist in Mealie, create a manual item and link it in one step.

Once linked, any future scan of that barcode goes straight to the shopping list — no lookup needed.

> **Tip:** The bell icon shows only items that need attention. Visiting a barcode's detail page automatically marks its notification as read.

---

## Reviewing Auto-Linked Items

When fuzzy matching links a barcode automatically, it creates a notification flagged **"Auto-linked — review"**. The match might be wrong (e.g. "Organic Whole Milk" matched to "Coconut Milk").

To review:

1. Click the notification in the bell dropdown
2. Check the linked item on the detail page
3. If correct — you're done, the notification is already cleared
4. If wrong — click **Unlink**, then search for the right item and link it

You can also check auto-linked items from the **Activity** page (filter by "Auto-linked" tab).

---

## Scan & Link Mode

### What it's for

When you first set up the system, you probably want to scan everything in your kitchen to build up barcode mappings. But normally every scan adds an item to your Mealie shopping list — that's the point. During initial setup, this floods your list with dozens of items you don't actually need to buy.

**Scan & Link mode** solves this. It temporarily suspends all shopping list additions while keeping everything else running:

- Barcode lookups and caching still happen
- Auto-linking still creates mappings
- Notifications and HA webhooks still fire
- The activity log records every scan

The only thing skipped is the shopping list POST to Mealie.

### How to use it

1. Open the **three-dot menu** (top-right) and click **Scan & Link Mode**
2. Pick a duration: 5 min, 20 min, 1 hour, or 4 hours
3. A **yellow banner** appears at the top of every page showing the countdown
4. Start scanning — all your products get looked up and linked without touching the shopping list
5. When you're done, click **Stop** in the banner or menu, or let the timer expire

When the mode ends, a toast confirms: _"Scan & link ended — scans will now add to your list."_

### When to use it

- **Initial setup** — scan your entire pantry, fridge, and pantry staples
- **Reorganizing** — scanning shelf labels without buying anything
- **Testing** — trying out new barcode types or products

### What happens to barcodes scanned during Scan & Link?

They're fully processed. Check the **Barcodes** page afterward — you'll see all the products you scanned, with status badges showing which are linked, which need attention, and which are unknown. The activity log shows every scan with a "(paused)" label so you know it was during Scan & Link mode.

> **Admin only:** Scan & Link mode can only be started by admin users. Non-admin users see the banner (so they understand why scans aren't adding to the list) but can't toggle it.

---

## Making Labels for Unlabeled Items

Some things don't have barcodes — produce, bulk bin items, homemade stock, spice jars. The **Labels** page lets you create QR code labels for these.

1. Go to **Labels** (`/labels`)
2. Search for a Mealie item (e.g. "Bananas") or type custom text
3. Add items to the label sheet — each gets a QR code preview
4. Click **Register & Print** — the middleware registers the barcodes and opens the browser print dialog
5. Cut and stick the labels on containers or shelves

Each label encodes a `GENERIC:<text>` barcode. When scanned, it fuzzy-matches against your Mealie catalog just like a regular barcode. Labels linked to a specific item at creation time skip fuzzy matching entirely.

> **Tip:** Print on adhesive label paper for a clean result. Standard printer paper and tape works too.

---

## Daily Use

Once your barcodes are linked, the daily workflow is simple:

1. **Run out of something** → scan the barcode (or QR label)
2. The item appears on your **Mealie shopping list** within seconds
3. Check the list when you're at the store

### The Bell

The bell icon in the navbar shows notifications for scans that need your attention. Typical reasons:

- A new barcode was scanned that isn't linked yet
- An auto-link happened that you should review
- A retry failed after the middleware couldn't reach Mealie

Click a notification to go to the barcode detail page and take action. Notifications are deduplicated — scanning the same unknown barcode repeatedly creates only one notification.

### Activity Log

The **Activity** page (`/activities`) shows a full chronological log of every scan event. Use the filter tabs to focus on specific result types (Added, Unknown, Auto-linked, etc.). This is your audit trail — useful for verifying that scans went through, especially after a bulk scanning session.

### Push Notifications (Optional)

If you've configured a Home Assistant webhook (`HA_WEBHOOK_URL`), you'll also get push notifications on your phone for scans that need attention. Tap the notification to open the barcode detail page in the middleware. See [Middleware Setup — Push Notifications](middleware-setup.md#push-notifications-via-home-assistant) for configuration.

---

## Next Steps

- **[How Barcode Scanning Works](barcode-workflow.md)** — deep dive into the scan pipeline, lookup strategies, and fuzzy matching
- **[Web Dashboard](web-dashboard.md)** — full reference for every page and setting
- **[Troubleshooting](troubleshooting.md)** — common issues and fixes
