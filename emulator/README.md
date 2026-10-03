# SkolDisplay emulator

Runs `apps/skol_display/__init__.py` (the real, unmodified app source)
against stubbed badge globals and device-only modules, for development
without needing the physical badge — built after repeated hardware hangs
made live iteration impractical (2026-10-02/03).

## Running

```
python3 emulator/server.py
```

Then open http://localhost:8765/ in a browser. The page shows the 39×26
LED matrix (rendered as dots), click-able `Button A/B/C`, and an
`Online/Offline` toggle to exercise both the connected and disconnected
code paths in the app. `urequests.get()` is wired to the real `requests`
library, so when "online," it hits the actual ESPN endpoint — this can
show real live score data, not just the mocked override used for earlier
on-device testing.

## How it works

- `sys_modules.py` installs fake `network`/`wifi`/`ntptime`/`badgeware`/
  `urequests` modules into `sys.modules` before the app is loaded, so its
  `import` statements resolve to these instead of erroring (desktop Python
  has none of these real modules). `badgeware.State` persists to
  `emulator/state/*.json`, mirroring `/state/*.json` on the real device.
- `stubs.py` provides the injected globals a real app module executes
  with (`screen`, `badge`, `color`, `rom_font`, `BUTTON_A/B/C`, `run`,
  `fatal_error`) — only what `apps/skol_display/__init__.py` actually
  uses (see that file's own docstring/comments for the confirmed real API
  surface; this doesn't attempt to cover the full device API).
- `server.py` reads the app's source, `exec`s it with those stubs (the
  same technique `badgeware.launch()` uses on the real device), captures
  the function passed to `run()`, and drives it in a loop on a background
  thread at `FRAME_HZ`. Each frame is rendered to a PNG and served over a
  tiny page that polls `/frame.png` + `/status` every 150ms.

## Fidelity — what's accurate vs. approximate

- **Exact**: `badge.ticks` timing, button edge-detection, the adaptive
  polling state machine, NTP-sync tracking, `badgeware.State` persistence,
  and — for the two strings this app actually needed exact layout for,
  `"SKOL"` and `"VIKINGS"` — text **width and height**, taken from real
  `screen.measure_text()` values measured live against all 37 `rom_font`
  entries (see `font_metrics.py`). The default-screen layout decision
  (which font, whether two lines fit, the near-edge-of-screen "VIKINGS"
  width) is trustworthy here because of that.
- **Approximate**: actual glyph *shapes*. We don't have the device's real
  `.ppf` bitmap font files, so text is rendered with a real system font
  (Hack Nerd Font Mono Bold) whose point size is iteratively fit so its
  *rendered width* matches the measured target width for known strings —
  for other text (scores, clock, team abbreviations), both width and
  glyph shapes are interpolated/approximated, not measured.
- **Not emulated at all**: anything that was a genuine hardware/firmware
  behavior rather than application logic — the frame-only-flips-once-
  per-`update()`-call timing quirk, the `machine.WDT` danger, Disk Mode,
  the DTR-reset-on-close serial gotcha, and whatever was actually causing
  the live-hardware freezes this emulator was built to work around. Those
  remain real-device-only concerns; a feature working here doesn't
  guarantee it'll behave identically on hardware, only that the
  application-level logic is sound. Hardware check-ins are still worth
  doing periodically, just not for every small iteration.
