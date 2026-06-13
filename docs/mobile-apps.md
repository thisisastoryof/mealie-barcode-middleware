# Mobile App Scanning

Don't have an ESP32 scanner? No problem. Your phone works too.

This guide covers two options: **BinaryEye** (Android) and **iOS Shortcuts** (iPhone/iPad). Both send scanned barcodes directly to the middleware — no Home Assistant required, no cloud services involved.

> **Push notifications work too.** If you've set up the HA webhook (see [Middleware Setup](middleware-setup.md#home-assistant-push-notifications-optional)), you'll get phone notifications for scans that need attention — regardless of whether you scanned with the ESP32, BinaryEye, or an iOS Shortcut.

---

## How It Works

The middleware exposes two scan endpoints:

| Endpoint         | Auth Method                    | Used By                                         |
| ---------------- | ------------------------------ | ----------------------------------------------- |
| `POST /scan`     | `Authorization: Bearer` header | ESP32 scanner, curl, iOS Shortcuts, scripts     |
| `POST /scan/app` | Token in `deviceId` JSON field | Android apps (BinaryEye) that can't set headers |

Both endpoints use the **same tokens** from the Settings page. The only difference is where the token travels — in a header or in the request body. The scan pipeline (lookup, fuzzy matching, shopping list) is identical.

---

## Android — BinaryEye

