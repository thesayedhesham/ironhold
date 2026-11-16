//! Ubuntu / GNOME backend: copies packs into the XDG user dirs and switches gsettings.
use crate::packs::{self, theme_name, THEME_PREFIX};
use crate::util::{copy_dir, local_art_name, remove_dir_if_exists, say};
use crate::{Ctx, Part};
use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::{env, fs};

pub const PACK_KIND: &str = "linux";
const GTK4_MARK: &str = "/* ironhold-managed */";
const USER_THEME_EXT: &str = "user-theme@gnome-shell-extensions.gcampax.github.com";

/// Every gsettings key Ironhold may change; all are snapshotted before the first apply.
const KEYS: &[(&str, &str)] = &[
    ("org.gnome.desktop.interface", "color-scheme"),
    ("org.gnome.desktop.interface", "gtk-theme"),
    ("org.gnome.desktop.interface", "icon-theme"),
    ("org.gnome.desktop.interface", "cursor-theme"),
    ("org.gnome.desktop.background", "picture-uri"),
    ("org.gnome.desktop.background", "picture-uri-dark"),
    ("org.gnome.desktop.sound", "theme-name"),
    ("org.gnome.desktop.sound", "event-sounds"),
    ("org.gnome.shell.extensions.user-theme", "name"),
];

struct Dirs {
    themes: PathBuf,
    icons: PathBuf,
    sounds: PathBuf,
    bg: PathBuf,
    bgprops: PathBuf,
    gtk4: PathBuf,
    fonts: PathBuf,
    state: PathBuf,
}

/// XDG base dir: per the spec, unset, empty or relative values fall back to the default.
fn xdg(var: &str, home: &Path, default: &str) -> PathBuf {
    env::var_os(var).map(PathBuf::from).filter(|p| p.is_absolute()).unwrap_or_else(|| home.join(default))
}

fn dirs() -> Result<Dirs> {
    let home = PathBuf::from(env::var("HOME").context("HOME not set")?);
    if !home.is_absolute() {
        bail!("HOME must be an absolute path");
    }
    let data = xdg("XDG_DATA_HOME", &home, ".local/share");
    let config = xdg("XDG_CONFIG_HOME", &home, ".config");
    let state = xdg("XDG_STATE_HOME", &home, ".local/state");
    Ok(Dirs {
        themes: home.join(".themes"),
        icons: home.join(".icons"),
        sounds: data.join("sounds"),
        bg: data.join("backgrounds"),
        bgprops: data.join("gnome-background-properties"),
        gtk4: config.join("gtk-4.0"),
        fonts: data.join("fonts").join("ironhold"),
        state: state.join("ironhold"),
    })
}

// ---------------------------------------------------------------- gsettings
fn has_schema(schema: &str) -> bool {
    Command::new("gsettings").args(["list-keys", schema]).output().map(|o| o.status.success()).unwrap_or(false)
}

fn gs_get(schema: &str, key: &str) -> Option<String> {
    let o = Command::new("gsettings").args(["get", schema, key]).output().ok()?;
    o.status.success().then(|| String::from_utf8_lossy(&o.stdout).trim().to_string())
}

fn gs_set(dry: bool, schema: &str, key: &str, value: &str) -> Result<()> {
    say(dry, format!("gsettings set {schema} {key} {value}"));
    if dry {
        return Ok(());
    }
    let st = Command::new("gsettings").args(["set", schema, key, value]).status().context("running gsettings")?;
    if !st.success() {
        bail!("gsettings set {schema} {key} failed");
    }
    Ok(())
}

fn quote(s: &str) -> String {
    format!("'{}'", s.replace('\\', "\\\\").replace('\'', "\\'"))
}

// ---------------------------------------------------------------- snapshot
#[derive(Serialize, Deserialize)]
struct Setting {
    schema: String,
    key: String,
    value: Option<String>,
}

#[derive(Serialize, Deserialize)]
struct Backup {
    settings: Vec<Setting>,
}

fn backup_path(d: &Dirs) -> PathBuf {
    d.state.join("backup.json")
}

