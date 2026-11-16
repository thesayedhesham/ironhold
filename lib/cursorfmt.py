"""Writers for cursor/icon binary formats: Xcursor (Linux), .cur / .ani / .ico (Windows)."""
import struct

# ---------------------------------------------------------------- Xcursor
_XCUR_IMAGE = 0xFFFD0002


def write_xcursor(path, frames):
    """frames: list of (nominal_size, Image, xhot, yhot, delay_ms) — all sizes, all frames."""
    header_len, toc_len, chunk_hdr = 16, 12, 36
    out = bytearray(struct.pack("<4sIII", b"Xcur", header_len, 0x10000, len(frames)))
    pos = header_len + toc_len * len(frames)
    chunks = []
    for size, img, xh, yh, delay in frames:
        out += struct.pack("<III", _XCUR_IMAGE, size, pos)
        chunk = struct.pack("<IIIIIIIII", chunk_hdr, _XCUR_IMAGE, size, 1,
                            img.width, img.height, xh, yh, delay) + img.argb
        chunks.append(chunk)
        pos += len(chunk)
    for c in chunks:
        out += c
    with open(path, "wb") as f:
        f.write(out)


# ---------------------------------------------------------------- Windows DIB entries
def _dib(img):
    """32bpp BITMAPINFOHEADER + bottom-up BGRA + empty AND mask."""
    w, h = img.width, img.height
    bgra = img.straight_bgra()
    rows = [bgra[y * w * 4:(y + 1) * w * 4] for y in range(h)]
    xor = b"".join(reversed(rows))
    mask_stride = ((w + 31) // 32) * 4
    and_mask = b"\x00" * (mask_stride * h)
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(xor) + len(and_mask), 0, 0, 0, 0)
    return hdr + xor + and_mask


def _icondir(kind, entries):
    """entries: list of (Image, field1, field2) — hotspot for cursors, planes/bpp for icons."""
    out = bytearray(struct.pack("<HHH", 0, kind, len(entries)))
    offset = 6 + 16 * len(entries)
    blobs = []
    for img, f1, f2 in entries:
        blob = _dib(img)
        dim = lambda v: 0 if v >= 256 else v
        out += struct.pack("<BBBBHHII", dim(img.width), dim(img.height), 0, 0, f1, f2, len(blob), offset)
        blobs.append(blob)
        offset += len(blob)
    for b in blobs:
        out += b
    return bytes(out)


def cur_bytes(images_with_hotspots):
    """images_with_hotspots: list of (Image, xhot, yhot)."""
    return _icondir(2, images_with_hotspots)


def write_cur(path, images_with_hotspots):
    with open(path, "wb") as f:
        f.write(cur_bytes(images_with_hotspots))


def write_ico(path, images):
    with open(path, "wb") as f:
        f.write(_icondir(1, [(img, 1, 32) for img in images]))


def write_ani(path, frames, jiffies):
    """frames: list of cur_bytes(); jiffies: frame duration in 1/60 s."""
    def chunk(tag, data):
        pad = b"\x00" if len(data) % 2 else b""
        return tag + struct.pack("<I", len(data)) + data + pad

    anih = struct.pack("<IIIIIIIII", 36, len(frames), len(frames), 0, 0, 0, 0, jiffies, 1)
    fram = b"fram" + b"".join(chunk(b"icon", f) for f in frames)
    body = b"ACON" + chunk(b"anih", anih) + chunk(b"LIST", fram)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", len(body)) + body)
