"""Procedural, original artwork for Ironhold: cursors, icons, wallpapers, emblems.

Every function takes the variant palette `c` (dict of hex colors) and returns SVG text.
"""
import math
import random

SVG = 'xmlns="http://www.w3.org/2000/svg"'


def _metal_defs(c, pre=""):
    return f"""
  <linearGradient id="{pre}metal" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{c['metal_hi']}"/><stop offset=".55" stop-color="{c['metal']}"/>
    <stop offset="1" stop-color="{c['metal_lo']}"/></linearGradient>
  <linearGradient id="{pre}steel" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{c['steel_hi']}"/><stop offset=".5" stop-color="{c['steel']}"/>
    <stop offset="1" stop-color="{c['steel_lo']}"/></linearGradient>
  <linearGradient id="{pre}banner" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{c['accent_hi']}"/><stop offset="1" stop-color="{c['accent_lo']}"/></linearGradient>
  <radialGradient id="{pre}gem" cx=".35" cy=".35" r=".7">
    <stop offset="0" stop-color="#ffffff"/><stop offset=".25" stop-color="{c['accent_hi']}"/>
    <stop offset="1" stop-color="{c['accent_lo']}"/></radialGradient>"""


# ======================================================================= runes
def rune_glyph(rng, x, y, w, h, stroke, width):
    """An original rune: one stave plus a few angular branches."""
    cx = x + w / 2
    parts = [f"M{cx:.1f} {y:.1f}V{y + h:.1f}"]
    for _ in range(rng.randint(1, 3)):
        y0 = y + h * rng.choice([0, .25, .5])
        side = rng.choice([-1, 1])
        kind = rng.random()
        if kind < .4:
            parts.append(f"M{cx:.1f} {y0:.1f}L{cx + side * w / 2:.1f} {y0 + h / 4:.1f}")
        elif kind < .75:
            parts.append(f"M{cx:.1f} {y0:.1f}L{cx + side * w / 2:.1f} {y0 + h / 4:.1f}L{cx:.1f} {y0 + h / 2:.1f}")
        else:
            parts.append(f"M{cx - w / 2:.1f} {y0:.1f}L{cx + w / 2:.1f} {y0 + h / 3:.1f}")
    return (f'<path d="{" ".join(parts)}" fill="none" stroke="{stroke}" stroke-width="{width}" '
            f'stroke-linecap="square" stroke-linejoin="miter"/>')


def rune_ring(c, cx, cy, r, count, size, seed=7, stroke=None, width=None):
    rng = random.Random(seed)
    stroke = stroke or c["metal_hi"]
    width = width or max(1, size / 7)
    out = []
    for i in range(count):
        a = 360 * i / count
        g = rune_glyph(rng, -size * .3, -size / 2, size * .6, size, stroke, width)
        out.append(f'<g transform="rotate({a:.2f} {cx} {cy}) translate({cx} {cy - r})">{g}</g>')
    return "\n".join(out)


# ======================================================================= emblem
def emblem(c, kind, pre="e"):
    """Original crest in a 200x200 box: kite shield + sword (Crown) or round shield + crossed axes (Ember)."""
    if kind == "sword":
        body = f"""
  <path d="M100 18 L164 40 C164 110 140 150 100 182 C60 150 36 110 36 40 Z"
        fill="url(#{pre}banner)" stroke="url(#{pre}metal)" stroke-width="9" stroke-linejoin="round"/>
  <path d="M100 34 L150 51 C150 108 131 140 100 166 C69 140 50 108 50 51 Z"
        fill="none" stroke="{c['metal_lo']}" stroke-width="2" opacity=".8"/>
  <path d="M93 22 L100 6 L107 22 L107 140 L100 156 L93 140 Z" fill="url(#{pre}steel)" stroke="{c['bg_alt']}" stroke-width="2"/>
  <path d="M100 12 V146" stroke="{c['steel_hi']}" stroke-width="1.5" opacity=".7"/>
  <path d="M62 130 Q100 118 138 130 L138 140 Q100 130 62 140 Z" fill="url(#{pre}metal)" stroke="{c['bg_alt']}" stroke-width="2"/>
  <rect x="94" y="140" width="12" height="30" rx="3" fill="{c['metal_lo']}" stroke="{c['bg_alt']}" stroke-width="2"/>
  <circle cx="100" cy="180" r="9" fill="url(#{pre}gem)" stroke="url(#{pre}metal)" stroke-width="3"/>"""
    else:
        spikes = "".join(
            f'<path d="M0 -86 L7 -74 L-7 -74 Z" fill="url(#{pre}steel)" transform="translate(100 100) rotate({a})"/>'
            for a in range(0, 360, 30))
        axe = (f'<g><rect x="96" y="22" width="8" height="160" rx="3" fill="{c["metal_lo"]}" stroke="{c["bg_alt"]}" stroke-width="2"/>'
               f'<path d="M104 30 C140 22 158 44 160 70 C146 62 128 66 104 74 Z" fill="url(#{pre}steel)" stroke="{c["bg_alt"]}" stroke-width="2.5"/>'
               f'<path d="M96 34 C76 32 66 44 64 58 C74 54 84 56 96 62 Z" fill="url(#{pre}steel)" stroke="{c["bg_alt"]}" stroke-width="2.5"/>'
               f'<path d="M108 35 C134 31 148 46 152 62" fill="none" stroke="{c["steel_hi"]}" stroke-width="2" opacity=".7"/></g>')
        body = f"""
  {spikes}
  <circle cx="100" cy="100" r="74" fill="url(#{pre}banner)" stroke="url(#{pre}metal)" stroke-width="9"/>
  <circle cx="100" cy="100" r="60" fill="none" stroke="{c['metal_lo']}" stroke-width="2" stroke-dasharray="6 5"/>
  <g transform="rotate(-32 100 100)">{axe}</g>
  <g transform="rotate(32 100 100) translate(200 0) scale(-1 1)">{axe}</g>
  <circle cx="100" cy="100" r="11" fill="url(#{pre}gem)" stroke="url(#{pre}metal)" stroke-width="3"/>"""
    return body


