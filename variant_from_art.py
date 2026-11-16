#!/usr/bin/env python3
"""Create a new Ironhold variant whose colors are pulled from artwork you supply.

    python3 variant_from_art.py local-art/Stormwind/*.jpg --name Stormwind --base Crown
    python3 build.py --variant Stormwind && ./install.sh Stormwind

The new variant keeps the base variant's emblem and sound style. Images in local-art/<Name>/
are also used as that variant's wallpapers. A swatch preview is written to dist/previews/.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "lib"))
import palette  # noqa: E402
import raster  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+", help="artwork to sample colors from")
    ap.add_argument("--name", required=True, help="new variant name, e.g. Stormwind")
    ap.add_argument("--base", default="Crown", help="variant to inherit emblem/sounds/status colors from")
    ap.add_argument("--force", action="store_true", help="overwrite an existing variant of that name")
    a = ap.parse_args()

    cfg_path = ROOT / "config.json"
    cfg = json.loads(cfg_path.read_text())
    if a.base not in cfg["variants"]:
        raise SystemExit(f"Unknown base variant {a.base}; have {', '.join(cfg['variants'])}")
    if a.name in cfg["variants"] and not a.force:
        raise SystemExit(f"Variant {a.name} exists; pass --force to overwrite")

    base = cfg["variants"][a.base]
    colors = palette.derive(a.images, base["colors"])
    cfg["variants"][a.name] = {
        "label": f"{a.name} (palette from your artwork, based on {a.base})",
        "emblem": base["emblem"], "sound": base.get("sound"),
        "windows_accent": base.get("windows_accent", "metal"),
        "colors": colors,
    }
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")

    out = ROOT / "dist" / "previews"
    out.mkdir(parents=True, exist_ok=True)
    svg, h = palette.swatch_svg(a.name, colors)
    raster.svg_to_png(svg, out / f"{a.name}-palette.png", 980, h)
    print(f"Added variant '{a.name}' to config.json")
    print(f"  metal {colors['metal']}  accent {colors['accent']}  bg {colors['bg']}")
    print(f"  preview: {out / (a.name + '-palette.png')}")
    print(f"Next: python3 build.py --variant {a.name} && ./install.sh {a.name}")


if __name__ == "__main__":
    main()
