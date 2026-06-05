# ESP8266 Barcode Scanner — Improvement & Extension Planning

## 1. Security — Hardcoded Credentials ✅ Addressed

**Problem:** Middleware URL and Bearer token were hardcoded in plaintext in the YAML.

**Fix:** Move both to `secrets.yaml`. Since `!secret` cannot be nested inside `!lambda`,
store the full Authorization header as a single secret:

```yaml
# secrets.yaml
middleware_url: "http://192.168.20.30:9930/scan"
middleware_auth_header: "Bearer PzjjYLtuoRyFxtvjFpULr4dIYzv3tbu7pxJbxFwlVjQ"
```

```yaml
# in the YAML config
url: !secret middleware_url
request_headers:
  Content-Type: "application/json"
  Authorization: !secret middleware_auth_header
```

> **Note:** `id()` in a `!lambda` references an ESPHome component ID (text_sensor, global, etc.),
> NOT a `secrets.yaml` value. And `!secret ${var}` is invalid — `!secret` and `${}` substitutions
> are separate YAML resolution mechanisms that cannot be combined.

---

## 2. Dead Code — Remove Unused Components

### 2a. `last_scan` Event Entity (lines ~168-177)

The `last_scan` event entity is declared but never triggered anywhere in the config.
No `event.trigger` call references it. It consumes flash space for no benefit.

**Action:** Remove the entire `event:` block, or wire it up by adding an
`event.trigger` in the `barcode_raw` `on_value` handler if diagnostic events
are actually wanted.

### 2b. `product_identified` HA Action (lines ~36-50)

This action allows Home Assistant to push a product name back to the device.
With the middleware now returning the product name directly in the HTTP response
(and `last_result` being set in the `on_response` handler), this action is only
useful if HA is independently sending product identifications.

**Action:** Confirm whether this HA→device callback is still used. If not, remove
the entire `actions:` block under `api:` to simplify the config.

### 2c. `logger.log` Inside `product_identified`

The `logger.log` call inside `product_identified` will never produce visible output
because `baud_rate: 0` disables serial logging. It would only appear in ESPHome
network logs (`esphome logs --device`), which is rarely monitored.

**Action:** Remove or leave as-is (harmless, just dead weight).

---

## 3. Robustness — WiFi Reconnection

**Problem:** Default WiFi behavior uses DHCP and full scanning on reconnect, which
can take several seconds. For a scanner that should feel instant, this adds
noticeable latency after WiFi drops.

**Improvement:** Add `fast_connect: true` and a static IP configuration:

```yaml
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_pwd
  fast_connect: true
  manual_ip:
    static_ip: 192.168.20.XX
    gateway: 192.168.20.1
    subnet: 255.255.255.0
    dns1: 192.168.20.1
```

`fast_connect: true` skips the full WiFi scan and connects directly to the
configured SSID, saving ~1-3 seconds on every reconnect.

---

## 4. Robustness — Boot State Machine

**Problem:** `on_boot` sets `screen_mode` to "connecting" and relies on
`on_client_connected` (HA API) to transition to "standby". If HA is down,
the device stays in "connecting" forever — even though the HTTP POST to the
middleware would still work fine.

**Improvement:** Add a fallback timeout that transitions to "standby" after
~30 seconds regardless of HA connection state:

```yaml
esphome:
  on_boot:
    priority: -10 # Run after WiFi + API init
    then:
      - text_sensor.template.publish:
          id: screen_mode
          state: "connecting"
      - delay: 30s
      - if:
          condition:
            text_sensor.state:
              id: screen_mode
              state: "connecting"
          then:
            - text_sensor.template.publish:
                id: screen_mode
                state: "standby"
```

This way the device becomes usable even if HA is unreachable.

---

## 5. Minor — UART List Syntax

**Current:** `uart:` uses a list (`- id: uart_bus`) but there's only one UART bus.

**Improvement:** Use the simpler non-list form:

