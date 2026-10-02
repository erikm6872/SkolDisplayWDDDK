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

- Custom **LED matrix**, resolution **39×26** (`blinky.Blinky.WIDTH/HEIGHT`, also
  exposed at runtime as `screen.width`/`screen.height`); bundled apps reference it
  as `40×26` (`SCREEN_W, SCREEN_H = 40, 26`) — use 39×26 as the authoritative
  drawable area, treat 40 as an app-level off-by-one convention.
- **Monochrome** — white LEDs, variable brightness only, no hue. Confirmed by
  building a purple/gold color-themed app and finding it visually indistinguishable
  on the real hardware; brightness contrast (e.g. `color.white` vs a dim
  `color.rgb(50,50,50)` vs `color.black`) is what actually reads. `color.rgb()`
  presumably gets converted to a single luminance/brightness value internally.
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
- **Apps** live as folders under `<dir>/<name>/__init__.py` (+ optional
  `icon.png`). Two app roots, per `/rom/utils/gatekeeper.py`:
  - `APPS_DIR = "/rom/apps"` — factory apps, allow-listed by name
    (`menu`, `innovation`, `intro_animation`, `achievement_locker`, `konami`).
  - `SYSTEM_APPS_DIR = "/system/apps"` — meant to be the user-app location
    (gatekeeper allows anything here unconditionally) and ships with several
    example apps: `demos`, `tutorial`, `games`, `logo`, `helloworld`, `weather`,
    `doomface`. **`helloworld` and `weather` are the best real-world reference
    apps** — read them before writing a new one.
- Each app module executes with these **globals pre-injected** by the launcher
  (confirmed by reading `konami`, `helloworld`, `weather`, and by introspecting
  `dir()` on each live on real hardware):
  - `badge` — the `Badge` singleton. Key members: `.ticks` (monotonically
    increasing ms counter, read fresh each frame — this is how apps do timing,
    *not* `time.ticks_ms()`), `.pressed(BTN)`/`.held(BTN)`/`.released(BTN)`,
    `.battery_level()`, `.battery_voltage()`, `.is_charging()`,
    `.usb_connected()`, `.light_level()`, `.sleep()`, `.uid`, `.model`.
  - `screen` — drawing surface. Confirmed methods: `.text(str, x, y)` (draws
    in the currently-selected `.font`), `.measure_text(str)` → **`(width,
    height)` tuple of floats** (not a bare width — easy to get wrong),
    `.font` (settable, see `rom_font` below), `.pen` (settable color),
    `.clear()`, `.circle(cx, cy, r)`, `.line(x0, y0, x1, y1)`,
    `.rectangle(x, y, w, h)`, `.triangle(...)`, `.put(x, y)` (single pixel),
    `.shape(shape_obj)` (draws a shape built via the `shape` global),
    `.width`/`.height`, plus `.blit*`, `.blur`, `.dither`, `.clip`, `.window`,
    `.load`/`.load_into` (images), `.batch`, `.alpha`, `.antialias`.
  - `shape` — shape-object factory for use with `screen.shape(...)`:
    `.circle`, `.rectangle`, `.rounded_rectangle`, `.squircle`, `.arc`, `.pie`,
    `.line`, `.star`, `.regular_polygon`, `.stroke`, `.custom`.
  - `color` — `.rgb(r, g, b)` plus named constants: `.black`, `.white`, `.red`,
    `.green`, `.blue`, `.yellow`, `.orange`, `.cyan`, `.navy`, `.lime`,
    `.grey`/`.light_grey`/`.dark_grey`, `.brown`, `.grape`, `.latte`, `.smoke`,
    `.taupe`, `.transparent`, plus `.hsv`/`.oklch` constructors. (Remember:
    hardware is monochrome, so only brightness matters, not hue.)
  - `rom_font` — one attribute per on-device font (minus the Workday ones),
    e.g. `rom_font.smart`, `rom_font.ark`, `rom_font.desert`. Assign to
    `screen.font` before drawing text. Measured glyph heights vary a lot by
    font — e.g. `smart` is 16px tall, `desert` is only 10px (useful for
    fitting a second line of text on the 26px-tall screen).
  - Button constants: `BUTTON_A/B/C`, plus (seen on `board`, not confirmed
    injected into every app) `UP/DOWN/HOME/INT/RESET`.
  - Display mode constants: `LORES` (and presumably `HIRES`, unconfirmed).
  - `run(update_fn)` — blocking main-loop driver; calls `update_fn()` every
    frame until the app exits, then hands control back to the launcher.
  - `fatal_error` — the launcher's crash handler. **Has a bug on this
    firmware build (`bw-1.27.0`)**: calling it (e.g. indirectly, by letting
    `wifi.tick()`/`wifi.connect()` fail) raises
    `AttributeError: 'module' object has no attribute 'scroll'` instead of
    showing the intended error screen. Catch exceptions around anything that
    might invoke it rather than letting it propagate.
- `wifi` — a plain **importable** module (not injected), confirmed via
  `import wifi; dir(wifi)`: `.connect()`, `.disconnect()`, `.is_connected()`,
  `.tick()` (non-blocking pump, call every frame), `.get_status()`/`.status`,
  `.ip`/`.ipv4`/`.ipv6`/`.gateway`/`.subnet`/`.nameserver`, `.wlan` (the
  underlying `network.WLAN`), `.secrets` (reads `/system/secrets.py`
  automatically — the `weather` example app never touches secrets itself,
  just calls `wifi.connect()`). On this unit, `/system/secrets.py` has at
  least one saved access point, `"McLaughlin"` — `wifi.connect()` fails with
  `"Access point McLaughlin not found"` when out of range, which triggers the
  `fatal_error` bug above.
