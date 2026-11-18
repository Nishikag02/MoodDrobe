"""Outfit compatibility: "do these two pieces go together?"

Style similarity says "these look alike". Compatibility asks a different
question: would a stylist put them in the same outfit? A white tee and
blue jeans don't look alike, but they go together.

The model is trained on Polyvore Outfits (68k outfits put together by real
users) on top of the same FashionCLIP vectors the catalogue uses, so
FashionCLIP itself is never retrained. See scripts/train_compat.py.

How it scores two items (the "type-aware" idea from Vasileva et al., 2018):
1. A small network turns each 512-number FashionCLIP vector into a
   256-number "outfit vector".
2. Every pair of categories (top+bottom, top+shoes, ...) has its own learned
   weighting of those 256 numbers, because what makes a top match a bottom
   is not what makes it match a bag.
3. The score is the (scaled) cosine similarity of the two weighted vectors.
   Higher = more compatible. `probability()` turns it into 0..1.

This file only needs NumPy at run time: the trained weights are saved to
data/processed/models/compat.npz by scripts/train_compat.py.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import config, garments

MODEL_PATH = Path(os.getenv("MOODDROBE_COMPAT_PATH", config.ML_ROOT / "data/processed/models/compat.npz"))
POLYVORE_DIR = Path(os.getenv("MOODDROBE_POLYVORE_DIR", config.ML_ROOT / "data/raw/polyvore_outfits"))
POLYVORE_EMB = Path(os.getenv("MOODDROBE_POLYVORE_EMB", config.ML_ROOT / "data/processed/polyvore/item_embeddings.npz"))
# How much compatibility counts in complete-the-look (the rest is style similarity).
COMPAT_WEIGHT = float(os.getenv("MOODDROBE_COMPAT_WEIGHT", "0.7"))

UNKNOWN = "unknown"


# ---------- DeepFashion category -> Polyvore category ----------

def polyvore_category(category: str | None, gtype: str | None = None) -> str:
    """Map a DeepFashion category (or garment type) to Polyvore's semantic categories."""
    name = garments.category_name(category) if category else None
    if name in garments.OUTER_LAYERS:
        return "outerwear"
    gtype = gtype or garments.garment_type(name)
    return {garments.UPPER: "tops", garments.LOWER: "bottoms", garments.FULL: "all-body"}.get(gtype, UNKNOWN)


# ---------- the model (NumPy inference) ----------

