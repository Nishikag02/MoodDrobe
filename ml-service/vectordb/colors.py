"""Colours: dominant-colour palettes and colour similarity.

The palette uses the same method as extract_dominant_colors() in main.py
(PIL quantize, most common colours first), plus two changes that make it
usable for ranking:

- it returns how much of the image each colour covers (a weight), and
- it crops to the garment (DeepFashion bounding box when known, otherwise
  the centre of the photo) so the background counts less.

Colours are compared in CIE Lab space, where distance roughly matches how
different two colours look to people (delta E). Each colour also gets a
plain name ("navy", "beige") so people can filter with words.
"""

from __future__ import annotations

import re

import numpy as np
from PIL import Image

PALETTE_SIZE = 5
MIN_NAME_WEIGHT = 0.12  # a colour must cover this share of the garment to be listed by name

# Plain colour names and a typical shade of each. Edit freely; no retraining needed.
COLOR_NAMES: dict[str, str] = {
    "black": "#1A1A1A", "charcoal": "#3C3C3C", "grey": "#8C8C8C", "silver": "#C0C0C0",
    "white": "#F5F5F5", "cream": "#F3E9D2", "beige": "#D8C3A5", "camel": "#C19A6B",
    "tan": "#B08D68", "brown": "#6B4226", "burgundy": "#7A1F2B", "red": "#C62828",
    "coral": "#F27B67", "orange": "#EF7D20", "mustard": "#D4A017", "yellow": "#F2D53C",
    "olive": "#6B6B2A", "khaki": "#A9A77A", "green": "#2E8B57", "mint": "#A8E0C2",
    "teal": "#1F7A7A", "turquoise": "#40C4C4", "light blue": "#9CC3E6", "denim blue": "#4A6A8F",
    "blue": "#2F5FC4", "navy": "#1F2A44", "lavender": "#B9A7D9", "purple": "#6A3D9A",
    "pink": "#F0A1BC", "hot pink": "#E0408A", "mauve": "#B07A8C",
}

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


