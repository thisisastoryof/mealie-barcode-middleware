# Middleware Setup

The middleware is a Python FastAPI service that sits between the ESP32 barcode scanner and your Mealie instance. It handles barcode lookups, fuzzy matching, shopping list management, and provides a web UI for barcode management.

## Architecture

```
[ESP32 Scanner] ──HTTP POST──► [Middleware :9930] ──REST API──► [Mealie :9925]
                                     │
                                     ├── SQLite database (/data/barcode.db)
                                     ├── Web UI (dashboard, barcode management)
                                     └── Background jobs (retry queue, item sync)
```

The middleware is the only component that talks to Mealie. The ESP32 never contacts Mealie directly. Home Assistant is **not** in the critical path — scanning works without it.

---

## Docker Deployment (Recommended)

### 1. Create the `.env` File

```bash
# Required
MEALIE_URL=http://192.168.x.x:9925
MEALIE_API_KEY=your-mealie-api-token
MEALIE_SHOPPING_LIST_ID=uuid-of-your-shopping-list

# Optional — see Configuration Reference below
MIDDLEWARE_BASE_URL=http://192.168.x.x:9930
TIMEZONE=Europe/Berlin
```

**Getting the Mealie API key:**

1. Open Mealie → Settings → API Tokens
2. Create a new token with a descriptive name
3. Copy the token value

**Getting the Shopping List ID:**

1. Open Mealie → Shopping Lists → select your list
2. The UUID is in the URL: `https://mealie.example.com/shopping-lists/<THIS-UUID>`

### 2. Create `docker-compose.yml`

```yaml
services:
  barcode-middleware:
    build: .
    image: mealie-barcode-middleware:latest
    restart: unless-stopped
    ports:
      - "9930:8000"
    volumes:
      - ./middleware-data:/data
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      start_period: 15s
```

### 3. Start the Container

```bash
docker compose up -d
```

The service is available at `http://your-ip:9930`. The SQLite database is persisted in `./middleware-data/barcode.db`.

### Updating

```bash
git pull
docker compose up -d --build
```

---

## Local Development

```bash
# Clone the repo
git clone https://github.com/gunrunner20/mealie-barcode-middleware.git
cd mealie-barcode-middleware

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .\.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your values

# Download Tabler UI assets (one-time, Windows)
.\scripts\download-tabler.ps1

# Run
uvicorn app.main:app --reload --port 8000
```

---

## Configuration Reference

All settings are environment variables. Set them in `.env` or directly in `docker-compose.yml`.

### Required

| Variable                  | Description                                                  |
| ------------------------- | ------------------------------------------------------------ |
| `MEALIE_URL`              | Base URL of your Mealie instance (e.g. `http://mealie:9925`) |
| `MEALIE_API_KEY`          | Mealie long-lived API token                                  |
| `MEALIE_SHOPPING_LIST_ID` | UUID of the target shopping list                             |

### Barcode Lookup Sources

| Variable                      | Default                                           | Description                                                                                       |
| ----------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `OFF_ENABLED`                 | `true`                                            | Enable OpenFoodFacts lookups                                                                      |
| `OFF_URL_BASE`                | `https://world.openfoodfacts.org/api/v2/product/` | OpenFoodFacts API endpoint                                                                        |
| `UPCDB_ENABLED`               | `false`                                           | Enable UPCDatabase lookups                                                                        |
| `UPCDB_URL_BASE`              | `https://api.upcdatabase.org/product/`            | UPCDatabase API endpoint                                                                          |
| `UPCDB_API_KEY`               | —                                                 | Required when `UPCDB_ENABLED=true`                                                                |
| `LOOKUP_STRATEGY`             | `failover`                                        | `failover` = secondary only when primary returns nothing; `complement` = fill gaps from secondary |
| `LOOKUP_PRIMARY`              | `off`                                             | Which API is tried first (`off` or `upcdb`)                                                       |
| `LOOKUP_ENRICH_IN_BACKGROUND` | `true`                                            | In complement mode, run secondary call after the ESP32 response (faster scans)                    |

> **OpenFoodFacts** is free, no API key needed, and has excellent coverage for European products. **UPCDatabase** has better US product coverage but requires a (free) API key from [upcdatabase.org](https://upcdatabase.org/).

#### Lookup Strategies Explained

**`failover`** (default) — The primary API is called first. Only if it returns _nothing_ (no product found at all) is the secondary API called. This is the simplest and fastest strategy — each scan makes at most one API call when the primary has data.

**`complement`** — The primary API is called first and its result is returned to the scanner immediately. If the result has empty enrichment fields (brand, quantity, or product type), the secondary API is called to fill the gaps. By default (`LOOKUP_ENRICH_IN_BACKGROUND=true`), this secondary call runs _after_ the HTTP response is sent to the ESP32, so it adds zero latency to scans. The enriched data is written to the cache and visible on the dashboard and in future scans of the same barcode.

If `LOOKUP_ENRICH_IN_BACKGROUND=false`, the secondary call is made synchronously before responding — this gives the ESP32 the richest possible data on the first scan, but adds up to 5 seconds of latency.

> **Guard rails:** If `UPCDB_API_KEY` is not set, UPCDatabase is silently disabled regardless of `UPCDB_ENABLED`. If only one source is enabled, the strategy setting has no effect. If the chosen `LOOKUP_PRIMARY` is unavailable (disabled or missing key), the other source is used automatically.

### Matching & Sync

| Variable                   | Default | Description                                                           |
| -------------------------- | ------- | --------------------------------------------------------------------- |
| `FUZZY_MATCH_THRESHOLD`    | `85`    | Minimum score (0–100) to auto-link a barcode to a Mealie item         |
| `FUZZY_AMBIGUITY_GAP`      | `10`    | Minimum gap between #1 and #2 match scores (prevents ambiguous links) |
| `ITEM_SYNC_INTERVAL_HOURS` | `6`     | How often to re-sync the Mealie food catalog                          |
| `LOOKUP_TTL_DAYS`          | `30`    | Days before retrying an external lookup for an unresolved barcode     |
| `MAX_RETRY_ATTEMPTS`       | `10`    | Max retries for failed Mealie shopping list additions                 |

### System

| Variable               | Default            | Description                                                      |
| ---------------------- | ------------------ | ---------------------------------------------------------------- |
| `MIDDLEWARE_BASE_URL`  | (empty)            | Full URL for deep links in notifications (e.g. `http://ip:9930`) |
| `HA_WEBHOOK_URL`       | (empty)            | HA webhook URL for push notifications (see below)                |
| `TIMEZONE`             | `Europe/Berlin`    | IANA timezone for UI timestamps                                  |
| `SESSION_MAX_AGE_DAYS` | `7`                | How long “Stay signed in” sessions last (days)                   |
| `DB_PATH`              | `/data/barcode.db` | SQLite database file path                                        |
| `PORT`                 | `8000`             | HTTP listen port (inside container)                              |
| `LOG_LEVEL`            | `INFO`             | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)           |