fn snapshot_once(d: &Dirs, dry: bool) -> Result<()> {
    let p = backup_path(d);
    if p.exists() {
        return Ok(()); // keep the pre-Ironhold state from the very first apply
    }
    let settings = KEYS.iter()
        .map(|(s, k)| Setting { schema: s.to_string(), key: k.to_string(), value: gs_get(s, k) })
        .collect();
    say(dry, format!("saving current look to {}", p.display()));
    if !dry {
        fs::create_dir_all(&d.state)?;
        fs::write(&p, serde_json::to_string_pretty(&Backup { settings })?)?;
    }
    Ok(())
}

fn active_path(d: &Dirs) -> PathBuf {
    d.state.join("active")
}

fn active_variant(d: &Dirs) -> Option<String> {
    fs::read_to_string(active_path(d)).ok().map(|s| s.trim().to_string()).filter(|s| !s.is_empty())
}

// ---------------------------------------------------------------- gtk4 (libadwaita) override file
fn install_gtk4(d: &Dirs, theme_dir: &Path, dry: bool) -> Result<()> {
    let css = d.gtk4.join("gtk.css");
    say(dry, format!("writing {} (libadwaita recolor)", css.display()));
    if dry {
        return Ok(());
    }
    fs::create_dir_all(&d.gtk4)?;
    let ours = fs::read_to_string(&css).map(|s| s.starts_with(GTK4_MARK)).unwrap_or(false);
    if css.exists() && !ours {
        fs::rename(&css, d.gtk4.join("gtk.css.ironhold-backup"))?;
        let dark = d.gtk4.join("gtk-dark.css");
        if dark.exists() {
            fs::rename(&dark, d.gtk4.join("gtk-dark.css.ironhold-backup"))?;
        }
        println!("  backed up your existing gtk.css");
    }
    let body = fs::read_to_string(theme_dir.join("gtk-4.0/gtk.css"))?;
    let full = format!("{GTK4_MARK}\n{body}");
    fs::write(&css, &full)?;
    fs::write(d.gtk4.join("gtk-dark.css"), &full)?;
    remove_dir_if_exists(&d.gtk4.join("ironhold-assets"))?;
    copy_dir(&theme_dir.join("gtk-4.0/ironhold-assets"), &d.gtk4.join("ironhold-assets"))
}

fn restore_gtk4(d: &Dirs, dry: bool) -> Result<()> {
    let css = d.gtk4.join("gtk.css");
    let ours = fs::read_to_string(&css).map(|s| s.starts_with(GTK4_MARK)).unwrap_or(false);
    if !ours {
        return Ok(());
    }
    say(dry, "restoring ~/.config/gtk-4.0");
    if dry {
        return Ok(());
    }
    let _ = fs::remove_file(&css);
    let _ = fs::remove_file(d.gtk4.join("gtk-dark.css"));
    remove_dir_if_exists(&d.gtk4.join("ironhold-assets"))?;
    for f in ["gtk.css", "gtk-dark.css"] {
        let b = d.gtk4.join(format!("{f}.ironhold-backup"));
        if b.exists() {
            fs::rename(b, d.gtk4.join(f))?;
        }
    }
    Ok(())
}

// ---------------------------------------------------------------- apply
fn install_dir(dry: bool, src: &Path, dst: &Path) -> Result<()> {
    say(dry, format!("installing {}", dst.display()));
    if !dry {
        remove_dir_if_exists(dst)?;
        copy_dir(src, dst)?;
    }
    Ok(())
}

fn pick_wallpaper(bgdir: &Path) -> Option<PathBuf> {
    let mut files: Vec<PathBuf> = fs::read_dir(bgdir).ok()?.filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| matches!(p.extension().and_then(|e| e.to_str()), Some("png" | "jpg" | "jpeg"))).collect();
    files.sort_by_key(|p| {
        let n = p.file_name().unwrap().to_string_lossy().to_string();
        (!n.starts_with("local-"), !n.contains("citadel"), n)
    });
    files.into_iter().next()
}

fn set_wallpaper(dry: bool, file: &Path) -> Result<()> {
    let uri = quote(&format!("file://{}", file.display()));
    gs_set(dry, "org.gnome.desktop.background", "picture-uri", &uri)?;
    gs_set(dry, "org.gnome.desktop.background", "picture-uri-dark", &uri)
}

