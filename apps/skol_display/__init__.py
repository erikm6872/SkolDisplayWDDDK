"""SkolDisplay - Minnesota Vikings badge app for the Workday DevCon 2026
DevKit (Pimoroni Blinky 2350). See docs/DEVICE_SPECS.md for the badgeware
app API this relies on (`badge`, `screen`, `color`, `run`, button/mode
constants injected as globals by the launcher at /rom/main.py).

Two states:
  - LIVE:  a Vikings game is in progress -> scroll the current score.
  - IDLE:  no game in progress -> cycle through Vikings-themed animations.

Game data comes from ESPN's public (unofficial) team endpoint - schema
verified by hand on 2026-10-01:
  https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/min
  team.nextEvent[0].competitions[0].status.type.state  -> "pre" | "in" | "post"
  team.nextEvent[0].competitions[0].status.period / displayClock
  team.nextEvent[0].competitions[0].competitors[].team.abbreviation / .score / .homeAway

ASSUMPTIONS NOT YET VERIFIED ON HARDWARE (the badge went offline mid-build):
  - That the badge's system WiFi (if any) is already connected by the time
    this app runs, via `network.WLAN(network.STA_IF)`. This app does not
    manage its own WiFi credentials - see "Open questions" in
    docs/DEVICE_SPECS.md. If the device needs this app to initiate its own
    connection, add that here using `secrets.py` (gitignored) for
    WIFI_SSID / WIFI_PASSWORD.
  - That `urequests` (or `requests`) works over HTTPS on this firmware.
  - Pixel font legibility on real hardware (FONT_3X5 below is hand-drawn
    and untested on the actual LED matrix).
"""

import time

badge.mode(LORES)

SCREEN_W, SCREEN_H = 39, 26

VIKINGS_TEAM_ENDPOINT = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/min"
POLL_INTERVAL_MS = 30_000
ANIM_SWITCH_MS = 8_000

PURPLE = (79, 38, 131)
GOLD = (255, 198, 47)


# ──────────────────────────────────────────────────────────────────────────
# PIXEL FONT (3 wide x 5 tall, a few letters wider) - covers A-Z, 0-9, space,
# dash and colon, enough for team abbreviations / scores / game clocks.
# ──────────────────────────────────────────────────────────────────────────

