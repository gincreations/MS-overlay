"""Application-wide UI palette. Never used by game recognition or OCR."""
import re

MODE = "dark"
_NAMESPACES = []
# Explicit light counterparts for the original dark UI. Gold buttons retain dark ink.
LIGHT = {}
for target, originals in {
    "#f3f5f9": "#0b0c10 #0d0f14",
    "#ffffff": "#14161c #101218 #1a1d26 #1b1e28",
    "#edf1f7": "#13151b #12141a #13151c #1b1e26 #161920 #171a21 #181b23 #191c25 #1a1c24 #1c1f28 #1c2029 #1d2029",
    "#e4e9f1": "#232732 #1f232d #20242e #212530 #222631 #222733 #232731 #232733 #262b37 #272c38",
    "#d7dfeb": "#2c313e #262b36 #2a2f3b #303644",
    "#c3cddd": "#242833 #343a48 #393e49 #4a505d",
    "#1c2535": "#f1efe9 #e8e6e0 #f4f2ec",
    "#48566d": "#9ba1ad #b3b8c0",
    "#59677b": "#6c7280 #6b7079",
    "#805600": "#ffcc33 #ffd966 #e5b52b #d9b04a #e9c15a #ffcf4a #ffe58f #ffd25a #fff1c2",
    "#a06600": "#ffb71f",
    "#167242": "#5fd38a #5fe39a",
    "#9b4c09": "#ffb27a",
    "#b53129": "#ff7a5c #ff8a7a",
    "#dce7fb": "#272c3a",
    "#d9f1e3": "#1b2a24 #15221c",
    "#fbe2de": "#2b1c1b #231615",
}.items():
    LIGHT.update(dict.fromkeys(originals.split(), target))


def color(value):
    return LIGHT.get(value.lower(), value) if MODE == "light" else value


def _is_color(value):
    return isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value)


def _contains_color(value):
    if _is_color(value):
        return True
    if isinstance(value, dict):
        return any(_contains_color(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return any(_contains_color(v) for v in value)
    return False


def _mapped(value):
    if _is_color(value):
        return color(value)
    if isinstance(value, dict):
        return {k: _mapped(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(_mapped(v) for v in value)
    if isinstance(value, list):
        return [_mapped(v) for v in value]
    return value


def register(namespace):
    """Keep original palette values so repeated switches never accumulate changes."""
    originals = {k: v for k, v in namespace.items() if k.isupper() and _contains_color(v)}
    _NAMESPACES.append((namespace, originals))
    namespace.update({k: _mapped(v) for k, v in originals.items()})


def set_mode(mode):
    global MODE
    MODE = mode if mode in ("dark", "light") else "dark"
    for namespace, originals in _NAMESPACES:
        namespace.update({k: _mapped(v) for k, v in originals.items()})


COLOR_FIELDS = (("exp", "EXP / hr"), ("meso", "Mesos"), ("eta", "Time to level"), ("progress", "Progress bar"),
                ("potion1", "Potion card 1"), ("potion2", "Potion card 2"))
COLOR_PRESETS = {
    "dark": {
        "Ocean": {"exp": "#67d8ff", "meso": "#88e4b4", "eta": "#aec5ff", "progress": "#67d8ff"},
        "Mint": {"exp": "#75edb0", "meso": "#abe579", "eta": "#c4ecd8", "progress": "#75edb0"},
        "Rose": {"exp": "#ff9ecb", "meso": "#d4b0ff", "eta": "#ffc6df", "progress": "#ff9ecb"},
    },
    "light": {
        "Ocean": {"exp": "#00628a", "meso": "#146c43", "eta": "#3c4e9d", "progress": "#00759e"},
        "Mint": {"exp": "#126b44", "meso": "#456514", "eta": "#305e49", "progress": "#187b50"},
        "Rose": {"exp": "#a12660", "meso": "#7339a3", "eta": "#8a3159", "progress": "#ae2d6b"},
    },
}


def normalize_overrides(value):
    """Accept only known display colors; never interpret arbitrary config as Tk options."""
    if not isinstance(value, dict):
        return {}
    return {key: value[key].strip().lower() for key, _ in COLOR_FIELDS
            if isinstance(value.get(key), str) and _is_color(value[key].strip())}


def normalize_colors(value):
    if not isinstance(value, dict):
        return {}
    return {mode: normalize_overrides(value.get(mode)) for mode in ("dark", "light")}


def color_defaults():
    return {"exp": color("#ffe58f"), "meso": color("#f1efe9"),
            "eta": color("#e9c15a"), "progress": "#ffb21f",
            "potion1": color("#ffb27a"), "potion2": color("#5fe39a")}


def contrast_ratio(a, b):
    def luminance(value):
        channels = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in channels]
        return sum(x * weight for x, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    x, y = sorted((luminance(a), luminance(b)))
    return (y + 0.05) / (x + 0.05)
