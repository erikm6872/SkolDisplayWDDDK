"""SkolDisplay - Minnesota Vikings badge app for the Workday DevCon 2026
DevKit (Pimoroni Blinky 2350 / "badgeware" firmware).

Two states:
  - LIVE: a Vikings game is in progress -> scroll the current score.
  - IDLE: no game in progress -> by default, shows a static "SKOL" at medium
    brightness. Press BUTTON_A to toggle on a rotation of Vikings-themed
    animations (off by default so they don't get annoying); the choice is
    persisted via badgeware.State so it survives app restarts.

API confirmed live on real hardware on 2026-10-01 (see docs/DEVICE_SPECS.md):
  - Globals injected by the launcher: screen, color, rom_font, badge,
    BUTTON_A/B/C, run, fatal_error.
  - `screen.text(str, x, y)` draws in the currently selected `screen.font`
    (set via `screen.font = rom_font.<name>`); `screen.measure_text(str)`
    returns `(width, height)` as floats - index [0] drives manual scrolling
    here (there is no built-in marquee).
  - `screen.circle(cx, cy, r)` / `screen.line(x0, y0, x1, y1)` /
    `screen.rectangle(x, y, w, h)` are direct filled-shape draw calls.
  - `color.rgb(r, g, b)` plus named constants (`color.black`, etc).
  - `badge.ticks` is a monotonically increasing ms counter, read fresh each
    frame (matches the on-device /system/apps/weather reference app).
  - `wifi` (plain importable module, not injected) exposes connect(),
    is_connected(), tick() and reads credentials from /system/secrets.py
    automatically - this app never touches secrets itself.

ESPN's public team endpoint (no API key); schema verified by hand against
the live endpoint:
  https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/min
  -> team.nextEvent[0].date ("2026-10-04T20:05Z", UTC, no seconds)
     .competitions[0].status.type.state ("pre"/"in"/"post"),
     .status.period / .displayClock, .competitors[].team.abbreviation / .score

Polling is adaptive rather than fixed-interval, since this is meant to be
left plugged in long-term: it checks once a day (FAR_POLL_INTERVAL_MS)
whenever a game isn't imminent, and only switches to a tight 30s cadence
(NEAR_POLL_INTERVAL_MS) once within PRE_GAME_WINDOW_S of kickoff or while a
game is actually live. Computing "how close is kickoff" needs real
wall-clock time, so the badge syncs its clock via NTP (`ntptime`) once
WiFi is reachable - confirmed working live on 2026-10-01. If NTP has never
succeeded, pre-game countdown can't be computed and polling just stays on
the daily cadence until a game is actually detected as "in".

fetch_game_state()'s urequests.get() is only ever attempted when
network.WLAN(network.STA_IF).isconnected() is True (see
_is_wifi_fully_connected()) - added after repeated unrecoverable hangs
(REPL unresponsive, needing a physical power-cycle) were observed live on
2026-10-02/03, suspected to be urequests.get() blocking indefinitely if
attempted while the interface is still mid-handshake. This is a
best-effort mitigation for a suspected, not fully confirmed, root cause -
if hangs recur even with this gate in place, the actual culprit is more
likely wifi.tick()/wifi.connect() themselves (called unconditionally every
~15s by _pump_wifi() while not yet connected), which can't be gated the
same way since they're what makes the connection happen in the first
place.
"""

import time
import network
import urequests
import wifi
from badgeware import State

try:
    import ntptime
except ImportError:
    ntptime = None

