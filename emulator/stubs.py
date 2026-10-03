"""Stand-ins for the globals the real badgeware launcher injects into an
app's namespace (confirmed live via dir() on real hardware - see
docs/DEVICE_SPECS.md). Only implements what apps/skol_display/__init__.py
actually uses: screen.{circle,clear,font,height,line,measure_text,pen,
rectangle,text,width}, badge.{pressed,ticks}, color.{black,rgb,white},
rom_font.{desert,sins,smart}, BUTTON_A, run(), fatal_error.

Rendering uses a real system font scaled to the measured height per
rom_font entry (see font_metrics.py) - this will not look pixel-identical
to the device's actual bitmap fonts, but position/size/timing should be
representative enough for layout and logic iteration.
"""

import math
import time

from PIL import Image, ImageDraw, ImageFont

from font_metrics import estimate_size

SCREEN_W = 39
SCREEN_H = 26

_SYSTEM_FONT_PATH = "/usr/share/fonts/TTF/HackNerdFontMono-Bold.ttf"
_fitted_font_cache = {}
_probe_draw = ImageDraw.Draw(Image.new("L", (1, 1), 0))


def _rendered_width(text, font):
    bbox = _probe_draw.textbbox((0, 0), text, font=font)
    return max(bbox[2] - bbox[0], 1)


def _fit_font(text, target_width):
    """The device's actual bitmap fonts are far more condensed than any
    standard system font - sizing purely by target height (the first cut
    at this) rendered badly overflowing/clipped text, confirmed visually.
    Instead, iteratively shrink/grow the point size until the system
    font's ACTUAL rendered width roughly matches our measured-on-hardware
    target width, so text fits the 39px screen the way it really does."""
    key = (text, int(target_width))
    if key in _fitted_font_cache:
        return _fitted_font_cache[key]

    size = max(int(target_width / max(len(text), 1) / 0.55), 6)
    font = ImageFont.truetype(_SYSTEM_FONT_PATH, size)
    for _ in range(4):
        w = _rendered_width(text, font)
        if target_width <= 0 or w == 0:
            break
        ratio = target_width / w
        new_size = max(int(round(size * ratio)), 6)
        if new_size == size:
            break
        size = new_size
        font = ImageFont.truetype(_SYSTEM_FONT_PATH, size)

    _fitted_font_cache[key] = font
    return font


class Device:
    """Holds the one shared mutable framebuffer/input/clock state a real
    badge would have in hardware. A single instance is threaded through
    all the stub globals below."""

    def __init__(self):
        self.pixels = [[0] * SCREEN_W for _ in range(SCREEN_H)]  # row-major, 0-255 brightness
        self.start_time = time.monotonic()
        self._pending_buttons = set()
        self._this_frame_buttons = set()

    def ticks(self):
        return int((time.monotonic() - self.start_time) * 1000)

    def press_button(self, name):
        """Called by the web server when a button is clicked."""
        self._pending_buttons.add(name)

    def begin_frame(self):
        """Snapshot pending button clicks into 'pressed this frame', then
        clear the pending set - mimics edge-triggered badge.pressed()."""
        self._this_frame_buttons = self._pending_buttons
        self._pending_buttons = set()

    def set_pixel(self, x, y, brightness):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < SCREEN_W and 0 <= y < SCREEN_H:
            self.pixels[y][x] = max(0, min(255, int(brightness)))

    def to_image(self, scale=12):
        """Renders the framebuffer as an LED-dot-style PNG."""
        img = Image.new("RGB", (SCREEN_W * scale, SCREEN_H * scale), (8, 8, 10))
        draw = ImageDraw.Draw(img)
        r = scale * 0.42
        for y in range(SCREEN_H):
            for x in range(SCREEN_W):
                b = self.pixels[y][x]
                cx, cy = x * scale + scale / 2, y * scale + scale / 2
                color = (b, b, max(b - 20, 0))  # faint warm-white LED look
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        return img


class _Color:
    """color.rgb(r,g,b) / named constants. Device is monochrome (confirmed
    live - see docs/DEVICE_SPECS.md), so everything collapses to a single
    luminance value; keeps the real API shape for app-code compatibility."""

    black = 0
    white = 255

    @staticmethod
    def rgb(r, g, b, a=255):
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return int(round(luminance * (a / 255.0)))