def sigil_svg(c, kind, size=256):
    """Standalone emblem (used for start-here / logo icons)."""
    return f"""<svg {SVG} width="{size}" height="{size}" viewBox="-20 -20 240 240">
<defs>{_metal_defs(c, 'e')}</defs>
<circle cx="100" cy="100" r="112" fill="{c['bg_alt']}" stroke="url(#emetal)" stroke-width="6"/>
{rune_ring(c, 100, 100, 101, 24, 9, seed=3, stroke=c['metal'], width=1.6)}
<g transform="translate(100 100) scale(.78) translate(-100 -100)">{emblem(c, kind)}</g>
</svg>"""


# ======================================================================= cursors (32x32 design grid)
ARROW = "M3 2 L3 25 L9 19.5 L13 28.5 L17 26.8 L13.2 18 L21 18 Z"
HAND = ("M9.5 4.2 a2 2 0 0 1 4 0 V12.5 h.8 V11.3 a2 2 0 0 1 4 0 V13 h.4 a2 2 0 0 1 4 0 V14.6 "
        "a2 2 0 0 1 3.6 1.2 V21.5 c0 4.3 -3 7.3 -7.3 7.3 h-3.8 c-3 0 -5 -1.4 -6.6 -4 L4.4 19.2 "
        "a2 2 0 0 1 3.2 -2.4 L9.5 19 Z")


def _cursor(c, body):
    return f"""<svg {SVG} width="32" height="32" viewBox="0 0 32 32">
<defs>{_metal_defs(c, 'c')}</defs>{body}</svg>"""


def _shadowed(d, c, fill="url(#csteel)", stroke=None, transform=""):
    stroke = stroke or c["metal_lo"]
    t = f' transform="{transform}"' if transform else ""
    return (f'<g{t}><path d="{d}" transform="translate(.9 1.1)" fill="#000" opacity=".38"/>'
            f'<path d="{d}" fill="{c["bg_alt"]}" stroke="{c["bg_alt"]}" stroke-width="3" stroke-linejoin="round"/>'
            f'<path d="{d}" fill="{fill}" stroke="url(#cmetal)" stroke-width="1.4" stroke-linejoin="round"/></g>')


def _ring(c, cx, cy, r, angle, w=2.4):
    ticks = "".join(
        f'<rect x="{cx - .6:.2f}" y="{cy - r - w / 2 - .2:.2f}" width="1.2" height="{w + .4:.2f}" '
        f'fill="{c["bg_alt"]}" transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 45))
    arc_len = 2 * math.pi * r
    return (f'<circle cx="{cx}" cy="{cy}" r="{r + w / 2 + .8}" fill="{c["bg_alt"]}" opacity=".85"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#cmetal)" stroke-width="{w}"/>'
            f'<g transform="rotate({angle} {cx} {cy})">{ticks}'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c["glow"]}" stroke-width="{w * .7:.2f}" '
            f'stroke-dasharray="{arc_len * .22:.2f} {arc_len:.2f}" stroke-linecap="round"/></g>'
            f'<circle cx="{cx}" cy="{cy}" r="{max(1.2, r * .38):.2f}" fill="url(#cgem)"/>')


def _double_arrow(c, rot):
    d = "M16 2 L22.5 9.5 H18.2 V22.5 H22.5 L16 30 L9.5 22.5 H13.8 V9.5 H9.5 Z"
    return _cursor(c, _shadowed(d, c, transform=f"rotate({rot} 16 16)"))


