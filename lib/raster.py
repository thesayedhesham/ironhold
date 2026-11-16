"""SVG rasterization through the system librsvg + cairo (via ctypes, no pip packages needed).

Present on every GNOME desktop: librsvg-2.so.2 and libcairo.so.2.
"""
import ctypes
import ctypes.util

_CAIRO_FORMAT_ARGB32 = 0


class _RsvgRect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double),
                ("width", ctypes.c_double), ("height", ctypes.c_double)]


def _load(name, fallback):
    path = ctypes.util.find_library(name) or fallback
    try:
        return ctypes.CDLL(path)
    except OSError as e:
        raise SystemExit(f"Could not load {path}: {e}\n"
                         "Install it with: sudo apt install librsvg2-2 libcairo2") from e


_rsvg = _load("rsvg-2", "librsvg-2.so.2")
_cairo = _load("cairo", "libcairo.so.2")
_gobj = _load("gobject-2.0", "libgobject-2.0.so.0")

_rsvg.rsvg_handle_new_from_data.restype = ctypes.c_void_p
_rsvg.rsvg_handle_new_from_data.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p]
_rsvg.rsvg_handle_render_document.restype = ctypes.c_int
_rsvg.rsvg_handle_render_document.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                              ctypes.POINTER(_RsvgRect), ctypes.c_void_p]
_cairo.cairo_image_surface_create.restype = ctypes.c_void_p
_cairo.cairo_image_surface_create.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
_cairo.cairo_create.restype = ctypes.c_void_p
_cairo.cairo_create.argtypes = [ctypes.c_void_p]
_cairo.cairo_destroy.argtypes = [ctypes.c_void_p]
_cairo.cairo_surface_flush.argtypes = [ctypes.c_void_p]
_cairo.cairo_surface_destroy.argtypes = [ctypes.c_void_p]
_cairo.cairo_surface_write_to_png.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_cairo.cairo_image_surface_get_data.restype = ctypes.POINTER(ctypes.c_ubyte)
_cairo.cairo_image_surface_get_data.argtypes = [ctypes.c_void_p]
_cairo.cairo_image_surface_get_stride.restype = ctypes.c_int
_cairo.cairo_image_surface_get_stride.argtypes = [ctypes.c_void_p]
_gobj.g_object_unref.argtypes = [ctypes.c_void_p]


class Image:
    """Rendered RGBA image. `argb` holds premultiplied ARGB32 rows (cairo native, little-endian BGRA bytes)."""

    def __init__(self, width, height, argb):
        self.width, self.height, self.argb = width, height, argb

    def straight_bgra(self):
        """Un-premultiplied BGRA bytes, top-down (what Windows .cur/.ico bitmaps want)."""
        out = bytearray(self.argb)
        for i in range(0, len(out), 4):
            a = out[i + 3]
            if 0 < a < 255:
                for c in range(3):
                    out[i + c] = min(255, out[i + c] * 255 // a)
        return bytes(out)


def _render(svg, width, height, png_path=None):
    data = svg.encode() if isinstance(svg, str) else svg
    handle = _rsvg.rsvg_handle_new_from_data(data, len(data), None)
    if not handle:
        raise ValueError("librsvg could not parse SVG")
    surf = _cairo.cairo_image_surface_create(_CAIRO_FORMAT_ARGB32, width, height)
    cr = _cairo.cairo_create(surf)
    rect = _RsvgRect(0, 0, width, height)
    ok = _rsvg.rsvg_handle_render_document(handle, cr, ctypes.byref(rect), None)
    _cairo.cairo_surface_flush(surf)
    try:
        if not ok:
            raise ValueError("librsvg failed to render SVG")
        if png_path:
            _cairo.cairo_surface_write_to_png(surf, str(png_path).encode())
            return None
        stride = _cairo.cairo_image_surface_get_stride(surf)
        ptr = _cairo.cairo_image_surface_get_data(surf)
        raw = ctypes.string_at(ptr, stride * height)
        rows = b"".join(raw[y * stride:y * stride + width * 4] for y in range(height))
        return Image(width, height, rows)
    finally:
        _cairo.cairo_destroy(cr)
        _cairo.cairo_surface_destroy(surf)
        _gobj.g_object_unref(handle)


def svg_to_png(svg, path, width, height):
    _render(svg, width, height, png_path=path)


def svg_to_image(svg, width, height):
    return _render(svg, width, height)
