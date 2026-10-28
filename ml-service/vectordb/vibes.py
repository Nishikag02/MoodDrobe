"""Vibes: turning moods, aesthetics and non-clothing photos into outfits.

FashionCLIP puts images and text in the same 512-number space. So a phrase
like "old money" or "rainy day in Paris" can be searched directly, and a
photo of a beach or a cafe can be described with vibe words first and then
matched to clothes. Searching a scenery photo directly against clothing
photos works poorly, because the images look nothing alike.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

# (name shown to users, prompt sent to FashionCLIP). Edit freely; no retraining needed.
VIBES = [
    ("minimalist", "minimalist clean neutral outfit"),
    ("streetwear", "streetwear outfit with oversized fit"),
    ("bohemian", "bohemian boho flowy outfit"),
    ("vintage", "vintage retro outfit"),
    ("preppy", "preppy collegiate outfit"),
    ("athleisure", "sporty athleisure outfit"),
    ("office", "formal office workwear outfit"),
    ("romantic", "romantic feminine outfit with lace and soft colors"),
    ("grunge", "edgy grunge outfit in dark colors"),
    ("casual", "casual everyday outfit"),
    ("party", "glamorous party outfit"),
    ("beach", "summer beach outfit"),
    ("winter cozy", "cozy winter knitwear outfit"),
    ("denim", "denim on denim outfit"),
    ("evening", "elegant evening outfit"),
    ("old money", "old money quiet luxury outfit in beige and navy"),
    ("cottagecore", "cottagecore floral prairie outfit"),
    ("y2k", "y2k early 2000s outfit"),
    ("dark academia", "dark academia outfit with tweed and brown tones"),
    ("coastal", "coastal linen outfit in white and blue"),
    ("festival", "music festival outfit"),
    ("monochrome black", "all black monochrome outfit"),
    ("pastel", "pastel colored outfit"),
    ("earthy", "earthy tones outfit in olive, rust and brown"),
    ("bright colorful", "bright colorful bold outfit"),
]
VIBE_TEMPLATE = "a photo of a {}"

# Used to tell clothing photos from mood photos (scenery, rooms, food, art).
CLOTHING_PROMPTS = ["a photo of clothing", "a photo of a person wearing an outfit", "a product photo of a garment"]
MOOD_PROMPTS = ["a photo of a landscape", "a photo of a room interior", "a photo of food",
                "a photo of a city street with no people", "a painting or artwork", "a photo of nature",
                "a photo of an object"]

_CACHE: dict[tuple[int, str], np.ndarray] = {}


def _norm(v):
    v = np.asarray(v, dtype=np.float32)
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def _texts(embed_text: Callable[[str], np.ndarray], key: str, texts: list[str]) -> np.ndarray:
    k = (id(embed_text), key)
    if k not in _CACHE:
        _CACHE[k] = _norm(np.stack([embed_text(t) for t in texts]))
    return _CACHE[k]


def vibe_matrix(embed_text) -> np.ndarray:
    return _texts(embed_text, "vibes", [VIBE_TEMPLATE.format(p) for _, p in VIBES])


def _softmax(sims: np.ndarray, temperature: float = 100.0) -> np.ndarray:
    e = np.exp((sims - sims.max()) * temperature)
    return e / e.sum()


def describe(vector, embed_text, top: int = 3) -> list[dict]:
    """Top vibe words for a vector, with shares that add up to 1 across all vibes."""
    probs = _softmax(vibe_matrix(embed_text) @ _norm(vector))
    order = np.argsort(-probs)[:top]
    return [{"vibe": VIBES[i][0], "score": round(float(probs[i]), 3)} for i in order]


def is_clothing_photo(vector, embed_text) -> tuple[bool, float]:
    """Zero-shot: does this image show clothes, or is it a mood picture?"""
    c = _texts(embed_text, "clothing", CLOTHING_PROMPTS)
    m = _texts(embed_text, "mood", MOOD_PROMPTS)
    probs = _softmax(np.concatenate([c, m]) @ _norm(vector))
    p_clothing = float(probs[: len(c)].sum())
    return p_clothing >= 0.5, round(p_clothing, 3)


def bridge(vector, embed_text, top: int = 3, keep_image: float = 0.35) -> np.ndarray:
    """Move a mood photo's vector towards clothing: mix its top vibe texts with
    a little of the image itself (keeps colours and texture)."""
    mat = vibe_matrix(embed_text)
    probs = _softmax(mat @ _norm(vector))
    order = np.argsort(-probs)[:top]
    w = probs[order] / probs[order].sum()
    text_part = _norm((w[:, None] * mat[order]).sum(axis=0))
    return _norm(keep_image * _norm(vector) + (1 - keep_image) * text_part)


def text_query(vibe: str) -> str:
    """Turn a short vibe like 'old money' into a prompt FashionCLIP handles well."""
    v = vibe.strip()
    return v if len(v.split()) > 4 else VIBE_TEMPLATE.format(f"{v} outfit")
