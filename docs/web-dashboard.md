# Web Dashboard

The middleware includes a full web UI built with [Tabler](https://tabler.io/) (vendored locally — no CDN calls). All pages are server-rendered with Jinja2 templates and enhanced with JavaScript for live updates.

The web UI has **no authentication** — it's designed for private home networks. Do not expose it to the internet.

---

## Dashboard (`/`)

The home page shows an at-a-glance overview of the system:

- **Stats cards:** Total barcodes, mapped, pending mapping, unknown, retry queue depth
- **Mealie status:** Connectivity check + last item sync time
- **Recent scans:** The last 10 scanned barcodes with status badges

The dashboard auto-refreshes via AJAX. When a barcode is scanned, a **live toast notification** appears in the bottom-right corner via Server-Sent Events (SSE) — no page reload needed.

---

## Barcodes (`/barcodes`)

The barcode list shows all known barcodes with filtering tabs:

| Tab      | Shows                                                   |
| -------- | ------------------------------------------------------- |
| All      | Every barcode the system has seen                       |
| Mapped   | Barcodes linked to a Mealie item                        |
| Pending  | Barcodes with a product title but no item link          |
| Unknown  | Barcodes not found in any external product database     |

### Barcode Detail (`/barcodes/{barcode}`)

Each barcode has a detail page showing:

- **Product info:** Title, brand, quantity, product type, lookup source
- **Linked item:** The Mealie item this barcode maps to (if any)
- **Fuzzy match candidates:** Top scoring Mealie items with match scores — useful for manual mapping
- **Item search:** Search Mealie items by name to find the right mapping

**Actions available:**

| Action              | Description                                              |
| ------------------- | -------------------------------------------------------- |
| Link to item        | Map this barcode to an existing Mealie item              |
| Create & link       | Create a new manual item and map it in one step          |
| Unlink              | Remove the barcode→item mapping                         |
| Retry lookup        | Re-query OpenFoodFacts/UPCDatabase (useful if TTL expired or API was down) |
| Delete              | Remove the barcode, its mapping, and any retry queue entries |

---

## Items (`/items`)

The items page shows all food items — both synced from Mealie and manually created.

- **Search** by name or aliases
- **Barcode count** per item (how many barcodes are mapped to it)
- **Last sync** timestamp
- **Manual sync** button to trigger an immediate Mealie catalog refresh

### Item Detail (`/items/{item_id}`)

Shows all barcodes mapped to this item, with the ability to remove individual mappings.

- **Mealie items** (`source=mealie`) cannot be deleted — they're managed by Mealie
- **Manual items** (`source=manual`) can be deleted, which also removes their barcode mappings

### Adding Manual Items

Click "Add Item" on the items page. Manual items are useful for products that exist in external databases but not in your Mealie food catalog.

---

## Activity Log (`/activities`)

A chronological log of all scan events and system notifications. Unlike the notification bell (which only shows unread items), the activity log shows everything.

Filter tabs:

| Tab      | Shows                    |
| -------- | ------------------------ |
| All      | Everything               |
| Added    | Successful additions     |
| Unknown  | Unrecognized barcodes    |
| (others) | Filter by result type    |

**Actions:**
- Mark all as read
- Delete all read notifications (cleanup)

---

## Notifications (Bell Icon)

The navigation bar has a bell icon showing the count of unread notifications. Clicking it opens a dropdown with the most recent unread items.

Notifications are created for events that may need your attention:

| Type          | When                                                     |
| ------------- | -------------------------------------------------------- |
| Unknown       | Barcode not found in any product database                |
| Auto-mapped   | Fuzzy matching linked a barcode automatically — confirm? |
| Needs mapping | Product found but no Mealie item matched                 |
| Retry failed  | Shopping list addition failed after all retries          |
| Broken mapping| A Mealie item was deleted but barcodes still pointed to it|

Each notification links to the barcode detail page where you can take action.

Notifications are **deduplicated per barcode** — scanning the same unknown barcode 5 times creates only one notification, not five.

---

## Settings (`/settings`)

### Configuration Tab

Displays all current configuration values (read-only). Grouped into:
- Mealie Connection
- Barcode Lookup Sources
- Matching & Sync
- System

These values come from environment variables and can only be changed by editing `.env` and restarting the container.

### Tokens Tab

Manage API tokens for scanner authentication:

- **Create:** Enter a name, click Create. The raw token is shown **once** — copy it immediately. It's stored as a bcrypt hash and cannot be recovered.
- **Delete:** Revoke a token. The scanner using it will immediately stop being able to submit scans.

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

| Endpoint                    | Method | Auth   | Returns            |
| --------------------------- | ------ | ------ | ------------------ |
| `POST /scan`                | POST   | Bearer | Scan result (JSON) |
| `GET /health`               | GET    | None   | Health status      |
| `GET /api/dashboard`        | GET    | None   | Dashboard stats    |
| `GET /api/barcodes`         | GET    | None   | Barcode list       |
| `GET /api/notifications`    | GET    | None   | Unread alerts      |
| `GET /api/activities`       | GET    | None   | Activity log       |
| `GET /events`               | GET    | None   | SSE stream         |
