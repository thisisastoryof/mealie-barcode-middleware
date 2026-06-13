# Troubleshooting

Common issues and their solutions, organized by component.

---

## Hardware / ESP32

| Symptom                            | Likely Cause                     | Fix                                                      |
| ---------------------------------- | -------------------------------- | -------------------------------------------------------- |
| ESP reboots when scanner fires     | 5 V rail sag → brownout          | Add/increase the 470 µF bulk cap; use a better USB cable |
| Random reboots / won't boot        | Weak EN pull-up (knockoff board) | Add 10 kΩ pull-up + 100 nF cap on EN pin                 |
| No barcode data received           | TX/RX wires swapped              | Swap the wires on GPIO16 ↔ GPIO17                        |
| Garbage characters from scanner    | Baud rate mismatch               | Verify GM67 is set to 9600 baud                          |
| WiFi keeps disconnecting           | Shared 5 V rail sag              | Bigger bulk cap; better USB power source                 |
| Scanner LED doesn't turn on        | Insufficient USB current         | Use a phone charger (2 A+), not a PC USB port            |
| Enters download mode randomly      | GPIO0 pulled LOW or EN glitch    | Check EN pin; don't connect anything to GPIO0            |
| Works on bench, fails in enclosure | Overheating                      | Add ventilation holes to 3D-printed case                 |
| Boot loops after flash             | GPIO12 pulled HIGH at boot       | Don't connect anything to GPIO12                         |

### Watchdog Timer (WDT) Reboot

If the ESPHome log shows a WDT reset, the HTTP request to the middleware took too long. Check:

1. **Is the middleware running?** Open `http://middleware-ip:9930/health` in a browser
2. **Are the external APIs slow?** The middleware has 5 s timeouts for OpenFoodFacts and UPCDatabase. In `failover` mode (default), at most two sequential API calls are made if the primary returns nothing — total up to 10 s plus Mealie time. In `complement` mode with `LOOKUP_ENRICH_IN_BACKGROUND=true` (default), only one API call blocks the response — the secondary call runs after the response is sent. If you set `LOOKUP_ENRICH_IN_BACKGROUND=false`, both calls are sequential and total time can approach 13 s. The ESP's HTTP timeout is 14 s, and the WDT is 15 s.
3. **Is WiFi reception weak?** Check the RSSI value on the status screen (long-press button). Below -80 dBm is unreliable.

### "Fault — Unknown" Crash

If you see `Fault - Unknown` in the ESPHome log with a backtrace pointing to `esp_cpu_wait_for_intr`:

- This is a memory corruption or exhaustion crash, not a clean timeout
- Ensure `web_server:` is **not** in your config — it uses ~40–60 KB RAM under ESP-IDF
- The config includes `sram1_as_iram: true` and `minimum_chip_revision: "3.0"` to optimize memory — make sure these are present

---

## Middleware

### HTTP 500 on Re-Scan

**Symptom:** First scan of a barcode works. Scanning the same barcode again returns HTTP 500.

**Cause:** Timezone-aware vs timezone-naive datetime comparison in the TTL check. Fixed in commit `8709859`.

**Fix:** Update to the latest code and rebuild Docker.

### Retry Queue Not Working

**Symptom:** Failed Mealie requests are never retried. Docker logs show:

```
NameError: name 'utcnow' is not defined
```

**Cause:** Missing import in `scheduler.py`. Fixed in commit `8709859`.

**Fix:** Update to the latest code and rebuild Docker.

### Can't Reach Mealie

**Symptom:** Health check shows `mealie_reachable: false`. Scans result in "queued".

Check:

1. Is `MEALIE_URL` correct? It should be the URL accessible from the Docker container (e.g. `http://192.168.x.x:9925`, not `localhost`)
2. Is the Mealie API key valid? Test with curl:
   ```bash
   curl -H "Authorization: Bearer YOUR_KEY" http://mealie-ip:9925/api/app/about
   ```
3. Are Mealie and the middleware on the same Docker network? If using Docker Compose, they need to be able to reach each other.

### Shopping List ID Not Found

**Symptom:** Scans succeed (HTTP 200) but nothing appears on the shopping list. Docker logs show Mealie returning 404 or 422.

**Fix:** Double-check `MEALIE_SHOPPING_LIST_ID`. Open the shopping list in Mealie's web UI — the UUID is in the browser URL bar.

### Fuzzy Matching Too Aggressive

**Symptom:** Barcodes are auto-linked to the wrong Mealie items.

**Fix:** Increase `FUZZY_MATCH_THRESHOLD` (default 85) and/or `FUZZY_AMBIGUITY_GAP` (default 10). Setting the threshold to 90+ and gap to 15+ will make auto-linking more conservative. You can always manually link from the barcode detail page.

### Fuzzy Matching Too Conservative

**Symptom:** Products are never auto-linked even when the correct Mealie item exists.

**Fix:** Lower `FUZZY_MATCH_THRESHOLD` (try 75) and/or add **aliases** to your Mealie items. The fuzzy matcher checks both the item name and its aliases. For example, if your Mealie item is "Hafermilch" but the external database returns "Oat Milk", add "Oat Milk" as an alias.

---

## Web UI

### Dashboard Shows "Mealie: Unreachable"

