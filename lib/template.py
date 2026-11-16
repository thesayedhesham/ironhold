"""Tiny template engine: {{key}} -> palette color, {{key,0.4}} -> rgba() with alpha."""
import re

_TOKEN = re.compile(r"\{\{\s*(\w+)\s*(?:,\s*([0-9.]+)\s*)?\}\}")


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def render(text, values, source="<template>"):
    def sub(m):
        key, alpha = m.group(1), m.group(2)
        if key not in values:
            raise KeyError(f"{source}: unknown template key '{key}'")
        val = str(values[key])
        if alpha is None:
            return val
        r, g, b = hex_to_rgb(val)
        return f"rgba({r}, {g}, {b}, {alpha})"

    return _TOKEN.sub(sub, text)
