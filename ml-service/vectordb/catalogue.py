"""Read products.csv and the saved embedding chunks (read-only)."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config

# Key names we look for inside each chunk .npz, most likely first.
VECTOR_KEYS = ("embeddings", "vectors", "embedding", "features", "image_embeddings")
ID_KEYS = ("product_ids", "ids", "product_id", "item_ids")


def load_products(csv_path: Path = config.PRODUCTS_CSV) -> dict[str, dict]:
    """Return {product_id: row} from products.csv. Blank cells become None."""
    products: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            clean = {k: (v if v not in ("", None) else None) for k, v in row.items()}
            products[row["product_id"]] = clean
    return products


def expected_chunks(products: dict[str, dict], chunk_size: int = config.CHUNK_SIZE) -> dict[str, int]:
    """How many chunks each split should have, from the CSV row counts."""
    counts = Counter(p.get("dataset_split") for p in products.values())
    return {s: math.ceil(counts.get(s, 0) / chunk_size) for s in config.SPLITS}


def list_chunk_files(embeddings_dir: Path = config.EMBEDDINGS_DIR, split: str | None = None) -> list[Path]:
    splits = [split] if split else list(config.SPLITS)
    files: list[Path] = []
    for s in splits:
        folder = embeddings_dir / s
        if folder.is_dir():
            files.extend(sorted(folder.glob("chunk_*.npz")))
    return files


def chunk_index(path: Path) -> int:
    """chunk_00023.npz -> 23"""
    return int(path.stem.split("_")[-1])


def _open_npz(path: Path):
    try:
        data = np.load(path, allow_pickle=False)
        # Touch every array so object arrays fail here, not later.
        _ = {k: data[k] for k in data.files}
        return data
    except ValueError:
        # String IDs saved as Python objects need pickle. These are our own
        # files, so loading them this way is safe.
        return np.load(path, allow_pickle=True)


def describe_chunk(path: Path) -> dict:
    """What is inside a chunk: array names, shapes, dtypes and manifest keys."""
    data = _open_npz(path)
    info = {"npz": str(path), "arrays": {k: [list(data[k].shape), str(data[k].dtype)] for k in data.files}}
    manifest = path.with_suffix(".json")
    if manifest.exists():
        with open(manifest, encoding="utf-8") as f:
            m = json.load(f)
        info["manifest_keys"] = {
            k: (v if isinstance(v, (int, float, str, bool)) or v is None else type(v).__name__)
            for k, v in (m.items() if isinstance(m, dict) else [])
        }
    return info


def _pick_vectors(data) -> np.ndarray:
    for k in VECTOR_KEYS:
        if k in data.files:
            return data[k]
    candidates = [k for k in data.files if data[k].ndim == 2 and np.issubdtype(data[k].dtype, np.floating)]
    if len(candidates) == 1:
        return data[candidates[0]]
    raise KeyError(f"Could not find the embedding array. Arrays in file: {data.files}")


def _pick_ids(data, n: int, manifest: dict | None) -> list[str]:
    for k in ID_KEYS:
        if k in data.files:
            return [str(x) for x in data[k].tolist()]
    candidates = [
        k for k in data.files
        if data[k].ndim == 1 and len(data[k]) == n and data[k].dtype.kind in ("U", "S", "O")
    ]
    if len(candidates) == 1:
        return [x.decode() if isinstance(x, bytes) else str(x) for x in data[candidates[0]].tolist()]
    if manifest:
        for k in ID_KEYS:
            if isinstance(manifest.get(k), list):
                return [str(x) for x in manifest[k]]
    raise KeyError(f"Could not find product IDs. Arrays in file: {data.files}")


@dataclass
class Chunk:
    path: Path
    split: str
    index: int
    ids: list[str]
    vectors: np.ndarray
    manifest: dict | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def rel_name(self) -> str:
        return f"{self.split}/{self.path.name}"


def load_chunk(path: Path) -> Chunk:
    """Load one chunk and its manifest. Raises if vectors or IDs can't be found."""
    manifest = None
    mpath = path.with_suffix(".json")
    if mpath.exists():
        with open(mpath, encoding="utf-8") as f:
            manifest = json.load(f)
    data = _open_npz(path)
    vectors = np.asarray(_pick_vectors(data), dtype=np.float32)
    ids = _pick_ids(data, len(vectors), manifest if isinstance(manifest, dict) else None)
    return Chunk(
        path=path,
        split=path.parent.name,
        index=chunk_index(path),
        ids=ids,
        vectors=vectors,
        manifest=manifest if isinstance(manifest, dict) else None,
    )


def validate_chunk(chunk: Chunk, products: dict[str, dict] | None = None, dim: int = config.EMBEDDING_DIM) -> Chunk:
    """Fill chunk.errors / chunk.warnings. Errors mean: do not index this chunk."""
    v = chunk.vectors
    if not chunk.path.with_suffix(".json").exists():
        chunk.warnings.append("manifest .json is missing")
    if v.ndim != 2 or v.shape[1] != dim:
        chunk.errors.append(f"vectors have shape {v.shape}, expected (n, {dim})")
        return chunk
    if len(chunk.ids) != len(v):
        chunk.errors.append(f"{len(chunk.ids)} IDs but {len(v)} vectors")
    if len(v) == 0:
        chunk.errors.append("chunk is empty")
        return chunk
    if not np.isfinite(v).all():
        chunk.errors.append(f"{int((~np.isfinite(v).all(axis=1)).sum())} vectors contain NaN/inf")
    norms = np.linalg.norm(v, axis=1)
    if np.abs(norms - 1).max() > 1e-2:
        chunk.warnings.append(
            f"vectors are not unit length (norm range {norms.min():.3f}-{norms.max():.3f}); cosine search still works"
        )
    dupes = len(chunk.ids) - len(set(chunk.ids))
    if dupes:
        chunk.errors.append(f"{dupes} duplicate product IDs inside the chunk")
    if products is not None:
        unknown = [i for i in chunk.ids if i not in products]
        if unknown:
            chunk.errors.append(f"{len(unknown)} IDs not in products.csv (e.g. {unknown[0]})")
        wrong_split = [i for i in chunk.ids if i in products and products[i].get("dataset_split") != chunk.split]
        if wrong_split:
            chunk.errors.append(f"{len(wrong_split)} IDs belong to a different split (e.g. {wrong_split[0]})")
    return chunk


def resolve_image_path(image_path: str) -> Path | None:
    """Find a catalogue image on disk from the image_path column of products.csv."""
    p = Path(image_path)
    candidates = [p] if p.is_absolute() else [
        config.ML_ROOT / p,
        config.RAW_DATA_DIR / p,
        config.RAW_DATA_DIR / "Img" / p,
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None