# ---------- conversions ----------

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    m = _HEX.match(h.strip())
    if not m:
        raise ValueError(f"Not a hex colour: {h!r}")
    s = m.group(1)
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def rgb_to_hex(rgb) -> str:
    r, g, b = (int(round(x)) for x in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def rgb_to_lab(rgb) -> np.ndarray:
    """sRGB (0-255), shape (..., 3) -> CIE Lab (D65), shape (..., 3)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def hex_to_lab(hexes) -> np.ndarray:
    return rgb_to_lab(np.array([hex_to_rgb(h) for h in hexes], dtype=np.float64).reshape(-1, 3))


_NAME_LIST = list(COLOR_NAMES)
_NAME_LAB = hex_to_lab(list(COLOR_NAMES.values()))


def color_name(hex_color: str) -> str:
    """Nearest plain name for a hex colour."""
    d = np.linalg.norm(_NAME_LAB - hex_to_lab([hex_color])[0], axis=1)
    return _NAME_LIST[int(np.argmin(d))]


# ---------- palettes ----------

def _crop(image: Image.Image, box: tuple[int, int, int, int] | None) -> Image.Image:
    w, h = image.size
    if box:
        x1, y1, x2, y2 = box
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
        if x2 - x1 >= 8 and y2 - y1 >= 8:
            return image.crop((x1, y1, x2, y2))
    # No box: the centre 60% x 70%, where the garment usually is.
    return image.crop((int(w * 0.2), int(h * 0.15), int(w * 0.8), int(h * 0.85)))


def palette(image: Image.Image, k: int = PALETTE_SIZE,
            box: tuple[int, int, int, int] | None = None) -> list[tuple[str, float]]:
    """Dominant colours of a garment photo: [(hex, share of pixels), ...], biggest first."""
    img = _crop(image.convert("RGB"), box)
    img.thumbnail((96, 96))
    q = img.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    # Merge near-identical shades (delta E < 6) so one navy garment is one navy entry.
    merged: list[list] = []  # [rgb, count]
    for count, idx in counts:
        rgb = np.array(pal[idx * 3: idx * 3 + 3], dtype=np.float64)
        lab = rgb_to_lab(rgb)
        for m in merged:
            if np.linalg.norm(rgb_to_lab(m[0]) - lab) < 6:
                m[0] = (m[0] * m[1] + rgb * count) / (m[1] + count)
                m[1] += count
                break
        else:
            merged.append([rgb, count])
    merged.sort(key=lambda m: -m[1])
    return [(rgb_to_hex(rgb), round(c / total, 4)) for rgb, c in merged[:k]]


def names(pal: list[tuple[str, float]], min_weight: float = MIN_NAME_WEIGHT) -> list[str]:
    """Plain names of the colours that cover a real part of the garment."""
    weights: dict[str, float] = {}
    for h, w in pal:
        if not h:
            continue
        n = color_name(h)
        weights[n] = weights.get(n, 0.0) + w
    return [n for n, w in sorted(weights.items(), key=lambda x: -x[1]) if w >= min_weight]


def merge(palettes: list[list[tuple[str, float]]], k: int = PALETTE_SIZE) -> list[tuple[str, float]]:
    """Combine several palettes (a moodboard) into one, keeping the biggest colours."""
    allc = [(h, w / len(palettes)) for p in palettes for h, w in p]
    allc.sort(key=lambda x: -x[1])
    top = allc[:k]
    s = sum(w for _, w in top) or 1.0
    return [(h, round(w / s, 4)) for h, w in top]


def parse(text: str | list[str] | None) -> list[tuple[str, float]]:
    """'navy, #F5F5F5, beige' -> palette with equal weights. Unknown words raise ValueError."""
    if not text:
        return []
    parts = text if isinstance(text, list) else re.split(r"[,;]", text)
    out = []
    for p in (x.strip().lower() for x in parts):
        if not p:
            continue
        if _HEX.match(p):
            out.append(("#" + _HEX.match(p).group(1).upper(), 1.0))
        elif p in COLOR_NAMES:
            out.append((COLOR_NAMES[p], 1.0))
        else:
            raise ValueError(f"Unknown colour {p!r}. Use a hex code like #1F2A44 or one of: "
                             + ", ".join(COLOR_NAMES))
    return [(h, round(1.0 / len(out), 4)) for h, _ in out]


# ---------- similarity ----------

def similarity_matrix(query: list[tuple[str, float]], hexes: list[list[str]],
                      weights: list[list[float]], scale: float = 20.0) -> np.ndarray:
    """How well each item's palette covers the query colours, 0 (none) to 1 (same).

    For every query colour, take the closest item colour (by delta E) and score
    it exp(-dE / scale); average over query colours weighted by how much of
    the query they cover. Items with more of their area in those colours rank
    higher, so a small navy button does not count like a navy coat.
    """
    if not query:
        return np.zeros(len(hexes), dtype=np.float32)
    q_lab = hex_to_lab([h for h, _ in query])
    q_w = np.array([w for _, w in query], dtype=np.float64)
    q_w = q_w / q_w.sum()
    out = np.zeros(len(hexes), dtype=np.float32)
    for i, (hs, ws) in enumerate(zip(hexes, weights)):
        if not hs:
            continue
        lab = hex_to_lab(hs)
        w = np.asarray(ws, dtype=np.float64)
        d = np.linalg.norm(q_lab[:, None, :] - lab[None, :, :], axis=2)  # (query, item)
        close = np.exp(-d / scale)
        # Match quality times how much of the item is that colour (sqrt keeps small accents relevant).
        per_q = (close * np.sqrt(w / max(w.max(), 1e-9))[None, :]).max(axis=1)
        out[i] = float(per_q @ q_w)
    return out


def matching_names(query: list[tuple[str, float]], item_hexes: list[str], max_de: float = 18.0) -> list[str]:
    """Plain names of item colours that are close to a query colour (for explanations)."""
    if not query or not item_hexes:
        return []
    q_lab = hex_to_lab([h for h, _ in query])
    found = []
    for h, lab in zip(item_hexes, hex_to_lab(item_hexes)):
        if np.linalg.norm(q_lab - lab, axis=1).min() <= max_de:
            n = color_name(h)
            if n not in found:
                found.append(n)
    return found


# ---------- catalogue palettes (made by scripts/extract_colors.py) ----------

def load_catalogue(folder=None) -> dict[str, tuple[list[str], list[float]]]:
    """{product_id: ([hex, ...], [weight, ...])} from the saved part files. Empty if none."""
    from . import config
    folder = folder or config.COLORS_DIR
    out: dict[str, tuple[list[str], list[float]]] = {}
    for f in sorted(folder.glob("part_*.npz")) if folder.is_dir() else []:
        data = np.load(f, allow_pickle=False)
        for pid, hs, ws in zip(data["product_ids"], data["hex"], data["weights"]):
            keep = [i for i, h in enumerate(hs) if h]
            out[str(pid)] = ([str(hs[i]) for i in keep], [float(ws[i]) for i in keep])
    return out
