"""The share card: a picture of how a session is going (EXP/hr, mesos/hr, the map), in the
overlay's own look, to paste into Discord or anywhere else. Drawn with ui_gfx (the same glowing
gold numbers, panels and trend line as the main window), at a fixed size, so it looks the same
on every screen.

It only ever shows what's on the overlay itself: the map, level, class and party size, and the
numbers. Never the character's name, and nothing from the log's notes."""
import random
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ui_gfx import GOLD_BOTTOM, GOLD_GLOW, GOLD_TOP, INK, TEXT, TEXT_DIM, TEXT_FAINT, Gfx, rgb

W, H = 640, 344            # the card, in the card's own units...
SCALE = 2                  # ...drawn this many pixels per unit (1280 x 688: sharp in Discord)
PAD = 26


@dataclass
class CardStats:
    exp_hr: str                         # "72,566"
    mesos_hr: str = "—"            # "1,234,567", or a dash if mesos weren't read
    map_name: str = ""                  # empty if it wasn't read
    level: int | None = None
    job: str | None = None
    party: str = ""                     # "Solo", "4ppl"
    pct_hr: str = ""                    # "12.40%": of a level per hour
    elapsed: str = ""                   # "1:02:33"
    trend: list = field(default_factory=list)    # EXP/hr over the session, for the line
    footer: str = ""                    # where the overlay comes from
    when: date = field(default_factory=date.today)


# A maple leaf on a 24-unit grid: the right half, from the top point down to the stem (mirrored
# for the left half).
_LEAF_RIGHT = [(12, 0.6), (13.6, 4.7), (16.1, 3.5), (15.3, 9.2), (19.2, 6.2), (18.5, 9.5), (23.2, 9.9),
               (19.8, 13.2), (21.0, 15.1), (15.8, 14.8), (13.4, 16.2), (12.7, 19.6)]


def _leaf_points(x, y, size):
    u = size / 24
    right = [(x + px * u, y + py * u) for px, py in _LEAF_RIGHT]
    left = [(x + (24 - px) * u, y + py * u) for px, py in reversed(_LEAF_RIGHT)]
    return right + left


