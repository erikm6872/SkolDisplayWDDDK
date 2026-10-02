# TODO

Ideas for future work, not yet implemented.

- **Survey the device's bundled animations for inspiration.** The badge
  ships several example apps under `/system/apps/` (and read-only ones
  under `/rom/apps/`) — `demos`, `games/worm`, `games/zoooom`, `doomface`,
  `logo`, `konami` — worth reading through for animation techniques (easing,
  sprite work, `picovector` usage) beyond what `apps/skol_display/__init__.py`
  currently does, to make the idle animations more elaborate than the
  current helmet pulse / chase-light sweep.
- **Default idle text**: change from "SKOL" to "SKOL VIKINGS", with a
  subtle wave animation (as opposed to the current hard toggle between
  static text and the animation rotation) — something gentler than the
  existing marquee/chase-light effects for the default resting state.
- **Real-life clock option** for the idle state when no game is on — an
  alternative to (or another entry in the rotation alongside) the current
  animations, showing the current time. Depends on the NTP time sync
  already added for adaptive polling (see `_sync_time_if_due()` /
  `_time_synced` in the app) actually having succeeded.
