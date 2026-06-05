# Barcode–Mealie Middleware

A self-hosted middleware service that connects an ESPHome barcode scanner to [Mealie](https://mealie.io/). It looks up scanned barcodes against product databases, maintains a local cache, fuzzy-matches products to your Mealie food catalog, and adds items to your shopping list — all without Home Assistant in the critical path.

```
[ESP32 + GM67 scanner]
        │
        │ HTTP POST /scan
        ▼
[mealie-barcode-middleware]  ◄──►  [OpenFoodFacts / UPCDatabase]
        │
        │ Mealie REST API
        ▼
[Mealie]  (shopping list, food catalog)
```

## Features

- **Barcode lookup** — OpenFoodFacts + UPCDatabase (optional) with local caching
- **Fuzzy auto-mapping** — Automatically links product titles to Mealie foods using `rapidfuzz`
- **Shopping list integration** — Adds via food ID (with deduplication) or falls back to plain note
- **Retry queue** — Failed Mealie requests are persisted and retried with exponential backoff
- **GENERIC QR codes** — Scan `GENERIC:Milk` to add "Milk" directly by name match
- **Web UI** — Tabler-based dashboard to review barcodes, manage mappings, trigger syncs
- **Token auth** — Bearer tokens for scanner devices; web UI is open (private network)
- **Offline-first** — No CDN calls; Tabler CSS/JS vendored locally

## Quick Start

### Prerequisites

- Python 3.14+
- A running Mealie instance with an API key

### Local Development

```bash
# Clone and enter the repo
cd mealie-barcode-middleware

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\Activate.ps1
# Activate (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your Mealie URL, API key, and shopping list ID

# Download Tabler UI (one-time, Windows)
.\scripts\download-tabler.ps1

# Run the server
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 to access the dashboard.

### Docker

A `docker-compose.yml` is included in the repository. Copy `.env.example` to `.env`, fill in your values, then:

```bash
docker compose up -d
```

<details>
<summary>docker-compose.yml</summary>

```yaml
services:
  barcode-middleware:
    build: .
    image: mealie-barcode-middleware:latest
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./middleware-data:/data
    env_file:
      - .env
```

</details>

Or build and run manually:

```bash
docker build -t mealie-barcode-middleware .
docker run -d -p 8000:8000 -v ./middleware-data:/data --env-file .env mealie-barcode-middleware
```

## Configuration

All configuration is via environment variables. Create a `.env` file from `.env.example` for local development, or set them in `docker-compose.yml` for production.

| Variable                   | Required | Default                                           | Description                                                                    |
| -------------------------- | -------- | ------------------------------------------------- | ------------------------------------------------------------------------------ |
| `MEALIE_URL`               | **Yes**  | —                                                 | Base URL of your Mealie instance (e.g. `http://mealie:9000`)                   |
| `MEALIE_API_KEY`           | **Yes**  | —                                                 | Mealie long-lived API token                                                    |
| `MEALIE_SHOPPING_LIST_ID`  | **Yes**  | —                                                 | UUID of the target shopping list in Mealie                                     |
| `OFF_ENABLED`              | No       | `true`                                            | Enable OpenFoodFacts lookups                                                   |
| `OFF_URL_BASE`             | No       | `https://world.openfoodfacts.org/api/v2/product/` | OpenFoodFacts API base URL                                                     |
| `UPCDB_ENABLED`            | No       | `false`                                           | Enable UPCDatabase lookups (also requires `UPCDB_API_KEY`)                     |
| `UPCDB_URL_BASE`           | No       | `https://api.upcdatabase.org/product/`            | UPCDatabase API base URL                                                       |
| `UPCDB_API_KEY`            | No       | —                                                 | UPCDatabase API key. Required when `UPCDB_ENABLED=true`                        |
| `ITEM_SYNC_INTERVAL_HOURS` | No       | `6`                                               | How often (in hours) to re-sync the Mealie item catalog                        |
| `FUZZY_MATCH_THRESHOLD`    | No       | `85`                                              | Minimum score (0–100) for automatic barcode→item mapping                       |
| `FUZZY_AMBIGUITY_GAP`      | No       | `10`                                              | Minimum score gap between #1 and #2 match to auto-map (avoids ambiguity)       |
| `LOOKUP_TTL_DAYS`          | No       | `30`                                              | How many days to wait before retrying external lookups for unresolved barcodes |
| `DB_PATH`                  | No       | `/data/barcode.db`                                | Path to the SQLite database file                                               |
| `PORT`                     | No       | `8000`                                            | HTTP port the server listens on                                                |
| `LOG_LEVEL`                | No       | `INFO`                                            | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)                         |
| `MIDDLEWARE_BASE_URL`      | No       | (empty)                                           | Base URL for deep links in HA notifications (e.g. `http://192.168.20.30:9930`) |
| `TIMEZONE`                 | No       | `Europe/Berlin`                                   | IANA timezone for displaying timestamps in the UI (e.g. `America/New_York`)    |

