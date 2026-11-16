use anyhow::{Context, Result};
use std::fs;
use std::path::{Path, PathBuf};

pub fn absolute(p: &Path) -> Result<PathBuf> {
    let abs = fs::canonicalize(p).with_context(|| format!("cannot open {}", p.display()))?;
    // Windows canonical paths carry a `\\?\` verbatim prefix that the shell and registry don't want
    let s = abs.to_string_lossy();
    Ok(match s.strip_prefix(r"\\?\") {
        Some(rest) if !rest.starts_with("UNC") => PathBuf::from(rest),
        _ => abs,
    })
}

/// Recursively copy `src` into `dst` (dst is created; existing files are overwritten).
/// Symlinks are recreated as symlinks on Unix and copied as files elsewhere.
pub fn copy_dir(src: &Path, dst: &Path) -> Result<()> {
    fs::create_dir_all(dst).with_context(|| format!("create {}", dst.display()))?;
    for entry in fs::read_dir(src).with_context(|| format!("read {}", src.display()))? {
        let entry = entry?;
        let from = entry.path();
        let to = dst.join(entry.file_name());
        let meta = fs::symlink_metadata(&from)?;
        if meta.file_type().is_symlink() {
            #[cfg(unix)]
            {
                let target = fs::read_link(&from)?;
                let _ = fs::remove_file(&to);
                std::os::unix::fs::symlink(target, &to)?;
            }
            #[cfg(not(unix))]
            {
                fs::copy(&from, &to)?;
            }
        } else if meta.is_dir() {
            copy_dir(&from, &to)?;
        } else {
            fs::copy(&from, &to).with_context(|| format!("copy {} -> {}", from.display(), to.display()))?;
        }
    }
    Ok(())
}

pub fn remove_dir_if_exists(p: &Path) -> Result<()> {
    if p.exists() {
        fs::remove_dir_all(p).with_context(|| format!("remove {}", p.display()))?;
    }
    Ok(())
}

/// File name safe for wallpapers: `local-<sanitized stem>.<ext>`
pub fn local_art_name(img: &Path) -> String {
    let stem = img.file_stem().and_then(|s| s.to_str()).unwrap_or("art");
    let safe: String = stem
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() || c == '.' || c == '_' || c == '-' { c } else { '-' })
        .collect();
    let safe = safe.trim_matches('-');
    let ext = img.extension().and_then(|s| s.to_str()).unwrap_or("png").to_ascii_lowercase();
    format!("local-{}.{}", if safe.is_empty() { "art" } else { safe }, ext)
}

pub fn say(dry: bool, msg: impl AsRef<str>) {
    if dry {
        println!("[dry-run] {}", msg.as_ref());
    } else {
        println!("{}", msg.as_ref());
    }
}
