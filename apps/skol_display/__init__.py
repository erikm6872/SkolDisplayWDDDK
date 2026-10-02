"""SkolDisplay - scrolling marquee app for the Workday DevCon 2026 DevKit
(Pimoroni Blinky 2350). See docs/DEVICE_SPECS.md for the badgeware app API
this relies on (`badge`, `screen`, `color`, `run`, button/mode constants
injected as globals by the launcher at /rom/main.py).
"""

import time

badge.mode(LORES)

SCREEN_W, SCREEN_H = 39, 26
SCROLL_SPEED_MS = 60
TEXT = "SKOL "

# 5-row pixel glyphs, (dx, dy) coordinates lit per character.
GLYPHS = {
    "S": [(1, 0), (2, 0), (0, 1), (1, 2), (2, 3), (0, 4), (1, 4)],
    "K": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (2, 1), (2, 3), (3, 0), (3, 4)],
    "O": [(1, 0), (2, 0), (0, 1), (3, 1), (0, 2), (3, 2), (0, 3), (3, 3), (1, 4), (2, 4)],
    "L": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 4), (2, 4)],
    " ": [],
}
GLYPH_WIDTH = 4
GLYPH_SPACING = 1

text_pixel_width = sum(GLYPH_WIDTH + GLYPH_SPACING for _ in TEXT)
scroll_x = SCREEN_W
last_scroll_time = 0


def draw_text(text, x, y):
    cursor = x
    for ch in text:
        for dx, dy in GLYPHS.get(ch, []):
            px, py = cursor + dx, y + dy
            if 0 <= px < SCREEN_W and 0 <= py < SCREEN_H:
                screen.rectangle(px, py, 1, 1)
        cursor += GLYPH_WIDTH + GLYPH_SPACING


def update():
    global scroll_x, last_scroll_time

    now = time.ticks_ms()
    if time.ticks_diff(now, last_scroll_time) >= SCROLL_SPEED_MS:
        scroll_x -= 1
        if scroll_x < -text_pixel_width:
            scroll_x = SCREEN_W
        last_scroll_time = now

    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    screen.pen = color.rgb(255, 215, 0)  # gold
    draw_text(TEXT, scroll_x, (SCREEN_H - 5) // 2)


run(update)
