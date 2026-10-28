"""Thin wrapper around Qdrant: create the collection, upsert, search."""

from __future__ import annotations

import uuid
from functools import lru_cache

import numpy as np
from qdrant_client import QdrantClient, models

from . import config

# Fixed namespace so the same product_id always maps to the same Qdrant
# point ID. This is what makes re-running ingestion safe (idempotent).
POINT_NAMESPACE = uuid.UUID("6f1c2a52-6d6f-4f64-9a1e-6d6f6f644472")

PAYLOAD_INDEX_FIELDS = ("category", "category_name", "garment_type", "tags", "dataset_split", "subcategory", "color", "pattern")


def point_id(product_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, product_id))


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    if config.QDRANT_PATH:
        return QdrantClient(path=config.QDRANT_PATH)
    return QdrantClient(url=config.QDRANT_URL, timeout=60)


def ensure_collection(client: QdrantClient, name: str = config.QDRANT_COLLECTION, dim: int = config.EMBEDDING_DIM) -> bool:
    """Create the collection if it does not exist. Returns True if created."""
    if client.collection_exists(name):
        return False
    client.create_collection(
        collection_name=name,
        # on_disk keeps the full vectors memory-mapped instead of in RAM (8 GB laptop).
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE, on_disk=True),
        # int8 copies of the vectors stay in RAM (~150 MB for 289k) for fast search;
        # results are re-scored with the full vectors.
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8, always_ram=True)
        ),
    )
    if not config.QDRANT_PATH:  # payload indexes only matter on a Qdrant server
        for field_name in PAYLOAD_INDEX_FIELDS:
            client.create_payload_index(name, field_name, models.PayloadSchemaType.KEYWORD)
        client.create_payload_index(name, "is_outer_layer", models.PayloadSchemaType.BOOL)
    return True


def upsert(client: QdrantClient, ids: list[str], vectors: np.ndarray, payloads: list[dict],
           name: str = config.QDRANT_COLLECTION, batch_size: int = 512) -> None:
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        client.upsert(
            collection_name=name,
            points=models.Batch(
                ids=[point_id(i) for i in ids[start:end]],
                vectors=vectors[start:end].tolist(),
                payloads=payloads[start:end],
            ),
            wait=True,
        )


def build_filter(category: str | None = None, include_splits: list[str] | None = None,
                 exclude_splits: list[str] | None = None, garment_types: list[str] | None = None,
                 outer_layers_only: bool = False, exclude_ids: list[str] | None = None,
                 tags: list[str] | None = None) -> models.Filter | None:
    must, must_not = [], []
    for tag in tags or []:  # every tag must be present
        must.append(models.FieldCondition(key="tags", match=models.MatchValue(value=tag)))
    if garment_types:
        must.append(models.FieldCondition(key="garment_type", match=models.MatchAny(any=garment_types)))
    if outer_layers_only:
        must.append(models.FieldCondition(key="is_outer_layer", match=models.MatchValue(value=True)))
    if exclude_ids:
        must_not.append(models.HasIdCondition(has_id=[point_id(i) for i in exclude_ids]))
    if category:
        must.append(models.FieldCondition(key="category", match=models.MatchValue(value=category)))
    if include_splits:
        must.append(models.FieldCondition(key="dataset_split", match=models.MatchAny(any=include_splits)))
    if exclude_splits:
        must_not.append(models.FieldCondition(key="dataset_split", match=models.MatchAny(any=exclude_splits)))
    if not must and not must_not:
        return None
    return models.Filter(must=must or None, must_not=must_not or None)


def search(vector, k: int = 12, query_filter: models.Filter | None = None,
           client: QdrantClient | None = None, name: str = config.QDRANT_COLLECTION,
           with_vectors: bool = False) -> list[dict]:
    """Nearest catalogue items for one 512-d query vector.

    with_vectors=True adds each item's stored vector under "vector" (used for re-ranking).
    """
    client = client or get_client()
    res = client.query_points(
        collection_name=name,
        query=np.asarray(vector, dtype=np.float32).tolist(),
        limit=k,
        query_filter=query_filter,
        with_payload=True,
        with_vectors=with_vectors,
    )
    out = []
    for p in res.points:
        item = {"product_id": (p.payload or {}).get("product_id"), "score": float(p.score), **(p.payload or {})}
        if with_vectors and p.vector is not None:
            item["vector"] = np.asarray(p.vector, dtype=np.float32)
        out.append(item)
    return out


def get_vectors(product_ids: list[str], client: QdrantClient | None = None,
                name: str = config.QDRANT_COLLECTION) -> dict[str, np.ndarray]:
    """Stored vectors for known products, {product_id: vector}. Unknown IDs are left out."""
    if not product_ids:
        return {}
    client = client or get_client()
    pts = client.retrieve(collection_name=name, ids=[point_id(i) for i in product_ids],
                          with_payload=True, with_vectors=True)
    return {p.payload["product_id"]: np.asarray(p.vector, dtype=np.float32) for p in pts if p.payload}


def get_product(product_id: str, client: QdrantClient | None = None,
                name: str = config.QDRANT_COLLECTION) -> dict | None:
    client = client or get_client()
    pts = client.retrieve(collection_name=name, ids=[point_id(product_id)], with_payload=True)
    return pts[0].payload if pts else None