pub fn apply(ctx: &Ctx, variant: &str, parts: &[Part]) -> Result<()> {
    packs::require_variant(&ctx.packs, PACK_KIND, variant)?;
    let d = dirs()?;
    let dry = ctx.dry_run;
    let theme = theme_name(variant);
    let src = ctx.packs.join("linux");
    let has = |p: Part| parts.contains(&p);
    snapshot_once(&d, dry)?;

    if has(Part::Gtk) || has(Part::Shell) {
        install_dir(dry, &src.join("themes").join(&theme), &d.themes.join(&theme))?;
    }
    if has(Part::Gtk) {
        install_gtk4(&d, &src.join("themes").join(&theme), dry)?;
        gs_set(dry, "org.gnome.desktop.interface", "gtk-theme", &quote(&theme))?;
    }
    if has(Part::Colors) {
        gs_set(dry, "org.gnome.desktop.interface", "color-scheme", "'prefer-dark'")?;
    }
    if has(Part::Icons) || has(Part::Cursors) {
        install_dir(dry, &src.join("icons").join(&theme), &d.icons.join(&theme))?;
        if has(Part::Icons) {
            gs_set(dry, "org.gnome.desktop.interface", "icon-theme", &quote(&theme))?;
        }
        if has(Part::Cursors) {
            gs_set(dry, "org.gnome.desktop.interface", "cursor-theme", &quote(&theme))?;
        }
    }
    if has(Part::Wallpaper) {
        let bg = d.bg.join(&theme);
        install_dir(dry, &src.join("backgrounds").join(&theme), &bg)?;
        if !dry {
            let xml_in = bg.join(format!("{theme}.xml.in"));
            if let Ok(xml) = fs::read_to_string(&xml_in) {
                fs::create_dir_all(&d.bgprops)?;
                fs::write(d.bgprops.join(format!("{theme}.xml")), xml.replace("@BGDIR@", &bg.display().to_string()))?;
                let _ = fs::remove_file(xml_in);
            }
        }
        let pick = pick_wallpaper(if dry { &src } else { &bg }).or_else(|| pick_wallpaper(&src.join("backgrounds").join(&theme)));
        if let Some(w) = pick {
            set_wallpaper(dry, &bg.join(w.file_name().unwrap()))?;
        }
    }
    if has(Part::Sounds) && src.join("sounds").join(&theme).is_dir() {
        install_dir(dry, &src.join("sounds").join(&theme), &d.sounds.join(&theme))?;
        gs_set(dry, "org.gnome.desktop.sound", "theme-name", &quote(&theme))?;
        gs_set(dry, "org.gnome.desktop.sound", "event-sounds", "true")?;
    }
    if has(Part::Fonts) && src.join("fonts").is_dir() {
        install_dir(dry, &src.join("fonts"), &d.fonts)?;
        if !dry {
            let _ = Command::new("fc-cache").arg("-f").arg(&d.fonts).output();
        }
    }
    if has(Part::Shell) {
        if has_schema("org.gnome.shell.extensions.user-theme") {
            if !dry {
                let _ = Command::new("gnome-extensions").args(["enable", USER_THEME_EXT]).output();
            }
            gs_set(dry, "org.gnome.shell.extensions.user-theme", "name", &quote(&theme))?;
        } else {
            println!("note: shell theme skipped; install the User Themes extension (sudo apt install gnome-shell-extensions)");
        }
    }
    if !dry {
        fs::create_dir_all(&d.state)?;
        fs::write(active_path(&d), variant)?;
    }
    println!("{theme} applied. Restart open apps to pick up the GTK theme.");
    Ok(())
}