## Usage

### 1. Create an API Token

Open `/settings/tokens` in the web UI, create a named token (e.g. "Kitchen scanner"). The raw token is shown **once** — copy it for your ESPHome config.

### 2. Configure ESPHome

See [`esphome/example-esphome-barcode-scanner.yaml`](esphome/example-esphome-barcode-scanner.yaml) for a complete example. The key section:

```yaml
- http_request.post:
    url: "http://YOUR-MIDDLEWARE-IP:8000/scan"
    headers:
      Content-Type: "application/json"
      Authorization: "Bearer YOUR-TOKEN-HERE"
    body: !lambda |-
      return "{\"barcode\":\"" + x + "\"}";
```

### 3. Scan Barcodes

The middleware will:

1. Check if the barcode is already mapped to a Mealie item → add via item ID
2. Look up the barcode via enabled external services (see below)
3. Attempt fuzzy auto-mapping against your Mealie item catalog
4. Fall back to adding as a plain note on the shopping list

**Lookup order:** OpenFoodFacts is tried first (if enabled). If it returns no result, UPCDatabase is tried (if enabled + API key set). The **first successful** result is stored in the local cache — only one source's data is kept per barcode. If both services are disabled, the barcode is immediately added to the shopping list as a plain-text note.

### 4. Review & Map

Visit the dashboard to see pending-mapping barcodes and assign them to the correct Mealie item. Auto-mapped entries are flagged and can be corrected at any time.

## API

| Endpoint              | Method | Auth         | Description              |
| --------------------- | ------ | ------------ | ------------------------ |
| `/scan`               | POST   | Bearer token | Submit a barcode scan    |
| `/health`             | GET    | None         | Health check (JSON)      |
| `/`                   | GET    | None         | Dashboard (HTML)         |
| `/barcodes`           | GET    | None         | Barcode list (HTML)      |
| `/barcodes/{barcode}` | GET    | None         | Barcode detail (HTML)    |
| `/items`              | GET    | None         | Item catalog list (HTML) |
| `/items/{itemId}`     | GET    | None         | Item detail (HTML)       |
| `/settings`           | GET    | None         | Settings (HTML)          |
| `/settings/tokens`    | GET    | None         | Token management (HTML)  |

### POST /scan

**Request:**

```json
{ "barcode": "4088600550862" }
```

**Responses:**

```json
{ "result": "added", "item": "Oat Milk", "via": "item_id", "needs_action": false, "brand": "Oatly", "quantity": "1L", "item_source": "mealie" }
{ "result": "added_as_note", "item": "Some Product", "via": "note", "needs_action": true, "action_url": "/barcodes/4088600550862" }
{ "result": "queued", "item": "Oat Milk", "via": "item_id", "needs_action": false }
{ "result": "unknown", "item": null, "via": null, "needs_action": true, "action_url": "/barcodes/4088600550862" }
```

## Project Structure

```
app/
├── main.py                 # FastAPI app, dashboard route, lifespan
├── config.py               # pydantic-settings configuration
├── database.py             # SQLAlchemy engine + session
├── models.py               # 5 ORM models
├── auth.py                 # bcrypt token hashing + Bearer auth
├── routers/
│   ├── scan.py             # POST /scan (core scan flow)
│   ├── barcodes.py         # Barcode list/detail/mapping UI
│   ├── foods.py            # Food list/detail + manual sync
│   ├── settings.py         # Config display + token CRUD
│   └── health.py           # GET /health
├── services/
│   ├── barcode_lookup.py   # OpenFoodFacts + UPCDatabase clients
│   ├── mealie.py           # Mealie API client
│   ├── fuzzy.py            # Title normalisation + rapidfuzz matching
│   └── scheduler.py        # APScheduler (food sync + retry queue)
├── templates/              # Jinja2 + Tabler UI templates
└── static/vendor/tabler/   # Vendored Tabler v1.4.0 CSS/JS
```

## Acknowledgements

This project is heavily inspired by [HA-Mealie-Barcode-Scanner](https://github.com/MattFryer/HA-Mealie-Barcode-Scanner) by **Matt Fryer** (@MattFryer), which provided the original concept of connecting a barcode scanner to Mealie via Home Assistant pyscript. The barcode lookup logic (OpenFoodFacts + UPCDatabase with the stray-HTML workaround) and the ESPHome integration pattern were derived from Matt's work.

This project is a modified version that replaces the Home Assistant/pyscript dependency with a standalone FastAPI middleware service, adds a web UI, persistent database, fuzzy matching, and a retry queue.

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

This is required because the upstream project ([HA-Mealie-Barcode-Scanner](https://github.com/MattFryer/HA-Mealie-Barcode-Scanner)) is licensed under GPL-3.0, and this project is a derivative work.

```
Copyright (C) 2025 Matt Fryer (original HA-Mealie-Barcode-Scanner)
Copyright (C) 2026 Contributors (mealie-barcode-middleware modifications)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```