def cursor_svgs(c):
    """Return {name: (svg_or_list_of_frames, hotspot32, frame_ms)}."""
    arrow = _shadowed(ARROW, c) + f'<path d="M4.6 6 V20.5" stroke="{c["steel_hi"]}" stroke-width=".9" opacity=".8"/>'
    hand = (_shadowed(HAND, c)
            + f'<path d="M9.8 9 h3.4 M14.6 15 h3.6 M18.6 15.2 h3.6 M10 24.6 Q16 23.2 24.4 24.2" '
              f'stroke="url(#cmetal)" stroke-width="1.3" fill="none"/>')
    ibeam = (f'<path d="M11 4 H21 L19 6.4 H17.2 V25.6 H19 L21 28 H11 L13 25.6 H14.8 V6.4 H13 Z" '
             f'fill="url(#cmetal)" stroke="{c["bg_alt"]}" stroke-width="1.6" stroke-linejoin="round"/>'
             f'<path d="M16 15 l1.6 1 -1.6 1 -1.6 -1 z" fill="{c["glow"]}"/>')
    cross = (f'<g stroke="{c["bg_alt"]}" stroke-width="3.6" fill="none"><circle cx="16" cy="16" r="8.5"/>'
             f'<path d="M16 2v8M16 22v8M2 16h8M22 16h8"/></g>'
             f'<g stroke="url(#cmetal)" stroke-width="1.6" fill="none"><circle cx="16" cy="16" r="8.5"/>'
             f'<path d="M16 2v8M16 22v8M2 16h8M22 16h8"/></g><circle cx="16" cy="16" r="1.6" fill="{c["glow"]}"/>')
    nope = (f'<circle cx="16" cy="16" r="11.5" fill="{c["bg_alt"]}" opacity=".55" stroke="{c["bg_alt"]}" stroke-width="5"/>'
            f'<circle cx="16" cy="16" r="11.5" fill="none" stroke="{c["danger"]}" stroke-width="3"/>'
            f'<path d="M8 8 L24 24" stroke="{c["bg_alt"]}" stroke-width="6"/><path d="M8 8 L24 24" stroke="{c["danger"]}" stroke-width="3"/>')
    fleur = _shadowed("M16 1.5 L21 7 H17.6 V14.4 H25 V11 L30.5 16 L25 21 V17.6 H17.6 V25 H21 L16 30.5 "
                      "L11 25 H14.4 V17.6 H7 V21 L1.5 16 L7 11 V14.4 H14.4 V7 H11 Z", c)
    help_ = (arrow + f'<circle cx="23.5" cy="23.5" r="7" fill="url(#cgem)" stroke="url(#cmetal)" stroke-width="1.4"/>'
             f'<text x="23.5" y="27.4" font-family="DejaVu Serif, serif" font-weight="bold" font-size="11" '
             f'text-anchor="middle" fill="{c["text_on_accent"]}">?</text>')
    frames = 12
    wait = [_cursor(c, _ring(c, 16, 16, 10, i * 360 / frames, 3.2)) for i in range(frames)]
    progress = [_cursor(c, arrow + _ring(c, 24, 24, 5.2, i * 360 / frames, 2.2)) for i in range(frames)]
    return {
        "default": (_cursor(c, arrow), (3, 2), 0),
        "pointer": (_cursor(c, hand), (11, 2), 0),
        "text": (_cursor(c, ibeam), (16, 16), 0),
        "crosshair": (_cursor(c, cross), (16, 16), 0),
        "not-allowed": (_cursor(c, nope), (16, 16), 0),
        "move": (_cursor(c, fleur), (16, 16), 0),
        "help": (_cursor(c, help_), (3, 2), 0),
        "ns-resize": (_double_arrow(c, 0), (16, 16), 0),
        "ew-resize": (_double_arrow(c, 90), (16, 16), 0),
        "nwse-resize": (_double_arrow(c, -45), (16, 16), 0),
        "nesw-resize": (_double_arrow(c, 45), (16, 16), 0),
        "wait": (wait, (16, 16), 60),
        "progress": (progress, (3, 2), 60),
    }


CURSOR_ALIASES = {
    "default": ["left_ptr", "arrow", "top_left_arrow", "right_ptr", "context-menu", "dnd-none", "center_ptr"],
    "pointer": ["hand", "hand1", "hand2", "pointing_hand", "grab", "openhand", "grabbing", "closedhand",
                "dnd-move", "e29285e634086352946a0e7090d73106", "9d800788f1b08800ae810202380a0822",
                "fleur-grab", "alias", "copy", "dnd-copy", "dnd-link", "link"],
    "text": ["xterm", "ibeam", "vertical-text"],
    "crosshair": ["cross", "tcross", "cross_reverse", "diamond_cross", "cell", "plus", "color-picker", "pencil"],
    "not-allowed": ["crossed_circle", "forbidden", "circle", "no-drop", "dnd-no-drop",
                    "03b6e0fcb3499374a867c041f52298f0", "X_cursor", "pirate"],
    "move": ["fleur", "all-scroll", "size_all", "4498f0e0c1937ffe01fd06f973665830",
             "9081237383d90e509aa00f00170e968f"],
    "help": ["question_arrow", "whats_this", "left_ptr_help", "dnd-ask",
             "5c6cd98b3f3ebcb1f9c7f1c204630408", "d9ce0ab605698f320427677b458ad60b"],
    "ns-resize": ["sb_v_double_arrow", "row-resize", "size_ver", "v_double_arrow", "n-resize", "s-resize",
                  "top_side", "bottom_side", "split_v", "up-arrow", "00008160000006810000408080010102"],
    "ew-resize": ["sb_h_double_arrow", "col-resize", "size_hor", "h_double_arrow", "e-resize", "w-resize",
                  "left_side", "right_side", "split_h", "028006030e0e7ebffc7f7070c0600140"],
    "nwse-resize": ["size_fdiag", "bd_double_arrow", "nw-resize", "se-resize", "top_left_corner",
                    "bottom_right_corner", "c7088f0f3e6c8088236ef8e1e3e70000"],
    "nesw-resize": ["size_bdiag", "fd_double_arrow", "ne-resize", "sw-resize", "top_right_corner",
                    "bottom_left_corner", "fcf1c3c7cd4491d801f1e1c78f100000"],
    "wait": ["watch"],
    "progress": ["left_ptr_watch", "half-busy", "08e8e1c95fe2fc01f976f1e063a24ccd",
                 "3ecb610c1bf2410f44200f48c40d3599"],
}

