# ESPHome Firmware

The barcode scanner runs [ESPHome](https://esphome.io/) firmware on an ESP32. The configuration file lives at [`esphome/barcode-scanner.yaml`](../esphome/barcode-scanner.yaml) and is deployed via the ESPHome dashboard in Home Assistant (or the ESPHome CLI).

## Prerequisites

- [Home Assistant](https://www.home-assistant.io/) with the [ESPHome add-on](https://esphome.io/guides/getting_started_hassio.html), **or** the ESPHome CLI
- The hardware build from [hardware-build.md](hardware-build.md) — ESP32 + GM67 + OLED + button
- WiFi credentials for your network
- A running instance of the middleware (see [middleware-setup.md](middleware-setup.md))
- An API token from the middleware's Settings page

## First-Time Setup

### 1. Create a `secrets.yaml`

In your ESPHome config directory (e.g. `/config/esphome/` on Home Assistant), create or edit `secrets.yaml`:

```yaml
wifi_ssid: "YourWiFiSSID"
wifi_pwd: "YourWiFiPassword"
ap_pwd: "fallback-hotspot-password"
api_key: "your-esphome-api-encryption-key"
ota_pwd: "your-ota-update-password"
middleware_url: "http://192.168.x.x:9930/scan"
middleware_auth_header: "Bearer your-api-token-here"
```

> **Generate an API encryption key** with: `python3 -c "import secrets; import base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`

> **Get an API token** from the middleware web UI at `/settings` → Tokens tab → Create Token. The raw token is shown once — copy it immediately.

### 2. Copy the Config

Copy `esphome/barcode-scanner.yaml` to your ESPHome config directory. On Home Assistant, this is typically `/config/esphome/barcode_scanner.yaml` (note: underscores, not hyphens — ESPHome uses the filename for the device name on HA).

### 3. Flash

- **Via USB (first time):** Connect the ESP32 via USB, select the serial port in the ESPHome dashboard, and click "Install"
- **Via OTA (subsequent):** The device supports over-the-air updates once connected to WiFi

After flashing, the OLED will show "Connecting..." for up to 30 seconds, then "Connected" with a checkmark once the Home Assistant API connects.

---

## How It Works

### Scan Flow

1. The GM67 scanner detects a barcode and sends it via UART
2. The ESP32 receives raw bytes, strips whitespace, filters out binary config responses
3. The OLED switches to "Looking up..." with the barcode number
4. After a 300 ms delay (lets the scanner LED current settle), an HTTP POST is sent to the middleware
5. The JSON response is parsed and displayed on the OLED
6. A Home Assistant event (`esphome.barcode_scanned`) is fired for optional HA automations
7. After a configurable timeout (default 8 s), the display turns off

### Display States

| State        | Trigger                        | Shows                                      |
| ------------ | ------------------------------ | ------------------------------------------ |
| `standby`    | Timeout after result           | Display off (power save)                   |
| `connecting` | Boot                           | "Barcode Scanner" / "Connecting..."        |
| `ready`      | HA API connected               | ✓ "Connected" / "Ready to scan"            |
| `scanning`   | Barcode received               | "Looking up..." + barcode number           |
| `result`     | HTTP response received         | Result icon + item name + brand/qty        |
| `status`     | Long-press button              | WiFi signal, IP, scan count, uptime        |

### Result Icons

| Result Type    | Icon           | Meaning                                  |
| -------------- | -------------- | ---------------------------------------- |
| `added`        | ✓ check-circle | Added to shopping list via Mealie item   |
| `added_as_note`| ✓ check-circle | Added as plain note (needs mapping)      |
| `queued`       | ⚠ alert        | Mealie unreachable, queued for retry     |
| `unknown`      | ⚠ alert        | Not found in any product database        |
| `timeout`      | ⚠ alert        | HTTP request timed out                   |
| `error`        | ✕ close-circle | Server error or parse failure            |

### Button Behavior

| Action                   | Duration    | Effect                                 |
| ------------------------ | ----------- | -------------------------------------- |
| Short press              | 50–1000 ms  | Wake display, show last scan result    |
| Long press               | 1000–5000 ms| Show status screen (WiFi, IP, uptime)  |

---

## Configuration Options

These are all configurable from Home Assistant's entity UI after the device connects.

### Scanner Settings (GM67)

| Setting             | Options                                                              | Default              |
| ------------------- | -------------------------------------------------------------------- | -------------------- |
| Trigger Mode        | Button Holding, Button Trigger, Continuous, Automatic Induction, Host| Automatic Induction  |
| Buzzer Volume       | Off, Low, Medium, High                                               | Medium               |
| Scanning Light      | On When Reading, Always On, Always Off                               | On When Reading      |
| Collimation (laser) | On When Reading, Always On, Always Off                               | On When Reading      |
| Collimation Flashing| On / Off                                                             | On                   |
| Same Code Delay     | 0.5s, 1s, 3s, 5s, 7s, No Repeat                                     | 3s                   |
| Scanning Enabled    | On / Off                                                             | On                   |

All settings are stored in the ESP32's flash (`restore_value: true`) and re-sent to the GM67 on every boot. The GM67 itself does not persist UART-configured settings across power loss.

### Display Settings

| Setting          | Range   | Default | Description                        |
| ---------------- | ------- | ------- | ---------------------------------- |
| Display Timeout  | 2–30 s  | 8 s     | How long the result screen stays on|

---

## Timeout Chain

The scan involves multiple networked calls. The timeouts are layered to prevent the ESP32's watchdog from triggering:

```
OpenFoodFacts lookup:  5 s ─┐
UPCDatabase lookup:    5 s  ├─ Middleware worst case: 13 s
Mealie POST:           3 s ─┘
                              < ESP32 HTTP timeout:   14 s
                              < ESP32 WDT:            15 s
```

If the middleware takes longer than 14 seconds, the ESP shows "Timed Out" instead of crashing. The WDT at 15 seconds is a safety net — if the HTTP client itself hangs, the ESP reboots cleanly instead of locking up.

---

## Framework Notes

This config uses **ESP-IDF** (not Arduino). This was chosen because:

- `sdkconfig_options` lets us configure the watchdog timeout (Arduino doesn't expose this cleanly)
- Better memory management for the HTTP client under ESP-IDF

Trade-offs:

- The `web_server` component uses significantly more RAM under ESP-IDF — it's **not included** to avoid crashes
- Build times are longer (~2–3 minutes vs ~1 minute for Arduino)
- Some ESPHome components behave slightly differently (e.g., `http_request` response body handling)

---

## Home Assistant Integration

The device registers with Home Assistant via the native ESPHome API. All sensors and controls appear automatically.

### Entities Created

| Entity                  | Type        | Category   | Description                        |
| ----------------------- | ----------- | ---------- | ---------------------------------- |
| Screen Mode             | Text Sensor | —          | Current display state              |
| Last Result             | Text Sensor | —          | Last scanned product name          |
| Last Barcode            | Text Sensor | —          | Last scanned barcode number        |
| Last Result Type        | Text Sensor | —          | Result category (added/unknown/etc)|
| Last Brand              | Text Sensor | —          | Product brand from lookup          |
| Last Quantity           | Text Sensor | —          | Product quantity from lookup       |
| Scan Count              | Sensor      | Diagnostic | Total scans since last reset       |
| WiFi Signal             | Sensor      | Diagnostic | RSSI in dBm                        |
| Uptime                  | Sensor      | Diagnostic | Seconds since last boot            |
| Trigger Mode            | Select      | Config     | Scanner trigger mode               |
| Buzzer Volume           | Select      | Config     | Scanner buzzer level               |
| Scanning Light          | Select      | Config     | Illumination LED mode              |
| Collimation             | Select      | Config     | Aiming laser mode                  |
| Same Code Delay         | Select      | Config     | Re-scan delay for same barcode     |
| Collimation Flashing    | Switch      | Config     | Laser blink on/off                 |
| Scanning Enabled        | Switch      | Config     | Enable/disable scanner             |
| Display Timeout         | Number      | Config     | Seconds before display standby     |
| Display Button          | Binary Sensor| —         | Physical button state              |

### Events

Every scan fires a Home Assistant event:

```yaml
event_type: esphome.barcode_scanned
data:
  barcode: "4088600550862"
  item: "Oat Milk"
  result_type: "added"
  needs_action: "false"
  action_url: ""
```

You can use this in HA automations — for example, to send a phone notification when `needs_action` is `"true"`, including the `action_url` as a deep link to the middleware's barcode detail page.

---

## Customization

### Changing Pins

Edit the `substitutions:` block at the top of the YAML:

```yaml
substitutions:
  tx_pin: GPIO17
  rx_pin: GPIO16
  sda_pin: GPIO21
  scl_pin: GPIO22
  button_pin: GPIO25
  oled_address: "0x3C"
```

### Changing the Middleware URL

Update `secrets.yaml`:

```yaml
middleware_url: "http://NEW-IP:PORT/scan"
middleware_auth_header: "Bearer NEW-TOKEN"
```

### Multiple Scanners

Each scanner needs:
- A unique `esphome: name:` (e.g., `barcode-scanner-kitchen`, `barcode-scanner-pantry`)
- Its own API token from the middleware
- The same `middleware_url` pointing to the shared middleware instance