VIKINGS_TEAM_ENDPOINT = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/min"
FAR_POLL_INTERVAL_MS = 24 * 60 * 60 * 1000
NEAR_POLL_INTERVAL_MS = 30 * 1000
PRE_GAME_WINDOW_S = 30 * 60
# Confirmed live on 2026-10-04: at fresh boot, WiFi often isn't fully
# connected yet at the exact moment of the very first poll attempt (it
# takes a few seconds to associate after the app starts) - with this at
# 2 minutes, that one unlucky-timing miss meant waiting a full 2 minutes
# before trying again, even though WiFi actually finished connecting
# within a few seconds. Short, since this is specifically for "WiFi isn't
# up yet," a transient startup condition, not sustained offline.
OFFLINE_RETRY_INTERVAL_MS = 10 * 1000
ANIM_SWITCH_MS = 8 * 1000
SCROLL_SPEED_MS = 70

# The LED matrix is monochrome (white LEDs, variable brightness only) -
# confirmed live on 2026-10-01 after the first hue-based attempt (purple vs
# gold) was invisible on real hardware. Everything below uses brightness
# contrast instead of color.
BRIGHT = color.white
MEDIUM = color.rgb(120, 120, 120)
DIM = color.rgb(50, 50, 50)

STATE_NAME = "skol_display"
_settings = {"animations_enabled": False}
State.load(STATE_NAME, _settings)

SCREEN_W, SCREEN_H = screen.width, screen.height

screen.font = rom_font.smart
# screen.measure_text()[1] is the glyph height for the current font (16px
# for "smart") - used to vertically center single-line text. Measured live
# on hardware on 2026-10-01 after an earlier hardcoded guess of 7px left
# text sitting in the bottom half of the screen. The -3 is an empirical
# nudge on top of that: the "smart" font's glyph box isn't visually
# centered within its own reported height (likely descender padding), so
# the math-centered position still read as slightly low on real hardware.
TEXT_Y = int((SCREEN_H - screen.measure_text("SKOL")[1]) / 2) - 2


# ──────────────────────────────────────────────────────────────────────────
# WIFI (non-blocking state machine, matches /system/apps/weather's pattern)
# ──────────────────────────────────────────────────────────────────────────

_wifi_connect_started = False
WIFI_RETRY_INTERVAL_MS = 15 * 1000
_last_wifi_attempt_ms = -WIFI_RETRY_INTERVAL_MS


def _pump_wifi():
    """Best-effort WiFi pump, throttled to once per WIFI_RETRY_INTERVAL_MS.

    Wrapped in try/except because on this firmware build, a connection
    failure (e.g. the saved access point not being in range) makes
    wifi.tick()'s internal fatal_error() handler itself crash with
    AttributeError: 'module' object has no attribute 'scroll' - a firmware
    bug, confirmed live on 2026-10-01. Without the throttle, that failure
    gets re-triggered on every single frame (no backoff happens because the
    crash interrupts tick() before it can set its own retry timer), which
    both spams the log and burns CPU that should go to animation.
    """
    global _wifi_connect_started, _last_wifi_attempt_ms

    try:
        if wifi.is_connected():
            return True
    except Exception:
        pass

    now = badge.ticks
    if now - _last_wifi_attempt_ms < WIFI_RETRY_INTERVAL_MS:
        return False
    _last_wifi_attempt_ms = now

    try:
        wifi.tick()
        if not _wifi_connect_started:
            wifi.connect()
            _wifi_connect_started = True
    except Exception as e:
        print("skol_display: wifi error (continuing offline):", e)
    return False


def _is_wifi_fully_connected():
    """Checks the underlying network.WLAN directly rather than
    wifi.is_connected() (whose own internal `wlan` reference has been
    observed as None/stale even while actually connected). This gates the
    blocking fetch_game_state() call: suspected (not fully confirmed) cause
    of a hang seen live on 2026-10-02/03 - urequests.get() apparently able
    to block indefinitely if attempted while the interface is still mid-
    handshake rather than fully associated with a working DHCP lease. Only
    proceeding when isconnected() is definitively True should avoid ever
    attempting the blocking call during that transitional window."""
    try:
        return network.WLAN(network.STA_IF).isconnected()
    except Exception:
        return False