Same as "Can't Reach Mealie" above. The dashboard polls `/health` which checks Mealie connectivity.

### No Live Toast Notifications

**Symptom:** Scanning a barcode doesn't show a toast in the browser.

Check:

1. Is the browser tab open? SSE only works with an active connection
2. Open browser dev tools → Network → filter by "events". You should see an active SSE connection to `/events`
3. If the connection keeps dropping, check if a reverse proxy is timing out idle connections

### Notifications Not Clearing

**Symptom:** Bell icon shows a count but clicking "Mark all read" doesn't clear it.

**Fix:** Hard-refresh the page (Ctrl+Shift+R). The notification count is updated via AJAX — a stale JavaScript cache can cause display issues.

---

## ESPHome Build Errors

### "CONFIG_ESP_TASK_WDT_TIMEOUT_S redefinition"

**Cause:** Using `build_flags: -D CONFIG_ESP_TASK_WDT_TIMEOUT_S=15` with the Arduino framework. The flag conflicts with `sdkconfig.h`.

**Fix:** The config uses ESP-IDF framework with `sdkconfig_options` instead. Make sure your `esp32:` section has:

```yaml
esp32:
  board: esp32dev
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_ESP_TASK_WDT_TIMEOUT_S: "15"
```

### Font Download Failures

**Symptom:** Build fails trying to download Google Fonts or the MDI icon font.

**Fix:** These are downloaded once and cached by ESPHome. If your HA instance doesn't have internet access, download the fonts manually and use `file: type: local` instead of `type: web` or `gfonts://`.

---

## Mobile Apps

### BinaryEye: 401 Unauthorized

**Symptom:** Docker logs show `401 Unauthorized` for POST `/scan/app`.

**Cause:** The Scanner ID in BinaryEye doesn't match any valid token.

**Fix:**

1. Make sure you're using the **raw token** (the long string shown once when you created it), not the token name
2. Check for leading/trailing spaces — copy-paste carefully
3. Verify the token still exists: middleware web UI → Settings → Tokens tab
4. If in doubt, create a fresh token and re-paste it

### BinaryEye: 422 Unprocessable Entity

**Symptom:** Scan sends but returns 422.

**Cause:** The `content` field is empty (BinaryEye scanned something it couldn't decode cleanly) or the Content-Type is wrong.

**Fix:** Make sure BinaryEye is configured to send **POST JSON** (`application/json`). The other modes (GET, form-urlencoded) are not supported by `/scan/app`.

### BinaryEye: Connection Refused / Timeout

**Fix:**

1. Is your phone on the same WiFi as the middleware? Mobile data won't reach a local IP.
2. Check the URL: `http://your-ip:9930/scan/app` — note the port and path.
3. Test from your phone's browser: open `http://your-ip:9930/health` — you should see a JSON response.
4. Firewall: some routers block inter-device traffic. Check your router's "AP isolation" setting.

### iOS Shortcut: "The request timed out"

**Fix:** Same network check as above. Also ensure the URL doesn't have a trailing slash.

---

## Home Assistant Notifications

### No Push Notifications After Scanning

**Check:**

1. Is `HA_WEBHOOK_URL` set? Check the middleware web UI → Settings → System → Home Assistant.
2. Is the URL correct? It should be `http://homeassistant.local:8123/api/webhook/YOUR-WEBHOOK-ID` (or your HA IP).
3. Does the webhook ID match? The ID in the URL must match the `webhook_id` in the HA automation YAML.
4. Is the HA automation enabled? Check Settings → Automations in HA.
5. Is `MIDDLEWARE_BASE_URL` set? Without it, the notification's deep link will be a relative path (`/barcodes/...`) instead of a clickable URL.

**Test the webhook manually:**

```bash
curl -X POST http://homeassistant.local:8123/api/webhook/barcode-scanner \
  -H "Content-Type: application/json" \
  -d '{"barcode":"0000000000000","item":"Test Item","result_type":"unknown","action_url":"http://ip:9930/barcodes/0000000000000"}'
```

If this triggers a notification, the webhook works and the issue is on the middleware side. Check Docker logs for `HA webhook` messages.

### Duplicate Notifications (ESP32 + Webhook)

If you previously used the ESPHome event-based automation (`esphome.barcode_scanned`), disable it. Notifications are now handled centrally by the middleware webhook — keeping both active will produce duplicates for ESP32 scans.

---

## Docker

### Container Won't Start

Check the logs:

```bash
docker logs mealie-barcode-middleware 2>&1 | head -30
```

Common causes:

- `.env` file missing or has syntax errors
- Required variables (`MEALIE_URL`, `MEALIE_API_KEY`, `MEALIE_SHOPPING_LIST_ID`) not set
- Port conflict — another service is already using port 9930

### Database Permission Error

**Symptom:** Container starts but crashes with a SQLite permission error.

**Fix:** The container runs as a non-root user. The `/data` volume must be writable:

```bash
chmod 777 ./middleware-data  # or chown to UID 1000
```

### Health Check Failing

**Symptom:** Docker reports the container as unhealthy.

The health check calls `GET /health` every 30 seconds. If it fails:

1. Check if uvicorn is running: `docker exec <container> ps aux`
2. Check if the port is correct: the container listens on port 8000 internally, mapped to your chosen external port
3. Check Docker logs for Python exceptions on startup