def _leaf(size, color, alpha=255, stem=True):
    """A maple leaf in one colour, size x size, at 3x and shrunk (smooth edges)."""
    s = size * 3
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    d.polygon(_leaf_points(0, 0, s), fill=alpha)
    if stem:
        d.line([(s * 0.5, s * 0.78), (s * 0.5, s * 0.99)], fill=alpha, width=max(2, s // 24))
    img = Image.new("RGBA", (s, s), rgb(color) + (0,))
    img.putalpha(m)
    return img.resize((size, size), Image.LANCZOS)


def _gold_leaf(size, glow=True):
    """The badge's leaf: gold, top to bottom, with a soft glow."""
    s = size * 3
    mask = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(mask)
    d.polygon(_leaf_points(0, 0, s), fill=255)
    d.line([(s * 0.5, s * 0.78), (s * 0.5, s * 0.99)], fill=255, width=max(2, s // 20))
    grad = Image.fromarray(Gfx._gradient(s, s, GOLD_TOP, GOLD_BOTTOM), "RGB").convert("RGBA")
    grad.putalpha(mask)
    pad = s // 3
    out = Image.new("RGBA", (s + 2 * pad, s + 2 * pad), (0, 0, 0, 0))
    if glow:
        g = Image.new("L", out.size, 0)
        g.paste(mask, (pad, pad))
        g = g.filter(ImageFilter.GaussianBlur(s / 9)).point(lambda v: int(v * 0.55))
        gl = Image.new("RGBA", out.size, rgb(GOLD_GLOW) + (0,))
        gl.putalpha(g)
        out = Image.alpha_composite(out, gl)
    out.alpha_composite(grad, (pad, pad))
    return out.resize((out.width // 3, out.height // 3), Image.LANCZOS), pad // 3


def _sparkle(d, x, y, r, alpha):
    """A little four-pointed star."""
    w = r * 0.22
    d.polygon([(x, y - r), (x + w, y - w), (x + r, y), (x + w, y + w), (x, y + r), (x - w, y + w),
               (x - r, y), (x - w, y - w)], fill=rgb("#ffe7a3") + (alpha,))


def _background(w, h, seed):
    """Ink, a warm glow from the top left, falling leaves at the right, a few sparkles."""
    yy, xx = np.mgrid[0:h, 0:w]
    base = np.zeros((h, w, 3), float) + np.array(rgb(INK), float)
    for cx, cy, rx, ry, strength in ((0.22, 0.30, 0.75, 0.95, 0.20), (0.98, 0.05, 0.55, 0.65, 0.07)):
        d = np.sqrt(((xx - w * cx) / (w * rx)) ** 2 + ((yy - h * cy) / (h * ry)) ** 2)
        a = np.clip(1 - d, 0, 1) ** 2 * strength
        base = base * (1 - a[..., None]) + np.array(rgb(GOLD_GLOW), float) * a[..., None]
    img = Image.fromarray(base.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    rnd = random.Random(seed)
    for size, x, y, angle, alpha in ((int(h * 0.95), w * 0.70, h * 0.02, -18, 16),
                                     (int(h * 0.26), w * 0.60, h * 0.70, 24, 22),
                                     (int(h * 0.16), w * 0.92, h * 0.80, -40, 30),
                                     (int(h * 0.11), w * 0.52, h * 0.06, 50, 26)):
        leaf = _leaf(size, GOLD_GLOW, alpha).rotate(angle, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(leaf, (int(x), int(y)))
    d = ImageDraw.Draw(img)
    for _ in range(14):
        x, y = rnd.uniform(w * 0.45, w * 0.98), rnd.uniform(h * 0.05, h * 0.95)
        _sparkle(d, x, y, rnd.uniform(1.5, 4.5) * SCALE, rnd.randint(40, 120))
    return img


def _fit(gfx, text, weight, size, max_w, min_size):
    """The biggest size, from `size` down to `min_size`, that `text` fits in max_w at."""
    while size > min_size and gfx.text_width(text, weight, size) > max_w:
        size -= 0.5
    return size


def _ellipsize(gfx, text, weight, size, max_w):
    if gfx.text_width(text, weight, size) <= max_w:
        return text
    while text and gfx.text_width(text + "…", weight, size) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def make_card(stats, fonts_dir):
    """The share card for these stats, as an RGB picture (W x H times SCALE pixels)."""
    g = Gfx(SCALE, fonts_dir)
    px = g.px
    card = _background(px(W), px(H), seed=stats.exp_hr)
    out = Image.new("RGBA", card.size, (0, 0, 0, 0))
    out.alpha_composite(card)

    def put(img, x, y):
        out.alpha_composite(img, (int(x), int(y)))

    def text(s, weight, size, x, y, top, bottom=None, glow=None, anchor="left"):
        """Draws text with its top-left at (x, y) units (or its top-right, anchor='right')."""
        img, asc, pad = g.text(s, weight, size, top, bottom, glow)
        left = px(x) - pad - (img.width - 2 * pad if anchor == "right" else 0)
        put(img, left, px(y) - pad)
        return img.width - 2 * pad

    # the badge: a gold leaf and the overlay's name; the date on the right
    leaf, lpad = _gold_leaf(px(22))
    put(leaf, px(PAD) - lpad, px(PAD - 3) - lpad)
    text("MAPLE CLASSIC EXP", "extra", 10.5, PAD + 30, PAD - 1, TEXT)
    text("SESSION CARD", "bold", 8.5, PAD + 30, PAD + 13, GOLD_TOP, GOLD_BOTTOM)
    text(stats.when.strftime("%b %d, %Y").replace(" 0", " "), "semibold", 9.5, W - PAD, PAD + 4, TEXT_DIM, anchor="right")

    # where: the map (big), then level, class and party
    y = PAD + 46
    where = stats.map_name or "Somewhere in Maple World"
    size = _fit(g, where, "extra", 21, W - 2 * PAD, 15)
    text(_ellipsize(g, where, "extra", size, W - 2 * PAD), "extra", size, PAD, y, TEXT)
    who = " · ".join(x for x in (f"Lv {stats.level}" if stats.level else "", stats.job or "", stats.party) if x)
    if who:
        text(who, "semibold", 11, PAD, y + 30, TEXT_DIM)

    # the hero: EXP per hour, big and glowing, on a panel with the trend line along its bottom
    hx, hy, hw, hh = PAD, y + 56, 372, 168
    hero = g.hero_panel(px(hw), px(hh), 18)
    glow_pad = 24                                    # (room for the whole blur: no hard edge)
    put(g.glow(px(hw), px(hh), 18, GOLD_GLOW, 7, 0.16, px(glow_pad)), px(hx - glow_pad), px(hy - glow_pad))
    put(hero, px(hx), px(hy))
    text("EXP PER HOUR", "bold", 9, hx + 20, hy + 18, TEXT_DIM)
    size = _fit(g, stats.exp_hr, "extra", 54, hw - 40, 30)
    text(stats.exp_hr, "extra", size, hx + 18, hy + 34, GOLD_TOP, GOLD_BOTTOM, glow=GOLD_GLOW)
    if stats.pct_hr:
        text(f"{stats.pct_hr} of a level / hr", "semibold", 10.5, hx + 20, hy + 108, "#d9b04a")
    spark = g.spark(stats.trend or [], px(hw - 48), px(36))
    put(spark, px(hx + 18), px(hy + hh - 44))

    # the side: mesos per hour and time, as tiles
    sx, sw = hx + hw + 14, W - PAD - (hx + hw + 14)
    tiles = [("MESOS PER HOUR", stats.mesos_hr, True), ("TIME TRACKED", stats.elapsed or "—", False)]
    th = (hh - 12) / 2
    for i, (label, value, gold) in enumerate(tiles):
        ty = hy + i * (th + 12)
        put(g.panel(px(sw), px(th), 14), px(sx), px(ty))
        text(label, "bold", 8.5, sx + 14, ty + 14, TEXT_DIM)
        vsize = _fit(g, value, "extra", 22, sw - 28, 12)
        if gold:
            text(value, "extra", vsize, sx + 14, ty + 34, "#fff1c2", GOLD_TOP)
        else:
            text(value, "extra", vsize, sx + 14, ty + 34, TEXT)

    # the footer: where the overlay comes from
    if stats.footer:
        text(stats.footer, "semibold", 8.5, PAD, H - PAD + 2, TEXT_FAINT)
    return out.convert("RGB")
