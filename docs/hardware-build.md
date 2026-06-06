# Hardware Build Guide

This guide covers the complete hardware build for the barcode scanner unit. The scanner is built around an ESP32 microcontroller, a GM67 barcode scanner module, a small OLED display, and a push button — all soldered onto a perf board and housed in a 3D-printed enclosure.

## Parts List

| #  | Component                          | Qty | Notes                                                |
| -- | ---------------------------------- | --- | ---------------------------------------------------- |
| 1  | ESP-WROOM-32 (28-pin devkit)       | 1   | Dx-labeled pins; with pin headers                    |
| 2  | GM67 barcode scanner breakout      | 1   | 5V input, 4-wire UART header                         |
| 3  | SSD1306 OLED 128×64 I2C            | 1   | 0.96", I2C address 0x3C                              |
| 4  | Momentary push button (NO)         | 1   | For display wake / status                            |
| 5  | Ceramic capacitor 100 nF           | 2   | One for GM67 decoupling, one for EN pin              |
| 6  | Electrolytic capacitor 470 µF 10V  | 1   | Low ESR preferred, through-hole                      |
| 7  | Resistor 10 kΩ                     | 1   | Pull-up for EN pin (if not already on your board)    |
| 8  | Perf board / prototype board       | 1   | ~5×7 cm or sized to your enclosure                   |
| 9  | Pin headers (male + female)        | 1   | For socketing the ESP32 (removable)                  |
| 10 | Hook-up wire (24–26 AWG)           | —   | Short runs between components                        |
| 11 | USB cable (good quality, short)    | 1   | 24 AWG power lines minimum — cheap cables cause sag  |

> **Total cost:** ~$15–20 from AliExpress/Amazon, depending on what you already have.

---

## Pin Mapping

| Device     | ESP32 Pin       | Board Label | Function               |
| ---------- | --------------- | ----------- | ---------------------- |
| GM67 TX    | GPIO16          | D16         | UART2 RX (from scanner)|
| GM67 RX    | GPIO17          | D17         | UART2 TX (to scanner)  |
| OLED SDA   | GPIO21          | D21         | I2C data               |
| OLED SCL   | GPIO22          | D22         | I2C clock              |
| Button     | GPIO25          | D25         | Active-low, pull-up    |

All five GPIOs are free from ESP32 strapping pin conflicts — they won't interfere with boot mode.

### Strapping Pins to Avoid

| Pin    | Why                              |
| ------ | -------------------------------- |
| GPIO0  | Boot mode select — don't use     |
| GPIO2  | Must be LOW/floating at boot     |
| GPIO5  | VSPI CS — must be HIGH at boot   |
| GPIO12 | Voltage select — HIGH can brick  |
| GPIO15 | Must be HIGH at boot             |

---

## Logic Levels — No Level Shifter Needed

| Device               | Supply | UART Logic | Notes                              |
| -------------------- | ------ | ---------- | ---------------------------------- |
| ESP32 (ESP-WROOM-32) | 3.3 V  | 3.3 V TTL  | GPIOs are **not** 5 V tolerant     |
| GM67 breakout        | 5 V in | 3.3 V TTL  | Internal engine runs at 3.3 V      |

The GM67's TX/RX signals are 3.3 V regardless of whether the breakout board is powered from 5 V or 3.3 V. **Direct connection to the ESP32 is safe.** No level shifter, no voltage divider.

---

## Power Design

### Dual-Rail Strategy

The ESP32 and GM67 each have their own voltage regulator. Both draw from the shared USB 5 V rail, but their 3.3 V sides are independent:

```
USB 5V ──┬──► [ESP32 AMS1117-3.3] ──► 3.3V ──► ESP32 core + OLED
         │
         └──► GM67 VCC (5V) ──► [GM67 onboard reg] ──► 3.3V scanner engine
```

**Both GND rails must be connected** (common ground).

### Why This Matters

The GM67 draws up to 350 mA when the illumination LED and aiming laser fire simultaneously. If this current flowed through the ESP32's regulator, it would cause voltage sag → WiFi dropouts or brownout resets. By wiring the GM67 directly to 5 V, its current stays off the ESP32's regulator entirely.

### Decoupling Capacitors

Place these **as close to the GM67 VCC/GND pins as possible**:

| Capacitor    | Value       | Purpose                                    |
| ------------ | ----------- | ------------------------------------------ |
| C1 (ceramic) | 100 nF      | High-frequency switching noise suppression |
| C2 (bulk)    | 470 µF 10 V | Absorbs the ~350 mA inrush when scanner fires |

The 470 µF bulk cap is the single most important passive component. Without it, the GM67's current spike can pull the USB 5 V rail low enough to brownout the ESP32 — even with separate regulators, because they share the same 5 V input.

> **If your ESP reboots every time you scan a barcode**, this cap is the fix. Also check your USB cable — thin/long cables have too much resistance.

### Power Budget

| Consumer                      | Typical | Peak     |
| ----------------------------- | ------- | -------- |
| ESP32 (WiFi active)           | ~120 mA | ~500 mA  |
| GM67 (idle / IR sensing)      | ~55 mA  | ~60 mA   |
| GM67 (active scan: LED+laser) | ~200 mA | ~350 mA  |
| **Combined worst case**       |         | **~850 mA** |

