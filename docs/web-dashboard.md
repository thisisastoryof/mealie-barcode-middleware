# Web Dashboard

The middleware includes a full web UI built with [Tabler](https://tabler.io/) (vendored locally — no CDN calls). All pages are server-rendered with Jinja2 templates and enhanced with JavaScript for live updates.

The web UI is protected by username/password login. On first run, you'll be prompted to create an admin account. Check **"Stay signed in"** on the login page to keep your session across browser restarts (duration controlled by `SESSION_MAX_AGE_DAYS`, default 7 days).

---

## Dashboard (`/`)

The home page shows an at-a-glance overview of the system:

- **Stats cards:** Total barcodes, linked, pending, unknown, retry queue depth
- **Mealie status:** Connectivity check + last item sync time
- **Recent scans:** The last 10 scanned barcodes with status badges

The dashboard auto-refreshes via AJAX. When a barcode is scanned, a **live toast notification** appears in the bottom-right corner via Server-Sent Events (SSE) — no page reload needed.

---

## Barcodes (`/barcodes`)

The barcode list shows all known barcodes with filtering tabs:

| Tab     | Shows                                               |
| ------- | --------------------------------------------------- |
| All     | Every barcode the system has seen                   |
| Linked  | Barcodes linked to a Mealie item                    |
| Pending | Barcodes with a product title but no item link      |
| Unknown | Barcodes not found in any external product database |

### Barcode Detail (`/barcodes/{barcode}`)

Each barcode has a detail page showing:

- **Product info:** Title, brand, quantity, product type, lookup source
- **Linked item:** The Mealie item this barcode maps to (if any)
- **Fuzzy match candidates:** Top scoring Mealie items with match scores — useful for manual linking
- **Item search:** Search Mealie items by name to find the right match

**Actions available:**

| Action        | Description                                                                |
| ------------- | -------------------------------------------------------------------------- |
| Link to item  | Link this barcode to an existing Mealie item                               |
| Create & link | Create a new manual item and link it in one step                           |
| Unlink        | Remove the barcode→item link                                               |
| Retry lookup  | Re-query OpenFoodFacts/UPCDatabase (useful if TTL expired or API was down) |
| Delete        | Remove the barcode, its link, and any retry queue entries                  |

---

## Items (`/items`)

The items page shows all food items — both synced from Mealie and manually created.

- **Search** by name or aliases
- **Barcode count** per item (how many barcodes are linked to it)
- **Last sync** timestamp
- **Manual sync** button to trigger an immediate Mealie catalog refresh

### Item Detail (`/items/{item_id}`)

Shows all barcodes linked to this item, with the ability to unlink individual barcodes.

- **Mealie items** (`source=mealie`) cannot be deleted — they're managed by Mealie
- **Manual items** (`source=manual`) can be deleted, which also removes their barcode links

### Adding Manual Items

Click "Add Item" on the items page. Manual items are useful for products that exist in external databases but not in your Mealie food catalog.

---

## Labels (`/labels`)

The QR Label Generator creates printable `GENERIC:<text>` QR code labels for items that don’t have a barcode — produce, bulk goods, homemade items, etc.

**How it works:**

1. **Search** for an existing Mealie item by name, or type custom text (e.g. “Milk”, “Rice”)
2. **Add** items to the label sheet — each gets a QR code preview
3. Click **Register & Print** — the middleware registers all `GENERIC:` barcodes in the database (linking them to items if matched), then opens the browser print dialog
4. **Stick** the printed labels on containers or shelves

When scanned, `GENERIC:Milk` is treated like any other barcode — it fuzzy-matches against your Mealie catalog and adds the item to the shopping list.

> **Tip:** Labels linked to a Mealie item at creation time skip fuzzy matching entirely — they go straight to the shopping list on scan.

---

## Activity Log (`/activities`)

A chronological log of all scan events and system notifications. Unlike the notification bell (which only shows unread items), the activity log shows everything.

Filter tabs:

| Tab      | Shows                 |
| -------- | --------------------- |
| All      | Everything            |
| Added    | Successful additions  |
| Unknown  | Unrecognized barcodes |
| (others) | Filter by result type |

**Actions:**

- Mark all as read
- Delete all read notifications (cleanup)

---

## Notifications (Bell Icon)

The navigation bar has a bell icon showing the count of unread notifications. Clicking it opens a dropdown with the most recent unread items.

Notifications are created for events that may need your attention:

| Type           | When                                                       |
| -------------- | ---------------------------------------------------------- |
| Unknown        | Barcode not found in any product database                  |
| Auto-linked    | Fuzzy matching linked a barcode automatically — review     |
| Not linked     | Product found but no Mealie item matched                   |
| Retry failed   | Shopping list addition failed after all retries            |
| Broken mapping | A Mealie item was deleted but barcodes still pointed to it |

Each notification links to the barcode detail page where you can take action.

Notifications are **deduplicated per barcode** — scanning the same unknown barcode 5 times creates only one notification, not five.

---

## Settings (`/settings`)

### Configuration Tab

Displays all current configuration values, grouped into:

- Mealie Connection — read-only (set via environment variables)
- Barcode Lookup Sources — source toggles are editable live
- Matching & Sync — thresholds, intervals, and unknown barcode behavior are editable live
- Scanning — unknown barcode handling and Scan & Link mode controls
- System — timezone and log level are editable live

Settings marked as editable can be changed directly in the UI without restarting the container. They’re saved to the database and override the env var value. A reset button next to each restores the env/default value. Read-only settings (Mealie URL, API key, DB path, port) can only be changed by editing `.env` and restarting.

### Tokens Tab

Manage API tokens for scanner authentication:

- **Create:** Enter a name, click Create. The raw token is shown **once** — copy it immediately. It's stored as a bcrypt hash and cannot be recovered.
- **Delete:** Revoke a token. The scanner using it will immediately stop being able to submit scans.

### Users Tab _(admin only)_

Manage user accounts for the web dashboard:

- **Add user:** Set username (min 3 chars), password (min 8 chars), and admin flag.
- **Change password:** Inline password field per user row. Admins can change any user’s password; non-admins can only change their own.
- **Delete:** Remove a user. Admins cannot delete themselves.

### Roles & Permissions

| Capability                                | Admin | User |
| ----------------------------------------- | ----- | ---- |
| View Dashboard, Barcodes, Items, Activity | ✓     | ✓    |
| Link/unlink barcodes, create items        | ✓     | ✓    |
| Access Settings page                      | ✓     | ✗    |
| Create/delete API tokens                  | ✓     | ✗    |
| Manage users                              | ✓     | ✗    |
| Backup/purge/reset database               | ✓     | ✗    |
| Change own password                       | ✓     | ✓    |

If an admin deletes a user or revokes their admin privileges, the change takes effect on the user’s next request — their active session is revalidated from the database.

### Database Tab _(admin only)_

Backup, purge individual tables, or factory-reset the application data.

---

## Real-Time Updates (SSE)

The web UI subscribes to a Server-Sent Events stream at `/events`. When a barcode is scanned anywhere, all open browser tabs receive:

```
event: scan
data: {"barcode": "4088600550862", "result": "added", "item": "Oat Milk"}
```

This powers:

- **Toast notifications** — "✓ Added: Oat Milk" appears briefly in the corner
- **Live table refresh** — The dashboard's recent scans table updates automatically
- **Notification bell update** — The unread count increments in real time

No polling, no page reloads.

---

## API Endpoints

For integration with other tools or custom scripts:

| Endpoint                 | Method | Auth    | Returns            |
| ------------------------ | ------ | ------- | ------------------ |
| `POST /scan`             | POST   | Bearer  | Scan result (JSON) |
| `GET /health`            | GET    | None    | Health status      |
| `GET /api/dashboard`     | GET    | Session | Dashboard stats    |
| `GET /api/barcodes`      | GET    | Session | Barcode list       |
| `GET /api/notifications` | GET    | Session | Unread alerts      |
| `GET /api/activities`    | GET    | Session | Activity log       |
| `GET /events`            | GET    | Session | SSE stream         |

> **Session** = requires a logged-in browser session (cookie). These are not open APIs — calling them with `curl` without a session cookie will redirect to `/login`. Use `POST /scan` with a Bearer token for programmatic access.
