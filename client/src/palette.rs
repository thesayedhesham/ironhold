//! Palette extraction from artwork (Rust port of lib/palette.py's role mapping, trimmed to
//! what the client needs live: trim/accent/background colors).
use anyhow::{Context, Result};
use std::path::Path;

#[derive(Clone, Copy, Debug)]
pub struct Hls {
    pub h: f64,
    pub l: f64,
    pub s: f64,
}

pub struct Palette {
    pub metal: Hls,
    pub accent: Hls,
    pub bg: Hls,
}

fn rgb_to_hls(r: f64, g: f64, b: f64) -> Hls {
    let max = r.max(g).max(b);
    let min = r.min(g).min(b);
    let l = (max + min) / 2.0;
    if (max - min).abs() < 1e-9 {
        return Hls { h: 0.0, l, s: 0.0 };
    }
    let d = max - min;
    let s = if l <= 0.5 { d / (max + min) } else { d / (2.0 - max - min) };
    let h = if max == r {
        ((g - b) / d).rem_euclid(6.0)
    } else if max == g {
        (b - r) / d + 2.0
    } else {
        (r - g) / d + 4.0
    } / 6.0;
    Hls { h, l, s }
}

pub fn hls_to_rgb(c: Hls) -> (u8, u8, u8) {
    let (h, l, s) = (c.h.rem_euclid(1.0), c.l.clamp(0.0, 1.0), c.s.clamp(0.0, 1.0));
    let q = if l < 0.5 { l * (1.0 + s) } else { l + s - l * s };
    let p = 2.0 * l - q;
    let f = |t: f64| {
        let t = t.rem_euclid(1.0);
        let v = if t < 1.0 / 6.0 {
            p + (q - p) * 6.0 * t
        } else if t < 0.5 {
            q
        } else if t < 2.0 / 3.0 {
            p + (q - p) * (2.0 / 3.0 - t) * 6.0
        } else {
            p
        };
        (v * 255.0).round() as u8
    };
    (f(h + 1.0 / 3.0), f(h), f(h - 1.0 / 3.0))
}

fn hex(c: Hls) -> String {
    let (r, g, b) = hls_to_rgb(c);
    format!("#{r:02x}{g:02x}{b:02x}")
}

impl Palette {
    #[cfg_attr(not(windows), allow(dead_code))]
    pub fn metal_rgb(&self) -> (u8, u8, u8) {
        hls_to_rgb(self.metal)
    }
    pub fn metal_hex(&self) -> String {
        hex(self.metal)
    }
    pub fn accent_hex(&self) -> String {
        hex(self.accent)
    }
    pub fn bg_hex(&self) -> String {
        hex(self.bg)
    }
}

fn hue_dist(a: f64, b: f64) -> f64 {
    let d = (a - b).abs().rem_euclid(1.0);
    d.min(1.0 - d)
}

/// Deterministic k-means over RGB pixels; returns (center, weight) sorted by weight.
fn kmeans(px: &[[f64; 3]], k: usize, iters: usize) -> Vec<([f64; 3], f64)> {
    let k = k.min(px.len()).max(1);
    let mut centers: Vec<[f64; 3]> = (0..k).map(|i| px[i * px.len() / k]).collect();
    let mut assign = vec![0usize; px.len()];
    for _ in 0..iters {
        for (i, p) in px.iter().enumerate() {
            assign[i] = (0..k)
                .min_by(|&a, &b| dist(p, &centers[a]).partial_cmp(&dist(p, &centers[b])).unwrap())
                .unwrap();
        }
        let mut sums = vec![[0.0; 3]; k];
        let mut counts = vec![0usize; k];
        for (i, p) in px.iter().enumerate() {
            for c in 0..3 {
                sums[assign[i]][c] += p[c];
            }
            counts[assign[i]] += 1;
        }
        for j in 0..k {
            if counts[j] > 0 {
                centers[j] = [sums[j][0] / counts[j] as f64, sums[j][1] / counts[j] as f64, sums[j][2] / counts[j] as f64];
            }
        }
    }
    let mut counts = vec![0usize; k];
    for a in &assign {
        counts[*a] += 1;
    }
    let mut out: Vec<_> = centers.into_iter().zip(counts).filter(|(_, n)| *n > 0)
        .map(|(c, n)| (c, n as f64 / px.len() as f64)).collect();
    out.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    out
}

