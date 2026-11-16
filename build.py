#!/usr/bin/env python3
"""Build every Ironhold variant into dist/.

    python3 build.py                 # everything
    python3 build.py --only gtk      # gtk | shell | icons | cursors | wallpapers | windows
    python3 build.py --variant Crown
    python3 build.py --fast          # 1920x1080 wallpapers, fewer cursor sizes (for quick iteration)

Only needs Python 3 plus the system librsvg/cairo libraries (present on any GNOME desktop).
"""
import argparse
import html
import re
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "lib"))

import art  # noqa: E402
import cursorfmt  # noqa: E402
import raster  # noqa: E402
import sound  # noqa: E402
from template import render  # noqa: E402

SRC, DIST = ROOT / "src", ROOT / "dist"
LOCAL_ART = ROOT / "local-art"
ART_EXT = {".jpg", ".jpeg", ".png"}
STEPS = ["gtk", "shell", "icons", "cursors", "wallpapers", "sounds", "windows"]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def symlink(target, link):
    if link.is_symlink() or link.exists():
        link.unlink()
    os.symlink(target, link)


class Variant:
    def __init__(self, cfg, key, opts):
        v = cfg["variants"][key]
        self.key, self.opts = key, opts
        self.name = f"{cfg['name']}-{key}"
        self.label = v["label"]
        self.c = v["colors"]
        self.emblem = v["emblem"]
        self.spiky = v["emblem"] == "axes"
        self.win_accent = self.c[v.get("windows_accent", "metal")]
        self.desc = cfg["description"]
        self.sound = v.get("sound", {"style": "crown", "root": 523.25})
        self.linux = DIST / "linux"
        self.win = DIST / "windows" / self.name
        self._cursor_cache = None

    def tpl(self, rel):
        return render((SRC / rel).read_text(), self.c, rel)

    # ------------------------------------------------------------ GTK + metacity index
    def _assets(self, dest):
        dest.mkdir(parents=True, exist_ok=True)
        for fn, (svg, w, h) in art.ui_assets(self.c).items():
            raster.svg_to_png(svg, dest / fn, w, h)

    def gtk(self):
        base = self.linux / "themes" / self.name
        self._assets(base / "gtk-3.0" / "assets")
        self._assets(base / "gtk-4.0" / "ironhold-assets")
        write(base / "gtk-3.0" / "gtk.css", self.tpl("gtk-3.0/gtk.css.in"))
        write(base / "gtk-3.0" / "gtk-dark.css", '@import url("gtk.css");\n')
        write(base / "gtk-4.0" / "gtk.css", self.tpl("gtk-4.0/gtk.css.in"))
        write(base / "gtk-4.0" / "gtk-dark.css", '@import url("gtk.css");\n')
        write(base / "index.theme",
              f"[Desktop Entry]\nType=X-GNOME-Metatheme\nName={self.name}\nComment={self.desc}\nEncoding=UTF-8\n\n"
              f"[X-GNOME-Metatheme]\nGtkTheme={self.name}\nIconTheme={self.name}\nCursorTheme={self.name}\n")

    def shell(self):
        base = self.linux / "themes" / self.name / "gnome-shell"
        self._assets(base / "assets")
        write(base / "gnome-shell.css", self.tpl("gnome-shell/gnome-shell.css.in"))

    # ------------------------------------------------------------ icons
    def icons(self):
        base = self.linux / "icons" / self.name
        places = base / "scalable" / "places"
        places.mkdir(parents=True, exist_ok=True)
        for name, svg in art.icon_svgs(self.c, self.emblem).items():
            write(places / f"{name}.svg", svg)
            for alias in art.ICON_ALIASES.get(name, []):
                symlink(f"{name}.svg", places / f"{alias}.svg")
        write(base / "index.theme",
              f"[Icon Theme]\nName={self.name}\nComment={self.desc}\n"
              "Inherits=Yaru,Adwaita,hicolor\nDirectories=scalable/places\n\n"
              "[scalable/places]\nSize=128\nMinSize=16\nMaxSize=512\nContext=Places\nType=Scalable\n")

    # ------------------------------------------------------------ cursors
    def _cursor_images(self, sizes):
        """{name: (frames[[Image per size]], hotspot32, ms)} rendered once and reused for Linux + Windows."""
        if self._cursor_cache is None:
            self._cursor_cache = {}
        out = {}
        for name, (svg, hot, ms) in art.cursor_svgs(self.c).items():
            frames = svg if isinstance(svg, list) else [svg]
            rendered = []
            for i, f in enumerate(frames):
                per_size = {}
                for s in sizes:
                    k = (name, i, s)
                    if k not in self._cursor_cache:
                        self._cursor_cache[k] = raster.svg_to_image(f, s, s)
                    per_size[s] = self._cursor_cache[k]
                rendered.append(per_size)
            out[name] = (rendered, hot, ms)
        return out

    def cursors(self):
        sizes = [24, 32, 48] if self.opts.fast else [24, 32, 48, 64, 96]
        base = self.linux / "icons" / self.name
        cdir = base / "cursors"
        cdir.mkdir(parents=True, exist_ok=True)
        for name, (frames, (hx, hy), ms) in self._cursor_images(sizes).items():
            entries = []
            for s in sizes:
                k = s / 32
                for fr in frames:
                    entries.append((s, fr[s], round(hx * k), round(hy * k), ms))
            cursorfmt.write_xcursor(cdir / name, entries)
            for alias in art.CURSOR_ALIASES.get(name, []):
                symlink(name, cdir / alias)
        write(base / "cursor.theme", f"[Icon Theme]\nName={self.name}\nInherits=Yaru,Adwaita\n")

    # ------------------------------------------------------------ wallpapers
    def wallpapers(self):
        w, h = (1920, 1080) if self.opts.fast else (art.W, art.H)
        out = self.linux / "backgrounds" / self.name
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("local-*"):
            old.unlink()
        files = self._local_art(out)
        for wname, svg in art.wallpapers(self.c, self.emblem, self.spiky).items():
            if (w, h) != (art.W, art.H):
                svg = svg.replace(f'width="{art.W}" height="{art.H}"', f'width="{w}" height="{h}"', 1)
            png = out / f"{self.name}-{wname}.png"
            raster.svg_to_png(svg, png, w, h)
            files.append(png)
            print(f"    wallpaper {png.name}")
        entries = "".join(
            f"  <wallpaper deleted=\"false\">\n    <name>{html.escape(self._wall_title(p))}</name>\n"
            f"    <filename>@BGDIR@/{p.name}</filename>\n    <filename-dark>@BGDIR@/{p.name}</filename-dark>\n"
            f"    <options>zoom</options>\n    <pcolor>{self.c['bg_alt']}</pcolor>\n"
            f"    <scolor>{self.c['bg']}</scolor>\n  </wallpaper>\n" for p in files)
        write(out / f"{self.name}.xml.in",
              f'<?xml version="1.0"?>\n<!DOCTYPE wallpapers SYSTEM "gnome-wp-list.dtd">\n<wallpapers>\n{entries}</wallpapers>\n')

    def _local_art(self, out):
        """Copy personal artwork from local-art/ (all variants) and local-art/<Variant>/ (this one)."""
        found = []
        for d in (LOCAL_ART, LOCAL_ART / self.key):
            if d.is_dir():
                found += sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in ART_EXT)
        copies = []
        for p in found:
            safe = re.sub(r"[^A-Za-z0-9._-]+", "-", p.stem).strip("-") or "art"
            dst = out / f"local-{safe}{p.suffix.lower()}"
            shutil.copyfile(p, dst)
            copies.append(dst)
            print(f"    wallpaper {dst.name}  (your artwork, personal use only)")
        return copies

    def _wall_title(self, p):
        if p.name.startswith("local-"):
            return p.stem[6:].replace("-", " ").replace("_", " ").title()
        return f"{self.name} {p.stem.split('-')[-1].title()}"

    # ------------------------------------------------------------ sounds (freedesktop sound theme)
    def sounds(self):
        base = self.linux / "sounds" / self.name
        stereo = base / "stereo"
        stereo.mkdir(parents=True, exist_ok=True)
        events = sound.STYLES[self.sound["style"]](self.sound["root"])
        for name, samples in events.items():
            sound.write_wav(stereo / f"{name}.wav", samples)
            for alias in sound.SOUND_ALIASES.get(name, []):
                symlink(f"{name}.wav", stereo / f"{alias}.wav")
        write(base / "index.theme",
              f"[Sound Theme]\nName={self.name}\nComment={self.desc}\nInherits=freedesktop\nDirectories=stereo\n\n"
              "[stereo]\nOutputProfile=stereo\n")
        print(f"    {len(events)} sounds")

    # ------------------------------------------------------------ Windows pack
    def windows(self):
        win = self.win
        (win / "Cursors").mkdir(parents=True, exist_ok=True)
        (win / "Wallpapers").mkdir(parents=True, exist_ok=True)
        (win / "Icons").mkdir(parents=True, exist_ok=True)

        # cursors: .cur / .ani with 32,48,64,96,128 px images
        sizes = [32, 48] if self.opts.fast else [32, 48, 64, 96, 128]
        files = {}
        for name, (frames, (hx, hy), ms) in self._cursor_images(sizes).items():
            def cur(fr):
                return cursorfmt.cur_bytes([(fr[s], round(hx * s / 32), round(hy * s / 32)) for s in sizes])
            if len(frames) > 1:
                fn = f"{name}.ani"
                cursorfmt.write_ani(win / "Cursors" / fn, [cur(f) for f in frames], max(1, round(ms * 60 / 1000)))
            else:
                fn = f"{name}.cur"
                (win / "Cursors" / fn).write_bytes(cur(frames[0]))
            files[name] = fn
        write(win / "cursor-map.txt", "\n".join(f"{role}={files[n]}" for role, n in art.WINDOWS_CURSORS.items()) + "\n")

        # wallpapers: reuse the Linux PNGs if built, otherwise render
        src = self.linux / "backgrounds" / self.name
        if not any(src.glob("*.png")):
            self.wallpapers()
        for old in (win / "Wallpapers").glob("*"):
            old.unlink()
        walls = sorted((p for p in src.iterdir() if p.suffix.lower() in ART_EXT),
                       key=lambda p: (not p.name.startswith("local-"), p.name))
        for p in walls:
            shutil.copy2(p, win / "Wallpapers" / p.name)

        # sounds: Windows needs PCM WAV, which is exactly what we generate
        (win / "Sounds").mkdir(parents=True, exist_ok=True)
        snd_src = self.linux / "sounds" / self.name / "stereo"
        if not snd_src.is_dir():
            self.sounds()
        for name in set(sound.WINDOWS_SOUNDS.values()):
            shutil.copyfile(snd_src / f"{name}.wav", win / "Sounds" / f"{self.name}-{name}.wav")
        write(win / "sound-map.txt", "\n".join(f"{ev}={self.name}-{n}.wav" for ev, n in sound.WINDOWS_SOUNDS.items()) + "\n")
        sound_lines = "\n".join(f"\n[AppEvents\\Schemes\\Apps\\{ev}]\nDefaultValue=@@DIR@@\\Sounds\\{self.name}-{n}.wav"
                                for ev, n in sound.WINDOWS_SOUNDS.items())

        # folder icons (.ico) for manual use via folder Properties > Customize
        for name, svg in art.icon_svgs(self.c, self.emblem).items():
            imgs = [raster.svg_to_image(svg, s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
            cursorfmt.write_ico(win / "Icons" / f"{name}.ico", imgs)

        r, g, b = (int(self.win_accent[i:i + 2], 16) for i in (1, 3, 5))
        cursor_lines = "\n".join(f"{role}=@@DIR@@\\Cursors\\{files[n]}" for role, n in art.WINDOWS_CURSORS.items())
        theme = f"""; {self.name} - {self.label}
[Theme]
DisplayName={self.name}

[Control Panel\\Desktop]
Wallpaper=@@DIR@@\\Wallpapers\\{walls[0].name}
TileWallpaper=0
WallpaperStyle=10
Pattern=

[Slideshow]
ImagesRootPath=@@DIR@@\\Wallpapers
Interval=1800000
Shuffle=1

[Control Panel\\Cursors]
{cursor_lines}
DefaultValue={self.name}

[VisualStyles]
Path=%SystemRoot%\\resources\\themes\\Aero\\Aero.msstyles
ColorStyle=NormalColor
Size=NormalSize
AutoColorization=0
ColorizationColor=0XC4{r:02X}{g:02X}{b:02X}
SystemMode=Dark
AppMode=Dark

[Sounds]
SchemeName={self.name}
{sound_lines}

[MasterThemeSelector]
MTSM=RJSPBS
"""
        write(win / f"{self.name}.theme.in", theme.replace("\n", "\r\n"))
        write(win / "install.ps1", (SRC / "windows" / "install.ps1").read_text()
              .replace("@@THEME_NAME@@", self.name).replace("\n", "\r\n"))

        # Windows Terminal color scheme
        c = self.c
        scheme = {"name": self.name, "background": c["bg_alt"], "foreground": c["text"],
                  "cursorColor": c["metal_hi"], "selectionBackground": c["accent"],
                  "black": c["bg"], "red": c["danger"], "green": c["success"], "yellow": c["metal"],
                  "blue": c["accent_hi"], "purple": "#8e6bb8", "cyan": "#5aa6a0", "white": c["text"],
                  "brightBlack": c["border_hi"], "brightRed": c["accent_hi"], "brightGreen": "#8fc46a",
                  "brightYellow": c["metal_hi"], "brightBlue": c["link"], "brightPurple": "#b796de",
                  "brightCyan": "#86d1c9", "brightWhite": "#ffffff"}
        write(win / "windows-terminal-scheme.json", json.dumps(scheme, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=STEPS, action="append")
    ap.add_argument("--variant", action="append")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--clean", action="store_true", help="delete dist/ first")
    opts = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text())
    if opts.clean and DIST.exists():
        shutil.rmtree(DIST)
    steps = opts.only or STEPS
    for key in opts.variant or cfg["variants"]:
        v = Variant(cfg, key, opts)
        print(f"==> {v.name}")
        for step in steps:
            print(f"  - {step}")
            getattr(v, step)()
    print(f"Done. Output in {DIST}")


if __name__ == "__main__":
    main()
