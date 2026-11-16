# local-art: your personal artwork

Put wallpapers you are allowed to use here, such as official wallpapers you downloaded for
personal use. The build uses them for your own desktop.

- `local-art/*.jpg|png`: used by every variant
- `local-art/<Variant>/*.jpg|png`: used only by that variant (for example `local-art/Crown/`)

Your images become the default wallpaper (sorted by filename). The theme's own wallpapers stay
available in Settings.

To make a whole variant match a piece of art:

    python3 variant_from_art.py local-art/Stormwind/*.jpg --name Stormwind --base Crown
    python3 build.py --variant Stormwind && ./install.sh Stormwind

Everything in this folder except this README is git-ignored. Builds that include local art put
your images into `dist/`, so don't share `dist/` or the Windows pack folder if it contains
artwork you don't have the right to redistribute.
