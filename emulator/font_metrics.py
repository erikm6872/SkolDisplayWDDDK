"""Real font metrics measured live on the physical badge on 2026-10-01/02,
via `screen.measure_text(...)` for every font in `rom_font` (confirmed 37
fonts total). We don't have the device's actual .ppf bitmap font files, so
exact glyph shapes can't be reproduced here - but exact (width, height) for
these two specific strings is this dict's job, since that's what layout
decisions (centering, line height, "does it fit") actually depend on.

For any OTHER string, `estimate_size()` interpolates a per-character width
from these two known data points (4-char "SKOL" and 7-char "VIKINGS") per
font - a reasonable approximation, not a guarantee.
"""

# font_name -> (skol_width, skol_height, vikings_width, vikings_height)
MEASURED = {
    "smart": (28, 16, 41, 16),
    "desert": (26, 10, 44, 10),
    "match": (30, 12, 51, 12),
    "ark": (28, 11, 49, 11),
    "memo": (32, 15, 52, 15),
    "badgeware": (44, 14, 77, 14),
    "corset": (35, 15, 60, 15),
    "outflank": (43, 17, 69, 17),
    "compass": (40, 16, 66, 16),
    "awesome": (36, 14, 59, 14),
    "badgewaremax": (52, 20, 91, 20),
    "bacteria": (52, 20, 89, 20),
    "curse": (30, 20, 48, 20),
    "fear": (41, 17, 61, 17),
    "futile": (58, 24, 101, 24),
    "holotype": (30, 15, 45, 15),
    "hungry": (32, 15, 56, 15),
    "ignore": (51, 28, 87, 28),
    "kobold": (30, 12, 48, 12),
    "lookout": (39, 14, 62, 14),
    "loser": (28, 12, 45, 12),
    "manticore": (39, 23, 62, 23),
    "more": (57, 30, 92, 30),
    "nope": (31, 13, 53, 13),
    "saga": (42, 15, 70, 15),
    "salty": (35, 17, 56, 17),
    "sins": (24, 12, 40, 12),
    "teatime": (32, 12, 56, 12),
    "torch": (28, 11, 47, 11),
    "troll": (51, 22, 80, 22),
    "unfair": (48, 14, 84, 14),
    "vest": (38, 15, 58, 15),
    "winds": (24, 12, 42, 12),
    "yesterday": (26, 16, 42, 16),
    "yolk": (34, 11, 55, 11),
    "ziplock": (46, 21, 70, 21),
    "absolute": (36, 16, 62, 16),
}

_SKOL_LEN = 4
_VIKINGS_LEN = 7


def estimate_size(font_name, text):
    """Returns (width, height) for `text` in `font_name`. Exact for "SKOL"
    and "VIKINGS" (the strings this app actually needed exact layout for);
    linearly interpolated/extrapolated from those two data points for
    anything else."""
    if font_name not in MEASURED:
        raise KeyError(
            "No measured data for font {!r} - only fonts actually probed "
            "live on hardware are supported: {}".format(font_name, sorted(MEASURED))
        )

    skol_w, skol_h, vikings_w, vikings_h = MEASURED[font_name]

    if text == "SKOL":
        return (float(skol_w), float(skol_h))
    if text == "VIKINGS":
        return (float(vikings_w), float(vikings_h))

    # height is identical between our two samples for every font measured,
    # so treat it as constant for this font regardless of content
    height = float(skol_h)

    if len(text) == 0:
        return (0.0, height)

    per_char = (vikings_w - skol_w) / (_VIKINGS_LEN - _SKOL_LEN)
    intercept = skol_w - per_char * _SKOL_LEN
    width = intercept + per_char * len(text)
    return (max(width, 0.0), height)