// ---------------------------------------------------------------- art
pub fn art_use(ctx: &Ctx, image: &Path, variant: Option<&str>, recolor: bool, name: Option<String>) -> Result<()> {
    let d = dirs()?;
    let dry = ctx.dry_run;
    let base = variant.map(String::from).or_else(|| active_variant(&d))
        .context("no active Ironhold variant; pass --variant or run `ironhold apply <variant>` first")?;

    if recolor {
        let root = packs::source_root().context("--recolor on Linux needs the Ironhold source checkout (it rebuilds the theme)")?;
        let name = name.unwrap_or_else(|| derive_name(image));
        let name = packs::normalize(&name);
        say(dry, format!("creating variant {name} from {} (based on {base})", image.display()));
        if dry {
            return Ok(());
        }
        packs::import_art(&root, image, Some(&name))?;
        let st = Command::new("python3").current_dir(&root)
            .args(["variant_from_art.py"]).arg(image).args(["--name", &name, "--base", &base, "--force"])
            .status().context("running variant_from_art.py")?;
        if !st.success() {
            bail!("variant_from_art.py failed");
        }
        packs::build(&[name.clone()])?;
        let ctx2 = Ctx { packs: root.join("dist"), dry_run: false };
        return apply(&ctx2, &name, &Part::all());
    }

    let theme = theme_name(&base);
    let bg = d.bg.join(&theme);
    let dst = bg.join(local_art_name(image));
    snapshot_once(&d, dry)?;
    say(dry, format!("copying {} -> {}", image.display(), dst.display()));
    if !dry {
        fs::create_dir_all(&bg)?;
        fs::copy(image, &dst)?;
    }
    set_wallpaper(dry, &dst)?;
    println!("Wallpaper set. Tip: add --recolor to retheme {theme} to match the artwork.");
    Ok(())
}

fn derive_name(image: &Path) -> String {
    let stem = image.file_stem().and_then(|s| s.to_str()).unwrap_or("Custom");
    let word: String = stem.split(|c: char| !c.is_ascii_alphanumeric()).filter(|w| !w.is_empty())
        .take(2).map(|w| packs::normalize(&w.to_ascii_lowercase())).collect();
    if word.is_empty() { "Custom".into() } else { word }
}

// ---------------------------------------------------------------- status / restore / uninstall
pub fn status() -> Result<()> {
    let d = dirs()?;
    println!("active variant : {}", active_variant(&d).unwrap_or_else(|| "none".into()));
    println!("backup saved   : {}", if backup_path(&d).exists() { "yes" } else { "no" });
    for (s, k) in KEYS {
        if let Some(v) = gs_get(s, k) {
            println!("{:<15}: {v}", k);
        }
    }
    Ok(())
}

pub fn restore(dry: bool) -> Result<()> {
    let d = dirs()?;
    let p = backup_path(&d);
    let b: Backup = serde_json::from_str(&fs::read_to_string(&p).with_context(|| {
        format!("no saved look at {} (nothing to restore)", p.display())
    })?)?;
    for s in &b.settings {
        match &s.value {
            Some(v) => gs_set(dry, &s.schema, &s.key, v).or_else(|e| if has_schema(&s.schema) { Err(e) } else { Ok(()) })?,
            None => {}
        }
    }
    restore_gtk4(&d, dry)?;
    if !dry {
        let _ = fs::remove_file(&p);
        let _ = fs::remove_file(active_path(&d));
    }
    println!("Previous look restored.");
    Ok(())
}

pub fn uninstall(dry: bool) -> Result<()> {
    let d = dirs()?;
    if backup_path(&d).exists() {
        restore(dry)?;
    } else {
        restore_gtk4(&d, dry)?;
    }
    for base in [&d.themes, &d.icons, &d.sounds, &d.bg] {
        if let Ok(rd) = fs::read_dir(base) {
            for e in rd.flatten() {
                if e.file_name().to_string_lossy().starts_with(THEME_PREFIX) {
                    say(dry, format!("removing {}", e.path().display()));
                    if !dry {
                        remove_dir_if_exists(&e.path())?;
                    }
                }
            }
        }
    }
    if let Ok(rd) = fs::read_dir(&d.bgprops) {
        for e in rd.flatten() {
            if e.file_name().to_string_lossy().starts_with(THEME_PREFIX) && !dry {
                fs::remove_file(e.path())?;
            }
        }
    }
    if !dry {
        remove_dir_if_exists(&d.fonts)?;
        let _ = Command::new("fc-cache").arg("-f").output();
    }
    println!("Ironhold removed.");
    Ok(())
}
