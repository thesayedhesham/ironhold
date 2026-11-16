#!/usr/bin/env python3
"""Render README preview images into docs/ from the theme's real assets.

    python3 make_previews.py

The desktop images are *mockups* composed from the generated textures, frames, icons, cursors,
wallpapers and fonts. They are not screenshots of a running GNOME session.
"""
import base64
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"

# Make the bundled Cinzel font visible to librsvg's fontconfig *before* the library loads.
_fc = Path(tempfile.mkdtemp()) / "fonts.conf"
_fc.write_text(f'<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'
               f'<include ignore_missing="yes">/etc/fonts/fonts.conf</include><dir>{ROOT / "fonts"}</dir>'
               f'<cachedir>{_fc.parent}</cachedir></fontconfig>')
os.environ["FONTCONFIG_FILE"] = str(_fc)

sys.path.insert(0, str(ROOT / "lib"))
import art  # noqa: E402
import raster  # noqa: E402

TITLE = "Cinzel, serif"
BODY = "DejaVu Sans, sans-serif"
W, H = 1280, 720


def png_uri(svg, w, h):
    tmp = Path(tempfile.mkstemp(suffix=".png")[1])
    raster.svg_to_png(svg, tmp, w, h)
    data = base64.b64encode(tmp.read_bytes()).decode()
    tmp.unlink()
    return f"data:image/png;base64,{data}"


def sized(svg, w, h):
    return svg.replace(f'width="{art.W}" height="{art.H}"', f'width="{w}" height="{h}"', 1)


def nine_slice(uri, x, y, w, h, src=96, s=24, b=12):
    """Draw a 9-slice border-image (like GTK/St do) from a PNG data URI."""
    parts = []
    cols = [(0, s, x, b), (s, src - 2 * s, x + b, w - 2 * b), (src - s, s, x + w - b, b)]
    rows = [(0, s, y, b), (s, src - 2 * s, y + b, h - 2 * b), (src - s, s, y + h - b, b)]
    for ry, rh, dy, dh in rows:
        for cx, cw, dx, dw in cols:
            if (cx, ry) == (s, s):
                continue  # centre stays empty
            parts.append(f'<svg x="{dx}" y="{dy}" width="{dw}" height="{dh}" viewBox="{cx} {ry} {cw} {rh}" '
                         f'preserveAspectRatio="none"><image href="{uri}" width="{src}" height="{src}"/></svg>')
    return "".join(parts)