def _draw_static_text(text, y, pen_color):
    width = screen.measure_text(text)[0]
    screen.pen = pen_color
    screen.text(text, int((SCREEN_W - width) / 2), y)


# Default idle screen: "SKOL" / "VIKINGS" stacked, as large as possible.
# Measured every ROM font against the 39x26 screen - "VIKINGS" (7 chars)
# doesn't fit under any of them; "sins" is the closest (40px vs the 39px
# screen, 1px over) while still being reasonably large (12px tall). Confirmed
# live that the 1px horizontal overflow doesn't crash screen.text() - it's
# just silently clipped.
#
# The real panel has 3 buttons embedded in the bottom few rows (~22-25) -
# see docs/DEVICE_SPECS.md - so "VIKINGS" needs to clear row ~22, not just
# the nominal 26px screen bottom. A real-hardware photo showed visible
# blank space above "SKOL" at y=0, meaning the real "sins" font has some
# built-in leading our height measurement didn't capture - so both lines
# have room to shift up. SKOL_Y and the tightened gap below are an
# empirical first attempt at using that slack; re-check against hardware
# and adjust further if "VIKINGS" still runs into the buttons.
SKOL_Y = -3
DEFAULT_LINE_HEIGHT = 12
DEFAULT_LINE_GAP = 0


def _draw_default_screen():
    screen.font = rom_font.sins
    _draw_static_text("SKOL", SKOL_Y, MEDIUM)
    _draw_static_text("VIKINGS", SKOL_Y + DEFAULT_LINE_HEIGHT + DEFAULT_LINE_GAP, MEDIUM)


# ──────────────────────────────────────────────────────────────────────────
# SCROLLING TEXT (shared by score display and the SKOL idle animation)
# ──────────────────────────────────────────────────────────────────────────

_scroll_text = None
_scroll_x = SCREEN_W
_scroll_last_ms = 0


def draw_scrolling_text(text, y, pen_color):
    global _scroll_text, _scroll_x, _scroll_last_ms

    now = badge.ticks
    if text != _scroll_text:
        _scroll_text = text
        _scroll_x = SCREEN_W
        _scroll_last_ms = now

    if now - _scroll_last_ms >= SCROLL_SPEED_MS:
        _scroll_x -= 1
        if _scroll_x < -screen.measure_text(text)[0]:
            _scroll_x = SCREEN_W
        _scroll_last_ms = now

    screen.pen = pen_color
    screen.text(text, _scroll_x, y)


# ──────────────────────────────────────────────────────────────────────────
# IDLE ANIMATIONS
# ──────────────────────────────────────────────────────────────────────────

def anim_skol_scroll():
    draw_scrolling_text("SKOL", TEXT_Y, BRIGHT)


def _draw_horn(cx, cy, points, mirror, pen_color):
    """Draws a curved horn as a chain of line segments. `points` is a list
    of (dx, dy) offsets from (cx, cy); mirror=-1 flips dx for the right horn."""
    screen.pen = pen_color
    px, py = points[0]
    for dx, dy in points[1:]:
        screen.line(cx + mirror * px, cy + py, cx + mirror * dx, cy + dy)
        px, py = dx, dy


# Horn curve: sweeps up and out from the dome, then hooks back toward the
# tip - the classic Vikings-logo horn silhouette. Offsets are for the LEFT
# horn; the right horn mirrors dx.
_HORN_POINTS = [(-5, -5), (-7, -8), (-9, -11), (-8, -13)]


