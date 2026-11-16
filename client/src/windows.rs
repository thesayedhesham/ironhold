//! Windows 10/11 backend: per-user registry + Win32 APIs, no admin rights needed.
use crate::packs::{self, theme_name, THEME_PREFIX};
use crate::util::{copy_dir, local_art_name, remove_dir_if_exists, say};
use crate::{palette, Ctx, Part};
use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::{env, fs};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    SendMessageTimeoutW, SystemParametersInfoW, HWND_BROADCAST, SMTO_ABORTIFHUNG, SPIF_SENDCHANGE,
    SPIF_UPDATEINIFILE, SPI_SETCURSORS, SPI_SETDESKWALLPAPER, WM_SETTINGCHANGE,
};
use winreg::enums::*;
use winreg::{RegKey, RegValue};

pub const PACK_KIND: &str = "windows";

const ROLES: [&str; 17] = [
    "Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No", "SizeNS", "SizeWE",
    "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person",
];
const DESKTOP: &str = r"Control Panel\Desktop";
const CURSORS: &str = r"Control Panel\Cursors";
const SCHEMES: &str = r"AppEvents\Schemes";
const APPS: &str = r"AppEvents\Schemes\Apps";
const PERSONALIZE: &str = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize";
const ACCENT: &str = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent";
const DWM: &str = r"Software\Microsoft\Windows\DWM";

fn hkcu() -> RegKey {
    RegKey::predef(HKEY_CURRENT_USER)
}

fn local_appdata() -> Result<PathBuf> {
    Ok(PathBuf::from(env::var("LOCALAPPDATA").context("LOCALAPPDATA not set")?))
}

fn themes_dir() -> Result<PathBuf> {
    Ok(local_appdata()?.join(r"Microsoft\Windows\Themes"))
}

fn state_dir() -> Result<PathBuf> {
    Ok(local_appdata()?.join("Ironhold"))
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

// ---------------------------------------------------------------- registry helpers
fn set_sz(key: &str, name: &str, value: &str) -> Result<()> {
    let (k, _) = hkcu().create_subkey(key).with_context(|| format!("open HKCU\\{key}"))?;
    k.set_value(name, &value.to_string()).with_context(|| format!("set HKCU\\{key}\\{name}"))
}

fn set_dword(key: &str, name: &str, value: u32) -> Result<()> {
    let (k, _) = hkcu().create_subkey(key)?;
    k.set_value(name, &value).with_context(|| format!("set HKCU\\{key}\\{name}"))
}

fn get_sz(key: &str, name: &str) -> Option<String> {
    hkcu().open_subkey(key).ok()?.get_value::<String, _>(name).ok()
}

// ---------------------------------------------------------------- Win32 calls
fn spi_wallpaper(path: &str) {
    let mut w = wide(path);
    unsafe {
        SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, w.as_mut_ptr().cast(), SPIF_UPDATEINIFILE | SPIF_SENDCHANGE);
    }
}

fn spi_reload_cursors() {
    unsafe {
        SystemParametersInfoW(SPI_SETCURSORS, 0, std::ptr::null_mut(), SPIF_UPDATEINIFILE | SPIF_SENDCHANGE);
    }
}

fn broadcast(area: &str) {
    let w = wide(area);
    let mut result = 0usize;
    unsafe {
        SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, w.as_ptr() as isize, SMTO_ABORTIFHUNG, 3000, &mut result);
    }
}

// ---------------------------------------------------------------- snapshot (exact raw registry values)
#[derive(Serialize, Deserialize)]
struct Saved {
    key: String,
    name: String,
    vtype: Option<u32>,
    data: Vec<u8>,
}

fn regtype(v: u32) -> RegType {
    match v {
        0 => REG_NONE,
        1 => REG_SZ,
        2 => REG_EXPAND_SZ,
        4 => REG_DWORD,
        7 => REG_MULTI_SZ,
        11 => REG_QWORD,
        _ => REG_BINARY,
    }
}

fn read_raw(key: &str, name: &str) -> Saved {
    let v = hkcu().open_subkey(key).ok().and_then(|k| k.get_raw_value(name).ok());
    Saved {
        key: key.into(),
        name: name.into(),
        vtype: v.as_ref().map(|r| r.vtype.clone() as u32),
        data: v.map(|r| r.bytes).unwrap_or_default(),
    }
}

fn write_raw(s: &Saved) -> Result<()> {
    match s.vtype {
        Some(t) => {
            let (k, _) = hkcu().create_subkey(&s.key)?;
            k.set_raw_value(&s.name, &RegValue { bytes: s.data.clone(), vtype: regtype(t) })?;
        }
        None => {
            if let Ok(k) = hkcu().open_subkey_with_flags(&s.key, KEY_SET_VALUE) {
                let _ = k.delete_value(&s.name);
            }
        }
    }
    Ok(())
}

