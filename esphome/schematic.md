# ESP8266 (NodeMCU v2) + GM67 Barcode Scanner — Wiring Schematic

## Hardware

| Component          | Specifics                                                  |
| ------------------ | ---------------------------------------------------------- |
| MCU board          | **NodeMCU v2** (ESP8266, 4MB flash, AMS1117-3.3 regulator) |
| Barcode scanner    | **GM67 breakout board** (5V input, onboard 3.3V regulator) |
| Scanner interface  | 4-wire UART header (VCC, GND, TX, RX)                      |
| OLED display       | **SSD1306 128×64 I2C** (0.96", address 0x3C)               |
| Button             | Momentary push button (NO, connects GPIO13/D7 to GND)      |
| Target form factor | Perf board, soldered, 3D-printed enclosure                 |

---

## 1. Logic Levels — No Level Shifter Needed

| Device            | Supply | UART Logic Level | Notes                                                                    |
| ----------------- | ------ | ---------------- | ------------------------------------------------------------------------ |
| ESP8266 (NodeMCU) | 3.3V   | 3.3V TTL         | **Not 5V-tolerant** on any GPIO                                          |
| GM67 breakout     | 5V in  | **3.3V TTL out** | Internal engine is 3.3V; the breakout board's regulator only feeds power |

The GM67's UART TX/RX signals are 3.3V regardless of whether the board is
fed 5V or 3.3V. **Direct connection to ESP8266 GPIOs is safe. No level
shifter required.**

---

## 2. Power Architecture

### Power Budget

| Consumer                      | Typical | Peak        |
| ----------------------------- | ------- | ----------- |
| ESP8266 (WiFi active)         | ~80 mA  | ~430 mA ¹   |
| GM67 (idle / IR sensing)      | ~55 mA  | ~60 mA      |
| GM67 (active scan: LED+laser) | ~200 mA | ~350 mA     |
| **Combined worst case**       |         | **~780 mA** |

¹ WiFi TX bursts, typically <5ms

### Strategy: Separate 5V/3.3V Rails

Since the GM67 breakout has its own onboard regulator, powering it from the
**5V USB rail directly** keeps its ~200-350 mA scan current completely off
the NodeMCU's AMS1117-3.3 regulator (rated 800 mA, but already serving the
ESP8266's WiFi peaks):

```
USB 5V ──┬──► [NodeMCU AMS1117-3.3] ──► 3.3V ──► ESP8266 only
         │
         └──► GM67 breakout VCC (5V) ──► [GM67 onboard reg] ──► 3.3V internal
```

Both GND rails must be connected (common ground).

### Decoupling Capacitors

Place these **as close to the GM67 VCC/GND pins as possible** on the perf board:

| Capacitor    | Value               | Purpose                                       |
| ------------ | ------------------- | --------------------------------------------- |
| C1 (ceramic) | **100 nF** (0.1 µF) | High-frequency switching noise suppression    |
| C2 (bulk)    | **470 µF, 10V**     | Absorbs inrush current when scanner LED fires |

**Why 470 µF?** The GM67 draws a sharp ~350 mA spike when the illumination
LED and aiming laser activate simultaneously. On a weak USB power source
(phone charger, long/thin cable, unpowered USB hub), this spike can pull
the 5V rail low enough to brownout the ESP8266 even though they have
separate regulators — because both regulators share the same USB 5V input.
The bulk cap provides local energy storage to ride through these transients.

> **If your "culprits" include WiFi disconnects, random reboots, or the
> scanner failing to respond after a scan — this capacitor is the fix.**

### Optional: Separate 3.3V Capacitor

If you still see instability, add a second pair near the NodeMCU's 3V3 pin:

| Capacitor    | Value        | Purpose                      |
| ------------ | ------------ | ---------------------------- |
| C3 (ceramic) | 100 nF       | ESP8266 rail noise filtering |
| C4 (bulk)    | 100 µF, 6.3V | WiFi TX burst energy reserve |

This is belt-and-suspenders — usually not needed with the split-rail design,
but cheap insurance on a perf board where you have the space.

---

## 3. UART Pin Selection

### Your Current Setup: UART0 (GPIO1/GPIO3)

Your config uses the **hardware UART0** pins with serial logging disabled:

```yaml
tx_pin: GPIO1 # NodeMCU TX pin (UART0 TX)
rx_pin: GPIO3 # NodeMCU RX pin (UART0 RX)
logger:
  baud_rate: 0 # Logging disabled to free UART0
```

**This is a valid and proven approach.** Trade-offs:

| Aspect               | UART0 (GPIO1/3) — your setup                                                               | Software UART (GPIO14/12)                                           |
| -------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| UART reliability     | Hardware peripheral — rock solid                                                           | Software bit-bang — good at 9600 baud but theoretically less robust |
| USB serial logging   | **Disabled** (can't debug via serial monitor)                                              | Available (UART0 stays free)                                        |
| Flashing over USB    | Works (UART0 is released during boot/flash)                                                | Works                                                               |
| Boot-mode conflicts  | None if logger is off                                                                      | None                                                                |
| Extra wiring concern | GM67 must be **disconnected** or **not driving** GPIO3 during flash — or flashing may fail | No issue                                                            |

**Verdict:** Keep GPIO1/GPIO3. Hardware UART is more reliable for a
production perf board where you won't be serial-debugging anymore.
If you ever need debug logs, use `logger:` with `esp8266_store_log_strings_in_flash: false`
and view them over the network via `esphome logs --device barcode-scanner.local`.

### Flash-Safety Note

When flashing via USB, the GM67 TX line connected to GPIO3 (RX) can
interfere with the bootloader. Two options for the perf board:

1. **Solder a 2-pin header with a jumper** on the GM67 TX → GPIO3 line.
   Remove the jumper to flash, replace to run.
2. **Accept OTA-only updates** after the first flash (your config already
   has `ota:` enabled). This is the easier path for a finished device.

---

## 4. Wiring Diagram

```
                     NodeMCU v2
                 ┌──────────────────┐
           USB ──┤ VIN(5V)    3V3   ├──────────────────── OLED VCC (3.3V)
                 │                  │
                 ┤ GND        GND   ├──┬───────────────── OLED GND
                 │                  │  └───────────────── Button leg 2
                 ┤ TX (GPIO1) [TX]──├────────────────┐
                 │                  │                │
                 ┤ RX (GPIO3) [RX]──├──────────┐     │
                 │                  │          │     │
                 ┤ D1 (GPIO5) [SCL]─├──────────┼─────┼── OLED SCL
                 │                  │          │     │
                 ┤ D2 (GPIO4) [SDA]─├──────────┼─────┼── OLED SDA
                 │                  │          │     │
                 ┤ D7 (GPIO13)──────├──────────┼─────┼── Button leg 1
                 │                  │          │     │
                 ┤ ...              ├          │     │
                 └──────────────────┘          │     │
                                               │     │
                       GM67 Breakout           │     │
                 ┌──────────────────┐          │     │
                 │  ┌────┐  ┌────┐  │          │     │
                 │  │USB │  │UART│  │          │     │
                 │  └────┘  └────┘  │          │     │
                 │                  │          │     │
    NodeMCU GND──├─ GND        TX ──├──────────┘     │
                 │                  │                │
    NodeMCU 5V───├─ VCC(5V)    RX ──├────────────────┘
                 │   │              │
                 └───┼──────────────┘
                     │
               ┌─────┴──────┐
               │ Decoupling │
               │            │
               │ C1: 100nF  │  ceramic, across VCC-GND
               │ C2: 470µF  │  electrolytic, across VCC-GND
               │     10V    │
               └─────┬──────┘
                     │
                    GND
```

### Wire-by-Wire

| Wire | From                   | To              | Color Suggestion | Notes                                    |
| ---- | ---------------------- | --------------- | ---------------- | ---------------------------------------- |
| 1    | NodeMCU **VIN/5V**     | GM67 **VCC**    | Red              | 5V power to breakout                     |
| 2    | NodeMCU **GND**        | GM67 **GND**    | Black            | Common ground — mandatory                |
| 3    | NodeMCU **TX** (GPIO1) | GM67 **RX**     | Yellow           | ESP sends commands to scanner            |
| 4    | NodeMCU **RX** (GPIO3) | GM67 **TX**     | Green            | Scanner sends barcodes to ESP            |
| 5    | NodeMCU **3V3**        | OLED **VCC**    | Red              | 3.3V power to OLED                       |
| 6    | NodeMCU **GND**        | OLED **GND**    | Black            | OLED ground                              |
| 7    | NodeMCU **D1** (GPIO5) | OLED **SCL**    | Blue             | I2C clock                                |
| 8    | NodeMCU **D2** (GPIO4) | OLED **SDA**    | White            | I2C data                                 |
| 9    | NodeMCU **D7** (GPIO13)| Button **leg 1**| Orange           | Internal pull-up, active-low             |
| 10   | NodeMCU **GND**        | Button **leg 2**| Black            | Button completes circuit to GND on press |

> **OLED pull-ups**: No external resistors needed — the SSD1306 breakout has them onboard.
>
> **Button**: No external resistor needed — `INPUT_PULLUP` uses the ESP8266's internal pull-up.

> **TX↔RX crossover**: ESP TX goes to GM67 RX and vice versa. This is standard
> for UART but a common wiring mistake. If you get no data, swap wires 3 & 4.

---

## 5. Perf Board Layout Suggestions

```
    ┌───────────────────────────────────────────┐
    │  ┌──────────────┐         ┌────────────┐  │
    │  │  NodeMCU v2  │         │   GM67     │  │
    │  │  (pin hdrs)  │  wires  │  breakout  │  │
    │  │              ├────────►│            │  │
    │  │              │         │            │  │
    │  │    D1,D2─────┼────┐    └─────┬──────┘  │
    │  │    D7────────┼──┐ │          │         │
    │  └──────┬───────┘  │ │     ┌────┴────┐    │
    │         │          │ │     │ C1 + C2 │    │
    │     ┌───┴───┐    [BTN]│    └─────────┘    │
    │     │USB out│      │ │                    │
    │     └───────┘      │ └──[OLED 0.96"]      │
    │                    │                      │
    └───────────────────────────────────────────┘
```

- Place **C1 and C2 directly adjacent to the GM67 power pins** — short traces/wires minimize inductance
- Keep UART wires short and away from the USB connector / WiFi antenna area
- Place **OLED** on the enclosure-facing side for visibility
- Place **button** accessible from outside the enclosure
- The NodeMCU's USB port should remain accessible (for power and emergency re-flash)
- Consider a **2-pin jumper header** on the GM67 TX → GPIO3 line for flash safety

---

## 6. Bill of Materials

| #   | Component                          | Qty | Notes                                   |
| --- | ---------------------------------- | --- | --------------------------------------- |
| 1   | NodeMCU v2 (ESP8266)               | 1   | With pin headers soldered               |
| 2   | GM67 barcode scanner breakout      | 1   | 5V input, 4-wire UART                   |
| 3   | Ceramic capacitor 100 nF           | 1   | Through-hole or 0805 SMD                |
| 4   | Electrolytic capacitor 470 µF, 10V | 1   | Low ESR preferred, through-hole         |
| 5   | Perf board / prototype board       | 1   | ~5×7cm or to fit your enclosure         |
| 6   | Pin headers (male + female)        | 1   | For socketing the NodeMCU               |
| 7   | 2-pin header + jumper (optional)   | 1   | Flash safety disconnect on GM67 TX line |
| 8   | Hook-up wire (24-26 AWG)           | —   | 4 connections, keep short               |
| 9   | USB cable (good quality, short)    | 1   | 24 AWG power lines minimum              |

---

## 7. Troubleshooting Checklist

| Symptom                            | Likely Cause                       | Fix                                           |
| ---------------------------------- | ---------------------------------- | --------------------------------------------- |
| ESP resets when scanner fires      | 5V rail sag → brownout             | Add/increase C2; use better USB cable         |
| No barcode data received           | TX/RX swapped                      | Swap wires on GPIO1↔GPIO3                     |
| Garbage characters                 | Baud rate mismatch                 | Verify GM67 is set to 9600 baud               |
| Can't flash via USB                | GM67 TX driving GPIO3 during flash | Disconnect GM67 TX; use OTA after first flash |
| WiFi keeps disconnecting           | Shared 5V rail sag                 | Bigger bulk cap; better USB power source      |
| Scanner LED doesn't turn on        | Insufficient USB current           | Use a phone charger (2A+), not a PC USB port  |
| Works on bench, fails in enclosure | Overheating (poor ventilation)     | Add vent holes to 3D-printed case             |