def anim_helmet_pulse():
    phase = (badge.ticks // 900) % 2
    pen_color = BRIGHT if phase == 0 else DIM
    screen.pen = pen_color

    cx, cy = SCREEN_W // 2, 17

    # Dome (the helmet shell)
    screen.circle(cx, cy, 7)
    # Jaw/chin-strap lines below the dome, to read as a football helmet
    # rather than a plain ball
    screen.line(cx - 7, cy + 2, cx - 5, cy + 6)
    screen.line(cx + 7, cy + 2, cx + 5, cy + 6)

    # The two curved horns
    _draw_horn(cx, cy, _HORN_POINTS, 1, pen_color)
    _draw_horn(cx, cy, _HORN_POINTS, -1, pen_color)


_chase_offset = 0
_chase_last_ms = 0
CHASE_DOT_SPACING = 5
CHASE_SPEED_MS = 60


def anim_chase_lights():
    """A row of bright 'marching' dots sweeping across the screen - a
    stand-in for a color wave that reads clearly on a brightness-only
    display (full on/off contrast instead of a hue swap, which was
    invisible on the real monochrome LED matrix)."""
    global _chase_offset, _chase_last_ms

    now = badge.ticks
    if now - _chase_last_ms >= CHASE_SPEED_MS:
        _chase_offset = (_chase_offset + 1) % CHASE_DOT_SPACING
        _chase_last_ms = now

    screen.pen = BRIGHT
    y = SCREEN_H // 2
    x = -_chase_offset
    while x < SCREEN_W:
        if 0 <= x < SCREEN_W:
            screen.circle(x, y, 1)
        x += CHASE_DOT_SPACING


IDLE_ANIMATIONS = (anim_skol_scroll, anim_helmet_pulse, anim_chase_lights)


# ──────────────────────────────────────────────────────────────────────────
# VIKINGS GAME DATA
# ──────────────────────────────────────────────────────────────────────────

def _fetch_live_summary(event_id):
    """The team endpoint's own `competitors[].score` is unreliable while a
    game is actually in progress - confirmed live on 2026-10-04:
    status.period/displayClock were correct ("in", period 1, "1:23") but
    both teams' `score` fields were null, so the live-score page was stuck
    showing 0-0 (falling back via `c.get("score") or "0"`) while the clock
    page kept advancing normally. The per-game summary endpoint has the
    real score. Returns a full game_state dict, or None on any failure
    (caller falls back to the team endpoint's own data in that case)."""
    try:
        resp = urequests.get(
            "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={}".format(
                event_id
            ),
            timeout=10,
        )
    except Exception as e:
        print("skol_display: summary request failed:", e)
        return None

    try:
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as e:
        print("skol_display: bad summary response:", e)
        return None
    finally:
        resp.close()

    competitions = (data.get("header") or {}).get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]
    status = comp.get("status") or {}

    scores = []
    for c in comp.get("competitors") or []:
        team = c.get("team") or {}
        scores.append({
            "abbr": team.get("abbreviation", "???"),
            "score": c.get("score") or "0",
        })

    return {
        "state": (status.get("type") or {}).get("state"),
        "date": comp.get("date"),
        "period": status.get("period"),
        "clock": status.get("displayClock"),
        "scores": scores,
    }


def fetch_game_state():
    """Returns a dict describing the Vikings' next/current game, or None if
    the request failed or there's no upcoming/live game data."""
    try:
        resp = urequests.get(VIKINGS_TEAM_ENDPOINT, timeout=10)
    except Exception as e:
        print("skol_display: request failed:", e)
        return None

    try:
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as e:
        print("skol_display: bad response:", e)
        return None
    finally:
        resp.close()

    events = (data.get("team") or {}).get("nextEvent") or []
    if not events:
        return None
    event = events[0]
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]

    status = comp.get("status") or {}
    state = (status.get("type") or {}).get("state")  # "pre" | "in" | "post"

    if state == "in":
        event_id = event.get("id")
        if event_id:
            live = _fetch_live_summary(event_id)
            if live:
                return live
        # fall through to the team endpoint's own (score-unreliable) data
        # if the summary fetch itself failed, rather than showing nothing

    scores = []
    for c in comp.get("competitors") or []:
        team = c.get("team") or {}
        scores.append({
            "abbr": team.get("abbreviation", "???"),
            "score": c.get("score") or "0",
        })

    return {
        "state": state,
        "date": event.get("date"),  # "2026-10-04T20:05Z" (UTC, kickoff)
        "period": status.get("period"),
        "clock": status.get("displayClock"),
        "scores": scores,
    }