class _Font:
    def __init__(self, name):
        self.name = name


class _RomFont:
    def __init__(self):
        # Only the fonts the app actually references need to exist as
        # attributes, but font_metrics.py has data for all 37 real fonts.
        for name in ("smart", "desert", "sins"):
            setattr(self, name, _Font(name))


class _Screen:
    def __init__(self, device):
        self._device = device
        self.width = SCREEN_W
        self.height = SCREEN_H
        self.font = None
        self.pen = _Color.white

    def clear(self):
        for y in range(SCREEN_H):
            for x in range(SCREEN_W):
                self._device.pixels[y][x] = self.pen

    def measure_text(self, text):
        font_name = self.font.name if self.font else "smart"
        return estimate_size(font_name, text)

    def text(self, text, x, y):
        font_name = self.font.name if self.font else "smart"
        target_width, _ = estimate_size(font_name, text)
        pil_font = _fit_font(text, target_width)

        # Measure the ACTUAL rendered bbox at the fitted size for patch
        # sizing - fitting the point size to our target width (above)
        # keeps things from overflowing the 39px screen the way a plain
        # height-based guess did (confirmed visually: "SKOL" rendered
        # overflowing/clipped at the screen edge before this fit step).
        bbox = _probe_draw.textbbox((0, 0), text, font=pil_font)
        render_w = max(bbox[2] - bbox[0], 1)
        render_h = max(bbox[3] - bbox[1], 1)

        # Render to a small alpha-masked patch so brightness == self.pen
        # exactly where the glyph has ink, using the real font's actual
        # shapes - an approximation of the device's bitmap font, not a
        # reproduction of it (see module docstring).
        pad = 4
        patch = Image.new("L", (render_w + pad * 2, render_h + pad * 2), 0)
        draw = ImageDraw.Draw(patch)
        draw.text((pad - bbox[0], pad - bbox[1]), text, font=pil_font, fill=255)
        patch_pixels = patch.load()
        for py in range(patch.height):
            for px in range(patch.width):
                if patch_pixels[px, py] > 90:
                    self._device.set_pixel(x + px - pad, y + py - pad, self.pen)

    def put(self, x, y):
        self._device.set_pixel(x, y, self.pen)

    def line(self, x0, y0, x1, y1):
        dx, dy = x1 - x0, y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        for i in range(int(steps) + 1):
            t = i / steps
            self._device.set_pixel(x0 + dx * t, y0 + dy * t, self.pen)

    def rectangle(self, x, y, w, h):
        x0, y0 = int(x), int(y)
        for py in range(y0, y0 + int(h)):
            for px in range(x0, x0 + int(w)):
                self._device.set_pixel(px, py, self.pen)

    def circle(self, cx, cy, r):
        r2 = r * r
        for dy in range(-int(r), int(r) + 1):
            for dx in range(-int(r), int(r) + 1):
                if dx * dx + dy * dy <= r2:
                    self._device.set_pixel(cx + dx, cy + dy, self.pen)


class _Badge:
    def __init__(self, device):
        self._device = device

    @property
    def ticks(self):
        return self._device.ticks()

    def pressed(self, button_name):
        return button_name in self._device._this_frame_buttons


def fatal_error(message, exc=None):
    print("FATAL_ERROR (emulated):", message, exc)
    raise SystemExit(1)


class _Runner:
    """run(update_fn) on the real device blocks forever, calling update_fn
    every frame. Here it just stores the function so the server's own loop
    can call it - matches the call signature apps use (`run(update)` as
    the last line of the module) without actually blocking import."""

    def __init__(self):
        self.update_fn = None

    def __call__(self, update_fn):
        self.update_fn = update_fn


def build_globals(device):
    """Returns the dict of injected globals an app module executes with,
    plus the Runner so the caller can drive the frame loop afterward."""
    runner = _Runner()
    g = {
        "screen": _Screen(device),
        "badge": _Badge(device),
        "color": _Color,
        "rom_font": _RomFont(),
        "BUTTON_A": "A",
        "BUTTON_B": "B",
        "BUTTON_C": "C",
        "run": runner,
        "fatal_error": fatal_error,
    }
    return g, runner
