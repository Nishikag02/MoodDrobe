"""Small models trained on top of the saved FashionCLIP vectors (no FashionCLIP run).

- Category head: 512 numbers -> one of the DeepFashion categories (softmax).
- Attribute head: 512 numbers -> DeepFashion attributes such as "floral",
  "denim", "sleeveless" (one yes/no score per attribute, sigmoid).

Both are linear models trained with plain NumPy (no extra libraries), so
they train in minutes on a laptop CPU. Trained weights live in
data/processed/models/heads.npz.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import config, garments

MODEL_PATH = Path(os.getenv("MOODDROBE_HEADS_PATH", config.ML_ROOT / "data/processed/models/heads.npz"))
ATTRIBUTE_TYPES = {"1": "texture", "2": "fabric", "3": "shape", "4": "part", "5": "style"}


# ---------- reading DeepFashion attribute files ----------

def find_anno_file(name: str) -> Path | None:
    for p in (config.RAW_DATA_DIR / name, config.RAW_DATA_DIR / "Anno" / name,
              config.RAW_DATA_DIR / "Anno_coarse" / name):
        if p.is_file():
            return p
    return None


def image_key(path: str) -> str:
    """'C:\\...\\Img\\img\\Sheer_Blouse\\img_01.jpg' or 'img/Sheer_Blouse/img_01.jpg' -> 'img/Sheer_Blouse/img_01.jpg'"""
    p = str(path).replace("\\", "/")
    i = p.find("img/")
    return p[i:] if i >= 0 else p


def read_attribute_names(path: Path) -> list[tuple[str, str]]:
    """list_attr_cloth.txt -> [(name, type), ...]. Names can contain spaces."""
    lines = path.read_text(encoding="utf-8").splitlines()[2:]
    out = []
    for line in lines:
        parts = line.rsplit(None, 1)
        if len(parts) == 2:
            out.append((parts[0].strip(), ATTRIBUTE_TYPES.get(parts[1], parts[1])))
    return out


def read_attribute_labels(path: Path, wanted: set[str], n_attrs: int) -> dict[str, np.ndarray]:
    """list_attr_img.txt -> {image_key: bool array}. Only images in `wanted` are kept."""
    labels = {}
    with open(path, encoding="utf-8") as f:
        next(f)
        next(f)
        for line in f:
            name, _, rest = line.partition(" ")
            key = image_key(name)
            if key not in wanted:
                continue
            vals = np.array(rest.split(), dtype=np.int8)
            if len(vals) == n_attrs:
                labels[key] = vals > 0
    return labels


# ---------- training ----------

def _adam_train(x, y, loss: str, epochs: int, lr: float = 3e-3, l2: float = 1e-5,
                batch: int = 1024, seed: int = 0, log=print):
    """Linear model trained with mini-batch Adam. loss = 'softmax' or 'sigmoid'."""
    rng = np.random.default_rng(seed)
    n, d = x.shape
    c = y.shape[1]
    w = np.zeros((d, c), dtype=np.float32)
    b = np.zeros(c, dtype=np.float32)
    if loss == "sigmoid":  # start each attribute at its base rate
        rate = np.clip(y.mean(axis=0), 1e-4, 1 - 1e-4)
        b = np.log(rate / (1 - rate)).astype(np.float32)
    mw, vw, mb, vb = (np.zeros_like(w), np.zeros_like(w), np.zeros_like(b), np.zeros_like(b))
    step = 0
    for ep in range(epochs):
        order = rng.permutation(n)
        total = 0.0
        for s in range(0, n, batch):
            idx = order[s:s + batch]
            xb, yb = x[idx], y[idx].astype(np.float32)
            z = xb @ w + b
            if loss == "softmax":
                z = z - z.max(axis=1, keepdims=True)
                p = np.exp(z)
                p /= p.sum(axis=1, keepdims=True)
                total += float(-np.log((p * yb).sum(axis=1) + 1e-9).sum())
            else:
                p = 1 / (1 + np.exp(-z))
                total += float(-(yb * np.log(p + 1e-9) + (1 - yb) * np.log(1 - p + 1e-9)).sum() / c)
            g = (p - yb) / len(idx)
            gw = xb.T @ g + l2 * w
            gb = g.sum(axis=0)
            step += 1
            for param, grad, m, v in ((w, gw, mw, vw), (b, gb, mb, vb)):
                m *= 0.9
                m += 0.1 * grad
                v *= 0.999
                v += 0.001 * grad * grad
                param -= lr * (m / (1 - 0.9 ** step)) / (np.sqrt(v / (1 - 0.999 ** step)) + 1e-8)
        log(f"    epoch {ep + 1}/{epochs}: loss {total / n:.4f}")
    return w, b


def train_category_head(x, labels: list[str], epochs: int = 8, log=print):
    classes = sorted(set(labels))
    idx = {c: i for i, c in enumerate(classes)}
    y = np.zeros((len(labels), len(classes)), dtype=np.int8)
    y[np.arange(len(labels)), [idx[l] for l in labels]] = 1
    w, b = _adam_train(x, y, "softmax", epochs, log=log)
    return {"cat_w": w, "cat_b": b, "cat_classes": np.array(classes)}


def train_attribute_head(x, y, names: list[tuple[str, str]], min_positives: int = 50,
                         epochs: int = 6, log=print):
    keep = np.where(y.sum(axis=0) >= min_positives)[0]
    log(f"  using {len(keep)} attributes with at least {min_positives} positive training images")
    w, b = _adam_train(x, y[:, keep], "sigmoid", epochs, log=log)
    return {"attr_w": w, "attr_b": b, "attr_index": keep, "attr_names": np.array([names[i][0] for i in keep]),
            "attr_types": np.array([names[i][1] for i in keep]),
            "attr_prior": y[:, keep].mean(axis=0).astype(np.float32)}


def standardize_stats(x: np.ndarray):
    mean = x.mean(axis=0).astype(np.float32)
    std = (x.std(axis=0) + 1e-6).astype(np.float32)
    return mean, std


# ---------- metrics ----------

def topk_accuracy(probs: np.ndarray, true_idx: np.ndarray, k: int) -> float:
    top = np.argsort(-probs, axis=1)[:, :k]
    return float((top == true_idx[:, None]).any(axis=1).mean())


def attribute_recall_at_k(scores: np.ndarray, y: np.ndarray, k: int) -> float:
    """DeepFashion's attribute metric: share of true attributes found in each image's top k."""
    top = np.argsort(-scores, axis=1)[:, :k]
    hits = np.take_along_axis(y, top, axis=1).sum()
    return float(hits / max(y.sum(), 1))


# ---------- using a trained model ----------

class Heads:
    def __init__(self, path: Path = MODEL_PATH):
        data = np.load(path, allow_pickle=False)
        self.mean, self.std = data["mean"], data["std"]
        self.cat_w, self.cat_b = data["cat_w"], data["cat_b"]
        self.cat_classes = [str(c) for c in data["cat_classes"]]
        self.has_attrs = "attr_w" in data.files
        if self.has_attrs:
            self.attr_w, self.attr_b = data["attr_w"], data["attr_b"]
            self.attr_names = [str(n) for n in data["attr_names"]]
            self.attr_types = [str(t) for t in data["attr_types"]]
            self.attr_prior = data["attr_prior"]

    def _x(self, vectors) -> np.ndarray:
        v = np.atleast_2d(np.asarray(vectors, dtype=np.float32))
        v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
        return (v - self.mean) / self.std

    def category_probs(self, vectors) -> np.ndarray:
        z = self._x(vectors) @ self.cat_w + self.cat_b
        z -= z.max(axis=1, keepdims=True)
        p = np.exp(z)
        return p / p.sum(axis=1, keepdims=True)

    def detect(self, vector) -> dict:
        """Garment type and category of one query, same shape as recommend.detect_garment."""
        p = self.category_probs(vector)[0]
        by_type: dict[str, float] = {}
        for name, prob in zip(self.cat_classes, p):
            t = garments.garment_type(name) or "unknown"
            by_type[t] = by_type.get(t, 0.0) + float(prob)
        gtype = max(by_type, key=by_type.get)
        best = int(np.argmax(p))
        return {"garment_type": gtype, "category": garments.category_name(self.cat_classes[best]),
                "confidence": round(by_type[gtype], 3), "source": "category model"}

    def attribute_scores(self, vectors) -> np.ndarray:
        if not self.has_attrs:
            raise RuntimeError("This model was trained without attributes.")
        return 1 / (1 + np.exp(-(self._x(vectors) @ self.attr_w + self.attr_b)))

    def tags(self, vectors, max_tags: int = 8, lift: float = 3.0, min_prob: float = 0.15) -> list[list[str]]:
        """Attribute names likely for each vector: probability well above how common it is."""
        s = self.attribute_scores(vectors)
        out = []
        for row in s:
            # Well above the attribute's base rate, capped at 0.5 for common attributes.
            need = np.maximum(min_prob, np.minimum(lift * self.attr_prior, 0.5))
            ok = np.where(row >= need)[0]
            ok = ok[np.argsort(-row[ok])][:max_tags]
            out.append([self.attr_names[i] for i in ok])
        return out

    def describe(self, vector, per_type: int = 2) -> list[dict]:
        if not self.has_attrs:
            return []
        s = self.attribute_scores(vector)[0]
        ratio = s / np.maximum(self.attr_prior, 1e-6)
        out = []
        for t in ATTRIBUTE_TYPES.values():
            idx = [i for i, at in enumerate(self.attr_types) if at == t]
            idx = sorted(idx, key=lambda i: -ratio[i])[:per_type]
            out += [{"attribute": self.attr_names[i], "type": t, "score": round(float(s[i]), 3)}
                    for i in idx if ratio[i] >= 2.0]
        return out


@lru_cache(maxsize=1)
def load(path: str | None = None) -> Heads | None:
    """The trained heads, or None if train_heads.py has not been run yet."""
    p = Path(path) if path else MODEL_PATH
    return Heads(p) if p.exists() else None


def save(path: Path, arrays: dict, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **arrays)
    path.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
