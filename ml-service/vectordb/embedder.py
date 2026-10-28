"""Fallback FashionCLIP embedder, used only if main.py does not pass its own.

Prefer passing the embedding functions main.py already uses, so query
vectors are made exactly like the catalogue vectors.
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
from PIL import Image

MODEL_NAME = os.getenv("FASHIONCLIP_MODEL", "patrickjohncyh/fashion-clip")


@lru_cache(maxsize=1)
def _load():
    import torch
    from transformers import CLIPModel, CLIPProcessor

    model = CLIPModel.from_pretrained(MODEL_NAME).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    return torch, model, processor


def _as_tensor(out, kind: str):
    # Older transformers return a tensor; newer versions may return an output object.
    if hasattr(out, "shape"):
        return out
    for attr in (f"{kind}_embeds", "pooler_output"):
        if getattr(out, attr, None) is not None:
            return getattr(out, attr)
    return out[0]


def _normalize(v) -> np.ndarray:
    v = v.detach().cpu().numpy().astype(np.float32)[0]
    return v / (np.linalg.norm(v) + 1e-12)


def embed_image(image: Image.Image) -> np.ndarray:
    torch, model, processor = _load()
    with torch.no_grad():
        inputs = processor(images=image.convert("RGB"), return_tensors="pt")
        return _normalize(_as_tensor(model.get_image_features(**inputs), "image"))


def embed_text(text: str) -> np.ndarray:
    torch, model, processor = _load()
    with torch.no_grad():
        inputs = processor(text=[text], return_tensors="pt", padding=True, truncation=True)
        return _normalize(_as_tensor(model.get_text_features(**inputs), "text"))
