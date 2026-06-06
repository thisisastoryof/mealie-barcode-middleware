# Barcode → Mealie Shopping List

A self-hosted barcode scanner that adds items to your [Mealie](https://mealie.io/) shopping list. Scan a product, it gets looked up, matched to your food catalog, and added — all without Home Assistant in the critical path.

```
[ESP32 + GM67 Scanner + OLED]
        │
        │  HTTP POST /scan
        ▼
[Middleware]  ◄──►  [OpenFoodFacts / UPCDatabase]
        │
        │  Mealie REST API
        ▼
[Mealie]  →  Shopping List
```

## Features

- **Barcode lookup** — OpenFoodFacts + UPCDatabase with local caching and configurable TTL
- **Fuzzy auto-mapping** — Automatically links scanned products to your Mealie food catalog using `rapidfuzz`
- **Shopping list integration** — Adds via Mealie food ID (with deduplication) or falls back to plain note
- **Retry queue** — Failed Mealie requests are persisted and retried with exponential backoff
- **OLED display** — Shows scan results, product name, brand, and status in real time
- **GENERIC QR codes** — Scan `GENERIC:Milk` to add items by name without a barcode lookup
- **Web dashboard** — Tabler-based UI to manage barcodes, review mappings, and monitor the system
- **Real-time notifications** — SSE-powered live toasts and a notification bell in the web UI
- **Token auth** — Bearer tokens for scanner devices; web UI is open (private network)
- **Offline-first** — No CDN dependencies; all CSS/JS vendored locally

## Quick Start

### 1. Build the Scanner

Wire up an ESP32, GM67 barcode scanner module, SSD1306 OLED, and a push button on a perf board.

→ [**Hardware Build Guide**](docs/hardware-build.md) — parts list, wiring diagram, power design

> **First-time GM67 setup:** The scanner ships in USB mode. Before it will talk to the ESP32, you need to scan a one-time configuration QR code to switch it to UART. See [**Scanner Configuration**](docs/scanner-configuration.md#initial-setup-switching-to-uart-mode).

### 2. Deploy the Middleware

```bash
# Configure
cp .env.example .env
# Edit: MEALIE_URL, MEALIE_API_KEY, MEALIE_SHOPPING_LIST_ID

# Run
docker compose up -d
```

Open `http://your-ip:9930` → Settings → create an API token for the scanner.

→ [**Middleware Setup**](docs/middleware-setup.md) — Docker, configuration reference, security notes

### 3. Flash the Firmware

Copy `esphome/barcode-scanner.yaml` to your ESPHome dashboard, configure `secrets.yaml` with your WiFi and middleware credentials, and flash via USB.

→ [**ESPHome Firmware**](docs/esphome-firmware.md) — setup, display states, scanner options, HA integration
→ [**Scanner Configuration**](docs/scanner-configuration.md) — trigger modes, buzzer, laser, and the UART protocol explained

### 4. Scan!

Point the scanner at a barcode. The middleware looks it up, matches it to your Mealie catalog, and adds it to your shopping list. The OLED shows the result.

→ [**How Scanning Works**](docs/barcode-workflow.md) — the full pipeline, fuzzy matching, retry queue

---

## Documentation

| Guide                                                  | Description                                           |
| ------------------------------------------------------ | ----------------------------------------------------- |
| [Hardware Build](docs/hardware-build.md)               | Parts, wiring, power design, perf board layout        |
| [ESPHome Firmware](docs/esphome-firmware.md)           | Flashing, display states, scanner config, HA entities |
| [Scanner Configuration](docs/scanner-configuration.md) | GM67 initial setup, settings reference, UART protocol |
| [Middleware Setup](docs/middleware-setup.md)           | Docker deployment, env vars, tokens, database         |
| [How Scanning Works](docs/barcode-workflow.md)         | Scan pipeline, lookup, fuzzy matching, retry queue    |
| [Web Dashboard](docs/web-dashboard.md)                 | UI walkthrough, barcode management, notifications     |
| [Troubleshooting](docs/troubleshooting.md)             | Common issues for hardware, middleware, and Docker    |

---

## Configuration

All settings via environment variables. See [Middleware Setup](docs/middleware-setup.md) for the full reference.

| Variable                  | Required | Default         | Description                        |
| ------------------------- | -------- | --------------- | ---------------------------------- |
| `MEALIE_URL`              | **Yes**  | —               | Mealie instance URL                |
| `MEALIE_API_KEY`          | **Yes**  | —               | Mealie API token                   |
| `MEALIE_SHOPPING_LIST_ID` | **Yes**  | —               | Target shopping list UUID          |
| `OFF_ENABLED`             | No       | `true`          | Enable OpenFoodFacts lookups       |
| `UPCDB_ENABLED`           | No       | `false`         | Enable UPCDatabase lookups         |
| `FUZZY_MATCH_THRESHOLD`   | No       | `85`            | Min score for auto-mapping (0–100) |
| `MIDDLEWARE_BASE_URL`     | No       | (empty)         | URL for notification deep links    |
| `TIMEZONE`                | No       | `Europe/Berlin` | Timezone for UI timestamps         |

## Project Structure

```
app/
├── main.py                  # FastAPI app + lifespan
├── config.py                # Environment variable config
├── database.py              # SQLAlchemy + SQLite
├── models.py                # ORM models (6 tables)
├── auth.py                  # Bearer token authentication
├── events.py                # SSE event bus
├── routers/
│   ├── scan.py              # POST /scan — core scan pipeline
│   ├── barcodes.py          # Barcode list/detail/mapping UI
│   ├── items.py             # Item catalog + manual sync
│   ├── settings.py          # Config display + token CRUD
│   ├── notifications.py     # Activity log + bell dropdown
│   ├── dashboard.py         # Home page + stats API
│   └── health.py            # GET /health
├── services/
│   ├── barcode_lookup.py    # OpenFoodFacts + UPCDatabase clients
│   ├── mealie.py            # Mealie API client
│   ├── fuzzy.py             # Title normalization + rapidfuzz matching
│   └── scheduler.py         # APScheduler (item sync, retry, purge)
├── templates/               # Jinja2 + Tabler UI
└── static/                  # Vendored CSS/JS (no CDN)
esphome/
└── barcode-scanner.yaml     # ESPHome config for ESP32 + GM67
docs/                        # Detailed documentation
```

## Acknowledgements

Inspired by [HA-Mealie-Barcode-Scanner](https://github.com/MattFryer/HA-Mealie-Barcode-Scanner) by **Matt Fryer**, which provided the original concept of connecting a barcode scanner to Mealie via Home Assistant pyscript. The barcode lookup approach (OpenFoodFacts + UPCDatabase) and the ESPHome integration pattern were derived from that project.

This project replaces the HA/pyscript dependency with a standalone FastAPI middleware, adds a web UI, persistent database, fuzzy auto-mapping, and a retry queue.

## License

**GNU General Public License v3.0** — see [LICENSE](LICENSE).

Required because the upstream project is GPL-3.0 licensed.

```
Copyright (C) 2025 Matt Fryer (original HA-Mealie-Barcode-Scanner)
Copyright (C) 2026 Contributors (mealie-barcode-middleware)
```
