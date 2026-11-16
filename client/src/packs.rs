//! Locating built packs, variant names, and source-tree helpers (local-art import, build).
use anyhow::{bail, Context, Result};
use std::path::{Path, PathBuf};
use std::{env, fs};

pub const THEME_PREFIX: &str = "Ironhold-";

/// `crown` / `Crown` / `Ironhold-Crown` -> `Crown`
pub fn normalize(v: &str) -> String {
    let v = v.strip_prefix(THEME_PREFIX).unwrap_or(v);
    let mut c = v.chars();
    match c.next() {
        Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
        None => String::new(),
    }
}

pub fn theme_name(variant: &str) -> String {
    format!("{THEME_PREFIX}{variant}")
}

fn candidates(explicit: Option<PathBuf>) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(p) = explicit {
        out.push(p);
        return out;
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(dir) = exe.parent() {
            out.push(dir.join("packs"));
            for anc in dir.ancestors() {
                out.push(anc.join("dist"));
            }
        }
    }
    if let Ok(cwd) = env::current_dir() {
        out.push(cwd.join("packs"));
        for anc in cwd.ancestors() {
            out.push(anc.join("dist"));
        }
    }
    out
}

/// A packs directory contains `linux/` and/or `windows/` subfolders produced by build.py.
pub fn locate(explicit: Option<PathBuf>) -> Result<PathBuf> {
    for c in candidates(explicit.clone()) {
        if c.join("linux").is_dir() || c.join("windows").is_dir() {
            return Ok(c);
        }
    }
    match explicit {
        Some(p) => bail!("{} has no linux/ or windows/ packs", p.display()),
        None => bail!("could not find built packs; run `python3 build.py` or pass --packs <dir>"),
    }
}

/// Variant names available for a platform ("linux" or "windows").
pub fn variants(packs: &Path, kind: &str) -> Result<Vec<String>> {
    let dir = if kind == "linux" { packs.join("linux").join("themes") } else { packs.join("windows") };
    let mut out = Vec::new();
    if dir.is_dir() {
        for e in fs::read_dir(&dir)? {
            let name = e?.file_name().to_string_lossy().to_string();
            if let Some(v) = name.strip_prefix(THEME_PREFIX) {
                out.push(v.to_string());
            }
        }
    }
    out.sort();
    Ok(out)
}

pub fn require_variant(packs: &Path, kind: &str, variant: &str) -> Result<()> {
    let have = variants(packs, kind)?;
    if !have.iter().any(|v| v == variant) {
        bail!("variant '{variant}' not found in {} (have: {})", packs.display(),
              if have.is_empty() { "none".into() } else { have.join(", ") });
    }
    Ok(())
}

/// Root of an Ironhold source checkout (has build.py + config.json), searched upward from exe and cwd.
pub fn source_root() -> Option<PathBuf> {
    let mut starts = Vec::new();
    if let Ok(c) = env::current_dir() {
        starts.push(c);
    }
    if let Ok(e) = env::current_exe() {
        if let Some(p) = e.parent() {
            starts.push(p.to_path_buf());
        }
    }
    for s in starts {
        for anc in s.ancestors() {
            if anc.join("build.py").is_file() && anc.join("config.json").is_file() {
                return Some(anc.to_path_buf());
            }
        }
    }
    None
}

pub fn import_art(root: &Path, img: &Path, variant: Option<&str>) -> Result<PathBuf> {
    let ext = img.extension().and_then(|e| e.to_str()).unwrap_or("").to_ascii_lowercase();
    if !matches!(ext.as_str(), "jpg" | "jpeg" | "png") {
        bail!("{}: only .jpg/.jpeg/.png are supported", img.display());
    }
    let dir = match variant {
        Some(v) => root.join("local-art").join(normalize(v)),
        None => root.join("local-art"),
    };
    fs::create_dir_all(&dir)?;
    let dst = dir.join(img.file_name().context("bad file name")?);
    fs::copy(img, &dst).with_context(|| format!("copy {}", img.display()))?;
    Ok(dst)
}

/// Run build.py from the source checkout (Linux only: it needs librsvg/cairo).
pub fn build(variants: &[String]) -> Result<()> {
    let root = source_root().context("`build` must run inside an Ironhold source checkout")?;
    let mut cmd = std::process::Command::new("python3");
    cmd.current_dir(&root).arg("build.py");
    for v in variants {
        cmd.arg("--variant").arg(normalize(v));
    }
    let st = cmd.status().context("running python3 build.py")?;
    if !st.success() {
        bail!("build.py failed");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn normalizes_names() {
        assert_eq!(normalize("crown"), "Crown");
        assert_eq!(normalize("Ironhold-Ember"), "Ember");
        assert_eq!(theme_name("Grave"), "Ironhold-Grave");
    }
}
