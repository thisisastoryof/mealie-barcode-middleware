# How Barcode Scanning Works

This document explains what happens when you scan a barcode, how products are looked up, how fuzzy matching works, and how the retry queue handles failures.

## The Scan Pipeline

When a barcode is scanned — whether from the ESP32 hardware scanner, a phone app like BinaryEye, or an iOS Shortcut — the following steps execute in sequence:

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  GM67 scans │────►│  ESP32 receives  │────►│  HTTP POST /scan │
│  barcode    │     │  via UART        │     │  to middleware   │
└─────────────┘     └──────────────────┘     └────────┬─────────┘
                                                      │
┌─────────────┐     ┌──────────────────┐              │
│  Phone app  │────►│  HTTP POST       │──────────────┤
│  scans      │     │  /scan or        │              │
│  barcode    │     │  /scan/app       │              │
└─────────────┘     └──────────────────┘              │
                                                      │
                    ┌─────────────────────────────────┘
                    ▼
        ┌───────────────────────┐
        │ 1. Existing mapping?  │──yes──► Add to list via item ID ──► Done ✓
        └───────────┬───────────┘
                    │ no
                    ▼
        ┌───────────────────────┐
        │ 2. Cached lookup?     │──yes + found──► Go to step 4
        └───────────┬───────────┘
                    │ no / expired
                    ▼
        ┌───────────────────────┐
        │ 3. External lookup    │
        │    (strategy-based)   │──not found──► Add barcode as note ──► Done
        └───────────┬───────────┘
                    │ found
                    ▼
        ┌───────────────────────┐
        │ 4. Fuzzy auto-match   │──matched──► Add via item + flag for review
        └───────────┬───────────┘
                    │ no match
                    ▼
        ┌───────────────────────┐
        │ 5. Add as note        │──► Shopping list gets product title as note
        │    (not linked)       │
        └───────────────────────┘

After each scan, if the result needs attention (steps 3–5), two things happen:
- A **notification** is saved for the web UI bell icon
- If `HA_WEBHOOK_URL` is set, a **push notification** is sent to your phone via Home Assistant
```

Let's walk through each step.

---

## Step 1: Check Existing Mapping

The middleware first checks if this barcode has been linked to a Mealie item before (in the `barcode_mappings` table).

If a mapping exists:

- The linked item is fetched
- If the item comes from Mealie (`source=mealie`), it's added to the shopping list using Mealie's `foodId` — this gives proper deduplication (scanning the same item twice doesn't add it twice)
- If the item is manual (`source=manual`), it's added as a note

**This is the fast path.** A linked barcode skips all external lookups entirely.

---

## Step 2: Check the Cache

If there's no mapping, the middleware checks the `barcode_cache` table. This table stores results from previous external API lookups.

- If the barcode was looked up before and found → skip to fuzzy matching (step 4)
- If the barcode was looked up before but **not found** → check if the cache has expired (default: 30 days via `LOOKUP_TTL_DAYS`). If expired, re-lookup. If still fresh, treat as not found
- If the barcode has never been looked up → proceed to external lookup

---

## Step 3: External Lookup

The middleware queries up to two external product databases:

### OpenFoodFacts (default: enabled)

- Free, no API key required
- Excellent coverage for European grocery products
- Returns: product name, brand, quantity, product type
- URL: `https://world.openfoodfacts.org/api/v2/product/{barcode}.json`
- Timeout: 5 seconds

### UPCDatabase (default: disabled)