fn sound_map(pack: &Path) -> Result<Vec<(String, String)>> {
    Ok(fs::read_to_string(pack.join("sound-map.txt"))?.lines()
        .filter_map(|l| l.split_once('=').map(|(a, b)| (a.trim().to_string(), b.trim().to_string()))).collect())
}

fn cursor_map(pack: &Path) -> Result<HashMap<String, String>> {
    Ok(fs::read_to_string(pack.join("cursor-map.txt"))?.lines()
        .filter_map(|l| l.split_once('=').map(|(a, b)| (a.trim().to_string(), b.trim().to_string()))).collect())
}

fn snapshot_once(pack: &Path, dry: bool) -> Result<()> {
    let p = state_dir()?.join("backup.json");
    if p.exists() {
        return Ok(());
    }
    let mut saved = vec![];
    for n in ["Wallpaper", "WallpaperStyle", "TileWallpaper"] {
        saved.push(read_raw(DESKTOP, n));
    }
    saved.push(read_raw(CURSORS, ""));
    saved.push(read_raw(CURSORS, "Scheme Source"));
    for r in ROLES {
        saved.push(read_raw(CURSORS, r));
    }
    saved.push(read_raw(SCHEMES, ""));
    for (ev, _) in sound_map(pack)? {
        saved.push(read_raw(&format!(r"{APPS}\{ev}\.Current"), ""));
    }
    for n in ["AppsUseLightTheme", "SystemUsesLightTheme"] {
        saved.push(read_raw(PERSONALIZE, n));
    }
    for n in ["AccentPalette", "AccentColorMenu", "StartColorMenu"] {
        saved.push(read_raw(ACCENT, n));
    }
    for n in ["AccentColor", "ColorizationColor", "ColorizationAfterglow"] {
        saved.push(read_raw(DWM, n));
    }
    say(dry, format!("saving current look to {}", p.display()));
    if !dry {
        fs::create_dir_all(p.parent().unwrap())?;
        fs::write(&p, serde_json::to_string(&saved)?)?;
    }
    Ok(())
}

// ---------------------------------------------------------------- pieces
fn set_wallpaper(dry: bool, file: &Path) -> Result<()> {
    say(dry, format!("wallpaper -> {}", file.display()));
    if !dry {
        set_sz(DESKTOP, "WallpaperStyle", "10")?;
        set_sz(DESKTOP, "TileWallpaper", "0")?;
        spi_wallpaper(&file.display().to_string());
    }
    Ok(())
}

fn set_accent(dry: bool, (r, g, b): (u8, u8, u8)) -> Result<()> {
    say(dry, format!("accent color -> #{r:02X}{g:02X}{b:02X}, dark mode on"));
    if dry {
        return Ok(());
    }
    set_dword(PERSONALIZE, "AppsUseLightTheme", 0)?;
    set_dword(PERSONALIZE, "SystemUsesLightTheme", 0)?;
    let argb = 0xFF00_0000 | (r as u32) << 16 | (g as u32) << 8 | b as u32;
    let abgr = 0xFF00_0000 | (b as u32) << 16 | (g as u32) << 8 | r as u32;
    let mut pal = Vec::with_capacity(32);
    for k in [1.6, 1.35, 1.15, 1.0, 0.8, 0.6, 0.42, 0.3] {
        for c in [r, g, b] {
            pal.push(((c as f64) * k).min(255.0) as u8);
        }
        pal.push(0);
    }
    let (acc, _) = hkcu().create_subkey(ACCENT)?;
    acc.set_raw_value("AccentPalette", &RegValue { bytes: pal, vtype: REG_BINARY })?;
    set_dword(ACCENT, "AccentColorMenu", abgr)?;
    set_dword(ACCENT, "StartColorMenu", abgr)?;
    set_dword(DWM, "AccentColor", abgr)?;
    set_dword(DWM, "ColorizationColor", argb)?;
    set_dword(DWM, "ColorizationAfterglow", argb)?;
    Ok(())
}

fn theme_accent(theme_text: &str) -> Option<(u8, u8, u8)> {
    let line = theme_text.lines().find(|l| l.starts_with("ColorizationColor=0X"))?;
    let hex = &line["ColorizationColor=0X".len()..].trim()[2..8];
    let v = u32::from_str_radix(hex, 16).ok()?;
    Some(((v >> 16) as u8, (v >> 8) as u8, v as u8))
}