```yaml
uart:
  id: uart_bus
  baud_rate: ${gm67_baud}
  tx_pin: ${tx_pin}
  rx_pin: ${rx_pin}
  debug:
    # ...
```

This is purely cosmetic — both forms work identically.

---

## 6. Extension — Diagnostic Web Server

**Current:** No way to inspect the device without HA or serial.

**Improvement:** Add a minimal web server for diagnostics:

```yaml
web_server:
  port: 80
```

This exposes a status page at `http://<device-ip>/` showing all sensors,
switches, and selects. Useful for troubleshooting without HA access.
Adds ~50 KB to the firmware.

---

## 7. HA Feedback — Exposing Scan Results as Sensors

### Context

The original project routed everything through HA automations, which was clumsy and
hard to extend. The middleware now handles the scan→lookup→shopping-list pipeline
directly via HTTP. Still, since ESPHome manages the device, exposing useful state
back to HA is cheap and enables other users to build their own automations.

### Item Sources in the Middleware

The middleware has a unified `items` table with two source types:

| `item.source` | Origin                     | Shopping list behavior       |
| ------------- | -------------------------- | ---------------------------- |
| `"mealie"`    | Synced from Mealie food DB | Added via Mealie item ID     |
| `"manual"`    | User-created custom items  | Added as a note (plain text) |

Both types can have barcode mappings. The scan flow in `_add_via_item()` checks
the source to decide _how_ to add to the shopping list — item ID for Mealie items,
note text for manual/custom items. The `item` field in `ScanResponse` already
contains the best human-readable name regardless of source.

### Priority Cascade for Display Name

The middleware already resolves this in the scan endpoint — no client-side logic needed:

1. **Mapped to Mealie item** → `item` = Mealie item name (via item ID)
2. **Mapped to manual/custom item** → `item` = custom item name (via note)
3. **Auto-mapped (fuzzy)** → `item` = Mealie item name (auto-matched)
4. **Product found but unmapped** → `item` = product title from OpenFoodFacts/UPC
5. **Unknown barcode** → `item` = `null`

The ESP firmware simply displays whatever `item` returns. No priority logic on-device.

### Proposed HA-Visible Sensors

| Sensor (text_sensor) | Content                                    | Clears after  | Persists reboot? | HA entity ID                              |
| -------------------- | ------------------------------------------ | ------------- | ---------------- | ----------------------------------------- |
| `last_barcode`       | Raw barcode string                         | Next scan     | No               | `sensor.barcode_scanner_last_barcode`     |
| `last_result`        | Best display name (cascade above)          | Standby timer | No               | `sensor.barcode_scanner_last_result`      |
| `last_result_type`   | `added`/`added_as_note`/`queued`/`unknown` | Standby timer | No               | `sensor.barcode_scanner_last_result_type` |

All three are transient — empty after reboot. No `restore_value`.

### Sensor Population

`last_barcode` and `last_result_type` are set in the same `on_response` lambda
defined in §8. No separate code path needed — §7 and §8 share a single lambda:

```cpp
// In on_response lambda (see §8 for full listing):
id(last_result).publish_state(item_name);          // existing
id(last_result_type).publish_state(result);   // NEW — from root["result"]
id(last_barcode).publish_state(id(barcode_raw).state);  // NEW
```

`last_result` and `last_result_type` are cleared by the standby timer:

```yaml
script:
  - id: standby_timer
    mode: restart
    then:
      - delay: !lambda "return id(display_timeout).state * 1000;"
      - text_sensor.template.publish:
          id: screen_mode
          state: "standby"
      - text_sensor.template.publish:
          id: last_result
          state: ""
      - text_sensor.template.publish:
          id: last_result_type
          state: ""
      # last_barcode intentionally NOT cleared — persists until next scan
```

### HA Event — Only on Successful HTTP Response

The `homeassistant.event` (defined in §8) fires only inside the `on_response`
block — not on `on_error`. If the middleware is unreachable, the ESP has no
useful data to report, and the middleware's retry queue handles recovery
server-side. No error events to HA.

