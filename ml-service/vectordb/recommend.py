"""Style recommendations on top of vector search.

Plain search returns the nearest images, which are usually the same kind of
garment. This module turns that into suggestions:

- your_style: items that share the look (colour, texture, vibe) across
  different garment types, re-ranked for variety (MMR + a cap per category).
- complete_the_look: items that pair with the uploaded garment
  (top -> bottoms, bottom -> tops, dress/full outfit -> outer layers).
- closest_matches: the nearest items, for "find this exact piece".

Inputs can be one image, a moodboard (several images), a vibe in words
("old money"), a text steer such as "more formal" or "in black", and
liked/disliked product IDs. Mood photos (scenery, rooms) are translated into
vibe words first, see vibes.py.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import garments, heads, store, vibes

_TYPE_LABELS = {garments.UPPER: "top", garments.LOWER: "bottom", garments.FULL: "full outfit"}


def normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-12)


@dataclass
class StyleQuery:
    image_vectors: list[np.ndarray] = field(default_factory=list)
    text_vectors: list[np.ndarray] = field(default_factory=list)  # vibe words, e.g. "old money"
    pair_vector: np.ndarray | None = None  # set when the input is one garment photo
    steer_vector: np.ndarray | None = None  # embedded text such as "more formal"
    steer_strength: float = 0.35
    liked_vectors: list[np.ndarray] = field(default_factory=list)
    disliked_vectors: list[np.ndarray] = field(default_factory=list)
    exclude_ids: list[str] = field(default_factory=list)

    def style_vector(self) -> np.ndarray:
        """One vector for the whole query.

        Images are averaged (a moodboard's shared look), liked items pull the
        vector towards them and disliked items push it away (Rocchio), and an
        optional text steer nudges it in a direction.
        """
        parts = []
        inputs = [normalize(v) for v in self.image_vectors + self.text_vectors]
        if inputs:
            parts.append(normalize(np.mean(inputs, axis=0)))
        if self.liked_vectors:
            liked = normalize(np.mean([normalize(v) for v in self.liked_vectors], axis=0))
            parts.append(liked * (0.6 if inputs else 1.0))
        if not parts:
            raise ValueError("Need at least one image, a vibe, or one liked item.")
        q = np.sum(parts, axis=0)
        if self.disliked_vectors:
            q = q - 0.3 * normalize(np.mean([normalize(v) for v in self.disliked_vectors], axis=0))
        if self.steer_vector is not None:
            q = normalize(q) + self.steer_strength * normalize(self.steer_vector)
        return normalize(q)

    def anchors(self) -> list[np.ndarray]:
        """The separate inputs, so a moodboard with two different looks keeps both."""
        return [normalize(v) for v in (self.image_vectors + self.text_vectors or self.liked_vectors)]


def mmr(query: np.ndarray, candidates: list[dict], k: int, diversity: float = 0.3,
        max_per_category: int | None = 3, anchors: list[np.ndarray] | None = None) -> list[dict]:
    """Maximal Marginal Relevance: pick items that match the query but are not
    near-copies of items already picked. diversity=0 means plain ranking.

    Relevance is the average of similarity to the combined style vector and to
    the closest single input image (anchor).
    """
    pool = [c for c in candidates if "vector" in c]
    if not pool:
        return []
    vecs = np.stack([normalize(c["vector"]) for c in pool])
    rel = vecs @ query
    if anchors and len(anchors) > 1:
        rel = 0.5 * rel + 0.5 * (vecs @ np.stack(anchors).T).max(axis=1)

    chosen: list[int] = []
    per_cat: Counter = Counter()
    max_sim = np.full(len(pool), -1.0, dtype=np.float32)  # similarity to the closest chosen item
    while len(chosen) < min(k, len(pool)):
        score = (1 - diversity) * rel - diversity * np.where(max_sim > -1, max_sim, 0.0)
        for i in chosen:
            score[i] = -np.inf
        if max_per_category:
            for i, c in enumerate(pool):
                if per_cat[c.get("category_name") or c.get("category")] >= max_per_category:
                    score[i] = -np.inf
        best = int(np.argmax(score))
        if not np.isfinite(score[best]):
            break
        chosen.append(best)
        per_cat[pool[best].get("category_name") or pool[best].get("category")] += 1
        max_sim = np.maximum(max_sim, vecs @ vecs[best])
    return [{**pool[i], "match": round(float(rel[i]), 4)} for i in chosen]


def detect_garment(neighbors: list[dict], top: int = 10) -> dict:
    """Guess what the query shows from its nearest catalogue items (score-weighted vote)."""
    votes_type: Counter = Counter()
    votes_cat: Counter = Counter()
    for n in neighbors[:top]:
        w = max(n["score"], 0.0)
        name = n.get("category_name") or garments.category_name(n.get("category"))
        votes_cat[name] += w
        votes_type[n.get("garment_type") or garments.garment_type(name)] += w
    total = sum(votes_type.values()) or 1.0
    gtype, wt = votes_type.most_common(1)[0] if votes_type else (None, 0.0)
    cat = votes_cat.most_common(1)[0][0] if votes_cat else None
    return {"garment_type": gtype, "category": cat, "confidence": round(wt / total, 3)}


def _clean(items: list[dict], reason: str) -> list[dict]:
    out = []
    for it in items:
        it = {k: v for k, v in it.items() if k != "vector"}
        it["reason"] = reason
        out.append(it)
    return out


def recommend(query: StyleQuery, k: int = 12, diversity: float = 0.3, pool_size: int = 150,
              pair_with: bool = True, embed_text: Callable[[str], np.ndarray] | None = None,
              base_filter_kwargs: dict | None = None, must_have_tags: list[str] | None = None) -> dict:
    """Build all recommendation sections for one query."""
    base = dict(base_filter_kwargs or {})
    base.setdefault("exclude_ids", query.exclude_ids or None)
    if must_have_tags:
        base["tags"] = must_have_tags
    q = query.style_vector()
    anchors = query.anchors()

    # Candidate pool: neighbours of the combined vector plus of each input,
    # so every look on a moodboard is represented.
    pool: dict[str, dict] = {}
    for v in [q] + (anchors if len(anchors) > 1 else []):
        for item in store.search(v, k=pool_size, query_filter=store.build_filter(**base), with_vectors=True):
            pool.setdefault(item["product_id"], item)
    candidates = sorted(pool.values(), key=lambda c: -float(c["vector"] @ q))

    closest = candidates[: min(6, k)]
    model = heads.load()
    detected = None
    if query.pair_vector is not None:
        detected = model.detect(query.pair_vector) if model else \
            detect_garment(store.search(query.pair_vector, k=10, query_filter=store.build_filter(**base)))

    result = {
        "your_style": _clean(mmr(q, candidates, k, diversity, max_per_category=3, anchors=anchors),
                             "shares the look of your inspiration"),
        "closest_matches": _clean(closest, "closest visual match"),
        "detected": detected,
    }

    # Pair only when there is a single garment photo and we are fairly sure what it is.
    if pair_with and detected and detected["confidence"] >= 0.5:
        comp = garments.complementary_types(detected["garment_type"])
        if comp == ["outer"]:
            flt = store.build_filter(outer_layers_only=True, **base)
        else:
            flt = store.build_filter(garment_types=comp, **base)
        if comp:
            pair_pool = store.search(q, k=pool_size, query_filter=flt, with_vectors=True)
            label = _TYPE_LABELS.get(detected["garment_type"], "piece")
            result["complete_the_look"] = _clean(
                mmr(q, pair_pool, min(k, 8), diversity=0.4, max_per_category=2),
                f"pairs with your {detected['category'] or label}",
            )

    if embed_text is not None:
        result["vibes"] = vibes.describe(q, embed_text)
    if model is not None and model.has_attrs:
        result["attributes"] = model.describe(query.pair_vector if query.pair_vector is not None else q)
    return result