- Requires a free API key from [upcdatabase.org](https://upcdatabase.org/)
- Better coverage for US products
- Enable via `UPCDB_ENABLED=true` + `UPCDB_API_KEY=your-key`
- URL: `https://api.upcdatabase.org/product/{barcode}?apikey=KEY`
- Timeout: 5 seconds

### Lookup Strategies

The order and combination of API calls is controlled by `LOOKUP_STRATEGY` and `LOOKUP_PRIMARY`:

**`failover`** (default) — The primary API (`LOOKUP_PRIMARY`, default `off`) is tried first. If it returns no result at all, the secondary API is tried. The first successful result wins.

**`complement`** — The primary API is tried first. If it finds the product but some fields are empty (e.g. brand or quantity missing), the secondary API is called to fill the gaps. Both sources' data is merged and the `source` field records both (e.g. `openfoodfacts+upcdatabase`).

By default, the secondary call in complement mode runs in the background (`LOOKUP_ENRICH_IN_BACKGROUND=true`), meaning the ESP32 gets its response immediately from the primary API, and the cache is enriched asynchronously. The enriched data appears on the dashboard and is used for future scans of the same barcode.

> **Note:** If only one API is enabled, the strategy has no effect.

### If Nothing Is Found

If neither database recognizes the barcode, the barcode string itself is added as a plain note on the shopping list. A notification is created in the web UI so you can manually identify and link it later.

---

## Step 4: Fuzzy Auto-Mapping

When a product is found in an external database, the middleware attempts to automatically link it to a Mealie food item.

### How Fuzzy Matching Works

1. **Normalize the product title:**
   - Strip the brand name (e.g. "Oatly Oat Milk" → "Oat Milk")
   - Remove quantity/size strings (e.g. "Oat Milk 1L" → "Oat Milk")
   - Clean up separators and extra whitespace

2. **Score against all Mealie items:**
   - Each Mealie item's name and aliases are compared using `rapidfuzz`
   - Three scoring methods are used (best score wins):
     - **Token sort ratio** — ignores word order ("Light Tuna" ≈ "Tuna Light")
     - **Token set ratio** — handles extra words ("Chunk Light Tuna" ≈ "Tuna")
     - **Partial ratio** — substring matching ("Milk" in "Oat Milk")

3. **Decision criteria:**
   - The best match must score ≥ `FUZZY_MATCH_THRESHOLD` (default: 85)
   - The gap between the #1 and #2 scores must be ≥ `FUZZY_AMBIGUITY_GAP` (default: 10)

### Why the Ambiguity Gap?

Consider a product called "Chunk Light Tuna In Water". It might score:

- **Tuna** → 90 points
- **Water** → 90 points

Both exceed the threshold, but the gap is 0. Without the ambiguity check, it would pick whichever is alphabetically first — which could easily be wrong. The gap requirement prevents this class of false positive.

### Auto-Link Results

- **Match found:** The barcode is linked to the item with `mapped_by=auto`. The product is added to the shopping list. A notification is created so you can review the link.
- **No match:** The product title is added as a plain note. A notification is created so you can manually link it.

---

## Step 5: Add as Note (Fallback)

If no Mealie item matches, the product title (or barcode string if the product wasn't found) is added to the shopping list as a **plain note**. Notes appear on the Mealie shopping list without being linked to a food item.

This ensures something always gets added — you won't forget an item just because the middleware couldn't identify it.

---

## GENERIC QR Codes

You can create QR codes with the prefix `GENERIC:` followed by a product name:

```
GENERIC:Milk
GENERIC:Bread
GENERIC:Toilet Paper
```

When scanned, the middleware skips all external lookups and goes straight to fuzzy matching against your Mealie food catalog. This is useful for items that don't have barcodes (produce, bulk items) or items where you always want a specific Mealie item.

---

## Retry Queue

When the middleware can't reach Mealie (network issue, Mealie restart, etc.), the shopping list addition is **not lost**. Instead:

1. The failed request is saved to the `retry_queue` table
2. A background job runs every 2 minutes and retries pending items
3. Retries use exponential backoff: 1 min, 2 min, 4 min, 8 min, ... up to 60 min
4. After `MAX_RETRY_ATTEMPTS` (default: 10) failures, the item is marked as permanently failed and a notification is created

The ESP32 still shows the scan result immediately — it doesn't wait for the retry. The OLED displays "Queued" to indicate the item will be added later.

---

## Shopping List Deduplication

When adding via `foodId` (linked barcodes), Mealie handles deduplication — scanning the same item multiple times won't create duplicate entries on your shopping list.

When adding via note (unlinked barcodes), there's no deduplication — each scan adds a new note line. This is by design, since the middleware can't know if you intentionally scanned the same unknown barcode twice.

---

## Scan Response Format

The `/scan` endpoint always returns HTTP 200 with a JSON body:

```json
{
  "result": "added",
  "item": "Oat Milk",
  "via": "item_id",
  "needs_action": false,
  "action_url": null,
  "brand": "Oatly",
  "quantity": "1L",
  "item_source": "mealie"
}
```

| Field          | Values                                        | Description                           |
| -------------- | --------------------------------------------- | ------------------------------------- |
| `result`       | `added`, `added_as_note`, `queued`, `unknown` | What happened                         |
| `item`         | Product name or barcode string                | What's shown on the OLED              |
| `via`          | `item_id` or `note`                           | How it was added to the shopping list |
| `needs_action` | `true` / `false`                              | Should the user review this?          |
| `action_url`   | URL or `null`                                 | Deep link to barcode detail page      |
| `brand`        | Brand name or `null`                          | From external lookup                  |
| `quantity`     | "1L", "500g", etc. or `null`                  | From external lookup                  |
| `item_source`  | `mealie`, `manual`, or `null`                 | Where the matched item came from      |