### Repurpose Dead Components

- **`last_scan` event:** Wire it up as a real HA event, fired on every scan with
  `barcode`, `result_type`, `item`, and `needs_action` as event data. HA users
  can trigger automations on `esphome.barcode_scanned`.
- **`product_identified` action:** Remove — the middleware response handles everything.

---

## 8. HA Notifications — Actionable Popups

### Concept

When a scan requires user action, push a notification to the user's phone via HA
with a direct link to the middleware UI. Only important + actionable cases:

| Middleware `result` | Notification? | Message                         | Link target           |
| ------------------- | ------------- | ------------------------------- | --------------------- |
| `unknown`           | Yes           | "Unknown barcode {code}"        | `/barcodes/{barcode}` |
| `auto_mapped`       | Yes           | "{product} → {item} — confirm?" | `/barcodes/{barcode}` |
| `needs_mapping`     | Yes           | "{product} — assign to an item" | `/barcodes/{barcode}` |
| `added`             | No            | —                               | —                     |
| `queued`            | No            | —                               | —                     |

### Middleware Changes

**1. New config setting** in `config.py`:

```python
middleware_base_url: str = ""
```

| `middleware_base_url` value    | `action_url` in response                  | Use case                                 |
| ------------------------------ | ----------------------------------------- | ---------------------------------------- |
| `"https://barcode.home.local"` | `https://barcode.home.local/barcodes/123` | Behind reverse proxy                     |
| `"http://192.168.20.30:9930"`  | `http://192.168.20.30:9930/barcodes/123`  | Direct LAN access                        |
| `""` (empty/unset)             | `/barcodes/123`                           | Relative — usable with manual base in HA |

When empty, log a one-time INFO at startup:

```
MIDDLEWARE_BASE_URL not set — notification action_url will use relative paths.
Set MIDDLEWARE_BASE_URL=http://your-ip:9930 for full deep links in HA notifications.
```

The setting accepts any URL — LAN IP, DNS name, proxied HTTPS, Tailscale, etc.
The URL is never fetched by the server (no SSRF risk), only embedded in JSON responses.

**2. Extend `ScanResponse`:**

```python
class ScanResponse(BaseModel):
    result: str
    item: str | None = None
    via: str | None = None
    needs_action: bool = False
    action_url: str | None = None
    brand: str | None = None
    quantity: str | None = None
    item_source: str | None = None
```

**3. URL construction** in the scan endpoint:

```python
def _build_action_url(barcode: str) -> str:
    base = settings.middleware_base_url.rstrip("/")
    if base:
        return f"{base}/barcodes/{barcode}"
    return f"/barcodes/{barcode}"
```

Set `needs_action=True` and populate `action_url` wherever `_save_notification()`
is already called — the triggers are identical.

### ESPHome Changes — Response Parsing

The `on_response` lambda grows to extract all new fields:

```cpp
json::parse_json(body, [](JsonObject root) -> bool {
    // Display name
    std::string item_name = root["item"] | "";
    std::string result = root["result"] | "unknown";

    if (item_name.empty()) item_name = "Unknown";
    id(last_result).publish_state(item_name);
    id(last_result_type).publish_state(result);
    id(last_barcode).publish_state(id(barcode_raw).state);

    // Display enrichment (brand/quantity for OLED)
    std::string brand = root["brand"] | "";
    std::string qty = root["quantity"] | "";
    if (!brand.empty()) id(last_brand).publish_state(brand);
    if (!qty.empty()) id(last_quantity).publish_state(qty);

    // Notification relay — store action_url for HA event
    bool needs_action = root["needs_action"] | false;
    std::string action_url = root["action_url"] | "";
    id(pending_action_url).publish_state(needs_action ? action_url : "");

    return true;
});
```

### ESPHome Changes — HA Event Firing (Option B: Fire on Every Scan)

After the HTTP response block completes, always fire a HA event.
The HA automation filters on `needs_action`:

