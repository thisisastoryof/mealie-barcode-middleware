# Scanner Configuration (GM67)

The GM67 is a camera-based barcode scanner module built around a 640×480 CMOS sensor. It reads barcodes by capturing an image and decoding it in firmware — no moving laser mirror like the classic supermarket scanners from the '90s. This means it can also read QR codes, Data Matrix, and barcodes displayed on screens.

Out of the box, the GM67 only talks over USB. Before it will work with the ESP32 over UART, you need to perform a one-time configuration step. After that, all further settings are managed from Home Assistant via the ESPHome firmware.

---

## Initial Setup: Switching to UART Mode

The GM67 ships configured for USB HID mode (it acts like a keyboard when plugged into a PC). Since we're connecting it to an ESP32 via UART, you need to tell the GM67 to use its serial interface instead.

The GM67 is configured by scanning special QR codes printed in the vendor's programming manual. To enable UART/TTL mode, scan this QR code with the GM67 itself:

**QR code content:** `^#SC^3030010`

> You can generate this QR code using any free QR code generator (e.g., [qr-code-generator.com](https://www.qr-code-generator.com/)). Type `^#SC^3030010` as the text content, generate it, and display it on your phone or monitor. Then scan it with the GM67.

The scanner will beep to confirm the setting was accepted. **This only needs to be done once** — the GM67 stores this setting in its own flash memory and remembers it across power cycles.

> **Important:** Do this _before_ you flash the ESPHome firmware. If the GM67 is still in USB mode, the ESP32 won't receive any barcode data over UART and you'll think something is broken.

### Verifying UART Mode

After switching to UART mode, you can verify it's working:

1. Connect the GM67 to the ESP32 as described in the [hardware build guide](hardware-build.md)
2. Flash the ESPHome firmware (see [ESPHome firmware guide](esphome-firmware.md))
3. Open the ESPHome logs (serial or wireless)
4. Scan any barcode — you should see the raw bytes appear in the UART debug output

If you see nothing in the logs, double-check:

- TX/RX wires aren't swapped (ESP TX → GM67 RX, ESP RX → GM67 TX)
- Baud rate matches (the firmware defaults to 9600, which is the GM67's factory default)
- The GM67 is actually in UART mode (scan the QR code again to be sure)

---

## Supported Barcode Formats

The GM67 supports a wide range of 1D and 2D barcode standards. The formats most relevant for grocery/household product scanning are:

| Standard | Digits | Where You'll See It                                       |
| -------- | ------ | --------------------------------------------------------- |
| EAN-13   | 13     | Most products in Europe, Asia, Australia                  |
| EAN-8    | 8      | Small European products (spice jars, candy bars)          |
| UPC-A    | 12     | Most products in North America                            |
| UPC-E    | 8      | Small North American products                             |
| ITF-14   | 14     | Outer shipping cartons — occasionally on retail packaging |

The GM67 also reads QR codes, which this project uses for [GENERIC items](barcode-workflow.md) (e.g., scanning a QR code containing `GENERIC:Milk` adds "Milk" directly to your shopping list without a barcode lookup).

All of the above formats are enabled in the GM67's factory defaults. If you need to enable or disable specific symbologies (e.g., you're getting false reads from Code 128 barcodes on shipping labels), the vendor's programming manual has QR codes for toggling each format individually.

---

## Settings Reference

Once the ESP32 is flashed and connected to Home Assistant, you can configure the GM67's behavior from the HA entity UI. Each setting appears as a dropdown or toggle under the barcode scanner device.

All settings are stored in the ESP32's flash memory (`restore_value: true` in ESPHome) and re-sent to the GM67 on every boot. **The GM67 itself does not remember UART-configured settings across power loss** — this is a hardware limitation. ESPHome handles persistence on its behalf.

### Trigger Mode

Controls how the GM67 decides when to start scanning.

| Option                  | What It Does                                                                                                      | Best For                                                                      |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Button Holding**      | Scans only while the physical button on the GM67 breakout is held down                                            | Handheld use where you point and press                                        |
| **Button Trigger**      | A short button press starts scanning; stops after a read or timeout                                               | Similar to above but one-handed friendly                                      |
| **Continuous Scanning** | Never stops scanning — always looking for a barcode                                                               | High-throughput setups, but uses more power and the LED/laser are always on   |
| **Automatic Induction** | Wakes up when the ambient light in front of the sensor changes (e.g., a product moves in front), sleeps otherwise | **Wall/under-cabinet mounted scanners** — no button needed, no constant laser |
| **Host**                | Only scans when the ESP32 sends a UART command to start                                                           | Advanced use — full software control                                          |

**Default:** Automatic Induction — this is the best choice for a kitchen-mounted scanner. The GM67 sits idle with the laser off until you wave a product in front of it. No button press needed, no annoying always-on red light.

### Buzzer Volume

Controls the beep the GM67 makes when it successfully reads a barcode.

| Option     | Effect                   |
| ---------- | ------------------------ |
| **Off**    | Silent — no beep on scan |
| **Low**    | Quiet beep               |
| **Medium** | Normal beep              |
| **High**   | Loud beep                |

**Default:** Medium. The beep gives immediate tactile feedback that a scan was registered. Consider "Off" if the scanner is near a bedroom or "Low" for late-night scanning.

> **How it works internally:** "Off" disables the buzzer entirely (address `0x0038`, value `0x00`). The other three options first enable the buzzer, then set the volume level via a separate register (address `0x008C`).

### Scanning Light

The GM67 has a white illumination LED that lights up the barcode for the camera. This setting controls when it's active.

| Option              | Effect                                             |
| ------------------- | -------------------------------------------------- |
| **On When Reading** | LED on only while actively scanning                |
| **Always On**       | LED always on (bright, uses power)                 |
| **Always Off**      | LED always off (may struggle in dark environments) |

**Default:** On When Reading. Unless your scanner is in a very dark spot and you want a constant light, leave this alone.

### Collimation (Aiming Laser)

The red aiming lines/dots projected by the GM67 that help you line up a barcode. "Collimation" is the technical term — think of it as the red laser crosshair.

| Option              | Effect                                                                   |
| ------------------- | ------------------------------------------------------------------------ |
| **On When Reading** | Laser on only while actively scanning                                    |
| **Always On**       | Laser always on                                                          |
| **Always Off**      | Laser off — scanning still works, you just don't see where it's pointing |

**Default:** On When Reading. "Always Off" can be nice if the scanner is in a living area and the red glow is distracting, but you lose the visual feedback of knowing where to aim.

### Collimation Flashing

Whether the aiming laser blinks or stays solid when active.

| Option  | Effect                                                             |
| ------- | ------------------------------------------------------------------ |
| **On**  | Laser blinks (more attention-grabbing, helps locate the scan area) |
| **Off** | Laser stays solid                                                  |

**Default:** On.

### Same Code Delay

How long the GM67 waits before it will accept the _same_ barcode again. This prevents accidental double-scans when you hold a product in front of the scanner a bit too long.

| Option        | Effect                                                                         |
| ------------- | ------------------------------------------------------------------------------ |
| **0.5 s**     | Almost no delay — fast re-scanning                                             |
| **1 s**       | Short delay                                                                    |
| **3 s**       | Moderate delay                                                                 |
| **5 s**       | Longer delay                                                                   |
| **7 s**       | Long delay                                                                     |
| **No Repeat** | Same barcode cannot be scanned twice in a row (scan a different barcode first) |

**Default:** 3 s — a good balance. If you're scanning a batch of the same product (e.g., six cans of beans), lower this to 0.5 s. "No Repeat" is useful if family members keep accidentally re-scanning the same item.

### Scanning Enabled

A master on/off switch for the scanner.

| Option  | Effect                                                      |
| ------- | ----------------------------------------------------------- |
| **On**  | Scanner operates normally                                   |
| **Off** | Scanner is completely disabled — no reads, no laser, no LED |

**Default:** On.

**Practical uses:**

- **Child lock:** Toggle this off so curious kids can't add random items to your shopping list
- **Night mode:** Use a Home Assistant automation to disable scanning at night (no red laser flashing in a dark kitchen when the cat walks past)
- **Seasonal:** Disable the scanner when you're away on holiday

### Display Timeout

How long the OLED screen stays on after showing a scan result before going to standby (screen off).

| Value            | Range                          |
| ---------------- | ------------------------------ |
| **2–30 seconds** | Adjustable from Home Assistant |

**Default:** 8 s. Long enough to read the product name, short enough to not burn in the OLED. If your OLED is prone to image retention, lower this.

---

## How Settings Are Persisted

This is a detail worth understanding if you're debugging unexpected behavior:

1. **You change a setting** in Home Assistant (e.g., set Trigger Mode to "Continuous Scanning")
2. **ESPHome stores the value** in the ESP32's flash memory (NVS partition)
3. **ESPHome sends the UART command** to the GM67, which applies it immediately
4. **The GM67 does NOT save it** — its internal flash only stores settings written via the QR code programming method (the vendor manual approach)
5. **On next power cycle**, the GM67 boots with its own defaults. ESPHome reads the saved value from its flash and re-sends the UART command during boot

This means: if you power-cycle the scanner, there's a brief moment (~1–2 seconds) after boot where the GM67 is running its own defaults before ESPHome re-applies your settings. In practice, this is invisible — ESPHome sends the commands during its boot sequence before WiFi is even connected.

---

## The UART Command Protocol

If you want to add new GM67 settings or understand what the hex arrays in the ESPHome YAML actually mean, here's how the serial protocol works.

### Packet Structure

Every command sent to the GM67 follows this format:

```
[Length] [Type] [0x04] [Storage] [Addr_H] [Addr_L] [Data...] [Check_H] [Check_L]
```

| Field    | Size     | Description                                                                                                                       |
| -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Length   | 1 byte   | Number of bytes that follow, excluding the 2-byte checksum                                                                        |
| Type     | 1 byte   | Command type: `0xC6` = write parameter, `0xE9` = enable scanning, `0xEA` = disable scanning                                       |
| `0x04`   | 1 byte   | Constant — appears to indicate a "direct write" sub-type                                                                          |
| Storage  | 1 byte   | `0x08` = temporary (RAM), `0x00` = persistent (flash). The ESPHome config uses `0x08` because persistence is handled by the ESP32 |
| Address  | 2 bytes  | Big-endian register address for the setting                                                                                       |
| Data     | 1+ bytes | The value to write                                                                                                                |
| Checksum | 2 bytes  | 16-bit two's complement of the sum of all preceding bytes                                                                         |

### Checksum Calculation

The checksum is straightforward: sum all bytes before the checksum, then compute the 16-bit two's complement.

**Example:** Trigger Mode → Automatic Induction

```
Bytes:    0x07  0xC6  0x04  0x08  0x00  0x8A  0x09
Sum:      0x07 + 0xC6 + 0x04 + 0x08 + 0x00 + 0x8A + 0x09 = 0x0163
Checksum: 0x10000 - 0x0163 = 0xFE9D
Result:   [0x07, 0xC6, 0x04, 0x08, 0x00, 0x8A, 0x09, 0xFE, 0x94]
```

> Wait — the example above shows `0x09` (Automatic Induction value) but the final byte is `0x94`, not `0x9D`. That's because the sum includes `0x09`: `0x0163` is the sum for value `0x00` (Button Holding). For value `0x09`: sum = `0x016C`, checksum = `0xFE94`. Each value changes the checksum.

### Register Address Map

These are the register addresses used in this project's ESPHome configuration:

| Address  | Sub-Address | Setting           | Values                                                                                                        |
| -------- | ----------- | ----------------- | ------------------------------------------------------------------------------------------------------------- |
| `0x008A` | —           | Trigger Mode      | `0x00` = Button Holding, `0x02` = Button Trigger, `0x04` = Continuous, `0x09` = Auto Induction, `0x08` = Host |
| `0x0038` | —           | Buzzer Enable     | `0x00` = off, `0x01` = on                                                                                     |
| `0x008C` | —           | Buzzer Volume     | `0x00` = high, `0x01` = medium, `0x02` = low                                                                  |
| `0x00F2` | `0x02`      | Scanning Light    | `0x00` = on when reading, `0x01` = always on, `0x02` = always off                                             |
| `0x00F2` | `0x03`      | Collimation       | `0x00` = on when reading, `0x01` = always on, `0x02` = always off                                             |
| `0x00F2` | `0xB8`      | Collimation Flash | `0x00` = on, `0x01` = off                                                                                     |
| `0x00F2` | `0xC9`      | Same Code Delay   | `0x01` = 0.5 s, `0x03` = 1 s (see note), `0x05` = 3 s, `0x07` = 5 s, `0x09` = no repeat                       |

Settings under address `0x00F2` use a sub-address byte (the register is a "group" that contains multiple related settings), which adds one extra byte to the packet — that's why those commands are 10 bytes instead of 9.

### Enable / Disable Commands

The scanning enable/disable uses different command types (`0xE9` / `0xEA`) instead of `0xC6`:

```
Enable:  [0x04, 0xE9, 0x04, 0x00, 0xFF, 0x0F]
Disable: [0x04, 0xEA, 0x04, 0x00, 0xFF, 0x0E]
```

These are shorter (6 bytes) because there's no address or data field — the command type itself carries the meaning.

### Adding New Settings

If you want to expose additional GM67 settings (e.g., enabling/disabling specific barcode symbologies, changing the scan timeout, or adjusting the image sensor sensitivity):

1. Find the register address and values in the vendor's programming manual
2. Build the command bytes following the packet structure above
3. Calculate the checksum
4. Add a new `select:` or `switch:` entity in the ESPHome YAML with `uart.write:` actions

The vendor manual contains hundreds of configurable options — the seven exposed in this project cover the most useful day-to-day settings for a kitchen scanner.

---

## Sources and References

| Resource                                                                                                                                                                                                       | What It Contains                                                                                                                                                                                                      |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [GROW GM67 product page](https://en.hzgrow.com/product/161.html)                                                                                                                                               | Manufacturer's official product page (Hangzhou Grow Technology Co., Ltd.) with specs, photos, and downloads                                                                                                           |
| [GM67 User Manual V1.3 (PDF)](https://www.dropbox.com/scl/fo/87hz5h82k25j3p9k5u603/AAHeKnvPGQ-faoU-iEHKix0/GM67%20Barcode%20Reader%20Module%20User%20Manual-V1.3.pdf?rlkey=2fyvdir15kb1kj2ada1zkadqt&e=1&dl=0) | The vendor's full configuration manual (Oct 2020). Contains QR codes for every setting and the serial command protocol in Appendix 6. This is where the register addresses and values used in this project come from. |
| [ESPHome UART Bus docs](https://esphome.io/components/uart.html)                                                                                                                                               | How ESPHome's `uart.write` and UART debug work — used for sending commands and receiving barcodes                                                                                                                     |
| [ESPHome Select Component](https://esphome.io/components/select/template.html)                                                                                                                                 | Template select entities — used to create the setting dropdowns in Home Assistant                                                                                                                                     |
| [Matt Fryer's HA-Mealie-Barcode-Scanner](https://github.com/MattFryer/HA-Mealie-Barcode-Scanner)                                                                                                               | The original project that implemented the GM67 serial commands in ESPHome and built the Home Assistant integration pattern. The ESPHome YAML in this project is derived from Matt's work.                             |

> **A note on the vendor manual:** The PDF link above is hosted on Dropbox by the manufacturer — GROW doesn't offer direct downloads on their product page. If the link goes dead, search for "GM67 Barcode Reader Module User Manual V1.3" or check the [manufacturer's site](https://en.hzgrow.com/product/161.html) for updated links.