# ──────────────────────────────────────────────────────────────────────────
# ADAPTIVE POLLING - daily by default, 30s only near/during a live game.
# Needs real wall-clock time (via NTP) to know how close "kickoff" is; see
# module docstring.
# ──────────────────────────────────────────────────────────────────────────

_time_synced = False
_last_ntp_attempt_ms = -FAR_POLL_INTERVAL_MS


def _sync_time_if_due():
    """Best-effort NTP sync, re-attempted at most once per FAR_POLL_INTERVAL_MS
    (whether or not it succeeded last time, so a temporarily-offline badge
    keeps retrying once a day rather than being permanently stuck unsynced)."""
    global _time_synced, _last_ntp_attempt_ms

    if ntptime is None:
        return

    now = badge.ticks
    if now - _last_ntp_attempt_ms < FAR_POLL_INTERVAL_MS:
        return
    _last_ntp_attempt_ms = now

    try:
        ntptime.settime()
        _time_synced = True
    except Exception as e:
        print("skol_display: ntp sync failed:", e)


def _parse_kickoff_epoch(date_str):
    """Parses ESPN's "2026-10-04T20:05Z" (always UTC) into a epoch-seconds
    value comparable against time.time() on this same device - the two
    don't need to agree on an absolute epoch, only with each other."""
    if not date_str:
        return None
    try:
        year = int(date_str[0:4])
        month = int(date_str[5:7])
        day = int(date_str[8:10])
        hour = int(date_str[11:13])
        minute = int(date_str[14:16])
        return time.mktime((year, month, day, hour, minute, 0, 0, 0))
    except Exception as e:
        print("skol_display: kickoff date parse failed:", e)
        return None


def next_poll_interval_ms(game_state):
    """How long to wait before the next check, given what we just learned."""
    if game_state and game_state.get("state") == "in":
        return NEAR_POLL_INTERVAL_MS

    if game_state and game_state.get("state") == "pre" and _time_synced:
        kickoff_epoch = _parse_kickoff_epoch(game_state.get("date"))
        if kickoff_epoch is not None:
            seconds_until = kickoff_epoch - time.time()
            if seconds_until <= PRE_GAME_WINDOW_S:
                # Already inside (or past, e.g. clock drift) the pre-game
                # window - poll tightly so the pre->in transition is caught
                # promptly.
                return NEAR_POLL_INTERVAL_MS
            # Still far out: wait until we'd be PRE_GAME_WINDOW_S away from
            # kickoff, capped at a day, so a same-day or next-day game isn't
            # overshot by a rigid 24h gap.
            return min(int((seconds_until - PRE_GAME_WINDOW_S) * 1000), FAR_POLL_INTERVAL_MS)

    return FAR_POLL_INTERVAL_MS


def format_score_lines(game_state):
    lines = ["{} {}".format(s["abbr"], s["score"]) for s in game_state["scores"]]
    return lines or ["VIKINGS"]


def format_clock_text(game_state):
    period, clock = game_state.get("period"), game_state.get("clock")
    return "Q{} {}".format(period, clock) if period and clock else "LIVE"


# A full "MIN 17 - GB 14   Q3 8:42" line doesn't fit the 39px-wide screen in
# any available font without scrolling (measured: even the most compact ROM
# font, "desert", needs ~61px for team abbreviations + scores alone). Rather
# than scroll, show two static pages and toggle between them: team scores
# stacked two lines tall, then the quarter/clock - each one fits statically
# in "desert" (10px glyph height, narrow enough per line/string to stay
# under 39px at these string lengths).
SCORE_PAGE_SWITCH_MS = 4 * 1000
LIVE_LINE_HEIGHT = 10
LIVE_LINE_GAP = 2


