# SkolDisplay

A Minnesota Vikings badge app for the **Workday DevCon 2026 DevKit** — a
Pimoroni Blinky 2350 conference badge with a 39×26 monochrome LED matrix.

See [`docs/DEVICE_SPECS.md`](docs/DEVICE_SPECS.md) for full hardware specs
and the on-device "badgeware" app framework this project targets.

## Status: working, tested live on hardware (2026-10-01)

Three states in `apps/skol_display/__init__.py`:

1. **Vikings playing** — scrolls the live score and quarter/clock (e.g.
   `MIN 17  -  GB 14   Q3 8:42`), polled every 30s from ESPN's public team
   endpoint (`https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/min`,
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

## Deploying

- `/rom/apps/...` is factory firmware, read-only at the MicroPython level.
- `/system/apps/...` is what the on-device menu/launcher
  (`/rom/utils/gatekeeper.py`) actually scans for user apps — but it's
  **also read-only from the REPL** (`OSError 30`, confirmed live). It's
  presumably writable via the badge's USB mass-storage mode
  (`rp2.enable_msc()`) for drag-and-drop deployment from a host, but that
  path hasn't been exercised yet.
- `/` (root) **is** writable from the REPL, and isn't recognized by the
  menu/gatekeeper — but `badgeware.launch(path)` can run an app from any
  path directly, bypassing the menu. That's how this app has been
  deployed and tested so far:

  ```python
  # over the serial REPL, raw-REPL mode (Ctrl-A), after writing the file
  # to /apps/skol_display/__init__.py:
  import badgeware
  badgeware.launch("/apps/skol_display")
  ```

  This is a fine dev loop but isn't "real" end-user deployment — to make
  the app show up in the badge's own menu, it needs to land in
  `/system/apps/skol_display/`, which likely means the MSC drag-and-drop
  flow (untested).

## Hardware access notes

- `/dev/ttyACM0` is owned by `root:uucp` by default; run
  `sudo chmod 666 /dev/ttyACM0` per session (or add your user to `uucp`
  permanently: `sudo usermod -aG uucp $USER`, then re-login).
- Also run `stty -F /dev/ttyACM0 115200 raw -echo cs8 -cstopb -parenb -hupcl clocal`
  before opening the port. The `-hupcl` matters: without it, closing the
  serial connection drops DTR and resets the board — this caused the badge
  to repeatedly re-enumerate mid-session until it was found.