# Windows cursor-scheme role -> our cursor name
WINDOWS_CURSORS = {
    "Arrow": "default", "Help": "help", "AppStarting": "progress", "Wait": "wait",
    "Crosshair": "crosshair", "IBeam": "text", "NWPen": "crosshair", "No": "not-allowed",
    "SizeNS": "ns-resize", "SizeWE": "ew-resize", "SizeNWSE": "nwse-resize", "SizeNESW": "nesw-resize",
    "SizeAll": "move", "UpArrow": "default", "Hand": "pointer", "Pin": "pointer", "Person": "pointer",
}


# ======================================================================= icons (128x128)
GLYPHS = {
    "folder": "",
    "folder-documents": "M50 62 h28 a4 4 0 0 1 0 8 h-2 v22 a4 4 0 0 1 -4 4 h-28 a4 4 0 0 1 0 -8 h2 v-22 a4 4 0 0 1 4 -4 z M56 74 h14 M56 81 h14",
    "folder-download": "M58 58 h12 v18 h9 l-15 16 -15 -16 h9 z M46 96 h36",
    "folder-music": "M58 60 l20 -4 v28 a6 5 0 1 1 -4 -4.6 v-14 l-12 2.4 v20 a6 5 0 1 1 -4 -4.6 z",
    "folder-pictures": "M44 94 l14 -20 10 12 6 -8 12 16 z M76 66 a5 5 0 1 0 0.01 0",
    "folder-videos": "M54 60 l30 18 -30 18 z",
    "folder-desktop": "M44 60 h40 v26 h-40 z M58 92 h12 M64 86 v6",
    "folder-templates": "M46 60 h14 v14 h-14 z M68 60 h14 v14 h-14 z M46 82 h14 v14 h-14 z M68 82 h14 v14 h-14 z",
    "folder-publicshare": "M50 56 v42 M50 58 h30 l-6 9 6 9 h-30",
    "folder-remote": "M64 62 a5 5 0 1 0 .01 0 M48 88 a5 5 0 1 0 .01 0 M80 88 a5 5 0 1 0 .01 0 M64 67 L50 84 M64 67 L78 84 M53 92 h22",
    "user-home": "M50 98 v-26 h-4 v-10 h6 v4 h6 v-4 h6 v4 h6 v-4 h6 v10 h-4 v26 h-8 v-10 a4 4 0 0 0 -8 0 v10 z",
}
GLYPH_STROKED = {"folder-documents", "folder-desktop", "folder-publicshare", "folder-remote"}