```yaml
# In barcode_raw on_value, after http_request.post + on_response:
- homeassistant.event:
    event: esphome.barcode_scanned
    data:
      barcode: !lambda "return id(last_barcode).state;"
      item: !lambda "return id(last_result).state;"
      result_type: !lambda "return id(last_result_type).state;"
      needs_action: !lambda 'return id(pending_action_url).state.empty() ? "false" : "true";'
      action_url: !lambda "return id(pending_action_url).state;"
```

### New Text Sensors Required

```yaml
text_sensor:
  - platform: template
    name: "Last Barcode"
    id: last_barcode

  - platform: template
    name: "Last Result Type"
    id: last_result_type

  - platform: template
    name: "Last Brand"
    id: last_brand
    internal: true # Only used for OLED display

  - platform: template
    name: "Last Quantity"
    id: last_quantity
    internal: true # Only used for OLED display

  - platform: template
    id: pending_action_url
    internal: true # Never exposed to HA as entity
```

### Example HA Automation

```yaml
# Example HA automation — actionable notification on phone
automation:
  - alias: "Barcode Scanner — Needs Attention"
    trigger:
      - platform: event
        event_type: esphome.barcode_scanned
        event_data:
          needs_action: "true"
    action:
      - service: notify.mobile_app_phone
        data:
          title: "Barcode Scanner"
          message: >-
            {{ trigger.event.data.item | default('Unknown barcode') }}
            needs attention
          data:
            url: "{{ trigger.event.data.action_url }}"
            # For relative URLs (MIDDLEWARE_BASE_URL not set):
            # url: "http://192.168.20.30:9930{{ trigger.event.data.action_url }}"
```

---

## 9. OLED Display (0.96" SSD1306 I2C)

### Hardware Identification

The CP2102 chip on the NodeMCU is the **USB-to-UART bridge** — it has nothing to do
with flash memory. The NodeMCU v2 has a **4 MB (32 Mbit) SPI flash** chip (usually
a Winbond W25Q32). ESPHome firmware for ESP8266 typically uses ~400-500 KB. With
display + fonts + web_server + all GM67 selects, expect ~550-600 KB — well within
the 1 MB OTA partition limit.

**Display:** Your 0.96" OLED with SCL/SDA and address `0x78` is an **SSD1306 128×64
I2C OLED**. The address `0x78` is the 8-bit form — ESPHome uses the 7-bit address:
**`0x3C`** (0x78 >> 1). Some modules have an alternate address of `0x3D` depending
on a solder bridge/resistor.

### Wiring

| Function | GPIO  | NodeMCU Pin | Notes                  |
| -------- | ----- | ----------- | ---------------------- |
| SDA      | GPIO4 | **D2**      | Default I2C data line  |
| SCL      | GPIO5 | **D1**      | Default I2C clock line |
| VCC      | —     | **3V3**     | SSD1306 runs on 3.3V   |
| GND      | —     | **GND**     | Common ground          |

No pull-ups needed — the SSD1306 breakout board has them onboard.
No conflicts with UART0 (GPIO1/3) or boot pins.

> **Update the schematic.md** with these two additional wires when implementing.

### OLED Longevity — Sleep Strategy

OLEDs degrade with use (pixel burn-in, brightness loss). There is **no motivation
to keep the display on permanently**. Strategy:

**Button** on GPIO13 / D7 (no boot-mode constraints, internal pull-up):

| Press type        | Action                                        |
| ----------------- | --------------------------------------------- |
| Short press (<1s) | Wake display for 15s, show last scan result   |
| Long press (>2s)  | Wake display for 15s, show status/diagnostics |

No double-press — avoids the ~300ms detection delay on every short press.