def mockup(v):
    c, kind, spiky = v["colors"], v["emblem"], v["emblem"] != "sword"
    wall = png_uri(sized(art.wallpaper_citadel(c, spiky), W, H), W, H)
    assets = {k: png_uri(svg, w, h) for k, (svg, w, h) in art.ui_assets(c).items()}
    icons = art.icon_svgs(c, kind)
    icon = {n: png_uri(icons[n], 64, 64) for n in
            ["user-home", "folder-documents", "folder-download", "folder-music", "folder-pictures",
             "folder-videos", "folder-templates", "user-trash-full"]}
    cursor = png_uri(art.cursor_svgs(c, v.get("cursor", "plate"))["pointer"][0], 32, 32)

    wx, wy, ww, wh = 120, 78, 780, 500
    side = 190
    rows = ["Home", "Documents", "Downloads", "Music", "Pictures", "Trash"]
    sidebar = "".join(
        (f'<rect x="{wx}" y="{wy + 60 + i * 34}" width="{side}" height="30" fill="url(#sel)"/>'
         f'<rect x="{wx}" y="{wy + 60 + i * 34}" width="3" height="30" fill="{c["metal"]}"/>' if i == 0 else "")
        + f'<text x="{wx + 20}" y="{wy + 80 + i * 34}" font-family="{BODY}" font-size="14" '
          f'fill="{c["text_on_accent"] if i == 0 else c["text"]}">{r}</text>' for i, r in enumerate(rows))
    labels = ["Home", "Documents", "Downloads", "Music", "Pictures", "Videos", "Templates", "Trash"]
    grid = "".join(
        f'<image x="{wx + side + 40 + (i % 4) * 130}" y="{wy + 76 + (i // 4) * 120}" width="64" height="64" href="{u}"/>'
        f'<text x="{wx + side + 72 + (i % 4) * 130}" y="{wy + 160 + (i // 4) * 120}" text-anchor="middle" '
        f'font-family="{BODY}" font-size="13" fill="{c["text"]}">{labels[i]}</text>'
        for i, u in enumerate(icon.values()))
    by = wy + wh - 70
    bx = wx + side + 40
    widgets = f"""
  <rect x="{bx}" y="{by}" width="110" height="34" rx="4" fill="url(#btn)" stroke="{c['metal_lo']}"/>
  <text x="{bx + 55}" y="{by + 22}" text-anchor="middle" font-family="{BODY}" font-size="14" fill="{c['text']}">Cancel</text>
  <rect x="{bx + 125}" y="{by}" width="130" height="34" rx="4" fill="url(#leatherbtn)" stroke="{c['metal']}"/>
  <text x="{bx + 190}" y="{by + 22}" text-anchor="middle" font-family="{BODY}" font-weight="bold" font-size="14" fill="{c['text_on_accent']}">Forge Folder</text>
  <rect x="{bx + 280}" y="{by + 6}" width="50" height="24" rx="12" fill="{c['accent']}" stroke="{c['metal']}"/>
  <circle cx="{bx + 318}" cy="{by + 18}" r="10" fill="url(#rivet)" stroke="{c['bg_alt']}"/>
  <rect x="{bx + 350}" y="{by + 12}" width="170" height="10" rx="5" fill="{c['bg_alt']}" stroke="{c['border']}"/>
  <rect x="{bx + 350}" y="{by + 12}" width="110" height="10" rx="5" fill="url(#gold)"/>"""
    # tooltip above the suggested button, popup menu at the right
    tx, ty, tw, th = bx + 105, by - 62, 190, 44
    mx, my, mw, mh = 930, 40, 300, 236
    items = ["Settings", "Lock Screen", "Switch User", "Log Out", "Power Off"]
    menu = "".join(
        (f'<rect x="{mx + 12}" y="{my + 18 + i * 38}" width="{mw - 24}" height="34" fill="{c["accent"]}"/>' if i == 1 else "")
        + f'<text x="{mx + 30}" y="{my + 41 + i * 38}" font-family="{BODY}" font-size="15" '
          f'fill="{c["text_on_accent"] if i == 1 else c["text"]}">{t}</text>' for i, t in enumerate(items))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <pattern id="stone" width="128" height="128" patternUnits="userSpaceOnUse"><image href="{assets['stone.png']}" width="128" height="128"/></pattern>
  <pattern id="parch" width="128" height="128" patternUnits="userSpaceOnUse"><image href="{assets['parchment.png']}" width="128" height="128"/></pattern>
  <pattern id="leather" width="128" height="128" patternUnits="userSpaceOnUse"><image href="{assets['leather.png']}" width="128" height="128"/></pattern>
  <linearGradient id="sel" x1="0" x2="1"><stop offset="0" stop-color="{c['accent']}"/><stop offset="1" stop-color="{c['accent_lo']}"/></linearGradient>
  <linearGradient id="btn" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c['surface_hi']}"/><stop offset="1" stop-color="{c['surface']}"/></linearGradient>
  <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c['metal_hi']}"/><stop offset=".6" stop-color="{c['metal']}"/><stop offset="1" stop-color="{c['metal_lo']}"/></linearGradient>
  <radialGradient id="rivet" cx=".35" cy=".3"><stop offset="0" stop-color="{c['metal_hi']}"/><stop offset=".55" stop-color="{c['metal']}"/><stop offset="1" stop-color="{c['metal_lo']}"/></radialGradient>
  <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c['metal']}" stop-opacity=".1"/><stop offset="1" stop-color="#000" stop-opacity=".3"/></linearGradient>
  <filter id="drop" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="8" stdDeviation="12" flood-opacity=".65"/></filter>
</defs>
<image width="{W}" height="{H}" href="{wall}"/>

<!-- top panel -->
<image width="{W}" height="32" href="{assets['panel.png']}" preserveAspectRatio="xMidYMid slice"/>
<rect y="30" width="{W}" height="2" fill="{c['metal_lo']}"/>
<text x="18" y="21" font-family="{TITLE}" font-weight="bold" font-size="14" fill="{c['parchment']}">Activities</text>
<text x="{W / 2}" y="21" text-anchor="middle" font-family="{TITLE}" font-weight="bold" font-size="15" fill="{c['metal_hi']}">Tue 17 Nov  21:04</text>
<g fill="{c['parchment']}"><circle cx="{W - 70}" cy="16" r="5"/><circle cx="{W - 50}" cy="16" r="5"/><circle cx="{W - 30}" cy="16" r="5"/></g>

<!-- window -->
<g filter="url(#drop)"><rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" fill="{c['bg']}" stroke="{c['metal_lo']}"/></g>
<rect x="{wx + side}" y="{wy + 46}" width="{ww - side}" height="{wh - 46}" fill="{c['bg']}"/>
<rect x="{wx}" y="{wy + 46}" width="{side}" height="{wh - 46}" fill="url(#stone)"/>
<rect x="{wx}" y="{wy + 46}" width="{side}" height="{wh - 46}" fill="#000" opacity=".35"/>
<rect x="{wx + side - 1}" y="{wy + 46}" width="1" height="{wh - 46}" fill="{c['metal_lo']}"/>
<rect x="{wx}" y="{wy}" width="{ww}" height="46" fill="url(#stone)"/>
<rect x="{wx}" y="{wy}" width="{ww}" height="46" fill="url(#shade)"/>
<rect x="{wx}" y="{wy + 44}" width="{ww}" height="2" fill="{c['metal_lo']}"/>
<text x="{wx + ww / 2}" y="{wy + 29}" text-anchor="middle" font-family="{TITLE}" font-weight="bold" font-size="17" letter-spacing="1" fill="{c['metal_hi']}">Files</text>
<g stroke="{c['bg_alt']}">{"".join(f'<circle cx="{wx + ww - 24 - i * 28}" cy="{wy + 23}" r="9" fill="url(#rivet)"/>' for i in range(3))}</g>
{sidebar}
{grid}
<pattern id="leatherbtn" width="128" height="128" patternUnits="userSpaceOnUse"><rect width="128" height="128" fill="url(#leather)"/><rect width="128" height="128" fill="{c['accent_hi']}" opacity=".45"/></pattern>
{widgets}