Use a USB power source rated for at least 1 A. A phone charger (2 A+) works well. Avoid unpowered USB hubs and PC USB 2.0 ports (500 mA limit).

---

## EN Pin Stability

Many cheap ESP32 devkit boards (especially the 28-pin Dx-labeled ones from AliExpress) have a **weak or missing pull-up on the EN (enable) pin**. Symptoms:

- Random resets during operation
- Won't boot after power cycle
- Enters download mode unexpectedly

**Fix:** Solder a 10 kΩ resistor from EN → 3.3 V and a 100 nF capacitor from EN → GND, as close to the EN pin as possible.

| Component    | Value  | Connection    | Purpose                  |
| ------------ | ------ | ------------- | ------------------------ |
| R_EN         | 10 kΩ  | EN → 3V3      | Holds EN high            |
| C_EN         | 100 nF | EN → GND      | Filters noise glitches   |

> If your board boots reliably without these, skip them. But if you see random resets, this is almost always the fix.

---

## Wiring Diagram

```
               ESP-WROOM-32 (28-pin, Dx labels)
                 ┌──────────────────┐
           USB ──┤ VIN(5V)    3V3   ├──────────────────── OLED VCC (3.3V)
                 │                  │
                 ┤ GND        GND   ├──┬───────────────── OLED GND
                 │                  │  └───────────────── Button leg 2
                 ┤ D17/GPIO17 [TX2]─├────────────────┐
                 │                  │                │
                 ┤ D16/GPIO16 [RX2]─├──────────┐     │
                 │                  │          │     │
                 ┤ D22/GPIO22 [SCL]─├──────────┼─────┼── OLED SCL
                 │                  │          │     │
                 ┤ D21/GPIO21 [SDA]─├──────────┼─────┼── OLED SDA
                 │                  │          │     │
                 ┤ D25/GPIO25───────├──────────┼─────┼── Button leg 1
                 │                  │          │     │
                 ┤ EN ──[10kΩ]──3V3 │          │     │
                 │  └──[100nF]──GND │          │     │
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
    ESP32 GND────├─ GND        TX ──├──────────┘     │
                 │                  │                │
    ESP32 5V─────├─ VCC(5V)    RX ──├────────────────┘
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

### Wire-by-Wire Checklist

| # | From                       | To               | Color  | Notes                                    |
| - | -------------------------- | ---------------- | ------ | ---------------------------------------- |
| 1 | ESP32 **VIN/5V**           | GM67 **VCC**     | Red    | 5V power to breakout                     |
| 2 | ESP32 **GND**              | GM67 **GND**     | Black  | Common ground — mandatory                |
| 3 | ESP32 **D17/GPIO17** (TX2) | GM67 **RX**      | Yellow | ESP sends commands to scanner            |
| 4 | ESP32 **D16/GPIO16** (RX2) | GM67 **TX**      | Green  | Scanner sends barcodes to ESP            |
| 5 | ESP32 **3V3**              | OLED **VCC**     | Red    | 3.3V power to OLED                       |
| 6 | ESP32 **GND**              | OLED **GND**     | Black  | OLED ground                              |
| 7 | ESP32 **D22/GPIO22**       | OLED **SCL**     | Blue   | I2C clock                                |
| 8 | ESP32 **D21/GPIO21**       | OLED **SDA**     | White  | I2C data                                 |
| 9 | ESP32 **D25/GPIO25**       | Button **leg 1** | Orange | Internal pull-up, active-low             |
| 10| ESP32 **GND**              | Button **leg 2** | Black  | Button connects GPIO25 to GND on press   |

> **No external pull-ups needed** — the SSD1306 breakout has I2C pull-ups onboard, and the button uses the ESP32's internal pull-up (~45 kΩ).

> **TX↔RX crossover**: ESP TX goes to GM67 RX, and vice versa. This is standard UART wiring but a common mistake. If you get no data, swap wires 3 & 4.

---

## Perf Board Layout

```
    ┌───────────────────────────────────────────┐
    │  ┌──────────────┐         ┌────────────┐  │
    │  │ ESP-WROOM-32 │         │   GM67     │  │
    │  │  (28-pin)    │  wires  │  breakout  │  │
    │  │              ├────────►│            │  │
    │  │              │         │            │  │
    │  │  D22,D21─────┼────┐    └─────┬──────┘  │
    │  │  D25─────────┼──┐ │          │         │
    │  └──────┬───────┘  │ │     ┌────┴────┐    │
    │         │          │ │     │ C1 + C2 │    │
    │     ┌───┴───┐    [BTN]│    └─────────┘    │
    │     │USB out│      │ │                    │
    │     └───────┘      │ └──[OLED 0.96"]      │
    │                    │                      │
    │  [R_EN + C_EN near EN pin]                │
    │                                           │
    └───────────────────────────────────────────┘
```

**Tips:**
- Place **C1 and C2** directly adjacent to the GM67 VCC/GND pins — short traces minimize inductance
- Place **R_EN + C_EN** as close to the EN pin as possible
- Keep UART wires short and away from the USB connector and WiFi antenna
- Mount the **OLED** on the enclosure-facing side for visibility through a window
- Mount the **button** where it's accessible from outside the enclosure
- Keep the ESP32's **USB port accessible** for power input and emergency re-flash
- Consider adding **ventilation holes** to the enclosure — the ESP32 generates heat under sustained WiFi use