```yaml
binary_sensor:
  - platform: gpio
    pin:
      number: GPIO13 # D7
      mode: INPUT_PULLUP
      inverted: true # Active-low: button connects GPIO13 to GND
    name: "Display Button"
    id: display_button
    on_click:
      min_length: 50ms
      max_length: 1000ms
      then:
        - script.execute: wake_display_result
    on_press:
      then:
        - delay: 2s
        - if:
            condition:
              binary_sensor.is_on: display_button
            then:
              - script.execute: wake_display_status
```

Wiring: one wire from GPIO13/D7 to one leg of a momentary button, other leg to GND.
No external resistor needed — `INPUT_PULLUP` uses the ESP8266's internal pull-up.

The display stays **off by default** and only activates:

1. On scan (show result for display_timeout seconds, see §12)
2. On button press (show result or status for 15s)
3. On boot (show "Connecting..." then "Ready")

After timeout → display goes to sleep (`it.fill(COLOR_OFF)` + `turn_off()`).

### Display Pages — What to Show

**Page 1: Scan Result (auto-shown on scan, 5s)**

```
┌──────────────────────────┐
│ ✓ Added                  │   ← result icon + type
│                          │
│ Barilla Spaghetti        │   ← item name (from response)
│ No.5 500g                │   ← brand/quantity if available
│ ───────────────────────  │
│ 4006381333931     Mealie │   ← barcode + source badge
└──────────────────────────┘
```

**Page 2: Unknown/Error (auto-shown on scan)**

```
┌──────────────────────────┐
│ ⚠ Needs Mapping          │
│                          │
│ Organic Whole Milk       │   ← product title from API
│                          │
│ Open middleware to map   │
│ 4006381333931            │
└──────────────────────────┘
```

**Page 3: Status (shown on button press)**

```
┌──────────────────────────┐
│ Barcode Scanner          │
│                          │
│ WiFi: -62 dBm  ████░    │   ← RSSI bar
│ IP: 192.168.20.42       │
│ Scans: 147              │
│ Uptime: 3d 14h          │
└──────────────────────────┘
```

**Page 4: Boot/Connecting**

```
┌──────────────────────────┐
│                          │
│    Barcode Scanner       │
│    Connecting...         │
│                          │
│                          │
│                          │
└──────────────────────────┘
```

### Enriching the Middleware Response

To populate the display properly, `ScanResponse` needs additional fields from
`BarcodeCache` that are already stored but not returned:

```python
class ScanResponse(BaseModel):
    result: str
    item: str | None = None
    via: str | None = None
    needs_action: bool = False
    action_url: str | None = None
    brand: str | None = None              # NEW — from barcode_cache
    quantity: str | None = None           # NEW — from barcode_cache
    item_source: str | None = None        # NEW — "mealie" | "manual" | None
```

`item_source` tells the display whether to show "Mealie" or "Custom" badge.
`brand` and `quantity` allow a richer two-line product description.

### Display Character Handling

The SSD1306 is a pixel display with no character ROM — ESPHome renders each
character as a bitmap glyph from fonts defined in the YAML. If a glyph isn't
included, it renders as blank. This needs a deliberate strategy.

#### Problem Areas

| Category   | Characters        | Example                                    |
| ---------- | ----------------- | ------------------------------------------ |
| German     | ä ö ü ß Ä Ö Ü     | "Müller Milch Fürst Pückler"               |
| French     | é è ê ë à â ç     | "Crème fraîche légère"                     |
| Nordic     | å ø æ             | "Rødgrød med fløde"                        |
| Symbols    | ™ ® © – — ' ' " " | "Nutella® Hazelnut Spread"                 |
| Non-Latin  | 中文, 日本語, 🍎  | CJK product names from APIs                |
| UI mockups | ✓ ⚠ ✕ █ ░ →       | Not guaranteed in TTF fonts at small sizes |

#### Solution: Three Layers

**Layer 1 — Middleware sanitization (`ScanResponse`):**

Transliterate/normalize the `item`, `brand`, and `quantity` fields server-side
before sending to the ESP. Keep common European characters, degrade the rest:

