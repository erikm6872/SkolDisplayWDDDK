# Workday DevCon 2026 DevKit — Pimoroni Blinky 2350

Hardware specs extracted directly from a physical unit via its MicroPython serial
REPL (USB CDC-ACM, `idVendor=0x2e8a` "Pimoroni", `idProduct=0x1102` "Pimoroni Blinky
2350 MicroPython"). Confirmed by probing `sys.implementation`, `os.uname()`,
`board`, `blinky.Blinky`, `badgeware.badge`, and the on-device `/rom` filesystem.

## Identity

- **Product**: Pimoroni Blinky 2350 — custom-branded as the Workday DevCon 2026
  conference badge / DevKit (fonts on device are named `WorkdayBody-*`, bundled
  apps include `keynote` and `innovation`).
- **Firmware**: custom MicroPython build `bw-1.27.0` ("badgeware"), built
  2026-05-08, GCC 13.3.1 MinSizeRel.
- `sys.implementation`: `name='micropython', version=(1,27,0,''), _machine='Pimoroni Blinky 2350 with RP2350', _build='blinky'`

## Core hardware

| Component | Detail |
|---|---|
| MCU | Raspberry Pi **RP2350** (dual Cortex-M33/Hazard3), running at 150 MHz (`machine.freq()`) |
| Wireless | Infineon **CYW43439** combo chip — WiFi (`network.WLAN` → class `CYW43`) + Bluetooth (`bluetooth.BLE`, `aioble`) |
| RAM | ~8.3 MB free heap at idle (`gc.mem_free()`) — RP2350's internal SRAM is only 520 KB, so this implies external QSPI PSRAM |
| Storage | Internal flash, partitioned into `/rom` (read-only firmware/apps/assets/fonts), `/system` (settings, `secrets.py`), `/state` (persisted JSON state), plus a writable user filesystem area (~1 MB: 256 × 4096-byte blocks per `os.statvfs('/')`) |
| USB | Composite device: CDC-ACM serial (REPL) + mass-storage mode (`rp2.enable_msc()` / `rp2.is_msc_busy()`) for drag-and-drop file access from a host |
| Unique ID | 8-byte `machine.unique_id()` per unit (e.g. `9a9318b04def6348` on the probed unit) |

## Display

- Custom **LED matrix**, resolution **39×26** (`blinky.Blinky.WIDTH/HEIGHT`); bundled
  apps reference it as `40×26` (`SCREEN_W, SCREEN_H = 40, 26`) — use 39×26 as the
  authoritative drawable area, treat 40 as an app-level off-by-one convention.
- Driven via shift-register pins, not a framebuffer bus: `DISPLAY_ROW_CLK`,
  `DISPLAY_ROW_DATA`, `DISPLAY_COL_CLK`, `DISPLAY_COL_DATA`, `DISPLAY_COL_LATCH`,
  `DISPLAY_COL_BLANK` (all exposed on the `board` module).
- Has a `LORES` display mode constant (set via `badge.mode(LORES)` before drawing);
  a `HIRES` constant likely also exists (unconfirmed).
- Brightness is controllable via `blinky.Blinky` (`set_brightness`,
  `get_brightness`, `adjust_brightness`).

## Input

- Buttons (all exposed as `board` pins / global constants in apps):
  `BUTTON_A`, `BUTTON_B`, `BUTTON_C`, `BUTTON_UP`, `BUTTON_DOWN`, `BUTTON_HOME`,
  `BUTTON_INT`, `BUTTON_RESET`.
- `badge.pressed(btn)`, `badge.held(btn)`, `badge.released(btn)`, `badge.changed()`,
  `badge.poll()` drive the input state machine each frame.

## IR (badge-to-badge)

- Dedicated `IR_TX` / `IR_RX` GPIO pins.
- A full IR protocol stack ships on-device under `aye_arr` (NEC protocol send/receive,
  common remote descriptor tables, PIO-based pulse TX/RX) — this is how badges
  likely exchange data with each other, DEF-CON-badge style.

## Power / battery

- LiPo battery management: `BAT_MAX = 4.1V`, `BAT_MIN = 3.0V`.
- Sense/control pins: `VBAT_SENSE`, `SENSE_1V1` (ADC reference), `CHARGE_STAT`,
  `VBUS_DETECT`, `POWER_EN`.
- `badgeware.badge.Badge` API: `battery_level()`, `battery_voltage()`,
  `is_charging()`, `usb_connected()`, `light_level()` (has an onboard light sensor),
  `sleep()`, `pressed_to_wake`, `wake_reason()`, `woken_by_button()`,
  `woken_by_reset()`.

## RTC

- External RTC chip (PCF85063A driver bundled: `pcf85063a`), plus `RTC_ALARM` pin
  for wake-from-sleep scheduling. `badgeware.rtc` module present.

## I2C / expansion

- `I2C_SCL` / `I2C_SDA` exposed on `board`.
- A large set of Pimoroni "Breakout Garden"-style sensor drivers ship on-device
  (`breakout_bme280`, `breakout_bme68x`, `breakout_vl53l5cx`, `breakout_paa5100`,
  `breakout_msa301`, `breakout_sgp30`, `breakout_scd41`, `breakout_rgbmatrix5x5`,
  `breakout_trackball`, `breakout_potentiometer`, `breakout_encoder`,
  `breakout_ioexpander`, `qwstpad`, etc.) — strongly implies a physical
  Breakout Garden / Qw-ST style expansion connector on the board, even if not
  every sensor ships with the badge itself.

## Fonts / text rendering

- `badgeware.text` module: `load_font()`, `pen_glyph_renderer`, `ROMFonts`.
- On-device fonts in `/rom/fonts/`: Workday's own brand font in 4 weights
  (`WorkdayBody-Regular/Bold/Italic/BoldItalic.af`), plus ~35 pixel/bitmap fonts
  in `.ppf` format (Pimoroni PicoGraphics-style proportional pixel fonts) with
  playful names (`badgeware.ppf`, `corset.ppf`, `troll.ppf`, `yolk.ppf`, etc.).

## Software architecture ("badgeware")

- `/rom/main.py` is the boot entry point / launcher. It: puts `/rom` on
  `sys.path`, drains stray wake-button presses, starts a background
  `services.ble_repeater`, shows an intro animation (gated by boot count /
  skip-once state in `/state/intro_animation.json`), determines the first app to
  launch via `utils.gatekeeper`, then calls the global `launch()` function, and
  finally `reset()`s back to the loader when an app exits.
- **Apps** live as folders under `/rom/apps/<name>/__init__.py` (+ optional
  `icon.png`). Bundled apps: `achievement_locker`, `innovation`, `intro_animation`,
  `keynote`, `konami`, `menu`.
- Each app module executes with these **globals pre-injected** by the launcher
  (confirmed by reading the bundled `konami` app source):
  - `badge` — the `Badge` singleton (input polling, battery, sleep, etc.)
  - `screen` — drawing surface: `screen.pen = color.rgb(r, g, b, a=255)`,
    `screen.clear()`, `screen.rectangle(x, y, w, h)`
  - `color` — `color.rgb(...)` helper
  - Button constants: `BUTTON_A/B/C/UP/DOWN/HOME/...`
  - Display mode constants: `LORES` (and presumably `HIRES`)
  - `run(update_fn)` — blocking main-loop driver; calls `update_fn()` every
    frame until the app exits, then hands control back to the launcher
  - `badgeware.State.load(name, default_dict)` / `State.modify(name, dict)` —
    persists small JSON state blobs to `/state/<name>.json`
- A separate `_msc` service runs concurrently to serve the mass-storage USB mode
  and periodically updates "caselights"; it shows up in tracebacks when a REPL
  `Ctrl-C` interrupts it mid-update — harmless.

## Open / unconfirmed

- Exact flash chip total size (only the ~1 MB writable partition size was
  measured; firmware/`/rom` likely lives in a separate larger flash region).
- Whether a physical Breakout Garden connector is populated on this specific
  badge PCB vs. the drivers just being included generically in the firmware
  image.
- Whether `HIRES` mode exists and what resolution/color depth it offers.
- Where **user-written** apps are expected to live for the launcher to pick
  them up (only `/rom/apps/...` was inspected; there may be a writable
  `/apps` location — worth checking via `os.listdir('/')` → look for an `apps`
  entry alongside `rom`/`system`/`state`, or Pimoroni's own badge docs/repo if
  this ships as open source).

## How this was gathered

Via a live serial REPL session over `/dev/ttyACM0` (115200 8N1), using raw
`stty` + shell `exec 3<>/dev/ttyACM0` round-trips. No vendor documentation was
found publicly for this device as of 2026-10-01 — Workday/Pimoroni does not
appear to have published specs online, so this file is the primary reference
for future work with this hardware.
