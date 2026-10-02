# SkolDisplay

A Python (MicroPython) app for the **Workday DevCon 2026 DevKit** — a
Pimoroni Blinky 2350 conference badge with a 39×26 LED matrix.

See [`docs/DEVICE_SPECS.md`](docs/DEVICE_SPECS.md) for full hardware specs
and the on-device "badgeware" app framework this project targets.

## Status

Starter scaffold: `apps/skol_display/__init__.py` draws a scrolling "SKOL"
marquee using the device's `screen` drawing API. Hand-rolled pixel glyphs are
used for now since the official `badgeware.text` font-rendering API
(`load_font`, `pen_glyph_renderer`) wasn't fully verified against this
firmware build before the badge went offline.

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
