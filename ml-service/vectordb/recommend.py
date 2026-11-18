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

Colour matching: when query colours are given (from the uploaded photos, or
typed as "navy, white" / hex codes), how well each item's dominant colours
match them is added to its relevance, so on-palette items rise. Every result
also carries a "why" list explaining the suggestion.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import colors, compat, garments, heads, store, vibes

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


def color_scores(items: list[dict], color_query: list[tuple[str, float]] | None) -> np.ndarray:
    """0-1 colour match of each item to the query colours (0 for items without a palette)."""
    if not color_query:
        return np.zeros(len(items), dtype=np.float32)
    return colors.similarity_matrix(color_query, [it.get("palette") or [] for it in items],
                                    [it.get("palette_weights") or [] for it in items])


def mmr(query: np.ndarray, candidates: list[dict], k: int, diversity: float = 0.3,
        max_per_category: int | None = 3, anchors: list[np.ndarray] | None = None,
        color_query: list[tuple[str, float]] | None = None, color_weight: float = 0.0,
        relevance: np.ndarray | None = None) -> list[dict]:
    """Maximal Marginal Relevance: pick items that match the query but are not
    near-copies of items already picked. diversity=0 means plain ranking.

    Relevance is the average of similarity to the combined style vector and to
    the closest single input image (anchor). With query colours, the colour
    match is added: color_weight=1 lets colour move an item across the whole
    style range of the candidate pool, 0 ignores colour. `relevance` (one score
    per candidate, same order) replaces the style relevance, e.g. scores from
    an outfit-compatibility model; colour is still added on top.
    """
    keep = [i for i, c in enumerate(candidates) if "vector" in c]
    pool = [candidates[i] for i in keep]
    if not pool:
        return []
    vecs = np.stack([normalize(c["vector"]) for c in pool])
    rel = vecs @ query
    if anchors and len(anchors) > 1:
        rel = 0.5 * rel + 0.5 * (vecs @ np.stack(anchors).T).max(axis=1)
    style = rel.copy()
    if relevance is not None:
        rel = np.asarray(relevance, dtype=np.float32)[keep]
    col = color_scores(pool, color_query)
    if color_query and color_weight > 0:
        spread = float(rel.max() - rel.min()) or 0.1
        rel = rel + color_weight * spread * col

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
    out = []
    for i in chosen:
        item = {**pool[i], "match": round(float(style[i]), 4)}
        if color_query:
            item["color_match"] = round(float(col[i]), 3)
        out.append(item)
    return out


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


@dataclass
class Explainer:
    """Builds the "why this was suggested" lines for each result."""
    query_tags: list[str] = field(default_factory=list)  # predicted attributes of the query
    required_tags: list[str] = field(default_factory=list)  # attributes the user asked for
    color_query: list[tuple[str, float]] = field(default_factory=list)
    query_vibes: list[str] = field(default_factory=list)
    vibe_matrix: np.ndarray | None = None

    def why(self, item: dict, reason: str) -> list[str]:
        lines = [reason[0].upper() + reason[1:]] if reason else []
        if "match" in item:
            lines.append(f"Style similarity {item['match']:.2f}")
        if "compatibility" in item:
            lines.append(f"Outfit compatibility {item['compatibility']:.2f} (learned from Polyvore outfits)")
        tags = set(item.get("tags") or [])
        asked = [t for t in self.required_tags if t in tags]
        if asked:
            lines.append("Has what you asked for: " + ", ".join(asked))
        shared = [t for t in self.query_tags if t in tags and t not in asked]
        if shared:
            lines.append("Same details as your inspiration: " + ", ".join(shared[:4]))
        if self.color_query and item.get("palette"):
            names = colors.matching_names(self.color_query, item["palette"])
            if names:
                lines.append("Matches your colours: " + ", ".join(names[:3]))
        if self.vibe_matrix is not None and self.query_vibes and "vector" in item:
            top = vibes.VIBES[int(np.argmax(self.vibe_matrix @ normalize(item["vector"])))][0]
            if top in self.query_vibes:
                lines.append(f"Fits the {top} vibe")
        return lines


def _clean(items: list[dict], reason: str, explainer: Explainer | None = None) -> list[dict]:
    out = []
    for it in items:
        why = explainer.why(it, reason) if explainer else [reason]
        it = {k: v for k, v in it.items() if k != "vector"}
        it["reason"] = reason
        it["why"] = why
        out.append(it)
    return out