[BinaryEye](https://github.com/markusfisch/BinaryEye) is a free, open-source barcode scanner for Android. It can automatically forward scanned codes to a URL — perfect for our use case.

**Install:** [F-Droid](https://f-droid.org/en/packages/de.markusfisch.android.binaryeye/) or [Google Play](https://play.google.com/store/apps/details?id=de.markusfisch.android.binaryeye)

### Setup (5 minutes)

#### 1. Create a Token

1. Open the middleware web UI → **Settings** → **Tokens** tab
2. Enter a name like "Phone – BinaryEye" and click **Create**
3. **Copy the token immediately** — it's only shown once

#### 2. Configure BinaryEye

Open BinaryEye → ⚙️ Settings → scroll to **Send scan to URL**:

| Setting          | Value                                     |
| ---------------- | ----------------------------------------- |
| **URL**          | `http://your-middleware-ip:9930/scan/app` |
| **Content type** | `application/json` (POST JSON)            |
| **Scanner ID**   | Paste the raw API token you copied above  |

> ⚠️ **Important:** The Scanner ID field is your authentication secret. Don't share it. If compromised, revoke the token in Settings and create a new one.

#### 3. Enable Forwarding

Still in BinaryEye Settings:

- Toggle **Send scan automatically** ON

That's it. Every barcode you scan will be sent to the middleware and processed exactly like an ESP32 scan.

### What BinaryEye Sends

When you scan a barcode, BinaryEye POSTs JSON like this:

```json
{
  "content": "4006381333931",
  "raw": "3430303633383133333339333133",
  "format": "EAN_13",
  "errorCorrectionLevel": "",
  "version": "",
  "sequenceSize": "0",
  "sequenceIndex": "0",
  "sequenceId": "",
  "country": "DE",
  "addOn": "",
  "price": "",
  "issueNumber": "",
  "timestamp": "2026-06-12 14:30:00",
  "deviceId": "your-token-here"
}
```

The middleware uses `content` as the barcode and `deviceId` for authentication. All other fields are accepted but currently ignored (they're available for future features like format-specific handling).

### Troubleshooting

| Problem                           | Fix                                                                   |
| --------------------------------- | --------------------------------------------------------------------- |
| 401 Unauthorized                  | Check your Scanner ID matches a valid token exactly (no extra spaces) |
| 422 Unprocessable Entity          | The `content` field is empty — BinaryEye scanned something odd        |
| Connection refused                | Check the URL (port, IP). Is the middleware running? (`/health`)      |
| Nothing happens after scan        | Is "Send scan automatically" enabled? Check the Content type is JSON  |
| Works on WiFi, not on mobile data | Expected — the middleware is on your local network                    |

### Tips

- **Bulk scanning at the store:** BinaryEye has a "Bulk mode" (Settings → Scanning → Bulk mode) that continuously scans without returning to the result screen. Combined with auto-send, you can rapid-fire scan your entire grocery haul.
- **Visual feedback:** BinaryEye shows the HTTP response after each send. You'll see the JSON response with `"result": "added"` and the item name.
- **Multiple phones:** Create a separate token for each family member's phone. You can see who scanned what in the activity log (by token name).

---

## iOS — Shortcuts

iPhones don't have BinaryEye, but Apple's built-in **Shortcuts** app can scan barcodes and make HTTP requests — with full custom header support. This means iOS uses the standard `POST /scan` endpoint with Bearer auth, just like the ESP32.

### Setup (10 minutes)

#### 1. Create a Token

Same as above: middleware web UI → Settings → Tokens → create one named "iPhone".

#### 2. Build the Shortcut

Open the **Shortcuts** app and create a new shortcut:

**Step 1 — Scan:**

1. Add action: **Scan QR/Barcode**

**Step 2 — Send to middleware:**

1. Add action: **Get Contents of URL**
2. URL: `http://your-middleware-ip:9930/scan`
3. Method: **POST**
4. Headers: Add header:
   - Key: `Authorization`
   - Value: `Bearer YOUR_TOKEN_HERE`
5. Request Body: **JSON**
   - Add field: Key = `barcode`, Value = **QR/Barcode Result** (the variable from Step 1)

**Step 3 — Show result (optional):**

1. Add action: **Get Dictionary Value**
   - Get value for key `item` in **Contents of URL**
2. Add action: **Show Notification**
   - Body: "Added: " + **Dictionary Value**

#### 3. Add to Home Screen

Tap the shortcut name → **Add to Home Screen**. Now you have a one-tap barcode scanner on your iPhone home screen.

### Example Shortcut Flow

```
┌──────────────────┐
│  Scan QR/Barcode │  ← Opens camera, reads barcode
└────────┬─────────┘
         │ "4006381333931"
         ▼
┌──────────────────────────────┐
│  Get Contents of URL         │
│  POST http://ip:9930/scan    │
│  Header: Authorization:      │
│    Bearer abc123...          │
│  Body: {"barcode":           │
│    "4006381333931"}          │
└────────┬─────────────────────┘
         │ {"result":"added","item":"Whole Milk"}
         ▼
┌──────────────────┐
│  Show Notification│  ← "Added: Whole Milk"
└──────────────────┘
```

### Tips

- **Siri trigger:** Name your shortcut "Scan barcode" and you can say "Hey Siri, scan barcode" to trigger it hands-free.
- **Widget:** Add the shortcut to a home screen widget for even faster access.
- **NFC Automation:** Create a Personal Automation triggered by an NFC tag on your fridge/pantry — tap your phone to the tag and it opens the scanner.
- **Share with family:** Export the shortcut (minus the token) and share it. Each family member creates their own token.

### Troubleshooting

| Problem             | Fix                                                             |
| ------------------- | --------------------------------------------------------------- |
| "Could not connect" | Check URL, port, and that phone is on the same network          |
| 401 Unauthorized    | Check `Bearer ` prefix (with space) and that the token is valid |
| Camera doesn't open | Shortcuts needs camera permission — check iOS Settings          |
| Nothing happens     | Make sure the Shortcut actions are in the right order           |

---

## Comparison

| Feature                | ESP32 DIY Scanner | BinaryEye (Android)  | iOS Shortcuts        |
| ---------------------- | ----------------- | -------------------- | -------------------- |
| Dedicated device       | ✅                | ❌ (it's your phone) | ❌ (it's your phone) |
| Always-on, grab & scan | ✅                | Need to open app     | Need to tap shortcut |
| OLED feedback          | ✅                | In-app response      | Notification         |
| Works without phone    | ✅                | ❌                   | ❌                   |
| Zero hardware cost     | ❌ (~€15 parts)   | ✅                   | ✅                   |
| Bulk rapid scanning    | ✅                | ✅ (bulk mode)       | One at a time        |
| HA push notifications  | ✅                | ✅                   | ✅                   |
| Auth method            | Bearer header     | Pre-shared key       | Bearer header        |
| Setup difficulty       | Medium (solder)   | Easy (5 min)         | Easy (10 min)        |

**Recommended combo:** Build the ESP32 scanner for the kitchen (always ready, one-hand operation) and set up BinaryEye/iOS Shortcuts for scanning at the grocery store.

---

## Security Notes

- **Tokens are tokens** — whether sent as a Bearer header or as a deviceId, it's the same secret. Treat your Scanner ID in BinaryEye the same way you'd treat a password.
- **Local network only** — Don't expose the middleware to the internet. If you need remote scanning (e.g. at the store), use a VPN like WireGuard or Tailscale to reach your home network.
- **One token per device** — Create separate tokens for each scanner/phone. If a phone is lost or compromised, revoke just that token without affecting other devices.
- **The deviceId field is never logged** — The middleware only logs the token name/prefix, never the raw secret.
