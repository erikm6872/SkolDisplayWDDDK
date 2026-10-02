# SkolDisplay

A Minnesota Vikings badge app for the **Workday DevCon 2026 DevKit** — a
Pimoroni Blinky 2350 conference badge with a 39×26 LED matrix.

See [`docs/DEVICE_SPECS.md`](docs/DEVICE_SPECS.md) for full hardware specs
and the on-device "badgeware" app framework this project targets.

## What it does

Two states, chosen each frame by polling ESPN's game status every 30s:

1. **Vikings playing** — scrolls the live score (e.g. `MIN 17 - GB 14   Q3 8:42`).
2. **Vikings not playing** — cycles through three idle animations every 8s:
   a "SKOL" marquee, a pulsing purple/gold Viking helmet, and a scrolling
   purple/gold stripe wave.

Game data comes from ESPN's public team endpoint
(`https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/min`) —
no API key required. The response schema (`status.type.state`,
`status.period`/`displayClock`, `competitors[].team.abbreviation`/`.score`)
was verified by hand against the live endpoint on 2026-10-01.

## Status / open questions

Not yet tested on the physical badge — it went offline/reset mid-build.
Known assumptions to verify once the device is available again (see also
"Open / unconfirmed" in `docs/DEVICE_SPECS.md`):

- **WiFi**: the app checks `network.WLAN(network.STA_IF).isconnected()` but
  does **not** manage its own credentials — it assumes the badge's system
  software already has it on a network. If that's wrong, we'll need to add
  connection logic (likely reading from `/system/secrets.py` conventions, or
  a new `secrets.py` the app manages itself).
- **HTTPS via `urequests`**: untested on this firmware build.
- **Pixel font legibility**: the hand-drawn 3×5 font in
  `apps/skol_display/__init__.py` hasn't been seen on the real LED matrix.
- **Deploy path**: where user apps actually need to live for the launcher to
  pick them up (see Deploying below).

## Deploying

The badge enumerates as a MicroPython board over USB (`/dev/ttyACM0` on
Linux) and also supports a mass-storage mode (`rp2.enable_msc()`) for
drag-and-drop file copies. Options to push `apps/skol_display/` onto the
device:

- **mpremote** (not yet installed on this machine):
  `mpremote cp -r apps/skol_display :apps/skol_display`
  (confirm the writable app directory — only `/rom/apps/...` read-only paths
  were inspected so far; see "Open / unconfirmed" in the device specs doc)
- **Mass storage mode**: trigger `rp2.enable_msc()` from the REPL, then the
  badge should mount as a regular USB drive for drag-and-drop copying.

## Hardware access notes

`/dev/ttyACM0` is owned by `root:uucp` by default; either run
`sudo chmod 666 /dev/ttyACM0` per session, or add your user to the `uucp`
group (`sudo usermod -aG uucp $USER`, then re-login) for persistent access.

The badge appears to reset/re-enumerate periodically on its own (observed
during spec extraction) — reconnect if the serial port goes unresponsive.