<!-- tooltip -->
<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" fill="url(#parch)"/>
{nine_slice(assets['frame.png'], tx, ty, tw, th)}
<text x="{tx + tw / 2}" y="{ty + 27}" text-anchor="middle" font-family="{BODY}" font-size="13" fill="{c['ink']}">Create a new folder</text>
<image x="{bx + 200}" y="{by + 14}" width="32" height="32" href="{cursor}"/>

<!-- popup menu -->
<g filter="url(#drop)"><rect x="{mx}" y="{my}" width="{mw}" height="{mh}" fill="{c['surface']}"/></g>
{menu}
{nine_slice(assets['frame.png'], mx, my, mw, mh)}
<text x="{W - 16}" y="{H - 14}" text-anchor="end" font-family="{BODY}" font-size="11" fill="#ffffff" opacity=".55">Rendered mockup from the theme's generated assets</text>
</svg>"""


def wall_sheet(cfg):
    tw, th, pad = 620, 349, 14
    imgs = []
    for row, (key, v) in enumerate(cfg["variants"].items()):
        for col, (name, svg) in enumerate(art.wallpapers(v["colors"], v["emblem"], v["emblem"] != "sword").items()):
            x, y = pad + col * (tw + pad), pad + row * (th + pad)
            imgs.append(f'<image x="{x}" y="{y}" width="{tw}" height="{th}" href="{png_uri(sized(svg, tw, th), tw, th)}"/>'
                        f'<text x="{x + 12}" y="{y + th - 12}" font-family="{TITLE}" font-weight="bold" font-size="18" '
                        f'fill="#fff" opacity=".85">{key} · {name.title()}</text>')
    w, h = pad + 2 * (tw + pad), pad + len(cfg["variants"]) * (th + pad)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="#111"/>{"".join(imgs)}</svg>', w, h


def asset_sheet(cfg):
    items, y = [], 14
    for key, v in cfg["variants"].items():
        c = v["colors"]
        x = 14
        items.append(f'<text x="{x}" y="{y + 18}" font-family="{TITLE}" font-weight="bold" font-size="18" fill="{c["metal_hi"]}">{key}</text>')
        y += 30
        for name, (svg, hot, ms) in art.cursor_svgs(c, v.get("cursor", "plate")).items():
            s = svg[3] if isinstance(svg, list) else svg
            items.append(f'<image x="{x}" y="{y}" width="48" height="48" href="{png_uri(s, 48, 48)}"/>')
            x += 58
        x, y = 14, y + 60
        for name, svg in art.icon_svgs(c, v["emblem"]).items():
            items.append(f'<image x="{x}" y="{y}" width="80" height="80" href="{png_uri(svg, 80, 80)}"/>')
            x += 88
        y += 100
    w = 14 + 14 * 88
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{y}"><rect width="100%" height="100%" fill="#2a2a2a"/>{"".join(items)}</svg>', w, y


def hand_sheet(cfg):
    """Large close-up of each variant's hand cursors (normal, link, busy) on a neutral backdrop."""
    items, x = [], 16
    for key, v in cfg["variants"].items():
        cur = art.cursor_svgs(v["colors"], v.get("cursor", "plate"))
        for name in ("default", "pointer", "progress"):
            svg = cur[name][0][2] if isinstance(cur[name][0], list) else cur[name][0]
            items.append(f'<image x="{x}" y="16" width="128" height="128" href="{png_uri(svg, 128, 128)}"/>')
            x += 136
        items.append(f'<text x="{x - 210}" y="168" text-anchor="middle" font-family="{TITLE}" font-weight="bold" '
                     f'font-size="17" fill="{v["colors"]["metal_hi"]}">{key}</text>')
        x += 24
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{x}" height="184"><rect width="100%" height="100%" fill="#3b4038"/>'
            f'{"".join(items)}</svg>'), x, 184


def main():
    cfg = json.loads((ROOT / "config.json").read_text())
    cfg["variants"] = {k: v for k, v in cfg["variants"].items() if k in ("Crown", "Ember", "Grave")}
    DOCS.mkdir(exist_ok=True)
    for key, v in cfg["variants"].items():
        out = DOCS / f"preview-{key.lower()}.png"
        raster.svg_to_png(mockup(v), out, W, H)
        print(f"wrote {out.relative_to(ROOT)}")
    for name, (svg, w, h) in {"wallpapers.png": wall_sheet(cfg), "cursors-icons.png": asset_sheet(cfg), "hand-cursors.png": hand_sheet(cfg)}.items():
        raster.svg_to_png(svg, DOCS / name, w, h)
        print(f"wrote docs/{name}")


if __name__ == "__main__":
    main()