def _layer_norm(x, g, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    var = x.var(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * g + b


def _gelu(x):  # tanh approximation, same as torch gelu(approximate="tanh")
    return 0.5 * x * (1.0 + np.tanh(0.7978845608028654 * (x + 0.044715 * x ** 3)))


def _normalize_rows(x):
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


class CompatModel:
    def __init__(self, data: dict):
        self.w = {k: np.asarray(v, dtype=np.float32) for k, v in data.items() if k not in ("categories", "info")}
        self.categories = [str(c) for c in data["categories"]]
        self.cat_index = {c: i for i, c in enumerate(self.categories)}
        self.info = json.loads(str(data["info"])) if "info" in data else {}

    # one item -> outfit vector
    def encode(self, x: np.ndarray) -> np.ndarray:
        w = self.w
        x = _normalize_rows(np.atleast_2d(np.asarray(x, dtype=np.float32)))
        h = _gelu(_layer_norm(x @ w["fc1_w"].T + w["fc1_b"], w["ln_g"], w["ln_b"]))
        return h @ w["fc2_w"].T + w["fc2_b"] + x @ w["skip_w"].T

    def cat_ids(self, cats) -> np.ndarray:
        unk = self.cat_index.get(UNKNOWN, len(self.categories) - 1)
        return np.array([self.cat_index.get(c, unk) for c in cats], dtype=np.int64)

    def pair_scores(self, ha, ca, hb, cb) -> np.ndarray:
        """Scores for row-aligned pairs of encoded items (ha[i] with hb[i])."""
        m = self.w["masks"][ca, cb]  # (n, D); masks are stored symmetric
        a = _normalize_rows(ha * m)
        b = _normalize_rows(hb * m)
        return float(self.w["scale"]) * (a * b).sum(-1)

    def score(self, anchor: np.ndarray, anchor_cat: str, cands: np.ndarray, cand_cats: list[str]) -> np.ndarray:
        """Compatibility of one anchor item with each candidate (higher = better)."""
        ha = self.encode(anchor)
        hb = self.encode(cands)
        n = len(hb)
        return self.pair_scores(np.repeat(ha, n, 0), self.cat_ids([anchor_cat] * n), hb, self.cat_ids(cand_cats))

    def probability(self, scores: np.ndarray) -> np.ndarray:
        """Calibrated 0..1 ("how likely a stylist pairs these"), fitted on Polyvore validation pairs."""
        a, b = self.info.get("platt", (1.0, 0.0))
        return 1.0 / (1.0 + np.exp(-(a * np.asarray(scores) + b)))


@lru_cache(maxsize=1)
def load() -> CompatModel | None:
    """The trained model, or None if scripts/train_compat.py has not been run."""
    if not MODEL_PATH.is_file():
        return None
    with np.load(MODEL_PATH, allow_pickle=False) as f:
        return CompatModel({k: f[k] for k in f.files})


def rerank_scores(pair_vector, detected: dict | None, candidates: list[dict],
                  weight: float | None = None) -> np.ndarray | None:
    """Relevance for complete-the-look: compatibility with the uploaded garment
    blended with style similarity. Also adds a "compatibility" field (0..1) to
    each candidate. Returns None (keep the old behaviour) if no model is trained."""
    model = load()
    if model is None or pair_vector is None or not candidates:
        return None
    weight = COMPAT_WEIGHT if weight is None else weight
    vecs = _normalize_rows(np.stack([np.asarray(c.get("vector", np.zeros(config.EMBEDDING_DIM)), dtype=np.float32)
                                      for c in candidates]))
    anchor = _normalize_rows(np.asarray(pair_vector, dtype=np.float32)[None])[0]
    anchor_cat = polyvore_category((detected or {}).get("category"), (detected or {}).get("garment_type"))
    cand_cats = [polyvore_category(c.get("category_name") or c.get("category"), c.get("garment_type"))
                 for c in candidates]
    comp = model.score(anchor, anchor_cat, vecs, cand_cats)
    prob = model.probability(comp)
    for c, p in zip(candidates, prob):
        c["compatibility"] = round(float(p), 4)
    sim = vecs @ anchor

    def unit(v):  # rescale to 0..1 within this pool, so the two signals are comparable
        lo, hi = float(v.min()), float(v.max())
        return (v - lo) / (hi - lo) if hi > lo else np.full_like(v, 0.5)

    return (weight * unit(comp) + (1 - weight) * unit(sim)).astype(np.float32)


# ---------- reading Polyvore Outfits (used by training and evaluation) ----------

def load_polyvore(version: str = "nondisjoint", root: Path | None = None) -> dict:
    """Read outfits, the compatibility task and the fill-in-the-blank task.

    Polyvore files refer to items as "<outfit id>_<position>"; this turns
    them into real item ids via the outfit json files.
    """
    root = Path(root or POLYVORE_DIR)
    vdir = root / version
    meta = json.loads((root / "polyvore_item_metadata.json").read_text(encoding="utf-8"))
    category = {k: (v.get("semantic_category") or UNKNOWN) for k, v in meta.items()}

    out = {"category": category, "splits": {}}
    for split in ("train", "valid", "test"):
        outfits = json.loads((vdir / f"{split}.json").read_text(encoding="utf-8"))
        pos2item = {}
        sets = []
        for o in outfits:
            items = [it["item_id"] for it in o["items"]]
            for it in o["items"]:
                pos2item[f"{o['set_id']}_{it['index']}"] = it["item_id"]
            sets.append(items)

        compat = []  # (label, [item ids])
        cpath = vdir / f"compatibility_{split}.txt"
        if cpath.is_file():
            for line in cpath.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    ids = [pos2item.get(p) for p in parts[1:]]
                    if all(ids):
                        compat.append((int(parts[0]), ids))

        fitb = []  # (question item ids, answer item ids, index of the right answer)
        fpath = vdir / f"fill_in_blank_{split}.json"
        if fpath.is_file():
            for q in json.loads(fpath.read_text(encoding="utf-8")):
                qs = q["question"]
                gt_set = qs[0].split("_")[0]
                q_ids = [pos2item.get(p) for p in qs]
                a_ids = [pos2item.get(p) for p in q["answers"]]
                right = [i for i, p in enumerate(q["answers"]) if p.split("_")[0] == gt_set]
                if all(q_ids) and all(a_ids) and len(right) == 1:
                    fitb.append((q_ids, a_ids, right[0]))
        out["splits"][split] = {"outfits": sets, "compat": compat, "fitb": fitb}
    return out


def load_polyvore_embeddings(path: Path | None = None) -> dict[str, np.ndarray]:
    """item id -> unit-length FashionCLIP vector (made by scripts/embed_polyvore.py)."""
    path = Path(path or POLYVORE_EMB)
    with np.load(path, allow_pickle=False) as f:
        ids = [str(i) for i in f["item_ids"]]
        emb = f["embeddings"].astype(np.float32)
    return dict(zip(ids, _normalize_rows(emb)))
