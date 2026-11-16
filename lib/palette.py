"""Derive an Ironhold palette from a piece of artwork (your own / personally-used wallpapers).

Images are decoded with the system gdk-pixbuf (JPEG, PNG, WebP...) via ctypes, downscaled,
clustered with k-means, and the clusters are mapped onto palette roles:
  metal  <- the strongest warm gold/bronze tone
  accent <- the most saturated banner color that isn't the metal
  bg/surfaces <- the hue of the darkest substantial region, kept very dark
Readability is enforced afterwards (text and trim contrast against the backgrounds).
"""
import colorsys
import ctypes
import ctypes.util
import random

_pb = ctypes.CDLL(ctypes.util.find_library("gdk_pixbuf-2.0") or "libgdk_pixbuf-2.0.so.0")
_go = ctypes.CDLL(ctypes.util.find_library("gobject-2.0") or "libgobject-2.0.so.0")
for fn, res, args in [
    ("gdk_pixbuf_new_from_file", ctypes.c_void_p, [ctypes.c_char_p, ctypes.c_void_p]),
    ("gdk_pixbuf_scale_simple", ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]),
    ("gdk_pixbuf_get_width", ctypes.c_int, [ctypes.c_void_p]),
    ("gdk_pixbuf_get_height", ctypes.c_int, [ctypes.c_void_p]),
    ("gdk_pixbuf_get_rowstride", ctypes.c_int, [ctypes.c_void_p]),
    ("gdk_pixbuf_get_n_channels", ctypes.c_int, [ctypes.c_void_p]),
    ("gdk_pixbuf_get_pixels", ctypes.POINTER(ctypes.c_ubyte), [ctypes.c_void_p]),
]:
    getattr(_pb, fn).restype = res
    getattr(_pb, fn).argtypes = args
_go.g_object_unref.argtypes = [ctypes.c_void_p]


def load_pixels(path, max_side=120):
    """Return a list of (r, g, b) floats 0..1 from an image file, downscaled."""
    pb = _pb.gdk_pixbuf_new_from_file(str(path).encode(), None)
    if not pb:
        raise SystemExit(f"Could not read image: {path}")
    w, h = _pb.gdk_pixbuf_get_width(pb), _pb.gdk_pixbuf_get_height(pb)
    k = max_side / max(w, h)
    sw, sh = max(1, int(w * k)), max(1, int(h * k))
    small = _pb.gdk_pixbuf_scale_simple(pb, sw, sh, 2)
    _go.g_object_unref(pb)
    stride, ch = _pb.gdk_pixbuf_get_rowstride(small), _pb.gdk_pixbuf_get_n_channels(small)
    raw = ctypes.string_at(_pb.gdk_pixbuf_get_pixels(small), stride * (sh - 1) + sw * ch)
    _go.g_object_unref(small)
    return [(raw[y * stride + x * ch] / 255, raw[y * stride + x * ch + 1] / 255, raw[y * stride + x * ch + 2] / 255)
            for y in range(sh) for x in range(sw)]


def kmeans(pixels, k=10, iters=12, seed=1):
    rng = random.Random(seed)
    centers = rng.sample(pixels, k)
    for _ in range(iters):
        groups = [[] for _ in centers]
        for p in pixels:
            i = min(range(len(centers)), key=lambda j: sum((a - b) ** 2 for a, b in zip(p, centers[j])))
            groups[i].append(p)
        centers = [tuple(sum(c) / len(g) for c in zip(*g)) if g else centers[i] for i, g in enumerate(groups)]
    return sorted(((c, len(g) / len(pixels)) for c, g in zip(centers, groups) if g), key=lambda t: -t[1])