```python
import unicodedata

def sanitize_for_display(text: str, max_len: int = 21) -> str:
    """Normalize Unicode for OLED display compatibility."""
    KEEP_CHARS = set("äöüßÄÖÜéèêëàâçåøæ°")
    result = []
    for ch in text:
        if ch.isascii() or ch in KEEP_CHARS:
            result.append(ch)
        else:
            decomposed = unicodedata.normalize('NFKD', ch)
            ascii_part = decomposed.encode('ascii', 'ignore').decode()
            result.append(ascii_part if ascii_part else '?')
    return ''.join(result)[:max_len]
```

This keeps German/French/Nordic characters (supported in the font) and
gracefully degrades everything else (™→TM, ñ→n, 中→?).

**Layer 2 — ESPHome font with explicit European glyph set:**

```yaml
font:
  - file: "gfonts://Roboto"
    id: font_body
    size: 10
    glyphs: >-
      !"#$%&'()*+,-./0123456789:;<=>?@
      ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`
      abcdefghijklmnopqrstuvwxyz{|}~
      ÄÖÜäöüß
      ÉÈÊËéèêë
      ÀÂàâÇç
      ÅåØøÆæ
      °€£¥µ

  - file: "gfonts://Roboto"
    id: font_heading
    size: 14
    glyphs: >-
      ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
      0123456789 .-!?:ÄÖÜäöüß

  # MDI icons — only the specific icons we use
  - file: "materialdesignicons-webfont.ttf"
    id: font_icons
    size: 18
    glyphs:
      - "\U000F05E0" # mdi:check-circle
      - "\U000F0026" # mdi:alert
      - "\U000F0159" # mdi:close-circle
      - "\U000F05A9" # mdi:wifi
      - "\U000F092D" # mdi:wifi-off
      - "\U000F029A" # mdi:barcode-scan
```

**Layer 3 — Use drawing primitives for UI elements:**

Instead of Unicode block characters for signal bars, use ESPHome's drawing API:

```cpp
// Draw 5-bar WiFi indicator using filled rectangles
int rssi = id(wifi_rssi).state;
int bars = 0;
if (rssi > -50) bars = 5;
else if (rssi > -60) bars = 4;
else if (rssi > -70) bars = 3;
else if (rssi > -80) bars = 2;
else if (rssi > -90) bars = 1;

for (int i = 0; i < 5; i++) {
  int h = 2 + i * 2;
  if (i < bars)
    it.filled_rectangle(108 + i*4, 64-h, 3, h);
  else
    it.rectangle(108 + i*4, 64-h, 3, h);
}
```

#### Revised Display Mockups (Using MDI Icons)

```
┌──────────────────────────┐     ┌──────────────────────────┐
│ [mdi:check] Added        │     │ [mdi:alert] Needs Mapping│
│                          │     │                          │
│ Barilla Spaghetti        │     │ Organic Whole Milk       │
│ No.5 500g                │     │                          │
│ ─────────────────────    │     │ Open middleware to map   │
│ 4006381333931     Mealie │     │ 4006381333931            │
└──────────────────────────┘     └──────────────────────────┘
```

#### Flash Budget (Fonts)

| Component                                | Size       | Notes                  |
| ---------------------------------------- | ---------- | ---------------------- |
| Roboto 10px (extended Latin ~150 glyphs) | ~8 KB      | Body text              |
| Roboto 14px (basic + German ~80 glyphs)  | ~5 KB      | Headings               |
| MDI icons (6 glyphs at 18px)             | ~2 KB      | Status icons           |
| SSD1306 display driver + framebuffer     | ~15 KB     | I2C, 128x64            |
| **Total display overhead**               | **~30 KB** | Well within 4 MB flash |

#### Character Strategy Summary

| Content                        | Source            | Handling                                                 |
| ------------------------------ | ----------------- | -------------------------------------------------------- |
| Product names (ä,é,å)          | API responses     | Explicit glyphs in font + middleware sanitization        |
| Unknown Unicode (™,中,🍎)      | API responses     | Middleware transliterates/strips before sending          |
| UI icons (check, alert, close) | Display layout    | MDI icon font — platform-native, scalable                |
| Signal bars, separators        | Display layout    | `filled_rectangle()` / `line()` drawing primitives       |
| Line width (128px ≈ 21 chars)  | Layout constraint | Middleware truncates fields; word-wrap in display lambda |

---

## 10. Scan Counter Sensor

A numeric `sensor:` that counts total scans since boot, exposed to HA.

```yaml
sensor:
  - platform: template
    name: "Scan Count"
    id: scan_count
    icon: mdi:counter
    entity_category: DIAGNOSTIC
    accuracy_decimals: 0
    lambda: "return id(scan_count_val);"

