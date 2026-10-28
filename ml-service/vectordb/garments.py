"""Garment types for the 50 DeepFashion categories, used for outfit pairing.

DeepFashion's list_category_cloth.txt gives each category a type:
1 = upper body, 2 = lower body, 3 = full body. That file is read when it
exists; the table below is the same data as a fallback.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from . import config

UPPER, LOWER, FULL = "upper", "lower", "full"
_TYPE_CODES = {"1": UPPER, "2": LOWER, "3": FULL}

# In file order, so a numeric label N maps to the Nth name.
FALLBACK_CATEGORIES = [
    ("Anorak", UPPER), ("Blazer", UPPER), ("Blouse", UPPER), ("Bomber", UPPER), ("Button-Down", UPPER),
    ("Cardigan", UPPER), ("Flannel", UPPER), ("Halter", UPPER), ("Henley", UPPER), ("Hoodie", UPPER),
    ("Jacket", UPPER), ("Jersey", UPPER), ("Parka", UPPER), ("Peacoat", UPPER), ("Poncho", UPPER),
    ("Sweater", UPPER), ("Tank", UPPER), ("Tee", UPPER), ("Top", UPPER), ("Turtleneck", UPPER),
    ("Capris", LOWER), ("Chinos", LOWER), ("Culottes", LOWER), ("Cutoffs", LOWER), ("Gauchos", LOWER),
    ("Jeans", LOWER), ("Jeggings", LOWER), ("Jodhpurs", LOWER), ("Joggers", LOWER), ("Leggings", LOWER),
    ("Sarong", LOWER), ("Shorts", LOWER), ("Skirt", LOWER), ("Sweatpants", LOWER), ("Sweatshorts", LOWER),
    ("Trunks", LOWER),
    ("Caftan", FULL), ("Cape", FULL), ("Coat", FULL), ("Coverup", FULL), ("Dress", FULL),
    ("Jumpsuit", FULL), ("Kaftan", FULL), ("Kimono", FULL), ("Nightdress", FULL), ("Onesie", FULL),
    ("Robe", FULL), ("Romper", FULL), ("Shirtdress", FULL), ("Sundress", FULL),
]

# Layers that go over another garment. Suggested with dresses and full outfits.
OUTER_LAYERS = {"Anorak", "Blazer", "Bomber", "Cardigan", "Jacket", "Parka", "Peacoat",
                "Poncho", "Cape", "Coat", "Kimono"}


def _find_category_file() -> Path | None:
    for p in (config.RAW_DATA_DIR / "list_category_cloth.txt",
              config.RAW_DATA_DIR / "Anno" / "list_category_cloth.txt",
              config.RAW_DATA_DIR / "Anno_coarse" / "list_category_cloth.txt"):
        if p.is_file():
            return p
    return None


@lru_cache(maxsize=1)
def category_table() -> list[tuple[str, str]]:
    path = _find_category_file()
    if path is None:
        return FALLBACK_CATEGORIES
    lines = path.read_text(encoding="utf-8").splitlines()[2:]  # count line, header line
    table = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[-1] in _TYPE_CODES:
            table.append((parts[0], _TYPE_CODES[parts[-1]]))
    return table or FALLBACK_CATEGORIES


def category_name(value: str | None) -> str | None:
    """Accepts 'Blouse', 'blouse' or a 1-based label like '3'."""
    if value is None:
        return None
    v = str(value).strip()
    table = category_table()
    if v.isdigit() and 1 <= int(v) <= len(table):
        return table[int(v) - 1][0]
    for name, _ in table:
        if name.lower() == v.lower():
            return name
    return v


def garment_type(category: str | None) -> str | None:
    name = category_name(category)
    for n, t in category_table():
        if n == name:
            return t
    return None


def complementary_types(gtype: str | None) -> list[str]:
    """What to suggest next to a garment of this type."""
    return {UPPER: [LOWER], LOWER: [UPPER], FULL: ["outer"]}.get(gtype or "", [])
