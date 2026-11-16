//! `ironhold` — apply, switch and restore the Ironhold desktop theme.
//!
//! Works on Ubuntu/GNOME (gsettings + XDG dirs) and Windows 10/11 (registry + Win32 APIs).
//! Your previous look is snapshotted the first time you apply, so `ironhold restore`
//! always returns to the desktop you had before Ironhold.

mod packs;
mod palette;
mod util;

#[cfg(not(windows))]
mod linux;
#[cfg(not(windows))]
use linux as platform;
#[cfg(windows)]
mod windows;
#[cfg(windows)]
use windows as platform;

use anyhow::Result;
use clap::{Parser, Subcommand, ValueEnum};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "ironhold", version, about = "Apply, switch and restore the Ironhold desktop theme")]
struct Cli {
    /// Directory holding built packs (contains linux/ and/or windows/). Defaults to auto-detect.
    #[arg(long, global = true, env = "IRONHOLD_PACKS")]
    packs: Option<PathBuf>,
    /// Show what would change without touching anything
    #[arg(long, global = true)]
    dry_run: bool,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// List variants available in the packs directory
    List,
    /// Install a variant and switch the desktop to it
    Apply {
        /// Variant name, e.g. Crown, Ember, Grave
        variant: String,
        /// Only apply these parts
        #[arg(long, value_delimiter = ',')]
        only: Vec<Part>,
        /// Skip these parts
        #[arg(long, value_delimiter = ',')]
        skip: Vec<Part>,
    },
    /// Use your own artwork (e.g. official wallpapers you downloaded)
    Art {
        #[command(subcommand)]
        cmd: ArtCmd,
    },
    /// Show what is currently active
    Status,
    /// Return the desktop to how it was before Ironhold was first applied
    Restore,
    /// Restore the previous look and remove all installed Ironhold files
    Uninstall,
    /// (Linux, from a source checkout) rebuild packs with build.py
    Build {
        /// Variants to build; all when omitted
        variants: Vec<String>,
    },
}

#[derive(Subcommand)]
enum ArtCmd {
    /// Set an image as the wallpaper of the active (or given) variant
    Use {
        image: PathBuf,
        /// Variant to attach the art to (default: the active one)
        #[arg(long)]
        variant: Option<String>,
        /// Also recolor the theme from the artwork's palette
        #[arg(long)]
        recolor: bool,
        /// Name for the recolored variant (Linux; default derived from the file name)
        #[arg(long)]
        name: Option<String>,
    },
    /// Copy images into the source tree's local-art/ folder for future builds
    Import {
        images: Vec<PathBuf>,
        #[arg(long)]
        variant: Option<String>,
    },
    /// Print the palette the client would derive from an image
    Palette { image: PathBuf },
}

#[derive(Copy, Clone, Debug, PartialEq, Eq, ValueEnum)]
pub enum Part {
    Wallpaper,
    Cursors,
    Sounds,
    Colors,
    Gtk,
    Shell,
    Icons,
    Fonts,
}

impl Part {
    pub fn all() -> Vec<Part> {
        use Part::*;
        vec![Wallpaper, Cursors, Sounds, Colors, Gtk, Shell, Icons, Fonts]
    }
}

pub struct Ctx {
    pub packs: PathBuf,
    pub dry_run: bool,
}

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e:#}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    let ctx = || -> Result<Ctx> { Ok(Ctx { packs: packs::locate(cli.packs.clone())?, dry_run: cli.dry_run }) };
    match cli.cmd {
        Cmd::List => {
            let c = ctx()?;
            let found = packs::variants(&c.packs, platform::PACK_KIND)?;
            if found.is_empty() {
                println!("No {} packs in {}. Build them first.", platform::PACK_KIND, c.packs.display());
            }
            for v in found {
                println!("{v}");
            }
        }
        Cmd::Apply { variant, only, skip } => {
            let parts: Vec<Part> = if only.is_empty() { Part::all() } else { only };
            let parts: Vec<Part> = parts.into_iter().filter(|p| !skip.contains(p)).collect();
            platform::apply(&ctx()?, &packs::normalize(&variant), &parts)?;
        }
        Cmd::Art { cmd } => match cmd {
            ArtCmd::Use { image, variant, recolor, name } => {
                let image = util::absolute(&image)?;
                platform::art_use(&ctx()?, &image, variant.as_deref().map(packs::normalize).as_deref(), recolor, name)?;
            }
            ArtCmd::Import { images, variant } => {
                let root = packs::source_root().ok_or_else(|| anyhow::anyhow!("not inside an Ironhold source checkout"))?;
                for img in images {
                    let dst = packs::import_art(&root, &img, variant.as_deref())?;
                    println!("imported {}", dst.display());
                }
                println!("Rebuild to include them: ironhold build");
            }
            ArtCmd::Palette { image } => {
                let p = palette::derive(&image)?;
                println!("trim (metal) {}\naccent       {}\nbackground   {}", p.metal_hex(), p.accent_hex(), p.bg_hex());
            }
        },
        Cmd::Status => platform::status()?,
        Cmd::Restore => platform::restore(cli.dry_run)?,
        Cmd::Uninstall => platform::uninstall(cli.dry_run)?,
        Cmd::Build { variants } => packs::build(&variants)?,
    }
    Ok(())
}