globals:
  - id: scan_count_val
    type: int
    restore_value: yes
    initial_value: "0"
```

Increment `scan_count_val` in the `barcode_raw` `on_value` handler.
Useful for HA dashboards ("items scanned today") and general diagnostics.

---

## 11. WiFi Signal on Display (Button-Activated)

Show RSSI on the status page (Page 3) — **not always-on**, only when the button
is pressed. Uses the built-in `wifi_signal` sensor:

```yaml
sensor:
  - platform: wifi_signal
    name: "WiFi Signal"
    id: wifi_rssi
    update_interval: 30s
    entity_category: DIAGNOSTIC
```

Rendered as a signal bar icon + dBm value on the status display page.

---

## 12. Configurable Standby Timeout via HA

Expose the result display duration as a `number:` entity so users can tune it
from HA (important with a display — you want to control how long it stays on):

```yaml
number:
  - platform: template
    name: "Display Timeout"
    id: display_timeout
    icon: mdi:timer-outline
    entity_category: CONFIG
    unit_of_measurement: "s"
    min_value: 2
    max_value: 30
    step: 1
    initial_value: 5
    restore_value: true
    optimistic: true
```

The `standby_timer` script references this value instead of a hardcoded `5s`:

```yaml
script:
  - id: standby_timer
    mode: restart
    then:
      - delay: !lambda "return id(display_timeout).state * 1000;"
      - text_sensor.template.publish:
          id: screen_mode
          state: "standby"
      # ... turn off display
```

---

## 13. 🗺️ Roadmap — Low Priority / Future

### 13a. Custom Buzzer Feedback by Result Type

Add a small passive buzzer on a GPIO for custom tones beyond the GM67's built-in beep:

- Single beep: successful add
- Double beep: needs mapping
- Long tone: error/unknown

**Priority:** Low. The GM67 already beeps on successful decode. Custom audio
feedback is nice-to-have but adds hardware complexity (buzzer + transistor driver).

---

## Summary Table

| #   | Category       | Item                            | Priority | Effort  |
| --- | -------------- | ------------------------------- | -------- | ------- |
| 1   | Security       | Move credentials to secrets     | High     | 5 min   |
| 2   | Cleanup        | Remove dead event/action code   | Low      | 5 min   |
| 3   | Robustness     | WiFi fast_connect + static IP   | Medium   | 5 min   |
| 4   | Robustness     | Boot state fallback timeout     | Medium   | 5 min   |
| 5   | Cosmetic       | UART list → single syntax       | Low      | 1 min   |
| 6   | Extension      | Add web_server for diagnostics  | Low      | 1 min   |
| 7   | HA Integration | Expose scan sensors + HA event  | Medium   | 30 min  |
| 8   | HA Integration | Actionable notifications via HA | Medium   | 30 min  |
| 9   | Hardware       | OLED display + button + sleep   | Medium   | 2-3 hrs |
| 10  | HA Integration | Scan counter sensor             | Low      | 5 min   |
| 11  | Display        | WiFi RSSI on status page        | Low      | 10 min  |
| 12  | UX             | Configurable standby timeout    | Medium   | 10 min  |
| 13  | 🗺️ Roadmap     | Custom buzzer feedback          | Low      | —       |