### Home Assistant Push Notifications (Optional)

When a barcode scan needs attention (unknown product, auto-linked item to review), the middleware can send a push notification to your phone via a Home Assistant webhook. This works for **all** scan sources — the ESP32 hardware scanner, BinaryEye (Android), and iOS Shortcuts.

**Setup:**

1. Copy `ha_automation/barcode-notification.yaml` into Home Assistant (Settings → Automations → Create → YAML mode)
2. In the automation, replace `notify.mobile_app_YOUR_PHONE` with your HA Companion App service name
3. Set these env vars in the middleware:
   ```bash
   MIDDLEWARE_BASE_URL=http://your-middleware-ip:9930
   HA_WEBHOOK_URL=http://homeassistant.local:8123/api/webhook/barcode-scanner
   ```

The webhook ID (`barcode-scanner`) must match the `webhook_id` in the HA automation. You can change it to anything — just keep them in sync.

> **No HA API key needed.** HA webhooks are accessible by their ID alone — the webhook ID acts as the secret. Keep it unique and don't share it publicly.

---

## Creating API Tokens

The middleware uses Bearer tokens for authentication. Tokens are hashed with bcrypt — the raw token is shown **once** when created and cannot be recovered.

1. Open the middleware web UI → **Settings** → **Tokens** tab
2. Enter a name (e.g. "Kitchen Scanner" or "Phone – BinaryEye") and click **Create**
3. Copy the displayed token immediately

### For the ESP32 DIY Scanner

Add the token to your ESPHome `secrets.yaml`:

```yaml
middleware_auth_header: "Bearer eyJ..."
```

The ESP32 sends it as a standard `Authorization: Bearer` header.

### For Mobile Apps (BinaryEye, etc.)

Mobile scanner apps that can't set custom HTTP headers use the **same token** as a pre-shared key. In BinaryEye, paste the raw token into the **Scanner ID** setting — see [Mobile Apps Guide](mobile-apps.md) for step-by-step setup.

You can create multiple tokens for multiple devices. Each can be revoked independently.

---

## Health Check

The middleware exposes a health endpoint at `GET /health`:

```json
{
  "status": "ok",
  "mealie_reachable": true,
  "db_ok": true
}
```

Status is `"degraded"` if Mealie is unreachable or the database is inaccessible. The Docker health check polls this every 30 seconds.

---

## Database

The middleware uses a single SQLite file at `/data/barcode.db` (configurable via `DB_PATH`). Tables are created automatically on first start.

| Table              | Purpose                                        |
| ------------------ | ---------------------------------------------- |
| `items`            | Mealie food items + manually created items     |
| `barcode_cache`    | Cached lookup results from external APIs       |
| `barcode_mappings` | Links between barcodes and items               |
| `api_tokens`       | Scanner authentication tokens (bcrypt hashed)  |
| `retry_queue`      | Failed Mealie requests awaiting retry          |
| `notifications`    | Activity log and actionable alerts             |
| `users`            | Web UI user accounts (bcrypt hashed passwords) |

**Backup:** The database is a single file. Copy `middleware-data/barcode.db` to back up everything. You can also download a backup from the Settings → Database tab.

> **Health check:** The Dockerfile includes a `HEALTHCHECK` instruction that polls `GET /health` every 30 seconds. Docker Compose inherits this automatically — no extra config needed.

---

## Background Jobs

The middleware runs three background jobs via APScheduler:

| Job                | Interval    | Description                                           |
| ------------------ | ----------- | ----------------------------------------------------- |
| Item sync          | Every 6 h   | Re-fetches Mealie food catalog, detects deletions     |
| Retry queue        | Every 2 min | Retries failed shopping list additions (exp. backoff) |
| Notification purge | Every 24 h  | Deletes read notifications older than 7 days          |

The item sync also runs on startup if no items exist in the database.

---

## Security Notes

- **Scanner → middleware:** Authenticated via Bearer token over HTTP. Use HTTPS if the scanner is on an untrusted network.
- **Web UI:** Protected by username/password login. On first run, you’ll be prompted to create an admin account. The “Stay signed in” checkbox controls whether the session persists across browser restarts (duration set by `SESSION_MAX_AGE_DAYS`). Without it, the session cookie expires when the browser closes.
- **CSRF protection:** All state-changing web UI requests are protected via Origin/Referer validation. The `/scan` endpoint is exempt (uses token auth instead).
- **Content Security Policy:** Strict CSP headers are set on all responses.
- **Mealie API key:** Stored as an environment variable, never exposed in the UI.