def recommend(query: StyleQuery, k: int = 12, diversity: float = 0.3, pool_size: int = 150,
              pair_with: bool = True, embed_text: Callable[[str], np.ndarray] | None = None,
              base_filter_kwargs: dict | None = None, must_have_tags: list[str] | None = None,
              avoid_tags: list[str] | None = None, color_query: list[tuple[str, float]] | None = None,
              color_weight: float = 0.5, only_colors: list[str] | None = None) -> dict:
    """Build all recommendation sections for one query.

    must_have_tags / avoid_tags: attribute filters ("floral", "sleeveless").
    color_query: colours to match, [(hex, weight)]; color_weight: how strongly (0-1).
    only_colors: colour names every result must contain (hard filter, e.g. ["navy"]).
    """
    base = dict(base_filter_kwargs or {})
    base.setdefault("exclude_ids", query.exclude_ids or None)
    if must_have_tags:
        base["tags"] = must_have_tags
    if avoid_tags:
        base["avoid_tags"] = avoid_tags
    if only_colors:
        base["color_names"] = only_colors
    q = query.style_vector()
    anchors = query.anchors()
    color_query = color_query or []

    # Candidate pool: neighbours of the combined vector plus of each input,
    # so every look on a moodboard is represented. When matching colours, also
    # add the nearest items that contain those colours, so on-palette items exist.
    pool: dict[str, dict] = {}
    searches = [(v, base) for v in [q] + (anchors if len(anchors) > 1 else [])]
    if color_query and color_weight > 0 and not only_colors:
        names = sorted({colors.color_name(h) for h, _ in color_query})
        searches.append((q, {**base, "color_names": names}))
    for v, flt in searches:
        for item in store.search(v, k=pool_size, query_filter=store.build_filter(**flt), with_vectors=True):
            pool.setdefault(item["product_id"], item)
    candidates = sorted(pool.values(), key=lambda c: -float(c["vector"] @ q))

    closest = [{**c, "match": round(float(normalize(c["vector"]) @ q), 4)} for c in candidates[: min(6, k)]]
    if color_query:
        for c, cs in zip(closest, color_scores(closest, color_query)):
            c["color_match"] = round(float(cs), 3)
    model = heads.load()
    detected = None
    if query.pair_vector is not None:
        detected = model.detect(query.pair_vector) if model else \
            detect_garment(store.search(query.pair_vector, k=10, query_filter=store.build_filter(**base)))

    focus = query.pair_vector if query.pair_vector is not None else q
    explainer = Explainer(required_tags=list(must_have_tags or []), color_query=color_query)
    if model is not None and model.has_attrs and (query.image_vectors or query.liked_vectors):
        explainer.query_tags = model.tags(focus)[0]
    query_vibes = vibes.describe(q, embed_text) if embed_text is not None else None
    if query_vibes:
        explainer.query_vibes = [v["vibe"] for v in query_vibes]
        explainer.vibe_matrix = vibes.vibe_matrix(embed_text)

    result = {
        "your_style": _clean(mmr(q, candidates, k, diversity, max_per_category=3, anchors=anchors,
                                 color_query=color_query, color_weight=color_weight),
                             "shares the look of your inspiration", explainer),
        "closest_matches": _clean(closest, "closest visual match", explainer),
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
            # With a trained outfit-compatibility model (compat.py), look wider
            # and rank by "goes with your piece" instead of "looks like it".
            use_compat = compat.load() is not None and query.pair_vector is not None
            pair_pool = store.search(q, k=pool_size * (2 if use_compat else 1), query_filter=flt,
                                     with_vectors=True)
            compat_rel = compat.rerank_scores(query.pair_vector, detected, pair_pool) if use_compat else None
            label = _TYPE_LABELS.get(detected["garment_type"], "piece")
            result["complete_the_look"] = _clean(
                mmr(q, pair_pool, min(k, 8), diversity=0.4, max_per_category=2,
                    color_query=color_query, color_weight=color_weight, relevance=compat_rel),
                f"pairs with your {detected['category'] or label}", explainer,
            )

    if query_vibes is not None:
        result["vibes"] = query_vibes
    if model is not None and model.has_attrs:
        result["attributes"] = model.describe(focus)
    if color_query:
        result["query_colors"] = [{"hex": h, "weight": w, "name": colors.color_name(h)} for h, w in color_query]
    return result