# ---------------------------------------------------------------- color helpers
def hexc(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1, max(0, min(1, l)), max(0, min(1, s)))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def to_hls(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


def luminance(hex_):
    def lin(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(int(hex_[i:i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _hue_dist(a, b):
    d = abs(a - b) % 1
    return min(d, 1 - d)


def _ensure(fg, bg, ratio):
    """Lighten fg until it reaches the contrast ratio against bg."""
    h, l, s = to_hls(fg)
    while contrast(hexc(h, l, s), bg) < ratio and l < 0.97:
        l += 0.02
    return hexc(h, l, s)


# ---------------------------------------------------------------- mapping
def derive(paths, base):
    pixels = []
    for p in paths:
        pixels += load_pixels(p)
    clusters = [(colorsys.rgb_to_hls(*c), w) for c, w in kmeans(pixels)]

    # metal: warm (hue 20-62 deg), saturated, mid-bright; weighted by presence
    warm = [(hls, w) for hls, w in clusters if 20 / 360 <= hls[0] <= 62 / 360 and hls[2] > .3 and .25 < hls[1] < .85]
    if warm:
        (mh, ml, ms), _ = max(warm, key=lambda t: t[1] * t[0][2] * (1 - abs(t[0][1] - .5)))
        ms = max(ms, .55)
    else:
        mh, ml, ms = to_hls(base["metal"])

    # accent: most saturated non-metal hue with some presence
    # (lightness is normalized later, so dark-but-saturated reds/blues still count)
    cands = [(hls, w) for hls, w in clusters if _hue_dist(hls[0], mh) > 12 / 360 and hls[2] > .3 and .05 < hls[1] < .75]
    if not cands:  # artwork is essentially one hue family: use its most present saturated tone
        cands = [(hls, w) for hls, w in clusters if hls[2] > .3 and hls[1] > .05]
    if cands:
        (ah, al, as_), _ = max(cands, key=lambda t: t[0][2] * t[1] ** .5)
        as_ = max(as_, .5)
    else:
        ah, al, as_ = to_hls(base["accent"])

    # background hue: darkest region with meaningful area
    darks = sorted([(hls, w) for hls, w in clusters if w > .03], key=lambda t: t[0][1])
    bh, _, bs = darks[0][0] if darks else to_hls(base["bg"])
    bs = min(max(bs, .18), .4)

    c = dict(base)
    c.update({
        "bg_alt": hexc(bh, .045, bs), "bg": hexc(bh, .07, bs),
        "surface": hexc(bh, .11, bs), "surface_hi": hexc(bh, .16, bs),
        "border": hexc(bh, .26, bs * .8), "border_hi": hexc(bh, .36, bs * .8),
        "metal": hexc(mh, .52, ms), "metal_hi": hexc(mh, .72, ms), "metal_lo": hexc(mh, .3, ms),
        "accent": hexc(ah, .38, as_), "accent_hi": hexc(ah, .5, as_), "accent_lo": hexc(ah, .24, as_),
        "sky_top": hexc(bh, .03, bs), "sky_mid": hexc(ah, .14, as_ * .7), "sky_low": hexc(ah, .38, as_ * .7),
        "glow": hexc(mh, .74, min(1, ms + .2)),
        "steel_hi": hexc(bh, .86, .15), "steel": hexc(bh, .6, .12), "steel_lo": hexc(bh, .3, .15),
        "text": hexc(mh, .88, .35), "text_dim": hexc(mh, .62, .12),
        "parchment": hexc(mh, .8, .45), "ink": hexc(mh, .15, .45),
    })
    c["text"] = _ensure(c["text"], c["surface_hi"], 9)
    c["text_dim"] = _ensure(c["text_dim"], c["surface"], 4.5)
    c["metal_hi"] = _ensure(c["metal_hi"], c["surface"], 6)
    c["text_on_accent"] = "#ffffff" if contrast("#ffffff", c["accent"]) >= 4.5 else c["ink"]
    return c


def swatch_svg(name, c):
    keys = list(c)
    cells = "".join(
        f'<rect x="{10 + (i % 8) * 120}" y="{40 + (i // 8) * 80}" width="110" height="46" rx="4" fill="{c[k]}" stroke="#888"/>'
        f'<text x="{14 + (i % 8) * 120}" y="{102 + (i // 8) * 80}" font-family="sans-serif" font-size="12" fill="#ddd">{k}</text>'
        for i, k in enumerate(keys))
    h = 60 + ((len(keys) + 7) // 8) * 80
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="980" height="{h}"><rect width="100%" height="100%" fill="#222"/>'
            f'<text x="10" y="26" font-family="sans-serif" font-size="18" fill="#fff">{name}</text>{cells}</svg>'), h