- `badgeware.State.load(name, default_dict)` / `State.modify(name, dict)` —
  persists small JSON state blobs to `/state/<name>.json`. `load` mutates the
  passed dict in place with any persisted values.
- `badgeware.launch(path)` — **callable directly from the REPL** (not just
  internally by the menu), e.g. `import badgeware; badgeware.launch("/apps/skol_display")`.
  This is the key to iterating on an app without needing the MSC/drag-and-drop
  deploy path: write the app to a writable location and launch it directly,
  bypassing the menu/gatekeeper entirely.
- **`icon.png` is required for an app to appear in the menu at all** — not
  just cosmetic. `/rom/apps/menu/app.py`'s `Apps.__init__` only constructs a
  menu entry for a folder if `icon.png` exists alongside `__init__.py`
  (`if is_dir(...) and file_exists(f"{root}/{folder}/icon.png")`); apps
  missing it are silently absent from the menu — no error, no placeholder,
  nothing. Confirmed live: an app deployed via MSC without an icon never
  appeared. Icons are blitted into a 24×24 rect
  (`screen.blit(self.icon, rect(..., 24*scale, 24*scale))`) and support
  alpha (the menu fades the icon out via `.alpha` during launch animation),
  so a 24×24 RGBA PNG is the right format.
- A separate `_msc` service runs concurrently to serve the mass-storage USB mode
  and periodically updates "caselights"; it shows up in tracebacks when a REPL
  `Ctrl-C` interrupts it mid-update — harmless.

## Filesystem write permissions (confirmed live, 2026-10-01)

- `/rom/...` — **read-only**, confirmed (`os.mkdir` under it raises
  `AttributeError: 'VfsRom' object has no attribute 'mkdir'`).
- `/system/...` (including `/system/apps/...`, despite gatekeeper.py's own
  comment calling it "user-writable") — **read-only at the MicroPython
  runtime level**, confirmed (`OSError: 30` / EROFS on both `mkdir` and
  plain file `open(..., 'w')`), even though `os.statvfs('/system')` reports
  plenty of free space. It **is** writable via USB mass-storage — confirmed
  end-to-end on 2026-10-01. The badge exposes a mass-storage drive (labeled
  `BLINKY`, ~13MB, vfat) automatically whenever it's plugged in, with no
  `rp2.enable_msc()` call needed — it runs concurrently alongside the serial
  CDC-ACM REPL as part of the normal composite USB device (3 interfaces).
  The drive's root **is** `/system`: `BLINKY/apps/<name>/` ≡
  `/system/apps/<name>/`, `BLINKY/secrets.py` ≡ `/system/secrets.py`, etc.
  Writes made this way are visible to the device's own runtime (`os.listdir`)
  immediately after unmount, no reboot needed to be *seen* — but the
  **on-device menu caches its app list at menu startup**, so a reboot (or at
  least relaunching the menu app) is needed before a newly-added app
  actually appears in the menu UI.
- `/` (root) **is writable** from the REPL/runtime (`os.mkdir('/apps')`
  succeeded) — but the gatekeeper/menu doesn't look here, so anything placed
  under `/apps/...` won't show up in the on-device menu. It's reachable only
  via `badgeware.launch(path)` called directly. Total capacity ~1MB (256 ×
  4096-byte blocks, per `os.statvfs('/')`).

## Serial connection gotcha

Closing the `/dev/ttyACM0` file descriptor with default Linux termios
settings drops DTR, which **resets the board** (classic Arduino-style
auto-reset behavior) — this caused the badge to repeatedly re-enumerate
across separate tool invocations during development. Fix: `stty -F
/dev/ttyACM0 ... -hupcl clocal` before opening the port keeps the board
(and its running app) alive across disconnect/reconnect.

## Open / unconfirmed

- Exact flash chip total size (only the ~1 MB writable root partition size was
  measured; `/rom` and `/system` live in separate, larger, read-only-at-runtime
  flash regions of unknown size).
- Whether a physical Breakout Garden connector is populated on this specific
  badge PCB vs. the drivers just being included generically in the firmware
  image.
- Whether `HIRES` mode exists and what resolution/color depth it offers
  (moot given the display is confirmed monochrome, but the constant may
  still affect pixel addressing/resolution).
- Whether the MSC drive's "always on" behavior (no `rp2.enable_msc()` call
  needed) is true from a cold boot too, or only because this unit still had
  an in-progress REPL session each time it was tested.
- Whether unplugging the USB cable (full re-enumeration) is actually
  required to recover a "stuck" MSC block device after `machine.reset()`,
  or whether there's a software-only fix — observed the host's block device
  report size 0 after a REPL-triggered reset until the cable was physically
  replugged.

## How this was gathered

Via a live serial REPL session over `/dev/ttyACM0` (115200 8N1), using raw
`stty` + shell `exec 3<>/dev/ttyACM0` round-trips. No vendor documentation was
found publicly for this device as of 2026-10-01 — Workday/Pimoroni does not
appear to have published specs online, so this file is the primary reference
for future work with this hardware.