fn write_utf16(path: &Path, text: &str) -> Result<()> {
    let mut bytes = vec![0xFF, 0xFE];
    for u in text.encode_utf16() {
        bytes.extend_from_slice(&u.to_le_bytes());
    }
    fs::write(path, bytes)?;
    Ok(())
}

fn active_variant() -> Option<String> {
    fs::read_to_string(state_dir().ok()?.join("active")).ok().map(|s| s.trim().to_string()).filter(|s| !s.is_empty())
}

// ---------------------------------------------------------------- apply
pub fn apply(ctx: &Ctx, variant: &str, parts: &[Part]) -> Result<()> {
    packs::require_variant(&ctx.packs, PACK_KIND, variant)?;
    let dry = ctx.dry_run;
    let theme = theme_name(variant);
    let pack = ctx.packs.join("windows").join(&theme);
    let dest = themes_dir()?.join(&theme);
    let has = |p: Part| parts.contains(&p);
    snapshot_once(&pack, dry)?;

    say(dry, format!("installing {}", dest.display()));
    let theme_text = fs::read_to_string(pack.join(format!("{theme}.theme.in")))?
        .replace("@@DIR@@", &dest.display().to_string());
    if !dry {
        for sub in ["Cursors", "Wallpapers", "Icons", "Sounds"] {
            remove_dir_if_exists(&dest.join(sub))?;
            copy_dir(&pack.join(sub), &dest.join(sub))?;
        }
        write_utf16(&dest.join(format!("{theme}.theme")), &theme_text)?;
    }

    let cmap = cursor_map(&pack)?;
    let cursor_path = |role: &str| dest.join("Cursors").join(&cmap[role]).display().to_string();
    let sounds = sound_map(&pack)?;
    let sound_id: String = theme.chars().filter(|c| c.is_ascii_alphanumeric()).collect();

    if !dry {
        // register schemes so they appear in Mouse Properties and Sound settings
        let joined = ROLES.iter().map(|r| cursor_path(r)).collect::<Vec<_>>().join(",");
        set_sz(&format!(r"{CURSORS}\Schemes"), &theme, &joined)?;
        set_sz(&format!(r"{SCHEMES}\Names\{sound_id}"), "", &theme)?;
        for (ev, file) in &sounds {
            set_sz(&format!(r"{APPS}\{ev}\{sound_id}"), "", &dest.join("Sounds").join(file).display().to_string())?;
        }
    }

    if has(Part::Wallpaper) {
        let wall = theme_text.lines().find_map(|l| l.strip_prefix("Wallpaper=")).context("no wallpaper in theme")?;
        set_wallpaper(dry, Path::new(wall.trim()))?;
    }
    if has(Part::Cursors) {
        say(dry, "cursors -> gauntlet scheme");
        if !dry {
            for r in ROLES {
                set_sz(CURSORS, r, &cursor_path(r))?;
            }
            set_sz(CURSORS, "", &theme)?;
            set_dword(CURSORS, "Scheme Source", 1)?;
            spi_reload_cursors();
        }
    }
    if has(Part::Sounds) {
        say(dry, "sounds -> fantasy scheme");
        if !dry {
            for (ev, file) in &sounds {
                set_sz(&format!(r"{APPS}\{ev}\.Current"), "", &dest.join("Sounds").join(file).display().to_string())?;
            }
            set_sz(SCHEMES, "", &sound_id)?;
        }
    }
    if has(Part::Colors) {
        if let Some(rgb) = theme_accent(&theme_text) {
            set_accent(dry, rgb)?;
        }
    }
    if !dry {
        broadcast("ImmersiveColorSet");
        broadcast("WindowsThemeElement");
        fs::create_dir_all(state_dir()?)?;
        fs::write(state_dir()?.join("active"), variant)?;
    }
    println!("{theme} applied. Folder icons for manual use: {}", dest.join("Icons").display());
    Ok(())
}

// ---------------------------------------------------------------- art
pub fn art_use(ctx: &Ctx, image: &Path, variant: Option<&str>, recolor: bool, _name: Option<String>) -> Result<()> {
    let dry = ctx.dry_run;
    let base = variant.map(String::from).or_else(active_variant)
        .context("no active Ironhold variant; pass --variant or run `ironhold apply <variant>` first")?;
    let theme = theme_name(&base);
    let pack = ctx.packs.join("windows").join(&theme);
    snapshot_once(&pack, dry)?;
    let walls = themes_dir()?.join(&theme).join("Wallpapers");
    let dst = walls.join(local_art_name(image));
    say(dry, format!("copying {} -> {}", image.display(), dst.display()));
    if !dry {
        fs::create_dir_all(&walls)?;
        fs::copy(image, &dst)?;
    }
    set_wallpaper(dry, &dst)?;
    if recolor {
        let p = palette::derive(image)?;
        println!("palette from artwork: trim {} accent {} background {}", p.metal_hex(), p.accent_hex(), p.bg_hex());
        set_accent(dry, p.metal_rgb())?;
        if !dry {
            broadcast("ImmersiveColorSet");
        }
        println!("note: cursors and sounds keep the {base} style; a full recolor needs a rebuild (ironhold build on Linux).");
    }
    Ok(())
}