FONT = {
    "0": (3, [(0,0),(1,0),(2,0), (0,1),(2,1), (0,2),(2,2), (0,3),(2,3), (0,4),(1,4),(2,4)]),
    "1": (3, [(1,0), (0,1),(1,1), (1,2), (1,3), (0,4),(1,4),(2,4)]),
    "2": (3, [(0,0),(1,0),(2,0), (2,1), (0,2),(1,2),(2,2), (0,3), (0,4),(1,4),(2,4)]),
    "3": (3, [(0,0),(1,0),(2,0), (2,1), (1,2),(2,2), (2,3), (0,4),(1,4),(2,4)]),
    "4": (3, [(0,0),(2,0), (0,1),(2,1), (0,2),(1,2),(2,2), (2,3), (2,4)]),
    "5": (3, [(0,0),(1,0),(2,0), (0,1), (0,2),(1,2),(2,2), (2,3), (0,4),(1,4),(2,4)]),
    "6": (3, [(0,0),(1,0),(2,0), (0,1), (0,2),(1,2),(2,2), (0,3),(2,3), (0,4),(1,4),(2,4)]),
    "7": (3, [(0,0),(1,0),(2,0), (2,1), (2,2), (2,3), (2,4)]),
    "8": (3, [(0,0),(1,0),(2,0), (0,1),(2,1), (0,2),(1,2),(2,2), (0,3),(2,3), (0,4),(1,4),(2,4)]),
    "9": (3, [(0,0),(1,0),(2,0), (0,1),(2,1), (0,2),(1,2),(2,2), (2,3), (0,4),(1,4),(2,4)]),
    "A": (3, [(1,0), (0,1),(2,1), (0,2),(1,2),(2,2), (0,3),(2,3), (0,4),(2,4)]),
    "B": (3, [(0,0),(1,0), (0,1),(2,1), (0,2),(1,2), (0,3),(2,3), (0,4),(1,4)]),
    "C": (3, [(1,0),(2,0), (0,1), (0,2), (0,3), (1,4),(2,4)]),
    "D": (3, [(0,0),(1,0), (0,1),(2,1), (0,2),(2,2), (0,3),(2,3), (0,4),(1,4)]),
    "E": (3, [(0,0),(1,0),(2,0), (0,1), (0,2),(1,2), (0,3), (0,4),(1,4),(2,4)]),
    "F": (3, [(0,0),(1,0),(2,0), (0,1), (0,2),(1,2), (0,3), (0,4)]),
    "G": (3, [(1,0),(2,0), (0,1), (0,2),(2,2), (0,3),(2,3), (1,4),(2,4)]),
    "H": (3, [(0,0),(2,0), (0,1),(2,1), (0,2),(1,2),(2,2), (0,3),(2,3), (0,4),(2,4)]),
    "I": (1, [(0,0),(0,1),(0,2),(0,3),(0,4)]),
    "J": (3, [(2,0),(2,1),(2,2), (0,3),(2,3), (1,4)]),
    "K": (3, [(0,0),(2,0), (0,1),(1,1), (0,2), (0,3),(1,3), (0,4),(2,4)]),
    "L": (3, [(0,0), (0,1), (0,2), (0,3), (0,4),(1,4),(2,4)]),
    "M": (5, [(0,0),(4,0), (0,1),(1,1),(3,1),(4,1), (0,2),(2,2),(4,2), (0,3),(4,3), (0,4),(4,4)]),
    "N": (4, [(0,0),(3,0), (0,1),(1,1),(3,1), (0,2),(2,2),(3,2), (0,3),(3,3), (0,4),(3,4)]),
    "O": (3, [(0,0),(1,0),(2,0), (0,1),(2,1), (0,2),(2,2), (0,3),(2,3), (0,4),(1,4),(2,4)]),
    "P": (3, [(0,0),(1,0), (0,1),(2,1), (0,2),(1,2), (0,3), (0,4)]),
    "Q": (3, [(1,0), (0,1),(2,1), (0,2),(2,2), (0,3),(2,3), (1,4),(2,4)]),
    "R": (3, [(0,0),(1,0), (0,1),(2,1), (0,2),(1,2), (0,3),(2,3), (0,4),(2,4)]),
    "S": (3, [(1,0),(2,0), (0,1), (1,2), (2,3), (0,4),(1,4)]),
    "T": (3, [(0,0),(1,0),(2,0), (1,1), (1,2), (1,3), (1,4)]),
    "U": (3, [(0,0),(2,0), (0,1),(2,1), (0,2),(2,2), (0,3),(2,3), (1,4)]),
    "V": (3, [(0,0),(2,0), (0,1),(2,1), (0,2),(2,2), (1,3), (1,4)]),
    "W": (5, [(0,0),(4,0), (0,1),(4,1), (0,2),(2,2),(4,2), (0,3),(1,3),(3,3),(4,3), (0,4),(4,4)]),
    "X": (3, [(0,0),(2,0), (0,1),(2,1), (1,2), (0,3),(2,3), (0,4),(2,4)]),
    "Y": (3, [(0,0),(2,0), (0,1),(2,1), (1,2), (1,3), (1,4)]),
    "Z": (3, [(0,0),(1,0),(2,0), (2,1), (1,2), (0,3), (0,4),(1,4),(2,4)]),
    " ": (2, []),
    "-": (3, [(0,2),(1,2),(2,2)]),
    ":": (1, [(0,1),(0,3)]),
}
GLYPH_SPACING = 1


def _draw_text(x, y, text, pen_color):
    screen.pen = pen_color
    cursor = x
    for ch in text:
        width, pixels = FONT.get(ch, FONT[" "])
        for dx, dy in pixels:
            px, py = cursor + dx, y + dy
            if 0 <= px < SCREEN_W and 0 <= py < SCREEN_H:
                screen.rectangle(px, py, 1, 1)
        cursor += width + GLYPH_SPACING
    return cursor - GLYPH_SPACING  # end x of last glyph


def _text_width(text):
    return sum(FONT.get(ch, FONT[" "])[0] + GLYPH_SPACING for ch in text) - GLYPH_SPACING


# ──────────────────────────────────────────────────────────────────────────
# SCROLLING TEXT (shared by the score display and the SKOL idle animation)
# ──────────────────────────────────────────────────────────────────────────

_scroll_text = None
_scroll_x = SCREEN_W
_scroll_last_ms = 0
SCROLL_SPEED_MS = 70


def draw_scrolling_text(text, y, pen_color):
    global _scroll_text, _scroll_x, _scroll_last_ms

    if text != _scroll_text:
        _scroll_text = text
        _scroll_x = SCREEN_W
        _scroll_last_ms = time.ticks_ms()

    now = time.ticks_ms()
    if time.ticks_diff(now, _scroll_last_ms) >= SCROLL_SPEED_MS:
        _scroll_x -= 1
        if _scroll_x < -_text_width(text):
            _scroll_x = SCREEN_W
        _scroll_last_ms = now

    _draw_text(_scroll_x, y, text, pen_color)


# ──────────────────────────────────────────────────────────────────────────
# SIMPLE DRAWING PRIMITIVES (for the helmet animation)
# ──────────────────────────────────────────────────────────────────────────

def _draw_filled_circle(cx, cy, r, pen_color):
    screen.pen = pen_color
    r2 = r * r
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r2:
                px, py = cx + dx, cy + dy
                if 0 <= px < SCREEN_W and 0 <= py < SCREEN_H:
                    screen.rectangle(px, py, 1, 1)


