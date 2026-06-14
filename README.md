# Barcode → Mealie Shopping List

A self-hosted barcode scanning system that adds items to your [Mealie](https://mealie.io/) shopping list. Scan a product — from a dedicated DIY scanner or your phone — and it gets looked up, matched to your food catalog, and added.

```
[ESP32 + GM67 Scanner + OLED]──┐
                               │  HTTP POST /scan (Bearer token)
[BinaryEye (Android)]──────────┤
                               │  HTTP POST /scan/app (PSK in body)
[iOS Shortcuts]────────────────┤
                               │  HTTP POST /scan (Bearer token)
                               ▼
                       [Middleware :9930]  ◄──►  [OpenFoodFacts / UPCDatabase]
                               │
                               │  Mealie REST API
                               ▼
                       [Mealie]  →  Shopping List
```

## Features

- **Barcode lookup** — OpenFoodFacts + UPCDatabase with configurable strategy (failover or complement), local caching, and configurable TTL
- **Fuzzy auto-mapping** — Automatically links scanned products to your Mealie food catalog using `rapidfuzz`
- **Shopping list integration** — Adds via Mealie food ID (with deduplication) or falls back to plain note
- **Retry queue** — Failed Mealie requests are persisted and retried with exponential backoff
- **OLED display** — Shows scan results, product name, brand, and status in real time
- **GENERIC QR codes** — Scan `GENERIC:Milk` to add items by name without a barcode lookup
- **Web dashboard** — Tabler-based UI to manage barcodes, review mappings, and monitor the system
- **Real-time notifications** — SSE-powered live toasts in the web UI, plus optional HA webhook push notifications to your phone (works for all scan sources)
- **Mobile app support** — Scan from your phone with BinaryEye (Android) or iOS Shortcuts
- **Token auth** — Bearer tokens for scanners with header support; pre-shared key auth for mobile apps
- **User accounts** — Login-protected web UI with admin/user roles and configurable session duration
- **Offline-first** — No CDN dependencies; all CSS/JS vendored locally

## Quick Start

### 1. Deploy the Middleware

```bash
# Configure
cp .env.example .env
# Edit: MEALIE_URL, MEALIE_API_KEY, MEALIE_SHOPPING_LIST_ID

# Run
docker compose up -d
```

Open `http://your-middleware-ip:9930` — on first launch you'll create an admin account. Then go to Settings → Tokens to create an API token for the scanner.

→ [**Middleware Setup**](docs/middleware-setup.md) — Docker, configuration reference, security notes

### 2. Set Up a Scanner

#### Option A: Build the DIY Scanner (ESP32)

Wire up an ESP32, GM67 barcode scanner module, SSD1306 OLED, and a push button on a perf board. This gives you a dedicated, always-on scanner — grab it, point, done.

→ [**Hardware Build Guide**](docs/hardware-build.md) — parts list, wiring diagram, power design

> **First-time GM67 setup:** The scanner ships in USB mode. Before it will talk to the ESP32, you need to scan a one-time configuration QR code to switch it to UART. See [**Scanner Configuration**](docs/scanner-configuration.md#initial-setup-switching-to-uart-mode).

Then flash the firmware: copy `esphome/barcode-scanner.yaml` to your ESPHome dashboard, configure `secrets.yaml` with your WiFi and middleware credentials, and flash via USB.

→ [**ESPHome Firmware**](docs/esphome-firmware.md) — setup, display states, scanner options, HA integration
→ [**Scanner Configuration**](docs/scanner-configuration.md) — trigger modes, buzzer, laser, and the UART protocol explained

#### Option B: Use Your Phone

No soldering required. Install [BinaryEye](https://github.com/markusfisch/BinaryEye) (Android) or build a quick iOS Shortcut, configure it to point at the middleware, and scan away.

→ [**Mobile Apps Guide**](docs/mobile-apps.md) — BinaryEye setup, iOS Shortcuts walkthrough

### 3. Scan!

Point the scanner at a barcode. The middleware looks it up, matches it to your Mealie catalog, and adds it to your shopping list.

→ [**How Scanning Works**](docs/barcode-workflow.md) — the full pipeline, fuzzy matching, retry queue

---

## Documentation

| Guide                                                  | Description                                           |
| ------------------------------------------------------ | ----------------------------------------------------- |
| [Hardware Build](docs/hardware-build.md)               | Parts, wiring, power design, perf board layout        |
| [ESPHome Firmware](docs/esphome-firmware.md)           | Flashing, display states, scanner config, HA entities |
| [Scanner Configuration](docs/scanner-configuration.md) | GM67 initial setup, settings reference, UART protocol |
| [Middleware Setup](docs/middleware-setup.md)           | Docker deployment, env vars, tokens, database         |
| [Mobile Apps](docs/mobile-apps.md)                     | BinaryEye (Android) + iOS Shortcuts setup             |
| [How Scanning Works](docs/barcode-workflow.md)         | Scan pipeline, lookup, fuzzy matching, retry queue    |
| [Web Dashboard](docs/web-dashboard.md)                 | UI walkthrough, barcode management, notifications     |
| [Troubleshooting](docs/troubleshooting.md)             | Common issues for hardware, middleware, and Docker    |

---

## Configuration

All settings via environment variables. See [Middleware Setup](docs/middleware-setup.md) for the full reference.

<details>
<summary>Key variables (subset — see full reference for all options)</summary>

| Variable                  | Required | Default         | Description                                               |
| ------------------------- | -------- | --------------- | --------------------------------------------------------- |
| `MEALIE_URL`              | **Yes**  | —               | Mealie instance URL                                       |
| `MEALIE_API_KEY`          | **Yes**  | —               | Mealie API token                                          |
| `MEALIE_SHOPPING_LIST_ID` | **Yes**  | —               | Target shopping list UUID                                 |
| `OFF_ENABLED`             | No       | `true`          | Enable OpenFoodFacts lookups                              |
| `UPCDB_ENABLED`           | No       | `false`         | Enable UPCDatabase lookups                                |
| `LOOKUP_STRATEGY`         | No       | `failover`      | `failover` or `complement` (fill gaps from secondary API) |
| `LOOKUP_PRIMARY`          | No       | `off`           | Which API is tried first (`off` or `upcdb`)               |
| `FUZZY_MATCH_THRESHOLD`   | No       | `85`            | Min score for auto-mapping (0–100)                        |
| `MIDDLEWARE_BASE_URL`     | No       | (empty)         | URL for notification deep links                           |
| `TIMEZONE`                | No       | `Europe/Berlin` | Timezone for UI timestamps                                |

</details>

## Project Structure

```
app/
├── main.py                  # FastAPI app + lifespan
├── config.py                # Environment variable config
├── database.py              # SQLAlchemy + SQLite
├── models.py                # ORM models (7 tables)
├── auth.py                  # Token auth (Bearer + PSK for mobile apps)
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

## Use of AI

This project was built almost entirely with AI assistance — the code, the firmware, the web UI, and even these docs. The author is a DIY smart home enthusiast who knows what he wants but doesn't have the programming skills to build it from scratch. LLMs did the heavy lifting; the author did the steering, testing, and debugging.

Everything here is designed to run locally on your home network. If you find a bug or see room for improvement, PRs and issues are welcome.

## License

**GNU General Public License v3.0** — see [LICENSE](LICENSE).

This is a copyleft license: you're free to use, modify, and distribute this software, but any derivative work must also be released under GPL-3.0 with full source code.

```
Copyright (C) 2026 Contributors (mealie-barcode-middleware)
```
