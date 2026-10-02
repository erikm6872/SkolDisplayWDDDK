# SkolDisplay

A Minnesota Vikings badge app for the **Workday DevCon 2026 DevKit** — a
Pimoroni Blinky 2350 conference badge with a 39×26 monochrome LED matrix.

See [`docs/DEVICE_SPECS.md`](docs/DEVICE_SPECS.md) for full hardware specs
and the on-device "badgeware" app framework this project targets.

## Status: working, deployed through the actual on-device menu (2026-10-01)

Three states in `apps/skol_display/__init__.py`:

1. **Vikings playing** — toggles between two static pages every 4s: team
   scores stacked two lines tall (e.g. `MIN 17` / `GB 14`), then the
   quarter/clock (e.g. `Q3 8:42`). No scrolling — a full score+clock line
   doesn't fit the 39px-wide screen in any available font, so it's split
   across pages instead of scrolled. Game data polled every 30s from ESPN's
   public team endpoint
   (`https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/min`,
   no API key needed).
2. **Not playing, animations off (default)** — static "SKOL" at medium
   brightness.
3. **Not playing, animations on** — cycles every 8s through a "SKOL"
   marquee, a pulsing Viking helmet, and a chase-light sweep.

Press **BUTTON_A** to toggle between states 2 and 3; the choice is
persisted via `badgeware.State` so it survives app restarts.

All three states, the WiFi retry path, and the button toggle have been
exercised live on the physical badge. Not yet tested: an actual live NFL
game (none was in progress during development — verified by mocking
`fetch_game_state()` to confirm the live-score rendering path instead; see
git history for that throwaway test harness).

## Confirmed quirks worth knowing

- **The display is monochrome** — white LEDs, brightness only, no hue. An
  earlier purple/gold color scheme was invisible on real hardware; see
  `docs/DEVICE_SPECS.md`.
- **Firmware bug**: when `wifi.connect()` fails (e.g. the saved access
  point isn't in range), the firmware's own `fatal_error()` handler crashes
  with `AttributeError: 'module' object has no attribute 'scroll'`. The app
  catches this (see `_pump_wifi()`), throttled to one retry per 15s.
- **`screen.measure_text()` returns `(width, height)`**, not a bare width —
  easy to get wrong (it crashed the first version).
- Vertical centering of `screen.text()` needed a small empirical nudge
  beyond the math — see the `TEXT_Y` comment in the app.
- **The display only flips once per completed `update()` call.** Drawing a
  status message and then blocking (e.g. a network call) in the *same*
  `update()` call never actually shows it — the frame never gets flushed
  before the blocking call runs out the clock. The app's "SYNC" status
  (shown before polling for a score) has to be drawn on one frame that
  returns immediately, with the actual blocking fetch deferred to the next
  frame — see the `_poll_pending` state machine in the app.
- **Never use `machine.WDT` here.** Tested it as a hang-mitigation idea; an
  unfed watchdog survives a normal reset on this chip and keeps force-
  rebooting the device until a full physical power-cycle. It's also a
  chip-global resource, not scoped to one app — arming it in this app could
  cause a *different* app to mysteriously reboot later if nothing in that
  app ever feeds it. See `docs/DEVICE_SPECS.md`.
- **USB mass-storage ("Disk Mode") is not automatic** — it's a toggle in
  the badge's own on-device menu (via `BUTTON_HOME`), doesn't persist
  across resets, and needs re-enabling each time you want to copy files
  over. The host-side block device can also go stale (0 bytes, won't
  mount) after the badge resets mid-session — unplug/replug or re-toggle
  Disk Mode to recover.

## Deploying

### Real deployment: USB mass-storage drag-and-drop (confirmed working)

Enable "Disk Mode" from the badge's own menu first (hold/press
`BUTTON_HOME`) — it's not automatic and doesn't persist across resets. Once
enabled, the badge exposes a USB mass-storage drive (labeled `BLINKY`)
alongside its serial REPL (e.g. `/run/media/$USER/BLINKY` on Linux). The
drive's root **is** `/system` on the device:
`BLINKY/apps/<name>/` = `/system/apps/<name>/`, which is exactly what
`/rom/utils/gatekeeper.py` (`SYSTEM_APPS_DIR`) scans for user apps — this
is the real deploy path, confirmed end-to-end:

1. Copy the app folder onto the drive: `cp -r apps/skol_display /path/to/BLINKY/apps/`
2. **Include `icon.png`** (24×24, transparency supported) — this isn't
   optional polish. `/rom/apps/menu/app.py`'s `Apps.__init__` only adds a
   folder to the menu at all if `icon.png` exists alongside `__init__.py`;
   without it the app is silently invisible, not just icon-less. Confirmed
   live: deploying without an icon left the app completely absent from the
   menu, with no error anywhere.
3. Unmount/eject the drive properly (`udisksctl unmount` or your OS's
   eject), then reboot the badge (physical reset, or `machine.reset()` over
   the REPL) — the on-device menu builds its app list once at menu startup,
   so changes made via USB while the menu was already running won't appear
   until it restarts.

### Dev-loop shortcut: `badgeware.launch()` over the REPL

For fast iteration without needing to eject/reboot each time,
`badgeware.launch(path)` can run an app from **any** path directly,
bypassing the menu entirely — this is how every change in this app's
history was tested before final menu deployment:

```python
# over the serial REPL, raw-REPL mode (Ctrl-A), after writing the file
# to /apps/skol_display/__init__.py (note: /apps at root, NOT /system/apps -
# root is writable from the REPL, /system is not, see DEVICE_SPECS.md):
import badgeware
badgeware.launch("/apps/skol_display")
```

## Hardware access notes

- `/dev/ttyACM0` is owned by `root:uucp` by default. A udev rule fixes this
  permanently (confirmed working — see `docs/DEVICE_SPECS.md` for the exact
  rule and install commands); the one-off alternative is
  `sudo chmod 666 /dev/ttyACM0` after every re-enumeration.
- Also run `stty -F /dev/ttyACM0 115200 raw -echo cs8 -cstopb -parenb -hupcl clocal`
  before opening the port. The `-hupcl` matters: without it, closing the
  serial connection drops DTR and resets the board — this caused the badge
  to repeatedly re-enumerate mid-session until it was found.