def draw_live_score(game_state):
    screen.font = rom_font.desert
    showing_scores = (badge.ticks // SCORE_PAGE_SWITCH_MS) % 2 == 0

    if showing_scores:
        lines = format_score_lines(game_state)
        total_h = len(lines) * LIVE_LINE_HEIGHT + (len(lines) - 1) * LIVE_LINE_GAP
        y = int((SCREEN_H - total_h) / 2)
        for line in lines:
            _draw_static_text(line, y, BRIGHT)
            y += LIVE_LINE_HEIGHT + LIVE_LINE_GAP
    else:
        y = int((SCREEN_H - LIVE_LINE_HEIGHT) / 2)
        _draw_static_text(format_clock_text(game_state), y, BRIGHT)


# ──────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────────────────────────────────

_game_state = None
_next_poll_due_ms = 0  # 0 so the very first frame checks immediately
_anim_index = 0
_last_anim_switch_ms = 0
_poll_pending = False


SYNC_ICON_SIZE = 3


def _draw_sync_icon():
    # Small top-right indicator instead of a full-screen takeover, so
    # whatever's already showing (score, clock, default screen, or an
    # animation) stays visible underneath it. Placed at x=35-37, y=0-2 -
    # clear of both right-side button dead zones (which start at y=5 and
    # y=13; see docs/DEVICE_SPECS.md), so it doesn't sit behind a button.
    screen.pen = BRIGHT
    screen.rectangle(SCREEN_W - SYNC_ICON_SIZE - 1, 0, SYNC_ICON_SIZE, SYNC_ICON_SIZE)


def update():
    global _anim_index, _last_anim_switch_ms, _game_state, _next_poll_due_ms, _poll_pending

    if badge.pressed(BUTTON_A):
        _settings["animations_enabled"] = not _settings["animations_enabled"]
        State.modify(STATE_NAME, {"animations_enabled": _settings["animations_enabled"]})

    _pump_wifi()

    now = badge.ticks
    poll_about_to_fire = False

    if _poll_pending:
        # The previous frame already drew the sync icon and returned, so
        # the display has had a chance to actually render it (confirmed on
        # hardware: drawing something and then blocking in the SAME
        # update() call never showed anything, because the framebuffer only
        # flips once update() returns - the blocking call ran out the clock
        # before the frame ever reached the screen). Now that a full frame
        # has rendered with the icon on it, it's safe to do the actual
        # blocking work (NTP sync, then the fetch itself) - but only if the
        # interface is definitively, fully connected; see
        # _is_wifi_fully_connected()'s docstring for why. The icon stays
        # frozen on the physical display throughout this blocking call,
        # since nothing flips again until this frame also returns.
        _poll_pending = False
        if _is_wifi_fully_connected():
            _sync_time_if_due()
            _game_state = fetch_game_state()
            _next_poll_due_ms = now + next_poll_interval_ms(_game_state)
        else:
            _next_poll_due_ms = now + OFFLINE_RETRY_INTERVAL_MS
    elif now >= _next_poll_due_ms:
        _poll_pending = True
        poll_about_to_fire = True

    is_live = bool(_game_state and _game_state.get("state") == "in")

    screen.pen = color.black
    screen.clear()
    # Reset to the default font every frame - draw_live_score() switches to
    # a more compact font for its own draws, and without resetting here that
    # would otherwise leak into the idle states on the frame after a game ends.
    screen.font = rom_font.smart

    if is_live:
        draw_live_score(_game_state)
    elif _settings["animations_enabled"]:
        if now - _last_anim_switch_ms >= ANIM_SWITCH_MS:
            _anim_index = (_anim_index + 1) % len(IDLE_ANIMATIONS)
            _last_anim_switch_ms = now
        IDLE_ANIMATIONS[_anim_index]()
    else:
        _draw_default_screen()

    if poll_about_to_fire:
        _draw_sync_icon()


run(update)