fn dist(a: &[f64; 3], b: &[f64; 3]) -> f64 {
    (a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2) + (a[2] - b[2]).powi(2)
}

pub fn derive(path: &Path) -> Result<Palette> {
    let img = image::open(path).with_context(|| format!("cannot read image {}", path.display()))?;
    let small = img.thumbnail(120, 120).to_rgb8();
    let px: Vec<[f64; 3]> = small.pixels().map(|p| [p[0] as f64 / 255.0, p[1] as f64 / 255.0, p[2] as f64 / 255.0]).collect();
    Ok(derive_from_pixels(&px))
}

pub fn derive_from_pixels(px: &[[f64; 3]]) -> Palette {
    let clusters: Vec<(Hls, f64)> = kmeans(px, 10, 12).into_iter().map(|(c, w)| (rgb_to_hls(c[0], c[1], c[2]), w)).collect();

    // trim: strongest warm gold/bronze tone
    let metal = clusters.iter()
        .filter(|(c, _)| (20.0 / 360.0..=62.0 / 360.0).contains(&c.h) && c.s > 0.3 && c.l > 0.25 && c.l < 0.85)
        .max_by(|a, b| score_metal(a).partial_cmp(&score_metal(b)).unwrap())
        .map(|(c, _)| Hls { h: c.h, l: 0.52, s: c.s.max(0.55) })
        .unwrap_or(Hls { h: 43.0 / 360.0, l: 0.52, s: 0.55 });

    // accent: most saturated present hue that differs from the trim
    let pick = |pred: &dyn Fn(&Hls) -> bool| {
        clusters.iter().filter(|(c, _)| pred(c))
            .max_by(|a, b| (a.0.s * a.1.sqrt()).partial_cmp(&(b.0.s * b.1.sqrt())).unwrap())
            .map(|(c, _)| *c)
    };
    let accent = pick(&|c| hue_dist(c.h, metal.h) > 12.0 / 360.0 && c.s > 0.3 && c.l > 0.05 && c.l < 0.75)
        .or_else(|| pick(&|c| c.s > 0.3 && c.l > 0.05))
        .map(|c| Hls { h: c.h, l: 0.38, s: c.s.max(0.5) })
        .unwrap_or(Hls { h: 217.0 / 360.0, l: 0.38, s: 0.6 });

    // background: hue of the darkest substantial region, kept very dark
    let bg = clusters.iter().filter(|(_, w)| *w > 0.03)
        .min_by(|a, b| a.0.l.partial_cmp(&b.0.l).unwrap())
        .map(|(c, _)| Hls { h: c.h, l: 0.07, s: c.s.clamp(0.18, 0.4) })
        .unwrap_or(Hls { h: 0.6, l: 0.07, s: 0.3 });

    Palette { metal, accent, bg }
}

fn score_metal((c, w): &(Hls, f64)) -> f64 {
    w * c.s * (1.0 - (c.l - 0.5).abs())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn red_art_gets_red_accent_and_gold_trim() {
        // mostly dark reds with a little gold, like the Ember wallpaper
        let mut px = vec![[0.25, 0.04, 0.03]; 600];
        px.extend(vec![[0.06, 0.02, 0.02]; 300]);
        px.extend(vec![[0.85, 0.62, 0.2]; 60]);
        let p = derive_from_pixels(&px);
        let (r, g, b) = hls_to_rgb(p.accent);
        assert!(r > g && r > b, "accent should be red, got {}", p.accent_hex());
        let (r, g, b) = p.metal_rgb();
        assert!(r > b && g > b, "trim should be warm, got {}", p.metal_hex());
    }

    #[test]
    fn hls_roundtrip() {
        let c = rgb_to_hls(201.0 / 255.0, 160.0 / 255.0, 61.0 / 255.0);
        assert_eq!(hls_to_rgb(c), (201, 160, 61));
    }
}
