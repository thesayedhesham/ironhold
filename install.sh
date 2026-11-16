#!/usr/bin/env bash
# Install Ironhold for the current user on Ubuntu / GNOME (no sudo needed).
#
#   ./install.sh                 # install Crown and apply it
#   ./install.sh Ember           # install Ember and apply it
#   ./install.sh Grave           # install Grave and apply it
#   ./install.sh Crown --no-apply
#   ./install.sh --uninstall
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="Ironhold"
VARIANT="Crown"
APPLY=1
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --no-apply) APPLY=0 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) VARIANT="$arg" ;;
  esac
done
THEME="$NAME-$VARIANT"
DIST="$HERE/dist/linux"
THEMES="$HOME/.themes"; ICONS="$HOME/.icons"
SOUNDS="$HOME/.local/share/sounds"
BG="$HOME/.local/share/backgrounds"; BGPROPS="$HOME/.local/share/gnome-background-properties"
GTK4="$HOME/.config/gtk-4.0"
FONTS="$HOME/.local/share/fonts/ironhold"
MARK="/* ironhold-managed */"

restore_gtk4() {
  if [ -f "$GTK4/gtk.css" ] && head -1 "$GTK4/gtk.css" | grep -qF "$MARK"; then
    rm -f "$GTK4/gtk.css" "$GTK4/gtk-dark.css"
    rm -rf "$GTK4/ironhold-assets"
    [ -f "$GTK4/gtk.css.ironhold-backup" ] && mv "$GTK4/gtk.css.ironhold-backup" "$GTK4/gtk.css"
    [ -f "$GTK4/gtk-dark.css.ironhold-backup" ] && mv "$GTK4/gtk-dark.css.ironhold-backup" "$GTK4/gtk-dark.css"
  fi
  return 0
}

if [ "$UNINSTALL" = 1 ]; then
  rm -rf "$THEMES/$NAME-"* "$ICONS/$NAME-"* "$BG/$NAME-"* "$BGPROPS/$NAME-"*.xml "$SOUNDS/$NAME-"*
  restore_gtk4
  rm -rf "$FONTS"; command -v fc-cache >/dev/null && fc-cache -f >/dev/null 2>&1 || true
  if command -v gsettings >/dev/null; then
    gsettings reset org.gnome.desktop.interface gtk-theme
    gsettings reset org.gnome.desktop.interface icon-theme
    gsettings reset org.gnome.desktop.interface cursor-theme
    gsettings reset org.gnome.shell.extensions.user-theme name 2>/dev/null || true
    gsettings reset org.gnome.desktop.background picture-uri
    gsettings reset org.gnome.desktop.background picture-uri-dark
    gsettings reset org.gnome.desktop.sound theme-name
  fi
  echo "Ironhold removed."; exit 0
fi

[ -d "$DIST/themes/$THEME" ] || { echo "Build first: python3 build.py --variant $VARIANT"; exit 1; }

mkdir -p "$THEMES" "$ICONS" "$BG" "$BGPROPS" "$GTK4" "$SOUNDS"
rm -rf "${THEMES:?}/$THEME" "${ICONS:?}/$THEME" "${BG:?}/$THEME" "${SOUNDS:?}/$THEME"
cp -a "$DIST/themes/$THEME" "$THEMES/"
cp -a "$DIST/icons/$THEME" "$ICONS/"
cp -a "$DIST/backgrounds/$THEME" "$BG/"
[ -d "$DIST/sounds/$THEME" ] && cp -a "$DIST/sounds/$THEME" "$SOUNDS/"
sed "s#@BGDIR@#$BG/$THEME#g" "$BG/$THEME/$THEME.xml.in" > "$BGPROPS/$THEME.xml"
rm -f "$BG/$THEME/$THEME.xml.in"
echo "Installed $THEME into ~/.themes, ~/.icons, ~/.local/share/backgrounds and ~/.local/share/sounds"

# libadwaita (GTK4) apps only read ~/.config/gtk-4.0 — back up whatever is there once.
if [ -f "$GTK4/gtk.css" ] && ! head -1 "$GTK4/gtk.css" | grep -qF "$MARK"; then
  mv "$GTK4/gtk.css" "$GTK4/gtk.css.ironhold-backup"
  [ -f "$GTK4/gtk-dark.css" ] && mv "$GTK4/gtk-dark.css" "$GTK4/gtk-dark.css.ironhold-backup"
  echo "Backed up existing ~/.config/gtk-4.0/gtk.css"
fi
{ echo "$MARK"; cat "$THEMES/$THEME/gtk-4.0/gtk.css"; } > "$GTK4/gtk.css"
cp "$GTK4/gtk.css" "$GTK4/gtk-dark.css"
rm -rf "$GTK4/ironhold-assets"
cp -a "$THEMES/$THEME/gtk-4.0/ironhold-assets" "$GTK4/"

# Cinzel fantasy fonts (SIL Open Font License) for titles, panel and lock screen
if [ -d "$HERE/fonts" ]; then
  mkdir -p "$FONTS"
  cp "$HERE"/fonts/*.ttf "$HERE"/fonts/OFL-*.txt "$FONTS/" 2>/dev/null || true
  command -v fc-cache >/dev/null && fc-cache -f "$FONTS" >/dev/null 2>&1 || true
fi

[ "$APPLY" = 1 ] || exit 0
command -v gsettings >/dev/null || { echo "gsettings not found; apply manually with GNOME Tweaks."; exit 0; }

gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gsettings set org.gnome.desktop.interface gtk-theme "$THEME"
gsettings set org.gnome.desktop.interface icon-theme "$THEME"
gsettings set org.gnome.desktop.interface cursor-theme "$THEME"
# Prefer your own artwork (local-art/) if the build included any, else the citadel
WP="$(ls "$BG/$THEME"/local-* 2>/dev/null | head -1)"
[ -n "$WP" ] || WP="$(ls "$BG/$THEME"/*citadel*.png | head -1)"
gsettings set org.gnome.desktop.background picture-uri "file://$WP"
gsettings set org.gnome.desktop.background picture-uri-dark "file://$WP"
if [ -d "$SOUNDS/$THEME" ]; then
  gsettings set org.gnome.desktop.sound theme-name "$THEME"
  gsettings set org.gnome.desktop.sound event-sounds true
fi

if gsettings list-schemas | grep -q org.gnome.shell.extensions.user-theme; then
  gnome-extensions enable user-theme@gnome-shell-extensions.gcampax.github.com 2>/dev/null || true
  gsettings set org.gnome.shell.extensions.user-theme name "$THEME"
  echo "Shell theme applied."
else
  echo "Shell theme skipped: install the User Themes extension first:"
  echo "  sudo apt install gnome-shell-extensions   (then log out/in and re-run this script)"
fi
echo "Done. Restart open apps to pick up the GTK theme."