// ---------------------------------------------------------------- status / restore / uninstall
pub fn status() -> Result<()> {
    println!("active variant : {}", active_variant().unwrap_or_else(|| "none".into()));
    println!("backup saved   : {}", if state_dir()?.join("backup.json").exists() { "yes" } else { "no" });
    println!("wallpaper      : {}", get_sz(DESKTOP, "Wallpaper").unwrap_or_default());
    println!("cursor scheme  : {}", get_sz(CURSORS, "").unwrap_or_default());
    println!("sound scheme   : {}", get_sz(SCHEMES, "").unwrap_or_default());
    let dark = hkcu().open_subkey(PERSONALIZE).ok().and_then(|k| k.get_value::<u32, _>("AppsUseLightTheme").ok());
    println!("dark mode      : {}", match dark { Some(0) => "on", Some(_) => "off", None => "default" });
    Ok(())
}

pub fn restore(dry: bool) -> Result<()> {
    let p = state_dir()?.join("backup.json");
    let saved: Vec<Saved> = serde_json::from_str(&fs::read_to_string(&p).with_context(|| {
        format!("no saved look at {} (nothing to restore)", p.display())
    })?)?;
    say(dry, format!("restoring {} saved settings", saved.len()));
    if dry {
        return Ok(());
    }
    for s in &saved {
        write_raw(s)?;
    }
    if let Some(w) = get_sz(DESKTOP, "Wallpaper") {
        spi_wallpaper(&w);
    }
    spi_reload_cursors();
    broadcast("ImmersiveColorSet");
    broadcast("WindowsThemeElement");
    fs::remove_file(&p)?;
    let _ = fs::remove_file(state_dir()?.join("active"));
    println!("Previous look restored.");
    Ok(())
}

pub fn uninstall(dry: bool) -> Result<()> {
    if state_dir()?.join("backup.json").exists() {
        restore(dry)?;
    }
    if dry {
        println!("[dry-run] would remove Ironhold themes, cursor and sound schemes");
        return Ok(());
    }
    if let Ok(k) = hkcu().open_subkey_with_flags(format!(r"{CURSORS}\Schemes"), KEY_ALL_ACCESS) {
        let names: Vec<String> = k.enum_values().filter_map(|v| v.ok().map(|(n, _)| n)).collect();
        for n in names.iter().filter(|n| n.starts_with(THEME_PREFIX)) {
            let _ = k.delete_value(n);
        }
    }
    if let Ok(apps) = hkcu().open_subkey(APPS) {
        for app in apps.enum_keys().flatten() {
            if let Ok(a) = apps.open_subkey(&app) {
                for ev in a.enum_keys().flatten() {
                    if let Ok(e) = a.open_subkey_with_flags(&ev, KEY_ALL_ACCESS) {
                        for sub in e.enum_keys().flatten().filter(|s| s.starts_with("Ironhold")).collect::<Vec<_>>() {
                            let _ = e.delete_subkey_all(&sub);
                        }
                    }
                }
            }
        }
    }
    if let Ok(names) = hkcu().open_subkey_with_flags(format!(r"{SCHEMES}\Names"), KEY_ALL_ACCESS) {
        for sub in names.enum_keys().flatten().filter(|s| s.starts_with("Ironhold")).collect::<Vec<_>>() {
            let _ = names.delete_subkey_all(&sub);
        }
    }
    if get_sz(CURSORS, "").map(|s| s.starts_with(THEME_PREFIX)).unwrap_or(false) {
        for r in ROLES {
            set_sz(CURSORS, r, "")?;
        }
        set_sz(CURSORS, "", "Windows Default")?;
        set_dword(CURSORS, "Scheme Source", 2)?;
        spi_reload_cursors();
    }
    for e in fs::read_dir(themes_dir()?)?.flatten() {
        if e.file_name().to_string_lossy().starts_with(THEME_PREFIX) {
            remove_dir_if_exists(&e.path())?;
        }
    }
    if get_sz(SCHEMES, "").map(|s| s.starts_with("Ironhold")).unwrap_or(false) {
        set_sz(SCHEMES, "", ".Default")?;
    }
    let _ = fs::remove_file(state_dir()?.join("active"));
    println!("Ironhold removed.");
    if false {
        bail!("unreachable");
    }
    Ok(())
}
