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

| Variable        | Default                                            | Description                                    |
| --------------- | -------------------------------------------------- | ---------------------------------------------- |
| `OFF_ENABLED`   | `true`                                             | Enable OpenFoodFacts lookups                   |
| `OFF_URL_BASE`  | `https://world.openfoodfacts.org/api/v2/product/`  | OpenFoodFacts API endpoint                     |
| `UPCDB_ENABLED` | `false`                                            | Enable UPCDatabase lookups                     |
| `UPCDB_URL_BASE`| `https://api.upcdatabase.org/product/`             | UPCDatabase API endpoint                       |
| `UPCDB_API_KEY` | —                                                  | Required when `UPCDB_ENABLED=true`             |

> **OpenFoodFacts** is free, no API key needed, and has excellent coverage for European products. **UPCDatabase** has better US product coverage but requires a (free) API key from [upcdatabase.org](https://upcdatabase.org/).

### Matching & Sync

| Variable                   | Default | Description                                                           |
| -------------------------- | ------- | --------------------------------------------------------------------- |
| `FUZZY_MATCH_THRESHOLD`    | `85`    | Minimum score (0–100) to auto-map a barcode to a Mealie item          |
| `FUZZY_AMBIGUITY_GAP`      | `10`    | Minimum gap between #1 and #2 match scores (prevents ambiguous maps)  |
| `ITEM_SYNC_INTERVAL_HOURS` | `6`     | How often to re-sync the Mealie food catalog                          |
| `LOOKUP_TTL_DAYS`          | `30`    | Days before retrying an external lookup for an unresolved barcode     |
| `MAX_RETRY_ATTEMPTS`       | `10`    | Max retries for failed Mealie shopping list additions                 |

### System

| Variable              | Default        | Description                                                        |
| --------------------- | -------------- | ------------------------------------------------------------------ |
| `MIDDLEWARE_BASE_URL`  | (empty)        | Full URL for deep links in HA notifications (e.g. `http://ip:9930`)|
| `TIMEZONE`            | `Europe/Berlin`| IANA timezone for UI timestamps                                    |
| `DB_PATH`             | `/data/barcode.db` | SQLite database file path                                      |
| `PORT`                | `8000`         | HTTP listen port (inside container)                                |
| `LOG_LEVEL`           | `INFO`         | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)             |

---

## Creating API Tokens

The ESP32 scanner authenticates to the middleware using Bearer tokens. Tokens are hashed with bcrypt — the raw token is shown **once** when created and cannot be recovered.

1. Open the middleware web UI → **Settings** → **Tokens** tab
2. Enter a name (e.g. "Kitchen Scanner") and click **Create**
3. Copy the displayed token immediately
4. Add it to your ESPHome `secrets.yaml`:
   ```yaml
   middleware_auth_header: "Bearer eyJ..."
   ```

You can create multiple tokens for multiple scanners. Each can be revoked independently.

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

| Table             | Purpose                                         |
| ----------------- | ----------------------------------------------- |
| `items`           | Mealie food items + manually created items      |
| `barcode_cache`   | Cached lookup results from external APIs        |
| `barcode_mappings`| Links between barcodes and items                |
| `api_tokens`      | Scanner authentication tokens (bcrypt hashed)   |
| `retry_queue`     | Failed Mealie requests awaiting retry           |
| `notifications`   | Activity log and actionable alerts              |

**Backup:** The database is a single file. Copy `middleware-data/barcode.db` to back up everything.

---

## Background Jobs

The middleware runs three background jobs via APScheduler:

| Job               | Interval    | Description                                          |
| ----------------- | ----------- | ---------------------------------------------------- |
| Item sync         | Every 6 h   | Re-fetches Mealie food catalog, detects deletions    |
| Retry queue       | Every 2 min | Retries failed shopping list additions (exp. backoff)|
| Notification purge| Every 24 h  | Deletes read notifications older than 7 days         |

The item sync also runs on startup if no items exist in the database.

---

## Security Notes

- **Scanner → middleware:** Authenticated via Bearer token over HTTP. Use HTTPS if the scanner is on an untrusted network.
- **Web UI:** No authentication — designed for private home networks. Do **not** expose the web UI to the internet.
- **CSRF protection:** All state-changing web UI requests are protected via Origin/Referer validation. The `/scan` endpoint is exempt (uses token auth instead).
- **Content Security Policy:** Strict CSP headers are set on all responses.
- **Mealie API key:** Stored as an environment variable, never exposed in the UI.
