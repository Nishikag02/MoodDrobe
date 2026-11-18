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
                "a photo of an object", "a photo of a shop or cafe interior", "a photo of bookshelves",
                "a photo of buildings and architecture", "a photo of the sky"]

# Places and settings for non-clothing photos: (name, how the photo looks, what to wear there).
# The photo is matched to the second column; the third column is what gets searched.
# Edit freely; no retraining needed.
SCENES = [
    ("cozy cafe", "a photo of a cozy coffee shop or cafe interior",
     "cozy knit sweater and cardigan with relaxed trousers in warm earthy brown, beige and cream"),
    ("bookstore", "a photo of a bookstore or library with bookshelves",
     "vintage cardigan, tweed blazer and pleated skirt in muted brown, burgundy and olive"),
    ("beach", "a photo of a sunny beach with sand and sea",
     "breezy linen shirt, light sundress and shorts in white, sand and light blue"),
    ("sunset", "a photo of a sunset sky over water",
     "flowy summer dress in warm coral, orange and soft pink"),
    ("mountains", "a photo of mountains and a mountain landscape",
     "layered outdoor outfit with a jacket, warm knitwear and sturdy trousers in neutral tones"),
    ("forest", "a photo of a green forest with trees",
     "earthy utility jacket, cargo trousers and knitwear in olive green and brown"),
    ("snowy winter", "a photo of snow in winter",
     "warm wool coat, chunky knit sweater and scarf in cream, grey and camel"),
    ("garden", "a photo of a flower garden",
     "romantic floral dress and blouse in soft pastel colours"),
    ("city street", "a photo of a city street with buildings",
     "streetwear with a hoodie, jeans and an oversized jacket, casual urban layers"),
    ("night city", "a photo of a city at night with lights",
     "bold night out outfit in black with leather and shine"),
    ("minimal architecture", "a photo of minimalist modern architecture or interior",
     "minimalist tailored outfit in clean neutral black, white and grey"),
    ("luxury dining", "a photo of an elegant restaurant or luxury hotel",
     "elegant old money outfit with a blazer, silk blouse and tailored trousers in beige and navy"),
    ("rainy day", "a photo of a rainy grey day",
     "trench coat, dark jeans and a knit jumper in grey, navy and black"),
    ("desert", "a photo of a sandy desert",
     "loose linen layers in sand, beige and terracotta"),
    ("artwork", "a painting or colourful artwork",
     "artistic statement outfit with bold prints and colours"),
    ("countryside", "a photo of green countryside fields and a farm",
     "cottagecore floral prairie dress and cardigan in soft natural colours"),
]

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


def scene_matrix(embed_text) -> np.ndarray:
    return _texts(embed_text, "scenes", [p for _, p, _ in SCENES])


def scene_outfit_matrix(embed_text) -> np.ndarray:
    return _texts(embed_text, "scene_outfits", [VIBE_TEMPLATE.format(o) for _, _, o in SCENES])


def describe_scene(vector, embed_text, top: int = 2) -> list[dict]:
    """Which places/settings a photo shows: [{scene, score, outfit}], best first."""
    probs = _softmax(scene_matrix(embed_text) @ _norm(vector))
    order = np.argsort(-probs)[:top]
    return [{"scene": SCENES[i][0], "score": round(float(probs[i]), 3), "outfit": SCENES[i][2]} for i in order]


def interpret(vector, embed_text, keep_image: float = 0.2, scene_share: float = 0.5) -> tuple[np.ndarray, dict]:
    """Turn a non-clothing photo into a clothing search vector, and say how it was read.

    Mix of: what to wear in the recognised setting (scene_share), the photo's
    top vibe words, and a little of the photo itself (colour and texture).
    """
    v = _norm(vector)
    probs = _softmax(scene_matrix(embed_text) @ v)
    order = np.argsort(-probs)[:2]
    w = probs[order] / probs[order].sum()
    scene_part = _norm((w[:, None] * scene_outfit_matrix(embed_text)[order]).sum(axis=0))
    vibe_part = bridge(vector, embed_text, keep_image=0.0)
    q = _norm(keep_image * v + scene_share * scene_part + (1 - keep_image - scene_share) * vibe_part)
    top_scene = SCENES[int(order[0])]
    reading = {
        "scene": top_scene[0],
        "scenes": describe_scene(vector, embed_text),
        "fashion_reading": top_scene[2],
        "read_as": describe(vector, embed_text),
    }
    return q, reading


def text_query(vibe: str) -> str:
    """Turn a short vibe like 'old money' into a prompt FashionCLIP handles well."""
    v = vibe.strip()
    return v if len(v.split()) > 4 else VIBE_TEMPLATE.format(f"{v} outfit")