def _draw_line(x0, y0, x1, y1, pen_color):
    screen.pen = pen_color
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        if 0 <= x0 < SCREEN_W and 0 <= y0 < SCREEN_H:
            screen.rectangle(x0, y0, 1, 1)
        return
    for i in range(steps + 1):
        px = x0 + round(dx * i / steps)
        py = y0 + round(dy * i / steps)
        if 0 <= px < SCREEN_W and 0 <= py < SCREEN_H:
            screen.rectangle(px, py, 1, 1)


# ──────────────────────────────────────────────────────────────────────────
# IDLE ANIMATIONS
# ──────────────────────────────────────────────────────────────────────────

def anim_skol_scroll():
    draw_scrolling_text("SKOL  ", (SCREEN_H - 5) // 2, color.rgb(*GOLD))


def anim_helmet_pulse():
    phase = (time.ticks_ms() // 1200) % 2
    pen_color = color.rgb(*(GOLD if phase == 0 else PURPLE))

    cx, cy = SCREEN_W // 2, 16
    _draw_filled_circle(cx, cy, 7, pen_color)
    _draw_line(cx - 6, cy - 5, cx - 12, cy - 12, pen_color)
    _draw_line(cx - 12, cy - 12, cx - 10, cy - 14, pen_color)
    _draw_line(cx + 6, cy - 5, cx + 12, cy - 12, pen_color)
    _draw_line(cx + 12, cy - 12, cx + 10, cy - 14, pen_color)


_wave_offset = 0
_wave_last_ms = 0
WAVE_STRIPE_WIDTH = 4


def anim_color_wave():
    global _wave_offset, _wave_last_ms

    now = time.ticks_ms()
    if time.ticks_diff(now, _wave_last_ms) >= 80:
        _wave_offset = (_wave_offset + 1) % WAVE_STRIPE_WIDTH
        _wave_last_ms = now

    colors = (color.rgb(*GOLD), color.rgb(*PURPLE))
    x = -_wave_offset
    idx = 0
    while x < SCREEN_W:
        draw_x = max(x, 0)
        draw_w = min(x + WAVE_STRIPE_WIDTH, SCREEN_W) - draw_x
        if draw_w > 0:
            screen.pen = colors[idx % 2]
            screen.rectangle(draw_x, 0, draw_w, SCREEN_H)
        x += WAVE_STRIPE_WIDTH
        idx += 1


IDLE_ANIMATIONS = (anim_skol_scroll, anim_helmet_pulse, anim_color_wave)


# ──────────────────────────────────────────────────────────────────────────
# VIKINGS GAME DATA
# ──────────────────────────────────────────────────────────────────────────

def _is_wifi_connected():
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        return wlan.active() and wlan.isconnected()
    except Exception:
        return False


def fetch_game_state():
    """Returns a dict describing the Vikings' next/current game, or None if
    offline, the request failed, or there's no upcoming/live game data."""
    if not _is_wifi_connected():
        return None

    try:
        import urequests as requests
    except ImportError:
        import requests

    try:
        resp = requests.get(VIKINGS_TEAM_ENDPOINT)
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
    competitions = events[0].get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]

    status = comp.get("status") or {}
    state = (status.get("type") or {}).get("state")  # "pre" | "in" | "post"

    scores = []
    for c in comp.get("competitors") or []:
        team = c.get("team") or {}
        scores.append({
            "abbr": team.get("abbreviation", "???"),
            "score": c.get("score") or "0",
            "home": c.get("homeAway") == "home",
        })

    return {
        "state": state,
        "period": status.get("period"),
        "clock": status.get("displayClock"),
        "scores": scores,
    }


def format_score_text(game_state):
    parts = ["{} {}".format(s["abbr"], s["score"]) for s in game_state["scores"]]
    text = " - ".join(parts) if parts else "VIKINGS"
    period, clock = game_state.get("period"), game_state.get("clock")
    if period and clock:
        text += "   Q{} {}".format(period, clock)
    return text + "   "


# ──────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────────────────────────────────

_game_state = None
_last_poll_ms = -POLL_INTERVAL_MS
_anim_index = 0
_last_anim_switch_ms = 0


def _poll_game_state():
    global _game_state, _last_poll_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_poll_ms) < POLL_INTERVAL_MS:
        return
    _last_poll_ms = now
    _game_state = fetch_game_state()


def update():
    global _anim_index, _last_anim_switch_ms

    _poll_game_state()
    is_live = bool(_game_state and _game_state.get("state") == "in")

    screen.pen = color.rgb(0, 0, 0)
    screen.clear()

    if is_live:
        draw_scrolling_text(format_score_text(_game_state), (SCREEN_H - 5) // 2, color.rgb(*GOLD))
    else:
        now = time.ticks_ms()
        if time.ticks_diff(now, _last_anim_switch_ms) >= ANIM_SWITCH_MS:
            _anim_index = (_anim_index + 1) % len(IDLE_ANIMATIONS)
            _last_anim_switch_ms = now
        IDLE_ANIMATIONS[_anim_index]()


run(update)