def folder_svg(c, name):
    glyph = GLYPHS.get(name, "")
    if glyph:
        if name in GLYPH_STROKED:
            g = (f'<path d="{glyph}" fill="none" stroke="{c["bg_alt"]}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round" opacity=".5"/>'
                 f'<path d="{glyph}" fill="none" stroke="url(#imetal)" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
        else:
            g = (f'<path d="{glyph}" fill="{c["bg_alt"]}" stroke="{c["bg_alt"]}" stroke-width="4" stroke-linejoin="round" opacity=".5"/>'
                 f'<path d="{glyph}" fill="url(#imetal)" stroke="{c["metal_lo"]}" stroke-width="1" stroke-linejoin="round"/>')
    else:
        g = f'<circle cx="64" cy="78" r="9" fill="url(#igem)" stroke="url(#imetal)" stroke-width="3"/>'
    rivets = "".join(f'<circle cx="{x}" cy="{y}" r="2.2" fill="{c["metal_hi"]}" stroke="{c["metal_lo"]}" stroke-width=".8"/>'
                     for x, y in [(18, 50), (110, 50), (18, 108), (110, 108)])
    return f"""<svg {SVG} width="128" height="128" viewBox="0 0 128 128">
<defs>{_metal_defs(c, 'i')}
  <linearGradient id="leather" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{c['accent']}"/><stop offset="1" stop-color="{c['accent_lo']}"/></linearGradient>
  <pattern id="grain" width="6" height="6" patternUnits="userSpaceOnUse">
    <path d="M0 6 L6 0" stroke="#000" stroke-width=".6" opacity=".12"/></pattern>
</defs>
<path d="M10 28 a6 6 0 0 1 6 -6 h30 l8 8 h58 a6 6 0 0 1 6 6 v72 h-108 z" fill="{c['accent_lo']}" stroke="{c['bg_alt']}" stroke-width="2"/>
<rect x="16" y="32" width="96" height="30" rx="2" fill="{c['parchment']}" opacity=".9"/>
<path d="M22 40 h60 M22 47 h44" stroke="{c['ink']}" stroke-width="1.6" opacity=".35"/>
<path d="M8 46 a6 6 0 0 1 6 -6 h100 a6 6 0 0 1 6 6 v62 a8 8 0 0 1 -8 8 h-96 a8 8 0 0 1 -8 -8 z"
      fill="url(#leather)" stroke="{c['bg_alt']}" stroke-width="2"/>
<path d="M8 46 a6 6 0 0 1 6 -6 h100 a6 6 0 0 1 6 6 v62 a8 8 0 0 1 -8 8 h-96 a8 8 0 0 1 -8 -8 z" fill="url(#grain)"/>
<path d="M14 44 h100" stroke="#fff" stroke-width="1.2" opacity=".18"/>
<path d="M8 58 v-12 a6 6 0 0 1 6 -6 h12 v8 h-10 v10 z M120 58 v-12 a6 6 0 0 0 -6 -6 h-12 v8 h10 v10 z
         M8 98 v10 a8 8 0 0 0 8 8 h12 v-8 h-12 v-10 z M120 98 v10 a8 8 0 0 1 -8 8 h-12 v-8 h12 v-10 z"
      fill="url(#imetal)" stroke="{c['bg_alt']}" stroke-width="1.2"/>
<rect x="8" y="72" width="112" height="3" fill="{c['metal_lo']}" opacity=".6"/>
{rivets}
{g}
</svg>"""


def trash_svg(c, full):
    papers = ""
    if full:
        papers = (f'<path d="M40 30 l18 -10 10 16 -18 8 z" fill="{c["parchment"]}" stroke="{c["ink"]}" stroke-width="1.2"/>'
                  f'<path d="M62 26 l24 2 -2 16 -22 -2 z" fill="{c["parchment"]}" stroke="{c["ink"]}" stroke-width="1.2"/>'
                  f'<path d="M48 34 h36" stroke="{c["ink"]}" stroke-width="1" opacity=".4"/>')
    bands = "".join(f'<path d="M{x0} {y} Q64 {y + 5} {128 - x0} {y}" fill="none" stroke="url(#imetal)" stroke-width="6"/>'
                    for x0, y in [(28, 50), (24, 78), (28, 106)])
    staves = "".join(f'<path d="M{x} 40 Q{x + (x - 64) * .18:.1f} 78 {x} 116" stroke="#000" stroke-width="1.2" opacity=".3" fill="none"/>'
                     for x in range(40, 96, 10))
    return f"""<svg {SVG} width="128" height="128" viewBox="0 0 128 128">
<defs>{_metal_defs(c, 'i')}
  <linearGradient id="wood" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#3a2416"/><stop offset=".45" stop-color="#7a5232"/><stop offset="1" stop-color="#2e1b10"/></linearGradient>
</defs>
<ellipse cx="64" cy="118" rx="38" ry="6" fill="#000" opacity=".35"/>
{papers}
<path d="M30 40 Q22 78 30 116 H98 Q106 78 98 40 Z" fill="url(#wood)" stroke="{c['bg_alt']}" stroke-width="2"/>
{staves}
<ellipse cx="64" cy="40" rx="34" ry="8" fill="#1d120b" stroke="url(#imetal)" stroke-width="4"/>
{bands}
</svg>"""


def icon_svgs(c, emblem_kind):
    icons = {name: folder_svg(c, name) for name in GLYPHS}
    icons["user-trash"] = trash_svg(c, False)
    icons["user-trash-full"] = trash_svg(c, True)
    icons["start-here"] = sigil_svg(c, emblem_kind, 128)
    return icons


ICON_ALIASES = {
    "folder": ["inode-directory", "folder-new", "gtk-directory", "default-folder"],
    "folder-download": ["folder-downloads"],
    "folder-desktop": ["user-desktop"],
    "folder-publicshare": ["folder-public"],
    "folder-remote": ["folder-network", "network-workgroup"],
    "user-home": ["folder-home", "gnome-fs-home"],
    "user-trash": ["trashcan_empty", "gnome-fs-trash-empty"],
    "user-trash-full": ["trashcan_full", "gnome-fs-trash-full"],
    "start-here": ["distributor-logo", "view-app-grid-symbolic-ironhold"],
}


# ======================================================================= wallpapers (3840x2160)
W, H = 3840, 2160


def _castle(c, x, base, scale, spiky):
    """Silhouette keep built from blocks; returns (silhouette, windows, banners)."""
    s = scale
    dark = c["bg_alt"]
    parts, wins, flags = [], [], []

    def tower(tx, tw, th, roof):
        top = base - th
        parts.append(f'<rect x="{tx}" y="{top}" width="{tw}" height="{th}"/>')
        merl = int(max(6, tw // 6))
        for mx in range(int(tx), int(tx + tw), merl * 2):
            parts.append(f'<rect x="{mx}" y="{top - merl}" width="{merl}" height="{merl}"/>')
        if roof:
            rh = tw * (1.6 if not spiky else 1.0)
            if spiky:
                parts.append(f'<path d="M{tx - tw * .15} {top - merl} L{tx + tw * .2} {top - rh} L{tx + tw * .4} {top - merl} '
                             f'L{tx + tw / 2} {top - rh * 1.4} L{tx + tw * .6} {top - merl} L{tx + tw * .8} {top - rh} '
                             f'L{tx + tw * 1.15} {top - merl} Z"/>')
            else:
                parts.append(f'<path d="M{tx - tw * .1} {top - merl} L{tx + tw / 2} {top - rh} L{tx + tw * 1.1} {top - merl} Z"/>')
            pole_top = top - rh - (60 * s if not spiky else rh * .5 + 40 * s)
            flags.append((tx + tw / 2, pole_top, top - rh * (1.4 if spiky else 1) + 4))
        for wy in range(int(top + 40 * s), int(base - 30 * s), int(70 * s)):
            wins.append(f'<rect x="{tx + tw / 2 - 5 * s}" y="{wy}" width="{10 * s}" height="{22 * s}" rx="{5 * s}"/>')

    tower(x - 260 * s, 520 * s, 260 * s, False)               # curtain wall
    tower(x - 330 * s, 120 * s, 420 * s, True)
    tower(x + 210 * s, 120 * s, 400 * s, True)
    tower(x - 110 * s, 220 * s, 640 * s, True)                # keep
    tower(x + 40 * s, 90 * s, 520 * s, True)
    tower(x - 175 * s, 70 * s, 470 * s, True)
    parts.append(f'<path d="M{x - 60 * s} {base} v-{90 * s} a{50 * s} {50 * s} 0 0 1 {100 * s} 0 v{90 * s} z" fill="{c["glow"]}" opacity=".25"/>')
    banners = []
    for fx, top, bottom in flags:
        banners.append(f'<path d="M{fx} {bottom} V{top}" stroke="{dark}" stroke-width="{5 * s}"/>')
        if spiky:
            banners.append(f'<path d="M{fx} {top} h{70 * s} l-{14 * s} {22 * s} l{14 * s} {22 * s} h-{70 * s} z" fill="{c["accent"]}"/>')
        else:
            banners.append(f'<path d="M{fx} {top} h{60 * s} q-{10 * s} {14 * s} 0 {30 * s} h-{60 * s} z" fill="{c["accent"]}"/>'
                           f'<path d="M{fx} {top} h{60 * s}" stroke="{c["metal"]}" stroke-width="{4 * s}"/>')
    return "".join(parts), "".join(wins), "".join(banners)


def _ridge(rng, y, amp, step, jag):
    pts = [f"M0 {H}", f"L0 {y}"]
    x = 0
    cur = y
    while x < W:
        x += step * rng.uniform(.6, 1.4)
        cur = y + rng.uniform(-amp, amp) * (1 if rng.random() > jag else 1.8)
        pts.append(f"L{x:.0f} {cur:.0f}")
    pts.append(f"L{W} {H} Z")
    return " ".join(pts)


def _rgbf(hex_, i):
    return f"{int(hex_[1 + 2 * i:3 + 2 * i], 16) / 255:.3f}"


def wallpaper_citadel(c, spiky, seed=11):
    rng = random.Random(seed)
    stars = "".join(f'<circle cx="{rng.uniform(0, W):.0f}" cy="{rng.uniform(0, H * .55):.0f}" '
                    f'r="{rng.choice([1.2, 1.6, 2.2, 3]):.1f}" opacity="{rng.uniform(.25, .95):.2f}"/>' for _ in range(420))
    embers = ""
    if spiky:
        embers = "".join(f'<circle cx="{rng.uniform(0, W):.0f}" cy="{rng.uniform(H * .3, H):.0f}" '
                         f'r="{rng.uniform(2, 7):.1f}" fill="{c["glow"]}" opacity="{rng.uniform(.2, .8):.2f}"/>' for _ in range(160))
    sil, wins, banners = _castle(c, 2520, 1540, 1.35, spiky)
    moon_x, moon_y = (2050, 560) if spiky else (2900, 470)
    return f"""<svg {SVG} width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{c['sky_top']}"/><stop offset=".55" stop-color="{c['sky_mid']}"/>
    <stop offset=".8" stop-color="{c['sky_low']}"/><stop offset="1" stop-color="{c['sky_mid']}"/></linearGradient>
  <radialGradient id="moonglow"><stop offset="0" stop-color="{c['glow']}" stop-opacity=".55"/>
    <stop offset=".3" stop-color="{c['glow']}" stop-opacity=".18"/><stop offset="1" stop-color="{c['glow']}" stop-opacity="0"/></radialGradient>
  <linearGradient id="mist" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{c['sky_low']}" stop-opacity="0"/><stop offset=".5" stop-color="{c['sky_low']}" stop-opacity=".35"/>
    <stop offset="1" stop-color="{c['sky_low']}" stop-opacity="0"/></linearGradient>
  <filter id="clouds" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency=".0009 .0042" numOctaves="5" seed="8"/>
    <feColorMatrix type="matrix" values="0 0 0 0 {_rgbf(c['sky_low'], 0)}  0 0 0 0 {_rgbf(c['sky_low'], 1)}  0 0 0 0 {_rgbf(c['sky_low'], 2)}  2.4 0 0 0 -1.05"/>
  </filter>
  <linearGradient id="cloudfadeg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff" stop-opacity=".25"/><stop offset=".55" stop-color="#fff" stop-opacity=".8"/>
    <stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <mask id="cloudfade"><rect width="{W}" height="1500" fill="url(#cloudfadeg)"/></mask>
  <radialGradient id="vig" cx=".5" cy=".5" r=".75"><stop offset=".6" stop-color="#000" stop-opacity="0"/>
    <stop offset="1" stop-color="#000" stop-opacity=".65"/></radialGradient>
</defs>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
<g fill="{c['text']}">{stars}</g>
<circle cx="{moon_x}" cy="{moon_y}" r="900" fill="url(#moonglow)"/>
<circle cx="{moon_x}" cy="{moon_y}" r="170" fill="{c['glow']}" opacity=".92"/>
<circle cx="{moon_x + 40}" cy="{moon_y - 25}" r="150" fill="{c['parchment']}" opacity=".35"/>
<rect width="{W}" height="1500" filter="url(#clouds)" mask="url(#cloudfade)"/>
<path d="{_ridge(rng, 1250, 110, 160, .8)}" fill="{c['sky_mid']}" opacity=".85"/>
<rect y="1150" width="{W}" height="320" fill="url(#mist)"/>
<path d="{_ridge(rng, 1430, 70, 120, .7)}" fill="{c['sky_top']}" opacity=".8"/>
<g fill="{c['bg_alt']}">
  <path d="M1700 {H} L1900 1600 L2200 1540 L2950 1540 L3200 1590 L3500 1720 L3840 1700 L3840 {H} Z"/>
  {sil}
</g>
<g fill="{c['glow']}" opacity=".9">{wins}</g>
{banners}
<path d="{_ridge(rng, 1900, 60, 90, .5)}" fill="{c['bg_alt']}"/>
<g>{embers}</g>
<rect width="{W}" height="{H}" fill="url(#vig)"/>
</svg>"""


def wallpaper_sigil(c, kind, seed=5):
    rng = random.Random(seed)
    cx, cy = W / 2, H / 2
    cracks = "".join(
        f'<path d="M{x:.0f} {y:.0f} l{rng.uniform(-80, 80):.0f} {rng.uniform(20, 90):.0f} l{rng.uniform(-60, 60):.0f} {rng.uniform(20, 70):.0f}" '
        f'stroke="#000" stroke-width="{rng.uniform(1, 3):.1f}" opacity=".35" fill="none"/>'
        for x, y in ((rng.uniform(0, W), rng.uniform(0, H)) for _ in range(90)))
    blocks = []
    bh, bw = 240, 480
    for row in range(H // bh + 1):
        off = (bw / 2) * (row % 2)
        for col in range(-1, W // bw + 2):
            shade = rng.uniform(-.06, .06)
            blocks.append(f'<rect x="{col * bw + off + 4:.0f}" y="{row * bh + 4}" width="{bw - 8}" height="{bh - 8}" rx="10" '
                          f'fill="{"#fff" if shade > 0 else "#000"}" opacity="{abs(shade):.3f}"/>')
    return f"""<svg {SVG} width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>{_metal_defs(c, 'e')}
  <radialGradient id="stone" cx=".5" cy=".5" r=".7"><stop offset="0" stop-color="{c['surface_hi']}"/>
    <stop offset=".6" stop-color="{c['surface']}"/><stop offset="1" stop-color="{c['bg_alt']}"/></radialGradient>
  <radialGradient id="halo"><stop offset="0" stop-color="{c['glow']}" stop-opacity=".35"/>
    <stop offset=".5" stop-color="{c['glow']}" stop-opacity=".08"/><stop offset="1" stop-color="{c['glow']}" stop-opacity="0"/></radialGradient>
  <filter id="grit" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="4"/>
    <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .22 0"/></filter>
  <radialGradient id="vig" cx=".5" cy=".5" r=".72"><stop offset=".55" stop-color="#000" stop-opacity="0"/>
    <stop offset="1" stop-color="#000" stop-opacity=".75"/></radialGradient>
</defs>
<rect width="{W}" height="{H}" fill="url(#stone)"/>
<g stroke="#000" stroke-opacity=".45" stroke-width="6" fill="none">
  {"".join(f'<path d="M0 {r * bh} H{W}"/>' for r in range(1, H // bh + 1))}
</g>
{"".join(blocks)}
{cracks}
<rect width="{W}" height="{H}" filter="url(#grit)"/>
<circle cx="{cx}" cy="{cy}" r="900" fill="url(#halo)"/>
<circle cx="{cx}" cy="{cy}" r="610" fill="{c['bg_alt']}" opacity=".55"/>
<circle cx="{cx}" cy="{cy}" r="600" fill="none" stroke="url(#emetal)" stroke-width="22"/>
<circle cx="{cx}" cy="{cy}" r="560" fill="none" stroke="{c['metal_lo']}" stroke-width="4"/>
<circle cx="{cx}" cy="{cy}" r="470" fill="none" stroke="url(#emetal)" stroke-width="10"/>
{rune_ring(c, cx, cy, 515, 36, 56, seed=21, stroke=c['metal_hi'], width=6)}
<g transform="translate({cx} {cy}) scale(3.9) translate(-100 -100)">{emblem(c, kind)}</g>
<rect width="{W}" height="{H}" fill="url(#vig)"/>
</svg>"""


def wallpapers(c, kind, spiky):
    return {"citadel": wallpaper_citadel(c, spiky), "sigil": wallpaper_sigil(c, kind)}


# ======================================================================= ornate UI assets (original designs)
def frame_svg(c, size=96, s=24):
    """9-slice border-image: forged iron band, double gilded rule, filigree corner pieces with a gem.
    The centre is left empty (border-image without `fill`)."""
    corner = f"""
  <path d="M3 3 H{s + 4} M3 3 V{s + 4}" stroke="{c['bg_alt']}" stroke-width="6" stroke-linecap="square"/>
  <path d="M4 {s - 2} C4 10 10 4 {s - 2} 4" fill="none" stroke="url(#fmetal)" stroke-width="2.4"/>
  <path d="M{s - 2} 4 c3 0 5 2 5 5 c0 2.4 -2 3.6 -3.6 3 M4 {s - 2} c0 3 2 5 5 5 c2.4 0 3.6 -2 3 -3.6"
        fill="none" stroke="url(#fmetal)" stroke-width="1.8" stroke-linecap="round"/>
  <path d="M12.5 5 L20 12.5 L12.5 20 L5 12.5 Z" fill="url(#fmetal)" stroke="{c['bg_alt']}" stroke-width="1"/>
  <circle cx="12.5" cy="12.5" r="3.6" fill="url(#fgem)" stroke="{c['metal_lo']}" stroke-width=".8"/>"""
    corners = "".join(
        f'<g transform="translate({tx} {ty}) scale({sx} {sy})">{corner}</g>'
        for tx, ty, sx, sy in [(0, 0, 1, 1), (size, 0, -1, 1), (0, size, 1, -1), (size, size, -1, -1)])
    m = s / 2
    return f"""<svg {SVG} width="{size}" height="{size}" viewBox="0 0 {size} {size}">
<defs>{_metal_defs(c, 'f')}</defs>
<rect x="1" y="1" width="{size - 2}" height="{size - 2}" fill="none" stroke="{c['bg_alt']}" stroke-width="2"/>
<rect x="3" y="3" width="{size - 6}" height="{size - 6}" fill="none" stroke="{c['steel_lo']}" stroke-width="3"/>
<rect x="{m - 4}" y="{m - 4}" width="{size - 2 * m + 8}" height="{size - 2 * m + 8}" fill="none" stroke="url(#fmetal)" stroke-width="2"/>
<rect x="{m - .5}" y="{m - .5}" width="{size - 2 * m + 1}" height="{size - 2 * m + 1}" fill="none" stroke="{c['metal_lo']}" stroke-width="1"/>
{corners}
</svg>"""


def texture_svg(c, kind, size=256, height=None):
    """Seamless (stitched) procedural textures: stone, leather, parchment."""
    base, freq, octv, alpha, light = {
        "stone": (c["surface"], ".045", 4, ".55", "#ffffff"),
        "leather": (c["accent_lo"], ".35", 3, ".45", "#ffffff"),
        "parchment": (c["parchment"], ".025", 4, ".40", c["metal_hi"]),
    }[kind]
    w, h = size, height or size
    grain = ""
    if kind == "stone":
        grain = f'<rect width="{w}" height="{h}" filter="url(#fine)" opacity=".5"/>'
    return f"""<svg {SVG} width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <filter id="mottle" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="{octv}" seed="7" stitchTiles="stitch"/>
    <feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -1.6 0 0 0 {alpha}"/>
  </filter>
  <filter id="hilite" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="{octv}" seed="19" stitchTiles="stitch"/>
    <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  1.2 0 0 0 -.62"/>
  </filter>
  <filter id="fine" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="3" stitchTiles="stitch"/>
    <feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -.9 .45"/>
  </filter>
</defs>
<rect width="{w}" height="{h}" fill="{base}"/>
<rect width="{w}" height="{h}" filter="url(#mottle)"/>
<g opacity=".18"><rect width="{w}" height="{h}" filter="url(#hilite)" fill="{light}"/></g>
{grain}
</svg>"""


def ui_assets(c):
    """{filename: (svg, width, height)} rendered to PNG for the GTK and Shell themes."""
    return {
        "frame.png": (frame_svg(c), 96, 96),
        "frame-48.png": (frame_svg(c), 48, 48),
        "panel.png": (texture_svg(c, "stone", 2048, 64), 2048, 64),
        "stone.png": (texture_svg(c, "stone"), 256, 256),
        "leather.png": (texture_svg(c, "leather"), 256, 256),
        "parchment.png": (texture_svg(c, "parchment"), 256, 256),
    }
